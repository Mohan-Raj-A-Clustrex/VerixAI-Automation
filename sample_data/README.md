# Sample Data for VerixAI Automation

This directory contains sample data files for VerixAI automation testing. These files are now used directly by the automation system without requiring file paths in the test request.

## Directory Structure

- `sample_data/notes.pdf` - Sample clinical notes file
- `sample_data/imaging.dcm` - Sample medical imaging file
- `sample_data/notes_folder/` - Directory for sample clinical notes files
- `sample_data/imaging_folder/` - Directory for sample medical imaging files

## Usage in All Environments

The automation system now uses these files directly, regardless of the environment. You only need to provide the case details in your test request:

```json
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

This simplified approach works the same way in both local testing and when running through GitHub Actions.

## Adding Your Own Sample Files

To add your own sample files:

1. Place clinical notes files (PDF, DOC, etc.) in the `notes_folder` directory
2. Place medical imaging files (DICOM, etc.) in the `imaging_folder` directory
3. Replace the sample notes file at `notes.pdf`
4. Replace the sample imaging file at `imaging.dcm`

Make sure to maintain the exact filenames (`notes.pdf` and `imaging.dcm`) as the automation system now looks for these specific files.
