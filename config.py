import os
import platform
from dotenv import load_dotenv

# Load environment variables from .env file
try:
    load_dotenv()
    print("Loaded environment variables from .env file")
except Exception as e:
    print(f"Warning: Could not load .env file: {str(e)}")

# Detect environment
APP_ENV = os.getenv("APP_ENV", "dev").lower()

class BaseConfig:
    # Common to all environments
    AZURE_API_VERSION = os.getenv('AZURE_API_VERSION', '2024-08-01-preview')
    MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o')

    # Default file paths
    system = platform.system()
    if system == 'Windows':
        DEFAULT_NOTES_FILE_PATH = os.getenv('DEFAULT_NOTES_FILE_PATH',
            os.path.join(os.path.expanduser('~'), 'Downloads', 'sample_notes.pdf'))
        DEFAULT_NOTES_FOLDER_PATH = os.getenv('DEFAULT_NOTES_FOLDER_PATH',
            os.path.join(os.path.expanduser('~'), 'Downloads', 'notes_folder'))
        DEFAULT_IMAGING_FILE_PATH = os.getenv('DEFAULT_IMAGING_FILE_PATH',
            os.path.join(os.path.expanduser('~'), 'Downloads', 'sample_image.dcm'))
        DEFAULT_IMAGING_FOLDER_PATH = os.getenv('DEFAULT_IMAGING_FOLDER_PATH',
            os.path.join(os.path.expanduser('~'), 'Downloads', 'imaging_folder'))
    else:
        DEFAULT_NOTES_FILE_PATH = os.getenv('DEFAULT_NOTES_FILE_PATH', './sample_data/sample_notes.pdf')
        DEFAULT_NOTES_FOLDER_PATH = os.getenv('DEFAULT_NOTES_FOLDER_PATH', './sample_data/notes_folder')
        DEFAULT_IMAGING_FILE_PATH = os.getenv('DEFAULT_IMAGING_FILE_PATH', './sample_data/sample_image.dcm')
        DEFAULT_IMAGING_FOLDER_PATH = os.getenv('DEFAULT_IMAGING_FOLDER_PATH', './sample_data/imaging_folder')

    # Selenium Configuration
    SCREENSHOTS_DIR = os.getenv('SCREENSHOTS_DIR', 'screenshots')
    SAVE_SCREENSHOTS_TO_DISK = os.getenv('SAVE_SCREENSHOTS_TO_DISK', 'False').lower() == 'true'


class DevConfig(BaseConfig):
    AZURE_API_KEY = os.getenv('DEV_AZURE_API_KEY')
    AZURE_ENDPOINT = os.getenv('DEV_AZURE_ENDPOINT')
    LOGIN_EMAIL = os.getenv('DEV_LOGIN_EMAIL')
    LOGIN_PASSWORD = os.getenv('DEV_LOGIN_PASSWORD')
    BASE_URL = os.getenv('DEV_BASE_URL')
    SMTP_SERVER = os.getenv('DEV_SMTP_SERVER')
    SMTP_PORT = int(os.getenv('DEV_SMTP_PORT', 587))
    EMAIL_USERNAME = os.getenv('DEV_EMAIL_USERNAME')
    EMAIL_PASSWORD = os.getenv('DEV_EMAIL_PASSWORD')
    EMAIL_RECIPIENTS = os.getenv('DEV_EMAIL_RECIPIENTS', '').split(',')


class StagingConfig(BaseConfig):
    AZURE_API_KEY = os.getenv('STAGING_AZURE_API_KEY')
    AZURE_ENDPOINT = os.getenv('STAGING_AZURE_ENDPOINT')
    LOGIN_EMAIL = os.getenv('STAGING_LOGIN_EMAIL')
    LOGIN_PASSWORD = os.getenv('STAGING_LOGIN_PASSWORD')
    BASE_URL = os.getenv('STAGING_BASE_URL')
    SMTP_SERVER = os.getenv('STAGING_SMTP_SERVER')
    SMTP_PORT = int(os.getenv('STAGING_SMTP_PORT', 587))
    EMAIL_USERNAME = os.getenv('STAGING_EMAIL_USERNAME')
    EMAIL_PASSWORD = os.getenv('STAGING_EMAIL_PASSWORD')
    EMAIL_RECIPIENTS = os.getenv('STAGING_EMAIL_RECIPIENTS', '').split(',')


class ProdConfig(BaseConfig):
    AZURE_API_KEY = os.getenv('PROD_AZURE_API_KEY')
    AZURE_ENDPOINT = os.getenv('PROD_AZURE_ENDPOINT')
    LOGIN_EMAIL = os.getenv('PROD_LOGIN_EMAIL')
    LOGIN_PASSWORD = os.getenv('PROD_LOGIN_PASSWORD')
    BASE_URL = os.getenv('PROD_BASE_URL')
    SMTP_SERVER = os.getenv('PROD_SMTP_SERVER')
    SMTP_PORT = int(os.getenv('PROD_SMTP_PORT', 587))
    EMAIL_USERNAME = os.getenv('PROD_EMAIL_USERNAME')
    EMAIL_PASSWORD = os.getenv('PROD_EMAIL_PASSWORD')
    EMAIL_RECIPIENTS = os.getenv('PROD_EMAIL_RECIPIENTS', '').split(',')


# Select config class based on APP_ENV
config_by_env = {
    'dev': DevConfig,
    'staging': StagingConfig,
    'prod': ProdConfig
}

Config = config_by_env.get(APP_ENV, DevConfig)  # Fallback to DevConfig


# Optional: Helper method to validate and print config
def validate_and_print_config():
    required = ['AZURE_API_KEY', 'AZURE_ENDPOINT', 'LOGIN_EMAIL', 'LOGIN_PASSWORD', 'BASE_URL']
    missing = [field for field in required if not getattr(Config, field)]

    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    print("\n=== Loaded Config ===")
    for attr in dir(Config):
        if not attr.startswith('__') and not callable(getattr(Config, attr)):
            val = getattr(Config, attr)
            if 'PASSWORD' in attr:
                val = '********'
            print(f"{attr}: {val}")
    print("======================\n")
