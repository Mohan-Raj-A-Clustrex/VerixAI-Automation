# Sample Data for VerixAI Automation

This directory contains sample data files for VerixAI automation testing. These files are used as default test files when specific paths are not provided in the test request.

## Directory Structure

- `sample_data/sample_notes.pdf` - Sample clinical notes file
- `sample_data/sample_image.dcm` - Sample medical imaging file
- `sample_data/notes_folder/` - Directory for sample clinical notes files
- `sample_data/imaging_folder/` - Directory for sample medical imaging files

## Usage in Different Environments

### Local Testing (Windows)

When running tests locally on Windows, you can:

1. Use the default paths in your user's Downloads folder:
   ```
   {
     "case_details": {
       "title": "Sample Test Case",
       "plaintiff_name": "John Doe",
       "medical_provider": "Test Hospital",
       "description": "This is a sample test case for VerixAI automation"
     },
     "env": "dev"
   }
   ```

2. Specify custom paths for your local files:
   ```
   {
     "case_details": {
       "title": "Sample Test Case",
       "plaintiff_name": "John Doe",
       "medical_provider": "Test Hospital",
       "description": "This is a sample test case for VerixAI automation"
     },
     "notes_file_path": "C:\\path\\to\\your\\notes.pdf",
     "notes_folder_path": "C:\\path\\to\\your\\notes_folder",
     "imaging_file_path": "C:\\path\\to\\your\\image.dcm",
     "imaging_folder_path": "C:\\path\\to\\your\\imaging_folder",
     "env": "dev"
   }
   ```

### GitHub Actions (Linux)

When running tests through GitHub Actions, the system will:

1. Use the default paths in the `sample_data` directory:
   ```
   {
     "case_details": {
       "title": "GitHub Actions Test Case",
       "plaintiff_name": "GitHub User",
       "medical_provider": "GitHub Hospital",
       "description": "This is a test case triggered from GitHub Actions"
     },
     "env": "dev"
   }
   ```

## Adding Your Own Sample Files

To add your own sample files:

1. Place clinical notes files (PDF, DOC, etc.) in the `notes_folder` directory
2. Place medical imaging files (DICOM, etc.) in the `imaging_folder` directory
3. Update the sample notes file at `sample_notes.pdf`
4. Update the sample imaging file at `sample_image.dcm`

## Environment Variables

You can also configure default file paths using environment variables:

- `DEFAULT_NOTES_FILE_PATH`
- `DEFAULT_NOTES_FOLDER_PATH`
- `DEFAULT_IMAGING_FILE_PATH`
- `DEFAULT_IMAGING_FOLDER_PATH`

These can be set in your `.env` file or in your GitHub Actions secrets.
