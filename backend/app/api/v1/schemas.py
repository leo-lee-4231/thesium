from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StreamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    timezone: str
    monitor_interval_minutes: int
    agent_enabled: bool
    created_at: datetime


class MetaOut(BaseModel):
    name: str
    version: str
    environment: str
    phase: str
    capabilities: list[str]