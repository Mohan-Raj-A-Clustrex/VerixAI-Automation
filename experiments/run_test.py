import json
import sys
import os
import traceback
from automation.verixai_automation import VerixAIAutomation
from utils.test_utils import TestResult
from utils.email_utils import send_test_result_email
from config import Config

def main():
    """Run a test locally using the sample payload or a specified JSON file"""

    # Create necessary directories
    os.makedirs('screenshots', exist_ok=True)
    os.makedirs('test_results', exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    # Load configuration
    try:
        # Print the current configuration
        Config.print_config()

        # Try to validate configuration but don't exit if it fails
        try:
            Config.validate()
            print("Configuration validation passed")
        except ValueError as e:
            print(f"Configuration warning: {str(e)}")
            print("Continuing with default values where possible...")
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        print("Continuing with default values...")

    # Determine which payload file to use
    payload_file = 'sample_payload.json'
    if len(sys.argv) > 1:
        payload_file = sys.argv[1]

    print(f"Using payload file: {payload_file}")

    # Load the test parameters from the JSON file
    try:
        with open(payload_file, 'r') as f:
            payload = json.load(f)
    except Exception as e:
        print(f"Error loading payload file: {str(e)}")
        print("Make sure the file exists and contains valid JSON.")
        sys.exit(1)

    # Extract test parameters
    test_id = payload.get('test_id', None)
    test_params = {
        'case_details': payload.get('case_details'),
        'notes_file_path': payload.get('notes_file_path', Config.DEFAULT_NOTES_FILE_PATH),
        'notes_folder_path': payload.get('notes_folder_path', Config.DEFAULT_NOTES_FOLDER_PATH),
        'imaging_file_path': payload.get('imaging_file_path', Config.DEFAULT_IMAGING_FILE_PATH),
        'imaging_folder_path': payload.get('imaging_folder_path', Config.DEFAULT_IMAGING_FOLDER_PATH)
    }

    # Verify file paths exist
    for key, path in {
        'notes_file_path': test_params['notes_file_path'],
        'notes_folder_path': test_params['notes_folder_path'],
        'imaging_file_path': test_params['imaging_file_path'],
        'imaging_folder_path': test_params['imaging_folder_path']
    }.items():
        if path and not os.path.exists(path):
            print(f"Warning: {key} path does not exist: {path}")

    # Create screenshots directory if it doesn't exist
    os.makedirs(Config.SCREENSHOTS_DIR, exist_ok=True)

    try:
        # Run the automation
        print(f"Starting VerixAI automation with parameters: {test_params}")
        automation = VerixAIAutomation(test_params)
        result = automation.run_automation()

        # Print the result
        print("\n=== Test Result ===")
        print(f"Test ID: {result.get('test_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Duration: {result.get('duration_seconds')} seconds")

        if result.get('status') == 'FAILED':
            print("\nError Message:")
            print(result.get('error_message'))

        print("\nScreenshots:")
        for screenshot in result.get('screenshots', []):
            print(f"- {screenshot}")

        return 0 if result.get('status') == 'PASSED' else 1
    except Exception as e:
        print(f"Unhandled exception in test execution: {str(e)}")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
