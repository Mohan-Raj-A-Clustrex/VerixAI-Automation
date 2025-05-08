from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import os
import threading
import uuid
import logging
import io
import sys
import traceback
import requests
import asyncio
import queue
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from contextlib import redirect_stdout, redirect_stderr, asynccontextmanager
from typing import Dict, List, Set

from config import Config
from automation.verixai_automation import VerixAIAutomation
from utils.test_utils import TestResult
from models.models import CaseDetails, TestRequest, HealthResponse, TestResponse, TestStatusResponse, WebhookConfig
from config import DevConfig, StagingConfig, ProdConfig


# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10),
        logging.StreamHandler()
    ]
)

env_map = {
    'dev': DevConfig,
    'staging': StagingConfig,
    'prod': ProdConfig
}

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifespan event handler for FastAPI app startup and shutdown"""
    # Startup: Start the broadcast processor and sync queue checker
    broadcast_task = asyncio.create_task(broadcast_processor())
    sync_queue_task = asyncio.create_task(check_sync_queue())

    logger.info("FastAPI application started with lifespan event handler")

    yield  # This is where the app runs

    # Shutdown: Cancel the tasks
    broadcast_task.cancel()
    sync_queue_task.cancel()

    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass

    try:
        await sync_queue_task
    except asyncio.CancelledError:
        pass

    logger.info("FastAPI application shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title="VerixAI Automation API",
    description="API for running VerixAI automation tests",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files directory
static_dir = os.path.join(os.getcwd(), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Dictionary to store running tests
running_tests = {}

# Dictionary to store webhook configurations
webhooks = {}

# Dictionary to store log queues for each test
log_queues = {}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        # Active connections for each test_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Lock for thread-safe operations
        self.lock = threading.Lock()

    async def connect(self, websocket: WebSocket, test_id: str):
        await websocket.accept()
        with self.lock:
            if test_id not in self.active_connections:
                self.active_connections[test_id] = []
            self.active_connections[test_id].append(websocket)

        # Send initial logs if available
        if test_id in running_tests:
            await websocket.send_text(json.dumps({
                "event": "initial_logs",
                "test_id": test_id,
                "logs": running_tests[test_id].get('logs', ''),
                "status": running_tests[test_id]['status']
            }))

    def disconnect(self, websocket: WebSocket, test_id: str):
        with self.lock:
            if test_id in self.active_connections:
                if websocket in self.active_connections[test_id]:
                    self.active_connections[test_id].remove(websocket)
                if not self.active_connections[test_id]:
                    del self.active_connections[test_id]

    async def broadcast(self, test_id: str, message: str):
        with self.lock:
            if test_id in self.active_connections:
                disconnected_websockets = []
                for connection in self.active_connections[test_id]:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        disconnected_websockets.append(connection)

                # Clean up disconnected websockets
                for ws in disconnected_websockets:
                    self.disconnect(ws, test_id)

# Initialize connection manager
manager = ConnectionManager()

class StreamingStringIO(io.StringIO):
    """A StringIO subclass that streams content to a queue in real-time"""

    def __init__(self, queue_obj=None, test_id=None, stream_type="stdout"):
        super().__init__()
        self.queue = queue_obj
        self.test_id = test_id
        self.stream_type = stream_type

    def write(self, s):
        # Write to the underlying StringIO
        ret = super().write(s)

        # If we have a queue, put the new content in it
        if self.queue and self.test_id:
            self.queue.put((self.test_id, s, self.stream_type))

        return ret

# Create a queue for broadcast messages
broadcast_queue = asyncio.Queue()

# Function to process broadcast messages in the main event loop
async def broadcast_processor():
    """Process broadcast messages in the main event loop"""
    while True:
        try:
            # Get a message from the queue
            test_id, message = await broadcast_queue.get()

            # Broadcast to WebSocket clients
            await manager.broadcast(test_id, message)

            # Mark the task as done
            broadcast_queue.task_done()
        except Exception as e:
            logger.error(f"Error in broadcast processor: {str(e)}")
            # Sleep briefly to avoid tight loop in case of persistent errors
            await asyncio.sleep(0.1)

def log_processor():
    """Background thread to process logs from the queue and update running_tests"""
    while True:
        try:
            # Get a log entry from the queue
            test_id, log_text, stream_type = log_queue.get()

            # Update the running_tests log
            if test_id in running_tests:
                running_tests[test_id]['logs'] += log_text

            # Create a message for broadcasting
            log_message = json.dumps({
                "event": "log_update",
                "test_id": test_id,
                "log": log_text,
                "stream_type": stream_type,
                "timestamp": datetime.now().isoformat()
            })

            # Add the message to the broadcast queue
            # We use a synchronous queue to communicate between threads
            if test_id in running_tests:
                # Use a thread-safe way to add to the asyncio queue
                asyncio_queue_sync.put((test_id, log_message))

            # Mark the task as done
            log_queue.task_done()
        except Exception as e:
            logger.error(f"Error in log processor: {str(e)}")
            # Sleep briefly to avoid tight loop in case of persistent errors
            time.sleep(0.1)

# Create a global queue for logs
log_queue = queue.Queue()

# Create a synchronous queue for communicating with the asyncio event loop
asyncio_queue_sync = queue.Queue()

# Start the log processor thread
log_processor_thread = threading.Thread(target=log_processor, daemon=True)
log_processor_thread.start()

# Function to check the synchronous queue and add items to the asyncio queue
async def check_sync_queue():
    """Check the synchronous queue and add items to the asyncio queue"""
    while True:
        try:
            # Check if there are items in the queue
            if not asyncio_queue_sync.empty():
                # Get an item from the queue
                test_id, message = asyncio_queue_sync.get_nowait()
                # Add it to the asyncio queue
                await broadcast_queue.put((test_id, message))
                # Mark the task as done
                asyncio_queue_sync.task_done()
            # Sleep briefly to avoid tight loop
            await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in check_sync_queue: {str(e)}")
            await asyncio.sleep(0.1)



def capture_output(func, test_id=None):
    """Capture stdout and stderr during function execution with real-time streaming"""
    # Create streaming buffers
    stdout_buffer = StreamingStringIO(log_queue, test_id, "stdout")
    stderr_buffer = StreamingStringIO(log_queue, test_id, "stderr")

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            result = func()
            return result, stdout_buffer.getvalue(), stderr_buffer.getvalue()
        except Exception as e:
            error_msg = f"\nException: {str(e)}\n{traceback.format_exc()}"
            stderr_buffer.write(error_msg)
            return None, stdout_buffer.getvalue(), stderr_buffer.getvalue()

def send_webhook_notification(test_id, event_type, data=None):
    """Send a webhook notification if configured for the test"""
    if test_id in webhooks:
        webhook_config = webhooks[test_id]
        if event_type in webhook_config.events:
            try:
                payload = {
                    'event': event_type,
                    'test_id': test_id,
                    'timestamp': datetime.now().isoformat(),
                    'data': data or {}
                }

                headers = webhook_config.headers or {'Content-Type': 'application/json'}

                response = requests.post(
                    str(webhook_config.url),
                    json=payload,
                    headers=headers,
                    timeout=5
                )

                logger.info(f"Webhook notification sent for test {test_id}, event {event_type}: {response.status_code}")
                return True
            except Exception as e:
                logger.error(f"Error sending webhook notification for test {test_id}: {str(e)}")
                return False
    return False

def run_test_in_background(test_id, test_params):
    """Run a test in a background thread and capture all output"""
    try:
        logger.info(f"Starting test {test_id} with params: {test_params}")

        # Send webhook notification for test started
        send_webhook_notification(test_id, 'test_started', {
            'status': 'running',
            'start_time': running_tests[test_id]['start_time']
        })

        # Broadcast test started event to WebSocket clients using the sync queue
        start_message = json.dumps({
            "event": "test_started",
            "test_id": test_id,
            "status": "running",
            "start_time": running_tests[test_id]['start_time']
        })
        asyncio_queue_sync.put((test_id, start_message))

        # Create automation instance
        automation = VerixAIAutomation(test_params)

        # Log the configuration being used
        env = test_params.get('env', 'dev')
        logger.info(f"Test {test_id} using environment: {env}")
        logger.info(f"Configuration for {env}:")
        logger.info(f"  BASE_URL: {automation.config.BASE_URL}")
        logger.info(f"  LOGIN_EMAIL: {automation.config.LOGIN_EMAIL}")
        logger.info(f"  NOTES_FILE_PATH: {automation.notes_file_path}")
        logger.info(f"  NOTES_FOLDER_PATH: {automation.notes_folder_path}")
        logger.info(f"  IMAGING_FILE_PATH: {automation.imaging_file_path}")
        logger.info(f"  IMAGING_FOLDER_PATH: {automation.imaging_folder_path}")

        # Run automation with output capture and streaming
        result, stdout, stderr = capture_output(automation.run_automation, test_id)

        # Store results and logs
        running_tests[test_id]['status'] = 'completed'
        running_tests[test_id]['result'] = result
        running_tests[test_id]['logs'] = stdout + stderr
        running_tests[test_id]['end_time'] = datetime.now().isoformat()

        # Send webhook notification for test completed
        send_webhook_notification(test_id, 'test_completed', {
            'status': 'completed',
            'start_time': running_tests[test_id]['start_time'],
            'end_time': running_tests[test_id]['end_time'],
            'result': result
        })

        # Email is already sent by TestResult.mark_passed/mark_failed
        logger.info(f"Email already sent by TestResult class for test {test_id}")

        # Broadcast test completed event to WebSocket clients using the sync queue
        complete_message = json.dumps({
            "event": "test_completed",
            "test_id": test_id,
            "status": "completed",
            "start_time": running_tests[test_id]['start_time'],
            "end_time": running_tests[test_id]['end_time'],
            "result": result
        })
        asyncio_queue_sync.put((test_id, complete_message))

        logger.info(f"Test {test_id} completed with status: {result.get('status') if result else 'ERROR'}")
    except Exception as e:
        logger.error(f"Error in test {test_id}: {str(e)}")
        running_tests[test_id]['status'] = 'error'
        running_tests[test_id]['error'] = str(e)
        running_tests[test_id]['logs'] = traceback.format_exc()
        running_tests[test_id]['end_time'] = datetime.now().isoformat()

        # Send webhook notification for test error
        send_webhook_notification(test_id, 'test_error', {
            'status': 'error',
            'start_time': running_tests[test_id]['start_time'],
            'end_time': running_tests[test_id]['end_time'],
            'error': str(e)
        })

        # Email is already sent by TestResult.mark_passed/mark_failed
        logger.info(f"Email already sent by TestResult class for test {test_id} (error case)")

        # Broadcast test error event to WebSocket clients using the sync queue
        error_message = json.dumps({
            "event": "test_error",
            "test_id": test_id,
            "status": "error",
            "start_time": running_tests[test_id]['start_time'],
            "end_time": running_tests[test_id]['end_time'],
            "error": str(e)
        })
        asyncio_queue_sync.put((test_id, error_message))

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }

@app.get("/logs", response_class=HTMLResponse)
async def get_log_viewer():
    """Serve the log viewer HTML page"""
    return FileResponse(os.path.join(static_dir, "log_viewer.html"))

@app.post("/api/run-test", response_model=TestResponse)
async def run_test(
    request: TestRequest,
    background_tasks: BackgroundTasks,
    env: str = Query(..., description="Environment to run the test in (dev, staging, prod)")
):
    """API endpoint to run a test"""
    try:
        # Validate and fetch config
        config_class = env_map.get(env)
        if not config_class:
            raise HTTPException(status_code=400, detail="Invalid environment specified")

        config = config_class  # Now you're using the correct env-specific class
        test_id = f"test_{uuid.uuid4().hex[:8]}"

        test_params = {
            'case_details': request.case_details.model_dump() if request.case_details else None,
            'notes_file_path': request.notes_file_path or config.DEFAULT_NOTES_FILE_PATH,
            'notes_folder_path': request.notes_folder_path or config.DEFAULT_NOTES_FOLDER_PATH,
            'imaging_file_path': request.imaging_file_path or config.DEFAULT_IMAGING_FILE_PATH,
            'imaging_folder_path': request.imaging_folder_path or config.DEFAULT_IMAGING_FOLDER_PATH,
            'env': env  # Pass the environment from the query parameter
        }

        running_tests[test_id] = {
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'params': test_params,
            'logs': ''
        }

        if request.webhook:
            webhooks[test_id] = request.webhook

        background_tasks.add_task(run_test_in_background, test_id, test_params)

        return {
            'status': 'success',
            'message': f'Test started with ID: {test_id}',
            'test_id': test_id
        }

    except Exception as e:
        logger.error(f"Error starting test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting test: {str(e)}")

@app.get("/api/test-status/{test_id}", response_model=TestStatusResponse)
async def test_status(test_id: str):
    """API endpoint to check test status"""
    if test_id not in running_tests:
        raise HTTPException(status_code=404, detail=f"Test ID {test_id} not found")

    return {
        'status': 'success',
        'test_id': test_id,
        'test_status': running_tests[test_id]['status'],
        'start_time': running_tests[test_id]['start_time'],
        'result': running_tests[test_id].get('result'),
        'logs': running_tests[test_id].get('logs', '')
    }

@app.get("/api/active-tests")
async def list_active_tests():
    """API endpoint to list all active tests"""
    active_tests = []
    for test_id, test_data in running_tests.items():
        active_tests.append({
            'test_id': test_id,
            'status': test_data['status'],
            'start_time': test_data['start_time'],
            'end_time': test_data.get('end_time'),
            'has_webhook': test_id in webhooks
        })

    return {
        'status': 'success',
        'count': len(active_tests),
        'tests': active_tests
    }

@app.get("/api/test-results")
async def list_test_results():
    """API endpoint to list all test results"""
    results_dir = os.path.join(os.getcwd(), 'test_results')
    if not os.path.exists(results_dir):
        return {
            'status': 'success',
            'message': 'No test results found',
            'results': []
        }

    results = []
    for filename in os.listdir(results_dir):
        if filename.endswith('.json'):
            with open(os.path.join(results_dir, filename), 'r') as f:
                result = json.load(f)
                results.append({
                    'test_id': result.get('test_id'),
                    'status': result.get('status'),
                    'start_time': result.get('start_time'),
                    'end_time': result.get('end_time'),
                    'duration_seconds': result.get('duration_seconds'),
                    'test_cases': result.get('test_cases', [])
                })

    return {
        'status': 'success',
        'count': len(results),
        'results': results
    }

@app.get("/api/test-results/{test_id}")
async def get_test_result(test_id: str):
    """API endpoint to get a specific test result by ID"""
    # First check if the test is still running
    if test_id in running_tests:
        return {
            'status': 'success',
            'message': f'Test {test_id} is still running or has not been saved yet',
            'test_status': running_tests[test_id]['status'],
            'start_time': running_tests[test_id]['start_time'],
            'result': running_tests[test_id].get('result'),
            'is_running': True
        }

    # If not running, check saved results
    results_dir = os.path.join(os.getcwd(), 'test_results')
    if not os.path.exists(results_dir):
        raise HTTPException(status_code=404, detail=f"Test ID {test_id} not found")

    # Look for the test result file
    for filename in os.listdir(results_dir):
        if filename.endswith('.json'):
            with open(os.path.join(results_dir, filename), 'r') as f:
                result = json.load(f)
                if result.get('test_id') == test_id:
                    return {
                        'status': 'success',
                        'test_id': test_id,
                        'result': result,
                        'is_running': False
                    }

    # If we get here, the test was not found
    raise HTTPException(status_code=404, detail=f"Test ID {test_id} not found")

@app.post("/api/test-webhook/{test_id}")
async def register_webhook(test_id: str, webhook: WebhookConfig):
    """API endpoint to register a webhook for an existing test"""
    # Check if the test exists
    if test_id not in running_tests and not any(
        json.load(open(os.path.join(os.getcwd(), 'test_results', f))).get('test_id') == test_id
        for f in os.listdir(os.path.join(os.getcwd(), 'test_results'))
        if f.endswith('.json') and os.path.exists(os.path.join(os.getcwd(), 'test_results', f))
    ):
        raise HTTPException(status_code=404, detail=f"Test ID {test_id} not found")

    # Register the webhook
    webhooks[test_id] = webhook

    # If the test is already completed, send a notification immediately
    if test_id in running_tests and running_tests[test_id]['status'] in ['completed', 'error']:
        event_type = 'test_completed' if running_tests[test_id]['status'] == 'completed' else 'test_error'
        data = {
            'status': running_tests[test_id]['status'],
            'start_time': running_tests[test_id]['start_time'],
            'end_time': running_tests[test_id].get('end_time', datetime.now().isoformat()),
            'result': running_tests[test_id].get('result')
        }
        if running_tests[test_id]['status'] == 'error':
            data['error'] = running_tests[test_id].get('error', 'Unknown error')

        send_webhook_notification(test_id, event_type, data)

    return {
        'status': 'success',
        'message': f'Webhook registered for test ID: {test_id}',
        'test_id': test_id
    }

@app.websocket("/ws/test-logs/{test_id}")
async def websocket_endpoint(websocket: WebSocket, test_id: str):
    """WebSocket endpoint for real-time test logs"""
    try:
        # Check if the test exists
        if test_id not in running_tests and not any(
            json.load(open(os.path.join(os.getcwd(), 'test_results', f))).get('test_id') == test_id
            for f in os.listdir(os.path.join(os.getcwd(), 'test_results'))
            if f.endswith('.json') and os.path.exists(os.path.join(os.getcwd(), 'test_results', f))
        ):
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "event": "error",
                "message": f"Test ID {test_id} not found"
            }))
            await websocket.close()
            return

        # Connect to the WebSocket
        await manager.connect(websocket, test_id)

        # Keep the connection open and handle messages
        try:
            while True:
                # Wait for messages from the client (can be used for interactive features)
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    # Handle client messages if needed
                    if message.get('type') == 'ping':
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            # Handle disconnection
            manager.disconnect(websocket, test_id)
    except Exception as e:
        logger.error(f"WebSocket error for test {test_id}: {str(e)}")
        try:
            await websocket.close()
        except:
            pass

@app.post("/api/github-webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint for GitHub Actions"""
    try:
        # Get JSON payload
        payload = await request.json()
        if not payload:
            raise HTTPException(status_code=400, detail="No JSON payload provided")

        # Extract repository and event information
        repository = payload.get('repository', {}).get('full_name', 'unknown')
        event_type = request.headers.get('X-GitHub-Event', 'unknown')

        logger.info(f"Received GitHub webhook: {event_type} from {repository}")

        # Generate a test ID
        test_id = f"github_{uuid.uuid4().hex[:8]}"

        # Extract test parameters from the payload or use defaults
        # Get environment from payload or default to 'dev'
        env = payload.get('env', 'dev')

        # Validate environment
        config_class = env_map.get(env)
        if not config_class:
            logger.warning(f"Invalid environment specified in GitHub webhook: {env}, defaulting to 'dev'")
            env = 'dev'
            config_class = DevConfig

        config = config_class

        test_params = {
            'case_details': payload.get('case_details'),
            'notes_file_path': payload.get('notes_file_path', config.DEFAULT_NOTES_FILE_PATH),
            'notes_folder_path': payload.get('notes_folder_path', config.DEFAULT_NOTES_FOLDER_PATH),
            'imaging_file_path': payload.get('imaging_file_path', config.DEFAULT_IMAGING_FILE_PATH),
            'imaging_folder_path': payload.get('imaging_folder_path', config.DEFAULT_IMAGING_FOLDER_PATH),
            'env': env,  # Pass the environment from the payload
            'github_event': {
                'repository': repository,
                'event_type': event_type,
                'sender': payload.get('sender', {}).get('login', 'unknown')
            }
        }

        # Start the test in a background thread
        running_tests[test_id] = {
            'status': 'running',
            'start_time': datetime.now().isoformat(),
            'params': test_params,
            'logs': ''
        }

        # Store webhook configuration if provided
        if payload.get('webhook'):
            try:
                webhook_config = WebhookConfig(**payload.get('webhook'))
                webhooks[test_id] = webhook_config
            except Exception as e:
                logger.error(f"Error parsing webhook configuration: {str(e)}")

        # Use background tasks to run the test
        background_tasks.add_task(run_test_in_background, test_id, test_params)

        return {
            'status': 'success',
            'message': f'Test started with ID: {test_id}',
            'test_id': test_id
        }

    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing GitHub webhook: {str(e)}")

if __name__ == '__main__':
    import uvicorn

    # Validate configuration
    from config import validate_and_print_config
    validate_and_print_config()

    # Create necessary directories
    os.makedirs(Config.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs('test_results', exist_ok=True)

    # Start the FastAPI app with uvicorn
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host='0.0.0.0', port=port)
