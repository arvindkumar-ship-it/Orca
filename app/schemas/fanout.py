from pydantic import BaseModel


class StartFanoutRequest(BaseModel):
    incident_id: str
    share_with: list[str] | None = None
    share_live_location: bool = True
    share_route: bool = True


class StopFanoutRequest(BaseModel):
    share_session_id: str
