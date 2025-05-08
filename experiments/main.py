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

# Configuration
AZURE_API_KEY = "c5acdea67a534928b2e7056707a7cfdf"
AZURE_ENDPOINT = "https://cmengine-openaieast.openai.azure.com/"
AZURE_API_VERSION = "2024-08-01-preview"
MODEL_NAME = "gpt-4o"

LOGIN_EMAIL = "amohanraj@cormetrix.com"
LOGIN_PASSWORD = "Mohan4161@raj"

NOTES_FILE_PATH = r"C:\Users\amohanraj_clustrex\Downloads\06-03-24 limited echo report_Redacted.pdf"
NOTES_FOLDER_PATH = r"C:\Users\amohanraj_clustrex\Downloads\TAVR_patient2 1\TAVR_patient2"
IMAGING_FILE_PATH  = r"C:\Users\amohanraj_clustrex\Downloads\IMG00002.dcm"
IMAGING_FOLDER_PATH = r"C:\Users\amohanraj_clustrex\Downloads\AMBRATEST"

BASE_URL = "https://dev-verixai.cormetrix.com/login.html"

# Initialize headless Chrome
def init_driver(headless=True):
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=chrome_options)

# Helper function to check if an element exists
def element_exists(driver, by, value, timeout=5):
    """Check if an element exists on the page"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return True
    except TimeoutException:
        return False

# Helper function to wait for page to fully load
def wait_for_page_load(driver, timeout=30):
    """Wait for the page to fully load"""
    try:
        # Wait for the document to be in ready state
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        # Additional wait for any JavaScript frameworks to finish loading
        time.sleep(2)
        return True
    except TimeoutException:
        print("Timeout waiting for page to load")
        return False

# Helper function to handle file or folder upload
def handle_upload(driver, wait, file_path, upload_type="file"):
    """Handle file or folder upload in the upload popup

    Args:
        driver: WebDriver instance
        wait: WebDriverWait instance
        file_path: Path to the file or folder to upload
        upload_type: 'file' or 'folder'
    """
    try:
        # Wait for the file upload dialog to be visible
        print(f"Waiting for file upload dialog to handle {upload_type} upload")
        wait.until(EC.visibility_of_element_located((By.ID, "file-upload-popup")))

        # Take a screenshot of the upload dialog
        driver.save_screenshot(f"before_{upload_type}_upload_dialog.png")
        print(f"Screenshot saved to before_{upload_type}_upload_dialog.png")

        # Print the structure of the upload dialog for debugging
        print("Upload dialog structure:")
        try:
            upload_dialog = driver.find_element(By.ID, "file-upload-popup")
            upload_inputs = upload_dialog.find_elements(By.TAG_NAME, "input")
            for i, input_elem in enumerate(upload_inputs):
                input_id = input_elem.get_attribute('id')
                input_type = input_elem.get_attribute('type')
                input_name = input_elem.get_attribute('name')
                print(f"  Input {i+1}: id='{input_id}', type='{input_type}', name='{input_name}'")
        except Exception as e:
            print(f"Error getting upload dialog structure: {str(e)}")

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
            file_input = wait.until(EC.presence_of_element_located((By.ID, input_id)))
            print(f"Found {upload_type} input element with ID: {input_id}")
        except TimeoutException:
            # Try by CSS selector
            try:
                selector = f"input#{input_id}" if upload_type == "file" else "input[webkitdirectory]"
                file_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                print(f"Found {upload_type} input element with CSS selector: {selector}")
            except TimeoutException:
                # Try by XPath
                try:
                    xpath = f"//input[@id='{input_id}']" if upload_type == "file" else "//input[@webkitdirectory]"
                    file_input = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    print(f"Found {upload_type} input element with XPath: {xpath}")
                except TimeoutException:
                    # Last resort: find all file inputs and use the appropriate one
                    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if len(inputs) > 0:
                        for inp in inputs:
                            if (upload_type == "folder" and inp.get_attribute("webkitdirectory")) or \
                               (upload_type == "file" and not inp.get_attribute("webkitdirectory")):
                                file_input = inp
                                print(f"Found {upload_type} input element by scanning all file inputs")
                                break

        if not file_input:
            raise Exception(f"Could not find {upload_type} input element")

        # Make sure the element is visible and enabled
        if not file_input.is_displayed() or not file_input.is_enabled():
            print(f"Warning: {upload_type} input element may not be visible or enabled")
            # Try to make it visible with JavaScript if needed
            driver.execute_script("arguments[0].style.display = 'block';", file_input)
            driver.execute_script("arguments[0].disabled = false;", file_input)
            driver.execute_script("arguments[0].removeAttribute('hidden');", file_input)
            # For folder upload, ensure webkitdirectory attribute is set
            if upload_type == "folder":
                driver.execute_script("arguments[0].setAttribute('webkitdirectory', '');", file_input)
                driver.execute_script("arguments[0].setAttribute('directory', '');", file_input)
                driver.execute_script("arguments[0].setAttribute('mozdirectory', '');", file_input)
                print("Set directory attributes on input element")

        # Send the file path to the input element
        print(f"Sending path: {file_path} to input element")
        file_input.send_keys(file_path)
        time.sleep(3)  # Give more time for the file/folder to be selected

        # Take a screenshot after selecting the file/folder
        driver.save_screenshot(f"after_{upload_type}_selection.png")
        print(f"Screenshot saved to after_{upload_type}_selection.png")

        # Click the upload button
        try:
            upload_files_btn = wait.until(EC.element_to_be_clickable((By.ID, "upload-files-btn")))
            print("Found upload files button")
            driver.execute_script("arguments[0].click();", upload_files_btn)
        except TimeoutException:
            # Try alternative selectors for the upload button
            try:
                upload_files_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Upload') or contains(@class, 'upload')]")))
                print("Found upload button with alternative selector")
                driver.execute_script("arguments[0].click();", upload_files_btn)
            except TimeoutException:
                print("Could not find upload button, trying to submit the form directly")
                try:
                    # Try to submit the form directly
                    form = driver.find_element(By.CSS_SELECTOR, "form")
                    driver.execute_script("arguments[0].submit();", form)
                    print("Submitted the form directly")
                except Exception as e:
                    print(f"Error submitting form: {str(e)}")
                    raise

        # Wait for upload to complete
        print("Waiting for upload to complete")
        time.sleep(20)  # Increased wait time for larger folders

        # Check for upload progress or success indicators
        try:
            # Look for success message or progress indicator
            success_elements = driver.find_elements(By.XPATH,
                "//*[contains(text(), 'Success') or contains(text(), 'Uploaded') or contains(text(), 'Complete')]")
            if success_elements:
                print(f"Found {len(success_elements)} success indicators")
        except Exception as e:
            print(f"Error checking for success indicators: {str(e)}")

        # Check if the file upload popup is still visible and close it if needed
        try:
            popup = driver.find_element(By.ID, "file-upload-popup")
            if popup.is_displayed():
                print("File upload popup is still visible, attempting to close it")
                try:
                    close_button = driver.find_element(By.ID, "fileUploadClosePopupBtn")
                    driver.execute_script("arguments[0].click();", close_button)
                except NoSuchElementException:
                    # Try alternative close button selectors
                    close_buttons = driver.find_elements(By.XPATH,
                        "//button[contains(@class, 'close') or contains(text(), 'Close') or contains(@class, 'cancel')]")
                    if close_buttons:
                        print(f"Found {len(close_buttons)} close buttons, clicking the first one")
                        driver.execute_script("arguments[0].click();", close_buttons[0])
                    else:
                        print("No close button found, trying to click outside the popup")
                        # Try clicking outside the popup
                        driver.execute_script("document.body.click();")
                time.sleep(2)
        except Exception as e:
            print(f"Error checking/closing file upload popup: {str(e)}")

        # Take a screenshot after upload
        driver.save_screenshot(f"after_{upload_type}_upload.png")
        print(f"Screenshot saved to after_{upload_type}_upload.png")

        # Check if files/folders appear in the UI after upload
        try:
            # Look for elements that might indicate successful upload
            file_elements = driver.find_elements(By.XPATH,
                "//*[contains(@class, 'file') or contains(@class, 'document') or contains(@class, 'item')]")
            if file_elements:
                print(f"Found {len(file_elements)} potential file/folder elements after upload")
                for i, elem in enumerate(file_elements[:5]):  # Show first 5 only
                    try:
                        elem_text = elem.text.strip()
                        if elem_text:
                            print(f"  Element {i+1}: '{elem_text}'")
                    except:
                        pass
        except Exception as e:
            print(f"Error checking for uploaded files in UI: {str(e)}")

        return True
    except Exception as e:
        print(f"Error during {upload_type} upload: {str(e)}")
        driver.save_screenshot(f"{upload_type}_upload_error.png")
        print(f"Screenshot saved to {upload_type}_upload_error.png")
        return False

# Helper function to close side panel
def close_side_panel(driver, wait):
    """Close the side panel if it's open"""
    try:
        # Look for the panel close button using the correct ID
        try:
            # First try by ID "panel-close-button" as specified in the requirements
            collapse_btn = wait.until(EC.element_to_be_clickable((By.ID, "panel-close-button")))
            print("Found panel close button by ID 'panel-close-button', clicking to close side panel")
        except TimeoutException:
            try:
                # Try by ID "close-side-panel" as alternative
                collapse_btn = wait.until(EC.element_to_be_clickable((By.ID, "close-side-panel")))
                print("Found panel close button by ID 'close-side-panel', clicking to close side panel")
            except TimeoutException:
                try:
                    # Try alternative ID
                    collapse_btn = wait.until(EC.element_to_be_clickable((By.ID, "collapseExpandBtn")))
                    print("Found collapse button by ID 'collapseExpandBtn', clicking to close side panel")
                except TimeoutException:
                    try:
                        # Try by CSS selector
                        collapse_btn = wait.until(EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button[title='Collapse Sidebar']")))
                        print("Found collapse button by title attribute, clicking to close side panel")
                    except TimeoutException:
                        # Try by XPath with SVG child
                        collapse_btn = wait.until(EC.element_to_be_clickable(
                            (By.XPATH, "//button[contains(@class, 'rounded-full') and .//svg]")))
                        print("Found collapse button by XPath, clicking to close side panel")

        # Use JavaScript to click the button to avoid any potential interception issues
        driver.execute_script("arguments[0].click();", collapse_btn)
        print("Clicked panel close button using JavaScript")
        time.sleep(2)  # Give more time for the animation to complete
        return True
    except Exception as e:
        print(f"Error closing side panel: {str(e)}")
        # Take a screenshot for debugging
        driver.save_screenshot("side_panel_close_error.png")
        print("Screenshot saved to side_panel_close_error.png")
        return False

# Helper function to ensure no overlays are blocking interaction
def ensure_no_overlays(driver):
    """Check for and close any overlays that might block interaction"""
    try:
        # Check for file upload popup
        try:
            popup = driver.find_element(By.ID, "file-upload-popup")
            if popup.is_displayed():
                print("File upload popup is visible, attempting to close it")
                close_button = driver.find_element(By.ID, "fileUploadClosePopupBtn")
                close_button.click()
                time.sleep(2)
        except NoSuchElementException:
            pass

        # Check for other potential overlays
        # Add more checks here if needed

        return True
    except Exception as e:
        print(f"Error checking for overlays: {str(e)}")
        return False

# Helper function to print page structure for debugging
def print_page_structure(driver):
    """Print the structure of the page for debugging"""
    print("\n=== PAGE STRUCTURE ===")
    # Get all tabs
    try:
        tabs = driver.find_elements(By.XPATH, '//ul[contains(@class, "nav-tabs")]/li')
        print(f"Found {len(tabs)} tab elements:")
        for i, tab in enumerate(tabs):
            try:
                tab_id = tab.get_attribute('id')
                tab_class = tab.get_attribute('class')
                tab_text = tab.text
                print(f"  Tab {i+1}: id='{tab_id}', class='{tab_class}', text='{tab_text}'")

                # Try to find the anchor inside the tab
                anchors = tab.find_elements(By.TAG_NAME, 'a')
                for j, anchor in enumerate(anchors):
                    anchor_id = anchor.get_attribute('id')
                    anchor_href = anchor.get_attribute('href')
                    anchor_text = anchor.text
                    print(f"    Anchor {j+1}: id='{anchor_id}', href='{anchor_href}', text='{anchor_text}'")
            except Exception as e:
                print(f"  Error getting tab {i+1} details: {str(e)}")
    except Exception as e:
        print(f"Error finding tabs: {str(e)}")

    # Try to find any elements with IDs containing 'tab'
    try:
        tab_elements = driver.find_elements(By.XPATH, '//*[contains(@id, "tab")]')
        print(f"\nFound {len(tab_elements)} elements with 'tab' in ID:")
        for i, elem in enumerate(tab_elements):
            try:
                elem_id = elem.get_attribute('id')
                elem_tag = elem.tag_name
                elem_text = elem.text
                print(f"  Element {i+1}: id='{elem_id}', tag='{elem_tag}', text='{elem_text}'")
            except Exception as e:
                print(f"  Error getting element {i+1} details: {str(e)}")
    except Exception as e:
        print(f"Error finding tab elements: {str(e)}")

    print("=== END PAGE STRUCTURE ===\n")

# Azure OpenAI Client Setup
def get_openai_client():
    return openai.AzureOpenAI(
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_ENDPOINT
    )

# Generate Case Details using Azure OpenAI
def generate_case_details(client):
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
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

# Automate VerixAI Case Workflow
def automate_case_workflow(driver, case_details):
    # Set default timeout for explicit waits
    wait = WebDriverWait(driver, 20)

    # Navigate to the login page
    driver.get(BASE_URL)

    # Login Workflow with explicit waits
    wait.until(EC.element_to_be_clickable((By.ID, "login-btn"))).click()
    wait.until(EC.element_to_be_clickable((By.ID, "social-VerixAI-SSO"))).click()

    wait.until(EC.visibility_of_element_located((By.NAME, "loginfmt"))).send_keys(LOGIN_EMAIL)
    wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

    wait.until(EC.visibility_of_element_located((By.NAME, "passwd"))).send_keys(LOGIN_PASSWORD)
    wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()

    # Handle "Stay signed in?" prompt
    try:
        wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
    except TimeoutException:
        print("No 'Stay signed in' prompt appeared, continuing...")

    # Create New Case
    try:
        # Wait for the dashboard to load and the new case button to be clickable
        new_case_button = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, ".dt-buttons .dt-button.bg-purple-600")))
        new_case_button.click()

        # Fill in case details
        wait.until(EC.visibility_of_element_located((By.ID, "title"))).send_keys(case_details["title"])
        driver.find_element(By.ID, "plaintiff_name").send_keys(case_details["plaintiff_name"])
        driver.find_element(By.ID, "medical_provider").send_keys(case_details["medical_provider"])
        driver.find_element(By.ID, "description").send_keys(case_details["description"])
        wait.until(EC.element_to_be_clickable((By.ID, "new-case-submit"))).click()

        # Wait for case to be created and page to load
        print("Waiting for page to load after case creation...")
        # wait_for_page_load(driver)
        print("Page loaded")

        # Debug: Print page source to see what's available
        print("Current URL:", driver.current_url)
        print("Page title:", driver.title)

        # Take a screenshot before attempting to find the Notes tab
        driver.save_screenshot("before_notes_tab.png")
        print("Screenshot saved to before_notes_tab.png")

        # Print the page structure for debugging
        print_page_structure(driver)

        # After creating a case, we need to make sure we're on the case details page
        print("Making sure we're on the case details page")



        # Try to find all tabs
        try:
            tabs = driver.find_elements(By.XPATH, '//ul[@role="tablist"]/li/a')
            print(f"Found {len(tabs)} tabs:")
            for i, tab in enumerate(tabs):
                print(f"  Tab {i+1}: id='{tab.get_attribute('id')}', text='{tab.text}'")
        except Exception as e:
            print(f"Error finding tabs: {str(e)}")

        # Upload Clinical Notes - handle tab-notes the same way as tab-imaging
        print("Navigating to Clinical Notes tab")
        try:
            # Try to find the button with id="tab-notes"
            print("Looking for notes tab")
            notes_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-notes")))
            print("Found notes tab with CSS selector button#tab-notes")

            # Try to use JavaScript to click the element if normal click might be intercepted
            try:
                driver.execute_script("arguments[0].click();", notes_tab)
                print("Clicked notes tab using JavaScript")
            except Exception as e:
                print(f"JavaScript click failed: {str(e)}, trying normal click")
                notes_tab.click()
        except TimeoutException:
            try:
                # Try with a more specific selector based on the HTML structure
                notes_tab = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//button[@id="tab-notes" and @data-tab="notes"]')))
                print("Found notes tab with specific XPATH selector")
                driver.execute_script("arguments[0].click();", notes_tab)
            except TimeoutException:
                try:
                    # Try with a selector that looks for the text "Clinical Notes" within the button
                    notes_tab = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//button[contains(., "Clinical Notes")]')))
                    print("Found notes tab by text content")
                    driver.execute_script("arguments[0].click();", notes_tab)
                except TimeoutException:
                    try:
                        # Try with a selector that looks for any button with data-tab="notes"
                        notes_tab = wait.until(EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, 'button[data-tab="notes"]')))
                        print("Found notes tab by data-tab attribute")
                        driver.execute_script("arguments[0].click();", notes_tab)
                    except TimeoutException:
                        # As a last resort, try to find all buttons in the side panel and click the one that looks like the Notes tab
                        print("Attempting to find all buttons in the side panel")
                        side_panel_buttons = driver.find_elements(By.CSS_SELECTOR, "#side-panel button")
                        for button in side_panel_buttons:
                            try:
                                button_text = button.text.strip()
                                button_id = button.get_attribute('id')
                                button_data_tab = button.get_attribute('data-tab')
                                print(f"Found button: id='{button_id}', data-tab='{button_data_tab}', text='{button_text}'")

                                # If this looks like the Notes tab, click it
                                if "notes" in button_id.lower() or "notes" in button_data_tab.lower() or "clinical notes" in button_text.lower():
                                    print(f"Clicking button that appears to be the Notes tab: {button_id}")
                                    driver.execute_script("arguments[0].click();", button)
                                    break
                            except Exception as e:
                                print(f"Error examining button: {str(e)}")
                        else:
                            raise Exception("Could not find the Notes tab button")

        # Wait for the clinical notes panel to be visible
        print("Waiting for clinical notes panel to be visible")
        wait.until(EC.visibility_of_element_located((By.ID, "clinical-notes-panel")))

        # Find the upload button in the clinical notes panel
        try:
            # Try to find the button at the bottom of the clinical notes panel
            upload_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
            print("Found upload button with text 'Upload'")
            driver.execute_script("arguments[0].click();", upload_button)
        except TimeoutException:
            try:
                # Try with a more general selector
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "#clinical-notes-panel button")))
                print("Found upload button with general selector")
                driver.execute_script("arguments[0].click();", upload_button)
            except TimeoutException:
                print("Could not find upload button in clinical notes panel, trying alternative approach")
                # Try to directly trigger the file upload dialog
                try:
                    # Wait for the file upload popup to appear
                    wait.until(EC.visibility_of_element_located((By.ID, "file-upload-popup")))
                except TimeoutException:
                    print("File upload popup not visible, trying to open it manually")

        # Test both file and folder uploads for clinical notes
        # First, try folder upload
        print("Testing folder upload for Clinical Notes")
        print(f"Using folder path: {NOTES_FOLDER_PATH}")

        # Take a screenshot before folder upload
        driver.save_screenshot("before_notes_folder_upload.png")
        print("Screenshot saved to before_notes_folder_upload.png")

        # Make sure the upload popup is visible
        if not element_exists(driver, By.ID, "file-upload-popup"):
            print("Upload popup not visible, clicking upload button again")
            try:
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                driver.execute_script("arguments[0].click();", upload_button)
                time.sleep(2)  # Wait for popup to appear
            except Exception as e:
                print(f"Error clicking upload button: {str(e)}")

        # Now try the folder upload
        folder_upload_success = handle_upload(driver, wait, NOTES_FOLDER_PATH, "folder")

        if folder_upload_success:
            print("Successfully uploaded folder to Clinical Notes")

            # Now try file upload - click upload button again
            try:
                # Find and click the upload button again
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                print("Found upload button for file upload")
                driver.execute_script("arguments[0].click();", upload_button)
                time.sleep(2)  # Wait for popup to appear

                # Handle file upload
                print("Testing file upload for Clinical Notes")
                print(f"Using file path: {NOTES_FILE_PATH}")
                file_upload_success = handle_upload(driver, wait, NOTES_FILE_PATH, "file")

                if file_upload_success:
                    print("Successfully uploaded file to Clinical Notes")
                else:
                    print("Failed to upload file to Clinical Notes")
            except Exception as e:
                print(f"Error during file upload attempt for clinical notes: {str(e)}")
                driver.save_screenshot("clinical_notes_file_upload_error.png")
                print("Screenshot saved to clinical_notes_file_upload_error.png")
        else:
            print("Failed to upload folder to Clinical Notes, trying file upload instead")

            # Try file upload as fallback
            try:
                # Find and click the upload button again (if needed)
                if element_exists(driver, By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]'):
                    upload_button = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="clinical-notes-panel"]//button[contains(text(), "Upload")]')))
                    driver.execute_script("arguments[0].click();", upload_button)
                    time.sleep(2)  # Wait for popup to appear

                # Handle file upload
                print(f"Using file path: {NOTES_FILE_PATH}")
                file_upload_success = handle_upload(driver, wait, NOTES_FILE_PATH, "file")

                if file_upload_success:
                    print("Successfully uploaded file to Clinical Notes as fallback")
                else:
                    print("Failed to upload file to Clinical Notes as fallback")
            except Exception as e:
                print(f"Error during fallback file upload attempt for clinical notes: {str(e)}")
                driver.save_screenshot("clinical_notes_fallback_upload_error.png")
                print("Screenshot saved to clinical_notes_fallback_upload_error.png")

        # Close the side panel immediately after uploads
        print("Closing side panel immediately after uploads")
        # Try to close the panel without delay
        try:
            # First try by ID "panel-close-button" as specified in the requirements
            if element_exists(driver, By.ID, "panel-close-button", timeout=2):
                collapse_btn = driver.find_element(By.ID, "panel-close-button")
                print("Found panel close button by ID 'panel-close-button', clicking immediately")
                driver.execute_script("arguments[0].click();", collapse_btn)
            else:
                # Fall back to the regular close function
                close_side_panel(driver, wait)
        except Exception as e:
            print(f"Error in immediate panel close: {str(e)}")
            # Fall back to the regular close function
            close_side_panel(driver, wait)

        # Make sure no overlays are blocking interaction
        print("Checking for overlays before proceeding to imaging tab")
        ensure_no_overlays(driver)

        # After closing the side panel, we need to reopen it to access the tabs
        print("Reopening the case to access the tabs")
        try:
            # Find the case in the table and click it immediately
            case_row = driver.find_element(By.XPATH, f"//td[contains(text(), '{case_details['title']}')]")
            print(f"Found case row with title: {case_details['title']}")
            driver.execute_script("arguments[0].click();", case_row)
            print("Clicked on case row to reopen it")
            # Shorter wait time
            time.sleep(1)
        except Exception as e:
            print(f"Error with quick reopening of case: {str(e)}")
            # Fall back to the original approach with wait
            try:
                case_row = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, f"//td[contains(text(), '{case_details['title']}')]")))
                driver.execute_script("arguments[0].click();", case_row)
                time.sleep(2)
            except Exception as e2:
                print(f"Error reopening case with fallback method: {str(e2)}")
                driver.save_screenshot("reopen_case_error.png")
                print("Screenshot saved to reopen_case_error.png")


        # Upload DICOM Imaging - using similar approach as for Notes tab
        try:
            # Try to find the button with id="tab-imaging"
            print("Looking for imaging tab")
            imaging_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-imaging")))
            print("Found imaging tab with CSS selector button#tab-imaging")

            # Try to use JavaScript to click the element if normal click might be intercepted
            try:
                driver.execute_script("arguments[0].click();", imaging_tab)
                print("Clicked imaging tab using JavaScript")
            except Exception as e:
                print(f"JavaScript click failed: {str(e)}, trying normal click")
                imaging_tab.click()
        except TimeoutException:
            try:
                # Try with a more specific selector
                imaging_tab = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//button[@id="tab-imaging" and @data-tab="imaging"]')))
                print("Found imaging tab with specific XPATH selector")
                imaging_tab.click()
            except TimeoutException:
                try:
                    # Try with a selector that looks for the text "Imaging" within the button
                    imaging_tab = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//button[contains(., "Imaging")]' )))
                    print("Found imaging tab by text content")
                    driver.execute_script("arguments[0].click();", imaging_tab)
                except TimeoutException:
                    # As a last resort, try to find all buttons in the side panel
                    print("Attempting to find all buttons in the side panel for imaging tab")
                    side_panel_buttons = driver.find_elements(By.CSS_SELECTOR, "#side-panel button")
                    for button in side_panel_buttons:
                        try:
                            button_text = button.text.strip()
                            button_id = button.get_attribute('id')
                            button_data_tab = button.get_attribute('data-tab')

                            # If this looks like the Imaging tab, click it
                            if "imaging" in button_id.lower() or "imaging" in button_data_tab.lower() or "imaging" in button_text.lower():
                                print(f"Clicking button that appears to be the Imaging tab: {button_id}")
                                driver.execute_script("arguments[0].click();", button)
                                break
                        except Exception as e:
                            print(f"Error examining button: {str(e)}")
                    else:
                        raise Exception("Could not find the Imaging tab button")

        # Wait for the medical imaging panel to be visible
        print("Waiting for medical imaging panel to be visible")
        wait.until(EC.visibility_of_element_located((By.ID, "medical-imaging-panel")))

        # Find the upload button in the medical imaging panel
        try:
            # Try to find the button at the bottom of the medical imaging panel
            upload_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
            print("Found upload button with text 'Upload'")
            driver.execute_script("arguments[0].click();", upload_button)
        except TimeoutException:
            try:
                # Try with a more general selector
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "#medical-imaging-panel button")))
                print("Found upload button with general selector")
                driver.execute_script("arguments[0].click();", upload_button)
            except TimeoutException:
                print("Could not find upload button in medical imaging panel, trying alternative approach")

        # Test both file and folder uploads for medical imaging
        # First, try folder upload
        print("Testing folder upload for Medical Imaging")
        print(f"Using folder path: {IMAGING_FOLDER_PATH}")

        # Take a screenshot before folder upload
        driver.save_screenshot("before_imaging_folder_upload.png")
        print("Screenshot saved to before_imaging_folder_upload.png")

        # Make sure the upload popup is visible
        if not element_exists(driver, By.ID, "file-upload-popup"):
            print("Upload popup not visible, clicking upload button again")
            try:
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                driver.execute_script("arguments[0].click();", upload_button)
                time.sleep(2)  # Wait for popup to appear
            except Exception as e:
                print(f"Error clicking upload button: {str(e)}")

        # Now try the folder upload
        folder_upload_success = handle_upload(driver, wait, IMAGING_FOLDER_PATH, "folder")

        if folder_upload_success:
            print("Successfully uploaded folder to Medical Imaging")

            # Now try file upload - click upload button again
            try:
                # Find and click the upload button again
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                print("Found upload button for file upload")
                driver.execute_script("arguments[0].click();", upload_button)
                time.sleep(2)  # Wait for popup to appear

                # Handle file upload
                print("Testing file upload for Medical Imaging")
                print(f"Using file path: {IMAGING_FILE_PATH}")
                file_upload_success = handle_upload(driver, wait, IMAGING_FILE_PATH, "file")

                if file_upload_success:
                    print("Successfully uploaded imaging file to Medical Imaging")
                else:
                    print("Failed to upload imaging file to Medical Imaging")
            except Exception as e:
                print(f"Error during file upload attempt for medical imaging: {str(e)}")
                driver.save_screenshot("medical_imaging_file_upload_error.png")
                print("Screenshot saved to medical_imaging_file_upload_error.png")
        else:
            print("Failed to upload folder to Medical Imaging, trying file upload instead")

            # Try file upload as fallback
            try:
                # Find and click the upload button again (if needed)
                if element_exists(driver, By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]'):
                    upload_button = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//div[@id="medical-imaging-panel"]//button[contains(text(), "Upload")]')))
                    driver.execute_script("arguments[0].click();", upload_button)
                    time.sleep(2)  # Wait for popup to appear

                # Handle file upload
                print(f"Using file path: {IMAGING_FILE_PATH}")
                file_upload_success = handle_upload(driver, wait, IMAGING_FILE_PATH, "file")

                if file_upload_success:
                    print("Successfully uploaded imaging file to Medical Imaging as fallback")
                else:
                    print("Failed to upload imaging file to Medical Imaging as fallback")
            except Exception as e:
                print(f"Error during fallback file upload attempt for medical imaging: {str(e)}")
                driver.save_screenshot("medical_imaging_fallback_upload_error.png")
                print("Screenshot saved to medical_imaging_fallback_upload_error.png")

        # Close the side panel immediately after uploads
        print("Closing side panel immediately after uploads")
        # Try to close the panel without delay
        try:
            # First try by ID "panel-close-button" as specified in the requirements
            if element_exists(driver, By.ID, "panel-close-button", timeout=2):
                collapse_btn = driver.find_element(By.ID, "panel-close-button")
                print("Found panel close button by ID 'panel-close-button', clicking immediately")
                driver.execute_script("arguments[0].click();", collapse_btn)
            else:
                # Fall back to the regular close function
                close_side_panel(driver, wait)
        except Exception as e:
            print(f"Error in immediate panel close: {str(e)}")
            # Fall back to the regular close function
            close_side_panel(driver, wait)

        # Make sure no overlays are blocking interaction
        print("Checking for overlays before proceeding to chronology tab")
        ensure_no_overlays(driver)

        # After closing the side panel, we need to reopen it to access the tabs
        print("Reopening the case to access the tabs")
      

        # Medical Chronology Automation - using a more direct approach to find the tab faster
        print("Looking for chronology tab with optimized approach")

        # Take a screenshot before looking for chronology tab
        driver.save_screenshot("before_finding_chronology_tab.png")
        print("Screenshot saved to before_finding_chronology_tab.png")

        # Try multiple selectors in parallel rather than sequentially to save time
        chrono_tab_found = False

        # First, try direct ID lookup which is fastest
        if element_exists(driver, By.ID, "tab-chrono", timeout=2):
            print("Found chronology tab by direct ID lookup")
            chrono_tab = driver.find_element(By.ID, "tab-chrono")
            chrono_tab_found = True
        # Then try CSS selector
        elif element_exists(driver, By.CSS_SELECTOR, "button#tab-chrono", timeout=2):
            print("Found chronology tab with CSS selector")
            chrono_tab = driver.find_element(By.CSS_SELECTOR, "button#tab-chrono")
            chrono_tab_found = True
        # Try data attribute
        elif element_exists(driver, By.CSS_SELECTOR, 'button[data-tab="chrono"]', timeout=2):
            print("Found chronology tab by data-tab attribute")
            chrono_tab = driver.find_element(By.CSS_SELECTOR, 'button[data-tab="chrono"]')
            chrono_tab_found = True
        # Try text content
        elif element_exists(driver, By.XPATH, '//button[contains(., "Medical Chronology")]', timeout=2):
            print("Found chronology tab by text content")
            chrono_tab = driver.find_element(By.XPATH, '//button[contains(., "Medical Chronology")]')
            chrono_tab_found = True

        # If found by any method, click it
        if chrono_tab_found:
            try:
                print("Clicking chronology tab using JavaScript for reliability")
                driver.execute_script("arguments[0].click();", chrono_tab)
            except Exception as e:
                print(f"JavaScript click failed: {str(e)}, trying normal click")
                chrono_tab.click()
        else:
            # Fall back to the original approach if all quick methods fail
            try:
                # Try with the standard wait approach
                print("Using standard wait approach to find chronology tab")
                chrono_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tab-chrono")))
                print("Found chronology tab with CSS selector button#tab-chrono")
                driver.execute_script("arguments[0].click();", chrono_tab)
            except TimeoutException:
                # As a last resort, try to find all buttons in the side panel
                print("Attempting to find all buttons in the side panel for chronology tab")
                side_panel_buttons = driver.find_elements(By.CSS_SELECTOR, "#side-panel button")
                for button in side_panel_buttons:
                    try:
                        button_text = button.text.strip()
                        button_id = button.get_attribute('id')
                        button_data_tab = button.get_attribute('data-tab')

                        # If this looks like the Chronology tab, click it
                        if "chrono" in button_id.lower() or "chrono" in button_data_tab.lower() or "chronology" in button_text.lower():
                            print(f"Clicking button that appears to be the Chronology tab: {button_id}")
                            driver.execute_script("arguments[0].click();", button)
                            break
                    except Exception as e:
                        print(f"Error examining button: {str(e)}")
                else:
                    raise Exception("Could not find the Chronology tab button")

        # Wait for the medical chronology panel to be visible
        print("Waiting for medical chronology panel to be visible")
        wait.until(EC.visibility_of_element_located((By.ID, "medical-chronology-panel")))

        # Find the chronology button in the medical chronology panel
        try:
            # First, check if we need to upload documents before creating chronology
            # Look for an upload button in the chronology panel
            try:
                upload_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Upload")]')))
                print("Found upload button in chronology panel, will upload documents first")
                driver.execute_script("arguments[0].click();", upload_button)

                # Handle file upload using our helper function
                print("Uploading chronology documents")
                print(f"Using file path: {NOTES_FILE_PATH}")
                upload_success = handle_upload(driver, wait, NOTES_FILE_PATH, "file")

                if upload_success:
                    print("Successfully uploaded documents for chronology")

                    # Try folder upload for chronology
                    try:
                        print("Attempting to upload folder to Medical Chronology")
                        print(f"Using folder path: {NOTES_FOLDER_PATH}")

                        # Click upload button again
                        upload_button = wait.until(EC.element_to_be_clickable(
                            (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Upload")]')))
                        driver.execute_script("arguments[0].click();", upload_button)
                        time.sleep(2)  # Wait for popup to appear

                        # Handle folder upload using NOTES_FOLDER_PATH
                        folder_upload_success = handle_upload(driver, wait, NOTES_FOLDER_PATH, "folder")
                        if folder_upload_success:
                            print("Successfully uploaded folder to Medical Chronology")
                        else:
                            print("Failed to upload folder to Medical Chronology")
                    except Exception as e:
                        print(f"Error during folder upload attempt for chronology: {str(e)}")
                else:
                    print("Failed to upload documents for chronology")
            except TimeoutException:
                print("No upload button found in chronology panel, proceeding to create chronology")

            # Now look for the chronology creation button
            chrono_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[@id="medical-chronology-panel"]//button[contains(text(), "Chronology")]')))
            print("Found chronology button")
            driver.execute_script("arguments[0].click();", chrono_button)
        except TimeoutException:
            try:
                # Try with a more general selector
                chrono_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//div[@id="medical-chronology-panel"]//button')))
                print("Found chronology button with general selector")
                driver.execute_script("arguments[0].click();", chrono_button)
            except TimeoutException:
                print("Could not find chronology button in medical chronology panel")
                driver.save_screenshot("chrono_button_error.png")
                print("Screenshot saved to chrono_button_error.png")
                raise

        # Wait for the select all checkbox to be visible and click it medical chronology panel to be visible
        try:
            print("Waiting for select all checkbox")
            select_all = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="select-all-checkbox"]')))
            print("Found select all checkbox")
            driver.execute_script("arguments[0].click();", select_all)

            # Wait for selection to process
            print("Waiting for selection to process")
            time.sleep(6)

            # Click the create button
            print("Looking for create button")
            create_button = wait.until(EC.element_to_be_clickable((By.ID, "createBtn")))
            print("Found create button")
            driver.execute_script("arguments[0].click();", create_button)

            # Enter confirmation text
            print("Entering confirmation text")
            confirm_input = wait.until(EC.visibility_of_element_located((By.ID, "confirmInput")))
            confirm_input.send_keys("confirm")

            # Click the confirm button
            print("Clicking confirm button")
            confirm_button = wait.until(EC.element_to_be_clickable((By.ID, "confirmCreateBtn")))
            driver.execute_script("arguments[0].click();", confirm_button)

            # Wait for chronology creation to complete
            print("Waiting for chronology creation to complete")
            time.sleep(60)

            # Close the side panel immediately after successful chronology creation
            print("Closing side panel immediately after chronology creation")
            # Try to close the panel without delay
            try:
                # First try by ID "panel-close-button" as specified in the requirements
                if element_exists(driver, By.ID, "panel-close-button", timeout=2):
                    collapse_btn = driver.find_element(By.ID, "panel-close-button")
                    print("Found panel close button by ID 'panel-close-button', clicking immediately")
                    driver.execute_script("arguments[0].click();", collapse_btn)
                else:
                    # Fall back to the regular close function
                    close_side_panel(driver, wait)
            except Exception as e:
                print(f"Error in immediate panel close: {str(e)}")
                # Fall back to the regular close function
                close_side_panel(driver, wait)

        except Exception as e:
            print(f"Error during chronology creation: {str(e)}")
            driver.save_screenshot("chronology_creation_error.png")
            print("Screenshot saved to chronology_creation_error.png")

    except Exception as e:
        print(f"Error during automation: {str(e)}")
        # Take a screenshot for debugging
        screenshot_path = "error_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        raise

# Main Execution
def main():
    driver = init_driver(headless=False)  # Set to False for debugging
    client = get_openai_client()

    try:
        case_details = generate_case_details(client)
        print("Generated Case Details:", case_details)

        automate_case_workflow(driver, case_details)

        print("Automation workflow completed successfully.")
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        # Take a screenshot for debugging
        try:
            screenshot_path = "main_error_screenshot.png"
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
        except:
            print("Could not save screenshot")
    finally:
        # Always quit the driver to clean up resources
        try:
            driver.quit()
            print("Driver quit successfully")
        except:
            print("Error quitting driver")

if __name__ == "__main__":
    main()