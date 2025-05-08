import smtplib
import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from config import Config

def send_test_result_email(test_id, status, details, screenshots=None):
    """
    Send an email with test results and screenshots

    Args:
        test_id (str): Unique identifier for the test
        status (str): 'PASSED' or 'FAILED'
        details (dict): Dictionary containing test details
        screenshots (list): List of dictionaries with screenshot data and filenames
    """
    # Check if email configuration is available
    if not all([Config.SMTP_SERVER, Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD, Config.EMAIL_RECIPIENTS]):
        print("Email configuration is incomplete. Skipping email notification.")
        return False

    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_USERNAME
        msg['To'] = ', '.join(Config.EMAIL_RECIPIENTS)
        msg['Subject'] = f"VerixAI Automation Test {status}: {test_id}"

        # Get test start and end times
        start_time = datetime.fromisoformat(details.get('start_time')) if 'start_time' in details else datetime.now()
        end_time = datetime.fromisoformat(details.get('end_time')) if 'end_time' in details else datetime.now()

        # Calculate duration
        duration_seconds = details.get('duration_seconds', 0)
        minutes, seconds = divmod(int(duration_seconds), 60)
        duration_formatted = f"{minutes}m {seconds}s"

        # Get test cases if available
        test_cases = details.get('test_cases', [])

        # Get screenshot count
        screenshot_count = details.get('screenshot_count', 0)

        # Create HTML content with purple theme
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }}
                .header {{ background-color: #8200db; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
                .content {{ padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 5px 5px; }}
                .passed {{ color: #28a745; font-weight: bold; }}
                .failed {{ color: #dc3545; font-weight: bold; }}
                .test-case {{ margin-bottom: 20px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }}
                .test-case-header {{ padding: 10px; background-color: #f8f9fa; border-bottom: 1px solid #ddd; }}
                .test-case-content {{ padding: 15px; }}
                .test-case-passed {{ border-left: 4px solid #28a745; }}
                .test-case-failed {{ border-left: 4px solid #dc3545; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .summary {{ background-color: #f8f9fa; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #777; text-align: center; }}
                .badge {{ display: inline-block; padding: 5px 10px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
                .badge-success {{ background-color: #28a745; color: white; }}
                .badge-danger {{ background-color: #dc3545; color: white; }}
                .badge-primary {{ background-color: #8200db; color: white; }}
                .duration {{ color: #6c757d; font-size: 14px; }}
                .error-details {{ background-color: #fff8f8; border-left: 4px solid #dc3545; padding: 10px; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2 style="margin: 0;">VerixAI Automation Test Result</h2>
            </div>
            <div class="content">
                <div class="summary">
                    <h3>Test Summary</h3>
                    <p>Test ID: <strong>{test_id}</strong></p>
                    <p>Overall Status: <span class="badge badge-{'success' if status == 'PASSED' else 'danger'}">{status}</span></p>
                    <p>Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>Total Duration: <span class="duration">{duration_formatted}</span></p>
                    <p>Screenshots: {screenshot_count} (attached to this email)</p>
                </div>
        """

        # Add test parameters if available
        if 'test_params' in details:
            html_content += """
                <h3>Test Parameters</h3>
                <table>
                    <tr>
                        <th>Parameter</th>
                        <th>Value</th>
                    </tr>
            """

            test_params = details.get('test_params', {})

            # Add case details if available
            if 'case_details' in test_params:
                for key, value in test_params['case_details'].items():
                    html_content += f"""
                    <tr>
                        <td>Case {key.replace('_', ' ').title()}</td>
                        <td>{value}</td>
                    </tr>
                    """

            html_content += """
                </table>
            """

        # Add error details if test failed
        if status == 'FAILED' and 'error_message' in details:
            html_content += f"""
                <h3>Error Details</h3>
                <div class="error-details">
                    <pre>{details['error_message']}</pre>
                </div>
            """

        # Add individual test cases if available
        if test_cases:
            html_content += """
                <h3>Individual Test Cases</h3>
            """

            for test_case in test_cases:
                case_name = test_case.get('name')
                case_status = test_case.get('status')
                case_duration = test_case.get('duration_seconds', 0)
                case_minutes, case_seconds = divmod(int(case_duration), 60)
                case_duration_formatted = f"{case_minutes}m {case_seconds}s"
                case_screenshot_count = test_case.get('screenshot_count', 0)

                html_content += f"""
                    <div class="test-case test-case-{'passed' if case_status == 'PASSED' else 'failed'}">
                        <div class="test-case-header">
                            <h4 style="margin: 0;">{case_name} <span class="badge badge-{'success' if case_status == 'PASSED' else 'danger'}">{case_status}</span></h4>
                            <p class="duration">Duration: {case_duration_formatted}</p>
                        </div>
                        <div class="test-case-content">
                """

                # Add error message if test case failed
                if case_status == 'FAILED' and 'error_message' in test_case:
                    html_content += f"""
                            <div class="error-details">
                                <h5>Error Details:</h5>
                                <pre>{test_case['error_message']}</pre>
                            </div>
                    """

                html_content += """
                        </div>
                    </div>
                """

        # Add footer
        html_content += """
                <div class="footer">
                    <p>This is an automated email from the VerixAI Automation System.</p>
                    <p>Screenshots are attached to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))

        # Attach screenshots if provided
        if screenshots:
            for i, screenshot in enumerate(screenshots):
                try:
                    # Get screenshot data and filename
                    img_data = screenshot.get('data')
                    filename = screenshot.get('filename')

                    if img_data and filename:
                        image = MIMEImage(img_data)
                        image.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                        msg.attach(image)
                except Exception as e:
                    print(f"Error attaching screenshot {i+1}: {str(e)}")

        # Connect to SMTP server and send email
        try:
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD)
                server.send_message(msg)
                print(f"Email notification sent successfully to {Config.EMAIL_RECIPIENTS}")
                return True
        except Exception as e:
            print(f"SMTP Error: {str(e)}")
            print("Email notification could not be sent. This is non-critical and the test will continue.")
            return False

    except Exception as e:
        print(f"Error preparing email: {str(e)}")
        print("Email notification could not be prepared. This is non-critical and the test will continue.")
        return False

def send_test_result_email_from_json(test_result_json_path):
    """
    Send an email with test results from a JSON file

    Args:
        test_result_json_path (str): Path to the test result JSON file
    """
    try:
        # Load the test result JSON
        with open(test_result_json_path, 'r') as f:
            test_result = json.load(f)

        test_id = test_result.get('test_id')
        status = test_result.get('status')
        screenshots = test_result.get('screenshots', [])

        # Send the email
        return send_test_result_email(test_id, status, test_result, screenshots)

    except Exception as e:
        print(f"Error preparing email from JSON: {str(e)}")
        return False
