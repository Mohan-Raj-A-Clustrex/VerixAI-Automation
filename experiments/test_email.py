import os
import sys
import json
from utils.email_utils import send_test_result_email_from_json

def main():
    """Test the email functionality"""
    if len(sys.argv) < 2:
        print("Usage: python test_email.py <test_result_json_file>")
        print("Example: python test_email.py test_results/test_7b54bc42.json")
        return 1

    test_result_path = sys.argv[1]

    if not os.path.exists(test_result_path):
        print(f"Error: Test result file not found: {test_result_path}")
        return 1

    print(f"Sending email for test result: {test_result_path}")

    try:
        # Load the test result to display some info
        with open(test_result_path, 'r') as f:
            test_result = json.load(f)

        test_id = test_result.get('test_id')
        status = test_result.get('status')
        test_cases = test_result.get('test_cases', [])

        print(f"Test ID: {test_id}")
        print(f"Status: {status}")
        print(f"Test Cases: {len(test_cases)}")

        # Send the email
        success = send_test_result_email_from_json(test_result_path)

        if success:
            print("Email sent successfully!")
            return 0
        else:
            print("Failed to send email.")
            return 1

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
