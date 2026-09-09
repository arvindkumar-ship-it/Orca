from pydantic import BaseModel


class DispatchAuthorityRequest(BaseModel):
    incident_report_id: str
