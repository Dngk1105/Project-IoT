from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

from models.calendar import EventSource

class CalendarEventBase(BaseModel):
    summary: str = Field(..., description="Tiêu đề sự kiện")
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_recurring: bool = False
    rrule: Optional[str] = Field(None, description="Luật lặp lại (ví dụ: FREQ=WEEKLY)")
    
class CalendarEventCreate(CalendarEventBase):
    source: EventSource = EventSource.VOICE_AI
    
class CalendarEventUpdate(CalendarEventBase):
    """Update khong nhat thiet phai gui het du lieu"""
    summary: Optional[str] = None
    start_time: Optional[datetime] = None 
    end_time: Optional[datetime] = None

class CalendarEventResponse(CalendarEventBase):
    id: str
    source: EventSource
    tz_info: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EventLiteESP32(BaseModel):
    id: str
    t: int      # UNIX Timestamp
    a: str      # action
    msg: str    # tieu de