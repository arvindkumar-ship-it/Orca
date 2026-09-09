import uuid
from typing import List
from pydantic import BaseModel


class ShareStartRequest(BaseModel):
    incident_id: uuid.UUID
    share_with: List[uuid.UUID]
    share_live_location: bool = True
    share_route: bool = True


class SharedTarget(BaseModel):
    contact_id: uuid.UUID
    status: str


class ShareStartResponse(BaseModel):
    share_session_id: uuid.UUID
    status: str
    shared_with: List[SharedTarget]


class ShareStopRequest(BaseModel):
    share_session_id: uuid.UUID


class ShareStopResponse(BaseModel):
    share_session_id: uuid.UUID
    status: str


class ShareSessionResponse(BaseModel):
    share_session_id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    share_live_location: bool
    share_route: bool
    shared_with: List[SharedTarget]
