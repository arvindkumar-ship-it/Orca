from pydantic import BaseModel


class RequiredCapabilities(BaseModel):
    trauma: bool
    icu: bool
    pediatric: bool
    oxygen: bool
    coastal_access: bool


class DispatchHospitalRequest(BaseModel):
    incident_report_id: str
