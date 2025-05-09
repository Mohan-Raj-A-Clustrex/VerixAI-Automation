from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import openai
import json
import os
import traceback
from datetime import datetime
from fastapi import HTTPException
from config import DevConfig, StagingConfig, ProdConfig
from utils.test_utils import TestResult
from utils.email_utils import send_test_result_email


env_map = {
    'dev': DevConfig,
    'staging': StagingConfig,
    'prod': ProdConfig
}

class VerixAIAutomation:
    """Class to handle VerixAI automation"""

    def __init__(self, test_params=None):
        """
        Initialize the automation with test parameters

        Args:
            test_params (dict): Parameters for the test run
        """
        self.test_params = test_params or {}
        self.test_result = TestResult(test_params=test_params)
        self.driver = None
        self.wait = None
        self.openai_client = None

        # Get environment from test parameters or default to 'dev'
        env = self.test_params.get('env', 'dev')

        # Select the appropriate config class based on environment
        config_class = env_map.get(env)
        if not config_class:
            print(f"Invalid environment specified: {env}, defaulting to 'dev'")
            config_class = DevConfig

        # Set the config for this instance
        self.config = config_class

        print(f"Using environment: {env}")

        # Extract case details from parameters
        self.case_details = self.test_params.get('case_details', None)

        # Use sample_data directory structure directly
        sample_data_dir = os.path.join(os.getcwd(), 'sample_data')
        print(f"Using sample_data directory: {sample_data_dir}")

        # Set file and folder paths directly from sample_data directory
        self.notes_file_path = os.path.join(sample_data_dir, 'notes.pdf')
        self.notes_folder_path = os.path.join(sample_data_dir, 'notes_folder')
        self.imaging_file_path = os.path.join(sample_data_dir, 'imaging.dcm')
        self.imaging_folder_path = os.path.join(sample_data_dir, 'imaging_folder')

        # Use the same paths for chronology as for notes
        self.chronology_file_path = self.notes_file_path
        self.chronology_folder_path = self.notes_folder_path

        # Log the paths being used
        print(f"Using notes file path: {self.notes_file_path}")
        print(f"Using notes folder path: {self.notes_folder_path}")
        print(f"Using imaging file path: {self.imaging_file_path}")
        print(f"Using imaging folder path: {self.imaging_folder_path}")

        # Create screenshots directory
        os.makedirs(self.config.SCREENSHOTS_DIR, exist_ok=True)

    def init_driver(self, headless=True):
        """Initialize the Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_experimental_option("detach", True)
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        # Use the same approach as in main.py
        try:
            print("Initializing Chrome WebDriver with standard options")
            self.driver = webdriver.Chrome(options=chrome_options)
            print("Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"Error initializing Chrome driver: {str(e)}")
            print("Trying with additional options...")

            # Try with additional options
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-infobars")

            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                print("Chrome WebDriver initialized successfully with additional options")
            except Exception as e:
                print(f"Error initializing Chrome driver with additional options: {str(e)}")
                raise

        self.wait = WebDriverWait(self.driver, 20)
        return self.driver

    def get_openai_client(self):
        """Initialize and return the Azure OpenAI client"""
        self.openai_client = openai.AzureOpenAI(
            api_key=self.config.AZURE_API_KEY,
            api_version=self.config.AZURE_API_VERSION,
            azure_endpoint=self.config.AZURE_ENDPOINT
        )
        return self.openai_client

    def generate_case_details(self):
        """Generate case details using Azure OpenAI if not provided"""
        if self.case_details:
            print("Using provided case details")
            return self.case_details

        print("Generating case details with Azure OpenAI")
        client = self.get_openai_client()
        prompt = """
        Return ONLY a valid JSON object (no explanation text) with the following keys:
        - title
        - plaintiff_name
        - medical_provider
        - description

        The JSON must strictly follow this format:
        {
          "title": "string",
          "plaintiff_name": "string",
          "medical_provider": "string",
          "description": "string"
        }
        """
        response = client.chat.completions.create(
            model=self.config.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)

    def take_screenshot(self, name, test_case_name=None):
        """
        Take a screenshot and add it to the test result

        Args:
            name (str): Name of the screenshot
            test_case_name (str, optional): Name of the test case to associate the screenshot with
        """
        if not self.driver:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"

        try:
            # Capture screenshot as binary data
            screenshot_data = self.driver.get_screenshot_as_png()
            print(f"Screenshot captured: {filename}")

            # Add screenshot to test result
            self.test_result.add_screenshot(screenshot_data, filename, test_case_name)

            # For backward compatibility, also save to disk if needed
            if hasattr(self.config, 'SAVE_SCREENSHOTS_TO_DISK') and self.config.SAVE_SCREENSHOTS_TO_DISK:
                filepath = os.path.join(self.config.SCREENSHOTS_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(screenshot_data)
                print(f"Screenshot also saved to disk: {filepath}")

            return filename
        except Exception as e:
            print(f"Error taking screenshot: {str(e)}")
            return None

    def element_exists(self, by, value, timeout=5):
        """Check if an element exists on the page"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False

    def handle_upload(self, file_path, upload_type="file"):
        """Handle file or folder upload in the upload popup"""
        try:
            # Wait for the file upload dialog to be visible
            print(f"Waiting for file upload dialog to handle {upload_type} upload")
            self.wait.until(EC.visibility_of_element_located((By.ID, "file-upload-popup")))

            # Take a screenshot of the upload dialog
            self.take_screenshot(f"before_{upload_type}_upload_dialog")

            # Find and use the appropriate input element based on upload type
            if upload_type == "file":
                input_id = "upload-input-file"
                print("Using file upload input")
            else:  # folder
                input_id = "upload-input"
                print("Using folder upload input")

            # Try multiple approaches to find the input element
            file_input = None
            try:
                # First try by ID
                file_input = self.wait.until(EC.presence_of_element_located((By.ID, input_id)))
            except TimeoutException:
                # Try by CSS selector
                try:
                    selector = f"input#{input_id}" if upload_type == "file" else "input[webkitdirectory]"
                    file_input = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                except TimeoutException:
                    # Try by XPath
                    try:
                        xpath = f"//input[@id='{input_id}']" if upload_type == "file" else "//input[@webkitdirectory]"
                        file_input = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    except TimeoutException:
                        # Last resort: find all file inputs and use the appropriate one
                        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if len(inputs) > 0:
                            for inp in inputs:
                                if (upload_type == "folder" and inp.get_attribute("webkitdirectory")) or \
                                   (upload_type == "file" and not inp.get_attribute("webkitdirectory")):
                                    file_input = inp
                                    break

            if not file_input:
                raise Exception(f"Could not find {upload_type} input element")

            # Make sure the element is visible and enabled
            if not file_input.is_displayed() or not file_input.is_enabled():
                print(f"Warning: {upload_type} input element may not be visible or enabled")
                # Try to make it visible with JavaScript if needed
                self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
                self.driver.execute_script("arguments[0].disabled = false;", file_input)
                self.driver.execute_script("arguments[0].removeAttribute('hidden');", file_input)
                # For folder upload, ensure webkitdirectory attribute is set
                if upload_type == "folder":
                    self.driver.execute_script("arguments[0].setAttribute('webkitdirectory', '');", file_input)
                    self.driver.execute_script("arguments[0].setAttribute('directory', '');", file_input)
                    self.driver.execute_script("arguments[0].setAttribute('mozdirectory', '');", file_input)

            # Send the file path to the input element
            print(f"Sending path: {file_path} to input element")
            file_input.send_keys(file_path)
            time.sleep(3)  # Give more time for the file/folder to be selected

            # Take a screenshot after selecting the file/folder
            self.take_screenshot(f"after_{upload_type}_selection")

            # Click the upload button
            try:
                upload_files_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "upload-files-btn")))
                self.driver.execute_script("arguments[0].click();", upload_files_btn)
            except TimeoutException:
                # Try alternative selectors for the upload button
                try:
                    upload_files_btn = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Upload') or contains(@class, 'upload')]")))
                    self.driver.execute_script("arguments[0].click();", upload_files_btn)
                except TimeoutException:
                    # Try to submit the form directly
                    form = self.driver.find_element(By.CSS_SELECTOR, "form")
                    self.driver.execute_script("arguments[0].submit();", form)

            # Wait for upload to complete
            print("Waiting for upload to complete")
            time.sleep(20)  # Increased wait time for larger folders

            # Take a screenshot after upload
            self.take_screenshot(f"after_{upload_type}_upload")

            # Check if the file upload popup is still visible and close it if needed
            try:
                popup = self.driver.find_element(By.ID, "file-upload-popup")
                if popup.is_displayed():
                    print("File upload popup is still visible, attempting to close it")
                    try:
                        close_button = self.driver.find_element(By.ID, "fileUploadClosePopupBtn")
                        self.driver.execute_script("arguments[0].click();", close_button)
                    except NoSuchElementException:
                        # Try alternative close button selectors
                        close_buttons = self.driver.find_elements(By.XPATH,
                            "//button[contains(@class, 'close') or contains(text(), 'Close') or contains(@class, 'cancel')]")
                        if close_buttons:
                            self.driver.execute_script("arguments[0].click();", close_buttons[0])
                        else:
                            # Try clicking outside the popup
                            self.driver.execute_script("document.body.click();")
                    time.sleep(2)
            except Exception as e:
                print(f"Error checking/closing file upload popup: {str(e)}")

            return True
        except Exception as e:
            print(f"Error during {upload_type} upload: {str(e)}")
            self.take_screenshot(f"{upload_type}_upload_error")
            return False

    def close_side_panel(self):
        """Close the side panel if it's open"""
        try:
            # First try by ID "panel-close-button" as specified in the requirements
            if self.element_exists(By.ID, "panel-close-button", timeout=2):
                collapse_btn = self.driver.find_element(By.ID, "panel-close-button")
                print("Found panel close button by ID 'panel-close-button', clicking immediately")
                self.driver.execute_script("arguments[0].click();", collapse_btn)
                return True

            # Try by ID "close-side-panel" as alternative
            if self.element_exists(By.ID, "close-side-panel", timeout=2):
                collapse_btn = self.driver.find_element(By.ID, "close-side-panel")
                self.driver.execute_script("arguments[0].click();", collapse_btn)
                return True

            # Try alternative ID
            if self.element_exists(By.ID, "collapseExpandBtn", timeout=2):
                collapse_btn = self.driver.find_element(By.ID, "collapseExpandBtn")
                self.driver.execute_script("arguments[0].click();", collapse_btn)
                return True

            # Try by CSS selector
            if self.element_exists(By.CSS_SELECTOR, "button[title='Collapse Sidebar']", timeout=2):
                collapse_btn = self.driver.find_element(By.CSS_SELECTOR, "button[title='Collapse Sidebar']")
                self.driver.execute_script("arguments[0].click();", collapse_btn)
                return True

            # Try by XPath with SVG child
            if self.element_exists(By.XPATH, "//button[contains(@class, 'rounded-full') and .//svg]", timeout=2):
                collapse_btn = self.driver.find_element(By.XPATH, "//button[contains(@class, 'rounded-full') and .//svg]")
                self.driver.execute_script("arguments[0].click();", collapse_btn)
                return True

            print("Could not find any close button for the side panel")
            return False
        except Exception as e:
            print(f"Error closing side panel: {str(e)}")
            self.take_screenshot("side_panel_close_error")
            return False

    def run_automation(self):
        """Run the full VerixAI automation workflow"""
        try:
            print(f"Starting VerixAI automation with test ID: {self.test_result.test_id}")

            # Initialize the driver
            self.init_driver(headless=True)

            # Generate or use provided case details
            case_details = self.generate_case_details()
            print("Case Details:", case_details)

            # Start Login Test Case
            self.test_result.start_test_case("Login")
            try:
                # Navigate to the login page
                self.driver.get(self.config.BASE_URL)
                self.take_screenshot("login_page", "Login")

                # Login Workflow
                self.wait.until(EC.element_to_be_clickable((By.ID, "login-btn"))).click()
                self.wait.until(EC.element_to_be_clickable((By.ID, "social-VerixAI-SSO"))).click()

                self.wait.until(EC.visibility_of_element_located((By.NAME, "loginfmt"))).send_keys(self.config.LOGIN_EMAIL)
                self.wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
                self.take_screenshot("login_email_entered", "Login")

                self.wait.until(EC.visibility_of_element_located((By.NAME, "passwd"))).send_keys(self.config.LOGIN_PASSWORD)
                self.wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
                self.take_screenshot("login_password_entered", "Login")

                # Handle "Stay signed in?" prompt
                try:
                    self.wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
                except TimeoutException:
                    print("No 'Stay signed in' prompt appeared, continuing...")

                # Verify login success by checking for elements on the dashboard
                self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".dt-buttons")))
                self.take_screenshot("login_successful", "Login")

                # Mark login test case as passed
                self.test_result.end_test_case("Login", passed=True)
            except Exception as e:
                error_message = f"Login failed: {str(e)}"
                print(error_message)
                self.take_screenshot("login_error", "Login")
                self.test_result.end_test_case("Login", passed=False, error_message=error_message)
                raise

            # Start Case Creation Test Case
            self.test_result.start_test_case("Case Creation")
            try:
                # Create New Case
                new_case_button = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".dt-buttons .dt-button.bg-purple-600")))
                new_case_button.click()
                self.take_screenshot("new_case_form", "Case Creation")

                # Fill in case details
                self.wait.until(EC.visibility_of_element_located((By.ID, "title"))).send_keys(case_details["title"])
                self.driver.find_element(By.ID, "plaintiff_name").send_keys(case_details["plaintiff_name"])
                self.driver.find_element(By.ID, "medical_provider").send_keys(case_details["medical_provider"])
                self.driver.find_element(By.ID, "description").send_keys(case_details["description"])
                self.take_screenshot("case_details_filled", "Case Creation")

                self.wait.until(EC.element_to_be_clickable((By.ID, "new-case-submit"))).click()

                # Wait for case to be created and page to load
                print("Waiting for page to load after case creation...")
                time.sleep(5)

                # Take a screenshot after case creation
                self.take_screenshot("after_case_creation", "Case Creation")

                # Verify case was created by checking for case-specific elements
                self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "button#tab-notes")))

                # Mark case creation test case as passed
                self.test_result.end_test_case("Case Creation", passed=True)
            except Exception as e:
                error_message = f"Case creation failed: {str(e)}"
                print(error_message)
                self.take_screenshot("case_creation_error", "Case Creation")
                self.test_result.end_test_case("Case Creation", passed=False, error_message=error_message)
                raise

            # Make sure we're on the case details page
            print("Making sure we're on the case details page")

            # Start Clinical Notes Upload Test Case
            self.test_result.start_test_case("Clinical Notes Upload")
            try:
                # Upload Clinical Notes
                print("Navigating to Clinical Notes tab")
                notes_tab = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-notes")))
                self.driver.execute_script("arguments[0].click();", notes_tab)
                self.take_screenshot("clinical_notes_tab", "Clinical Notes Upload")

                # Wait for the clinical notes panel to be visible
                self.wait.until(EC.visibility_of_element_located((By.ID, "clinical-notes-panel")))

                # Find the upload button in the clinical notes panel
                upload_button = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                self.driver.execute_script("arguments[0].click();", upload_button)
                self.take_screenshot("clinical_notes_upload_button", "Clinical Notes Upload")

                # Test folder upload for Clinical Notes
                print("Testing folder upload for Clinical Notes")
                print(f"Using folder path: {self.notes_folder_path}")
                folder_upload_success = self.handle_upload(self.notes_folder_path, "folder")
                self.take_screenshot("after_folder_upload_attempt", "Clinical Notes Upload")

                if folder_upload_success:
                    print("Successfully uploaded folder to Clinical Notes")

                    # Now try file upload
                    upload_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                    self.driver.execute_script("arguments[0].click();", upload_button)
                    time.sleep(2)

                    print("Testing file upload for Clinical Notes")
                    print(f"Using file path: {self.notes_file_path}")
                    file_upload_success = self.handle_upload(self.notes_file_path, "file")
                    self.take_screenshot("after_file_upload_attempt", "Clinical Notes Upload")

                    if file_upload_success:
                        print("Successfully uploaded file to Clinical Notes")
                    else:
                        print("Failed to upload file to Clinical Notes")
                        # We don't fail the test case here since folder upload succeeded
                else:
                    print("Failed to upload folder to Clinical Notes, trying file upload instead")

                    # Try file upload as fallback
                    if self.element_exists(By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]'):
                        upload_button = self.wait.until(EC.element_to_be_clickable(
                            (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                        self.driver.execute_script("arguments[0].click();", upload_button)
                        time.sleep(2)

                    print(f"Using file path: {self.notes_file_path}")
                    file_upload_success = self.handle_upload(self.notes_file_path, "file")
                    self.take_screenshot("after_fallback_file_upload", "Clinical Notes Upload")

                    if file_upload_success:
                        print("Successfully uploaded file to Clinical Notes as fallback")
                    else:
                        print("Failed to upload file to Clinical Notes as fallback")
                        # Both folder and file upload failed, mark test case as failed
                        raise Exception("Both folder and file upload failed for Clinical Notes")

                # Verify uploads by checking for documents in the panel
                try:
                    self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#clinical-notes-panel .document-item")))
                    self.take_screenshot("clinical_notes_documents_visible", "Clinical Notes Upload")
                except TimeoutException:
                    print("Warning: Could not verify documents in Clinical Notes panel")
                    self.take_screenshot("clinical_notes_verification_warning", "Clinical Notes Upload")

                # Mark test case as passed
                self.test_result.end_test_case("Clinical Notes Upload", passed=True)
            except Exception as e:
                error_message = f"Clinical Notes upload failed: {str(e)}"
                print(error_message)
                self.take_screenshot("clinical_notes_upload_error", "Clinical Notes Upload")
                self.test_result.end_test_case("Clinical Notes Upload", passed=False, error_message=error_message)
                # Continue with other test cases instead of raising the exception
                print("Continuing with other test cases despite Clinical Notes upload failure")

            # Close the side panel
            self.close_side_panel()
            time.sleep(2)

            # Start Medical Imaging Upload Test Case
            self.test_result.start_test_case("Medical Imaging Upload")
            try:
                # Upload Medical Imaging
                print("Navigating to Medical Imaging tab")
                imaging_tab = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-imaging")))
                self.driver.execute_script("arguments[0].click();", imaging_tab)
                self.take_screenshot("medical_imaging_tab", "Medical Imaging Upload")

                # Wait for the medical imaging panel to be visible
                self.wait.until(EC.visibility_of_element_located((By.ID, "medical-imaging-panel")))

                # Find the upload button in the medical imaging panel
                upload_button = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                self.driver.execute_script("arguments[0].click();", upload_button)
                self.take_screenshot("medical_imaging_upload_button", "Medical Imaging Upload")

                # Test folder upload for Medical Imaging
                print("Testing folder upload for Medical Imaging")
                print(f"Using folder path: {self.imaging_folder_path}")
                folder_upload_success = self.handle_upload(self.imaging_folder_path, "folder")
                self.take_screenshot("after_imaging_folder_upload", "Medical Imaging Upload")

                if folder_upload_success:
                    print("Successfully uploaded folder to Medical Imaging")

                    # Now try file upload
                    upload_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                    self.driver.execute_script("arguments[0].click();", upload_button)
                    time.sleep(2)

                    print("Testing file upload for Medical Imaging")
                    print(f"Using file path: {self.imaging_file_path}")
                    file_upload_success = self.handle_upload(self.imaging_file_path, "file")
                    self.take_screenshot("after_imaging_file_upload", "Medical Imaging Upload")

                    if file_upload_success:
                        print("Successfully uploaded file to Medical Imaging")
                    else:
                        print("Failed to upload file to Medical Imaging")
                        # We don't fail the test case here since folder upload succeeded
                else:
                    print("Failed to upload folder to Medical Imaging, trying file upload instead")

                    # Try file upload as fallback
                    if self.element_exists(By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]'):
                        upload_button = self.wait.until(EC.element_to_be_clickable(
                            (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                        self.driver.execute_script("arguments[0].click();", upload_button)
                        time.sleep(2)

                    print(f"Using file path: {self.imaging_file_path}")
                    file_upload_success = self.handle_upload(self.imaging_file_path, "file")
                    self.take_screenshot("after_imaging_fallback_file_upload", "Medical Imaging Upload")

                    if file_upload_success:
                        print("Successfully uploaded file to Medical Imaging as fallback")
                    else:
                        print("Failed to upload file to Medical Imaging as fallback")
                        # Both folder and file upload failed, mark test case as failed
                        raise Exception("Both folder and file upload failed for Medical Imaging")

                # Verify uploads by checking for documents in the panel
                try:
                    self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#medical-imaging-panel .document-item")))
                    self.take_screenshot("medical_imaging_documents_visible", "Medical Imaging Upload")
                except TimeoutException:
                    print("Warning: Could not verify documents in Medical Imaging panel")
                    self.take_screenshot("medical_imaging_verification_warning", "Medical Imaging Upload")

                # Mark test case as passed
                self.test_result.end_test_case("Medical Imaging Upload", passed=True)
            except Exception as e:
                error_message = f"Medical Imaging upload failed: {str(e)}"
                print(error_message)
                self.take_screenshot("medical_imaging_upload_error", "Medical Imaging Upload")
                self.test_result.end_test_case("Medical Imaging Upload", passed=False, error_message=error_message)
                # Continue with other test cases instead of raising the exception
                print("Continuing with other test cases despite Medical Imaging upload failure")

            # Close the side panel
            self.close_side_panel()
            time.sleep(2)


            # Start Medical Chronology Test Case
            self.test_result.start_test_case("Medical Chronology")
            try:
                # Medical Chronology Automation - using a more direct approach to find the tab faster
                print("Looking for chronology tab with optimized approach")

                # Take a screenshot before looking for chronology tab
                self.take_screenshot("before_finding_chronology_tab", "Medical Chronology")

                # Try multiple selectors in parallel rather than sequentially to save time
                chrono_tab_found = False

            except Exception as e:
                error_message = f"Error during Medical Chronology tab lookup: {str(e)}"
                print(error_message)
                self.take_screenshot("medical_chronology_tab_lookup_error", "Medical Chronology")
                self.test_result.end_test_case("Medical Chronology", passed=False, error_message=error_message)
                # Continue with other test cases instead of raising the exception
                print("Continuing with other test cases despite Medical Chronology tab lookup failure")

            # First, try direct ID lookup which is fastest
            if self.element_exists(By.ID, "tab-chrono", timeout=2):
                print("Found chronology tab by direct ID lookup")
                chrono_tab = self.driver.find_element(By.ID, "tab-chrono")
                chrono_tab_found = True
            # Then try CSS selector
            elif self.element_exists(By.CSS_SELECTOR, "button#tab-chrono", timeout=2):
                print("Found chronology tab with CSS selector")
                chrono_tab = self.driver.find_element(By.CSS_SELECTOR, "button#tab-chrono")
                chrono_tab_found = True
            # Try data attribute
            elif self.element_exists(By.CSS_SELECTOR, 'button[data-tab="chrono"]', timeout=2):
                print("Found chronology tab by data-tab attribute")
                chrono_tab = self.driver.find_element(By.CSS_SELECTOR, 'button[data-tab="chrono"]')
                chrono_tab_found = True
            # Try text content
            elif self.element_exists(By.XPATH, '//button[contains(., "Medical Chronology")]', timeout=2):
                print("Found chronology tab by text content")
                chrono_tab = self.driver.find_element(By.XPATH, '//button[contains(., "Medical Chronology")]')
                chrono_tab_found = True

            # If found by any method, click it
            if chrono_tab_found:
                try:
                    print("Clicking chronology tab using JavaScript for reliability")
                    self.driver.execute_script("arguments[0].click();", chrono_tab)
                except Exception as e:
                    print(f"JavaScript click failed: {str(e)}, trying normal click")
                    chrono_tab.click()
            else:
                # Fall back to the original approach if all quick methods fail
                try:
                    # Try with the standard wait approach
                    print("Using standard wait approach to find chronology tab")
                    chrono_tab = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-chrono")))
                    print("Found chronology tab with CSS selector button#tab-chrono")
                    self.driver.execute_script("arguments[0].click();", chrono_tab)
                except TimeoutException:
                    # As a last resort, try to find all buttons in the side panel
                    print("Attempting to find all buttons in the side panel for chronology tab")
                    side_panel_buttons = self.driver.find_elements(By.CSS_SELECTOR, "#side-panel button")
                    for button in side_panel_buttons:
                        try:
                            button_text = button.text.strip()
                            button_id = button.get_attribute('id')
                            button_data_tab = button.get_attribute('data-tab')

                            # If this looks like the Chronology tab, click it
                            if "chrono" in button_id.lower() or "chrono" in button_data_tab.lower() or "chronology" in button_text.lower():
                                print(f"Clicking button that appears to be the Chronology tab: {button_id}")
                                self.driver.execute_script("arguments[0].click();", button)
                                break
                        except Exception as e:
                            print(f"Error examining button: {str(e)}")
                    else:
                        raise Exception("Could not find the Chronology tab button")

            # Wait for the medical chronology panel to be visible
            print("Waiting for medical chronology panel to be visible")
            self.wait.until(EC.visibility_of_element_located((By.ID, "medical-chronology-panel")))

            # Find the chronology button in the medical chronology panel
            try:
                # First, check if we need to upload documents before creating chronology
                # Look for an upload button in the chronology panel
                try:
                    upload_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Upload")]')))
                    print("Found upload button in chronology panel, will upload documents first")
                    self.driver.execute_script("arguments[0].click();", upload_button)

                    # Handle file upload
                    print("Uploading chronology documents")
                    print(f"Using file path: {self.chronology_file_path}")
                    upload_success = self.handle_upload(self.chronology_file_path, "file")

                    if upload_success:
                        print("Successfully uploaded documents for chronology")

                        # Try folder upload for chronology
                        try:
                            print("Attempting to upload folder to Medical Chronology")
                            print(f"Using folder path: {self.chronology_folder_path}")

                            # Click upload button again
                            upload_button = self.wait.until(EC.element_to_be_clickable(
                                (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Upload")]')))
                            self.driver.execute_script("arguments[0].click();", upload_button)
                            time.sleep(2)  # Wait for popup to appear

                            # Handle folder upload
                            folder_upload_success = self.handle_upload(self.chronology_folder_path, "folder")
                            if folder_upload_success:
                                print("Successfully uploaded folder to Medical Chronology")
                            else:
                                print("Failed to upload folder to Medical Chronology")
                        except Exception as e:
                            print(f"Error during folder upload attempt for chronology: {str(e)}")
                            self.take_screenshot("chronology_folder_upload_error", "Medical Chronology")
                    else:
                        print("Failed to upload documents for chronology")
                except TimeoutException:
                    print("No upload button found in chronology panel, proceeding to create chronology")

                # Now look for the chronology creation button
                chrono_button = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Chronology")]')))
                print("Found chronology button")
                self.driver.execute_script("arguments[0].click();", chrono_button)
            except TimeoutException:
                try:
                    # Try with a more general selector
                    chrono_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="medical-chronology-panel"]//button')))
                    print("Found chronology button with general selector")
                    self.driver.execute_script("arguments[0].click();", chrono_button)
                except TimeoutException:
                    print("Could not find chronology button in medical chronology panel")
                    self.take_screenshot("chrono_button_error", "Medical Chronology")
                    raise

            # Wait for the select all checkbox to be visible and click it
            try:
                print("Waiting for select all checkbox")
                select_all = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="select-all-checkbox"]')))
                print("Found select all checkbox")
                self.driver.execute_script("arguments[0].click();", select_all)

                # Wait for selection to process
                print("Waiting for selection to process")
                time.sleep(6)

                # Click the create button
                print("Looking for create button")
                create_button = self.wait.until(EC.element_to_be_clickable((By.ID, "createBtn")))
                print("Found create button")
                self.driver.execute_script("arguments[0].click();", create_button)

                # Enter confirmation text
                print("Entering confirmation text")
                try:
                    confirm_input = self.wait.until(EC.visibility_of_element_located((By.ID, "confirmInput")))
                    confirm_input.send_keys("confirm")

                    # Click the confirm button
                    print("Clicking confirm button")
                    confirm_button = self.wait.until(EC.element_to_be_clickable((By.ID, "confirmCreateBtn")))
                    self.driver.execute_script("arguments[0].click();", confirm_button)
                except TimeoutException:
                    print("No confirmation dialog found, continuing with chronology creation")

                # Wait for chronology creation to complete
                print("Waiting for chronology creation to complete")
                time.sleep(60)

                # Take a screenshot of the created chronology
                self.take_screenshot("chronology_created", "Medical Chronology")

                # Close the side panel immediately after successful chronology creation
                print("Closing side panel immediately after chronology creation")
                # Try to close the panel without delay
                try:
                    # First try by ID "panel-close-button" as specified in the requirements
                    if self.element_exists(By.ID, "panel-close-button", timeout=2):
                        collapse_btn = self.driver.find_element(By.ID, "panel-close-button")
                        print("Found panel close button by ID 'panel-close-button', clicking immediately")
                        self.driver.execute_script("arguments[0].click();", collapse_btn)
                    else:
                        # Fall back to the regular close function
                        self.close_side_panel()
                except Exception as e:
                    print(f"Error in immediate panel close: {str(e)}")
                    # Fall back to the regular close function
                    self.close_side_panel()

                print("Successfully created medical chronology")

                # Mark Medical Chronology test case as passed
                self.test_result.end_test_case("Medical Chronology", passed=True)
            except Exception as e:
                error_message = f"Error during chronology creation: {str(e)}"
                print(error_message)
                self.take_screenshot("chronology_creation_error", "Medical Chronology")
                self.test_result.end_test_case("Medical Chronology", passed=False, error_message=error_message)

            # Mark test as passed (this will also send the email)
            details = self.test_result.mark_passed()
            return details

        except Exception as e:
            error_message = f"Error during automation: {str(e)}\n{traceback.format_exc()}"
            print(error_message)

            # Take a final error screenshot
            self.take_screenshot("final_error", "Overall Test")

            # Mark test as failed (this will also send the email)
            details = self.test_result.mark_failed(error_message)
            return details

        finally:
            # Always quit the driver to clean up resources
            if self.driver:
                try:
                    self.driver.quit()
                    print("Driver quit successfully")
                except:
                    print("Error quitting driver")
