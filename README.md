# VerixAI Automation

A parameterized Flask application for automating VerixAI workflows, designed to run headless in Docker/Kubernetes, be triggered by GitHub Actions, and report test results via email.

## Features

- **Parameterized Execution**: All test parameters can be provided via JSON payload
- **Headless Operation**: Runs in the background without requiring a GUI
- **GitHub Actions Integration**: Can be triggered by GitHub Actions workflows
- **Email Reporting**: Sends test results via email with screenshots
- **Containerized**: Packaged as a Docker container for easy deployment
- **Kubernetes Ready**: Includes Kubernetes deployment configuration

## Getting Started

### Prerequisites

- Python 3.9+
- Chrome browser
- Docker (for containerized deployment)
- Kubernetes (for orchestrated deployment)

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/verixai-automation.git
   cd verixai-automation
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the application by creating a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Run the application:
   ```bash
   python app.py
   ```

# VerixAI Automation API with FastAPI

This is a FastAPI implementation of the VerixAI Automation API that returns detailed logs and test results, with WebSocket support for real-time log streaming and webhook notifications.

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure you have the correct configuration in your `.env` file or environment variables.

## Running the API

Run the FastAPI application:
```bash
python fastapi_app.py
```

Or use uvicorn directly:
```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at http://localhost:8000

## API Documentation

FastAPI automatically generates interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Health Check
```
GET /health
```
Returns the health status of the API.

### Run Test
```
POST /api/run-test
```
Starts a new automation test.

**Request Body:**
```json
{
  "case_details": {
    "title": "Sample Test Case",
    "plaintiff_name": "John Doe",
    "medical_provider": "Test Hospital",
    "description": "This is a sample test case for VerixAI automation"
  }
}

**Note:** The application now uses files from the `sample_data` directory structure directly:
- `sample_data/notes.pdf` - For clinical notes file upload
- `sample_data/notes_folder/` - For clinical notes folder upload
- `sample_data/imaging.dcm` - For medical imaging file upload
- `sample_data/imaging_folder/` - For medical imaging folder upload

### Test Status
```
GET /api/test-status/{test_id}
```
Returns the status of a test, including detailed logs and results.

### Test Results
```
GET /api/test-results
```
Returns a list of all test results.

### Get Specific Test Result
```
GET /api/test-results/{test_id}
```
Returns detailed results for a specific test.

### List Active Tests
```
GET /api/active-tests
```
Returns a list of all currently active tests.

### Register Webhook for Test
```
POST /api/test-webhook/{test_id}
```
Registers a webhook for an existing test.

**Request Body:**
```json
{
  "url": "https://example.com/webhook",
  "events": ["test_started", "test_completed", "test_error"],
  "headers": {
    "Authorization": "Bearer your-token-here"
  }
}
```

### GitHub Webhook
```
POST /api/github-webhook
```
Webhook endpoint for GitHub Actions integration.

### WebSocket for Real-time Logs
```
WebSocket: /ws/test-logs/{test_id}
```
Connect to this WebSocket endpoint to receive real-time logs for a specific test.

### Log Viewer UI
```
GET /logs
```
A simple web interface for viewing real-time logs from tests.

## Testing with Postman

1. **Start the FastAPI Server**:
   ```bash
   python fastapi_app.py
   ```

2. **Set Up Postman Request**:
   - Open Postman
   - Create a new request
   - Set the method to `POST`
   - Set the URL to `http://localhost:5000/api/run-test`
   - Go to the "Headers" tab and add:
     - Key: `Content-Type`
     - Value: `application/json`
   - Go to the "Body" tab
     - Select "raw"
     - Select "JSON" from the dropdown
     - Paste your JSON payload

3. **Send the Request**:
   - Click the "Send" button
   - You should receive a response with the test ID

4. **Check Test Status**:
   - Create a new GET request in Postman
   - Set the URL to `http://localhost:5000/api/test-status/{test_id}`
   - Send the request
   - You will receive the current status, logs, and results of the test

## Key Features

1. **Real-time Logs**: The API captures all stdout and stderr output during test execution and returns it in the test status endpoint.

2. **Detailed Test Results**: The API returns detailed test results including individual test case statuses, screenshots, and error messages.

3. **Background Processing**: Tests run in the background, allowing you to check their status asynchronously.

4. **Swagger Documentation**: Interactive API documentation is available at `/docs`.

5. **Input Validation**: The API uses Pydantic models to validate input data.

## Troubleshooting

If you encounter issues:

1. Check the logs in the `logs/app.log` file
2. Verify that all file paths in your request are accessible
3. Make sure all dependencies are installed
4. Check that the server is running and accessible


### Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t verixai-automation:latest .
   ```

2. Run the container:
   ```bash
   docker run -p 5000:5000 --env-file .env verixai-automation:latest
   ```

### Kubernetes Deployment

1. Create the Kubernetes secrets:
   ```bash
   # Create a secrets.env file with your configuration
   kubectl create secret generic verixai-secrets --from-env-file=secrets.env
   ```

2. Deploy to Kubernetes:
   ```bash
   kubectl apply -f kubernetes/deployment.yaml
   ```

## API Endpoints

### Run a Test

```
POST /api/run-test
```

Example payload:
```json
{
  "case_details": {
    "title": "Test Case",
    "plaintiff_name": "John Doe",
    "medical_provider": "Test Hospital",
    "description": "This is a test case"
  }
}

The API will use files from the `sample_data` directory structure directly.

### Check Test Status

```
GET /api/test-status/{test_id}
```

### List Test Results

```
GET /api/test-results
```

### GitHub Webhook

```
POST /api/github-webhook
```

## GitHub Actions Integration

### Deployment to Azure Kubernetes Service (AKS)

The project includes GitHub Actions workflows for deploying to Azure Kubernetes Service and triggering tests automatically when changes are made to the main VerixAI project.

1. Set up Azure resources using the provided script:
   ```bash
   chmod +x scripts/azure-setup.sh
   ./scripts/azure-setup.sh
   ```

2. Add the following secrets to your GitHub repository:
   - `AZURE_CREDENTIALS`: The JSON output from the service principal creation
   - `ACR_USERNAME`: Azure Container Registry username
   - `ACR_PASSWORD`: Azure Container Registry password
   - `WEBHOOK_URL`: Your webhook URL for test notifications
   - `WEBHOOK_TOKEN`: Your webhook authentication token

3. The GitHub Actions workflow will automatically build and deploy the application to AKS when changes are pushed to the main branch.

### Integration with Main Project

To trigger automated tests when changes are made to the main VerixAI project:

1. Add the `main-project-workflow.yml` file to the `.github/workflows` directory of your main project.
2. Create a Personal Access Token (PAT) with `repo` scope.
3. Add the PAT as a secret named `AUTOMATION_PAT` in your main project's GitHub repository.
4. Update the repository name in the workflow file to match your automation repository.

## Email Notifications

The application sends email notifications with test results. Configure the email settings in the `.env` file:

```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
```


