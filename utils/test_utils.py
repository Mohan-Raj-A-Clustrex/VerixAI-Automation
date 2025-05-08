import os
import json
import uuid
import time
import io
import base64
from datetime import datetime
from config import Config
from utils.email_utils import send_test_result_email

class TestCase:
    """Class to handle individual test case results"""

    def __init__(self, name, parent_test_id):
        """
        Initialize a new test case

        Args:
            name (str): Name of the test case
            parent_test_id (str): ID of the parent test run
        """
        self.name = name
        self.test_id = f"{parent_test_id}_{name.lower().replace(' ', '_')}"
        self.start_time = datetime.now()
        self.end_time = None
        self.status = "RUNNING"
        self.error_message = None
        self.screenshots = []  # List of dicts with screenshot data and metadata

    def add_screenshot(self, screenshot_data, filename):
        """
        Add a screenshot to the test case

        Args:
            screenshot_data (bytes): The binary data of the screenshot
            filename (str): The filename for the screenshot
        """
        self.screenshots.append({
            'filename': filename,
            'data': screenshot_data,
            'timestamp': datetime.now().isoformat()
        })

    def mark_passed(self):
        """Mark the test case as passed"""
        self.end_time = datetime.now()
        self.status = "PASSED"
        return self.get_details()

    def mark_failed(self, error_message):
        """Mark the test case as failed with an error message"""
        self.end_time = datetime.now()
        self.status = "FAILED"
        self.error_message = error_message
        return self.get_details()

    def get_details(self):
        """Get a dictionary of test case details"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else None

        # Create a list of screenshot filenames only (not the binary data)
        screenshot_filenames = [s['filename'] for s in self.screenshots]

        details = {
            'name': self.name,
            'test_id': self.test_id,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': duration,
            'screenshots': screenshot_filenames,
            'screenshot_count': len(self.screenshots)
        }

        if self.error_message:
            details['error_message'] = self.error_message

        return details

class TestResult:
    """Class to handle test results and reporting"""

    def __init__(self, test_id=None, test_params=None):
        """
        Initialize a new test result

        Args:
            test_id (str): Unique identifier for the test (generated if not provided)
            test_params (dict): Parameters used for the test
        """
        self.test_id = test_id or f"test_{uuid.uuid4().hex[:8]}"
        self.start_time = datetime.now()
        self.end_time = None
        self.status = "RUNNING"
        self.error_message = None
        self.screenshots = []  # List of dicts with screenshot data and metadata
        self.test_params = test_params or {}
        self.test_cases = {}  # Dictionary to store individual test cases
        self.email_sent = False  # Flag to track if email has been sent

        # Create a temporary directory for any necessary files
        self.temp_dir = os.path.join(os.getcwd(), 'temp')
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def add_screenshot(self, screenshot_data, filename, test_case_name=None):
        """
        Add a screenshot to the test result

        Args:
            screenshot_data (bytes): The binary data of the screenshot
            filename (str): The filename for the screenshot
            test_case_name (str, optional): Name of the test case to add the screenshot to
        """
        # Create screenshot metadata
        screenshot_info = {
            'filename': filename,
            'data': screenshot_data,
            'timestamp': datetime.now().isoformat()
        }

        # Add to overall screenshots
        self.screenshots.append(screenshot_info)

        # Add to specific test case if provided
        if test_case_name and test_case_name in self.test_cases:
            self.test_cases[test_case_name].add_screenshot(screenshot_data, filename)

    def start_test_case(self, name):
        """
        Start a new test case

        Args:
            name (str): Name of the test case

        Returns:
            TestCase: The created test case
        """
        test_case = TestCase(name, self.test_id)
        self.test_cases[name] = test_case
        return test_case

    def end_test_case(self, name, passed=True, error_message=None):
        """
        End a test case with a pass/fail status

        Args:
            name (str): Name of the test case
            passed (bool): Whether the test case passed
            error_message (str, optional): Error message if the test case failed

        Returns:
            dict: Details of the test case
        """
        if name not in self.test_cases:
            # Create the test case if it doesn't exist
            self.start_test_case(name)

        if passed:
            details = self.test_cases[name].mark_passed()
        else:
            details = self.test_cases[name].mark_failed(error_message)

        # Update the overall test status if any test case fails
        if not passed and self.status != "FAILED":
            self.status = "FAILED"
            if not self.error_message:
                self.error_message = f"Test case '{name}' failed: {error_message}"

        return details

    def mark_passed(self):
        """Mark the overall test as passed and send email"""
        # Only mark as passed if no test cases have failed
        if self.status != "FAILED":
            self.status = "PASSED"

        self.end_time = datetime.now()
        details = self.get_details()

        # Send email with results
        self.send_email_report()

        return details

    def mark_failed(self, error_message):
        """Mark the overall test as failed with an error message and send email"""
        self.end_time = datetime.now()
        self.status = "FAILED"
        self.error_message = error_message
        details = self.get_details()

        # Send email with results
        self.send_email_report()

        return details

    def get_details(self):
        """Get a dictionary of test details"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else None

        # Get details for all test cases
        test_case_details = [case.get_details() for case in self.test_cases.values()]

        # Create a list of screenshot filenames only (not the binary data)
        screenshot_filenames = [s['filename'] for s in self.screenshots]

        details = {
            'test_id': self.test_id,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': duration,
            'test_params': self.test_params,
            'screenshots': screenshot_filenames,
            'screenshot_count': len(self.screenshots),
            'test_cases': test_case_details
        }

        if self.error_message:
            details['error_message'] = self.error_message

        return details

    def send_email_report(self):
        """Send email with test results and screenshots"""
        if self.email_sent:
            print("Email already sent for this test run")
            return False

        try:
            # Get test details
            details = self.get_details()

            # Extract binary screenshot data for email attachments
            screenshot_data = []
            for screenshot in self.screenshots:
                screenshot_data.append({
                    'filename': screenshot['filename'],
                    'data': screenshot['data']
                })

            # Send email with results and screenshots
            success = send_test_result_email(
                self.test_id,
                self.status,
                details,
                screenshot_data
            )

            if success:
                self.email_sent = True
                print(f"Email report sent successfully for test {self.test_id}")
            else:
                print(f"Failed to send email report for test {self.test_id}")

            return success

        except Exception as e:
            print(f"Error sending email report: {str(e)}")
            return False

    def save_result(self):
        """Save the test result to a JSON file (for backward compatibility)"""
        # Create results directory if needed
        results_dir = os.path.join(os.getcwd(), 'test_results')
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        result_file = os.path.join(results_dir, f"{self.test_id}.json")

        # Get details without binary data
        details = self.get_details()

        with open(result_file, 'w') as f:
            json.dump(details, f, indent=2)

        return result_file
