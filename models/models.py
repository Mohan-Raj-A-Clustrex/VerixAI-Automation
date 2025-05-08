from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional, List

class CaseDetails(BaseModel):
    title: str
    plaintiff_name: str
    medical_provider: str
    description: str

class WebhookConfig(BaseModel):
    url: HttpUrl
    events: List[str] = ["test_started", "test_completed", "test_error"]
    headers: Optional[Dict[str, str]] = None

class TestRequest(BaseModel):
    case_details: Optional[CaseDetails] = None
    notes_file_path: Optional[str] = None
    notes_folder_path: Optional[str] = None
    imaging_file_path: Optional[str] = None
    imaging_folder_path: Optional[str] = None
    webhook: Optional[WebhookConfig] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

class TestResponse(BaseModel):
    status: str
    message: str
    test_id: str

class TestStatusResponse(BaseModel):
    status: str
    test_id: str
    test_status: str
    start_time: str
    result: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None
