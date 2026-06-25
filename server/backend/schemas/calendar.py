from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator, field_validator
from typing import Optional, Literal
from datetime import datetime, timezone

# Import Enum từ Model DB của huynh
from models.calendar import EventSource

class CalendarEventBase(BaseModel):
    summary: str = Field(..., min_length=1, max_length=255, description="Tiêu đề sự kiện")
    description: Optional[str] = Field(None, max_length=2000, description="Mô tả chi tiết")
    location: Optional[str] = Field(None, max_length=255, description="Địa điểm")
    
    # Bắt buộc chuỗi thời gian gửi lên phải có Timezone
    start_time: AwareDatetime
    end_time: Optional[AwareDatetime] = None
    
    is_recurring: bool = False
    rrule: Optional[str] = Field(None, max_length=255, description="Luật lặp lại iCal (VD: FREQ=WEEKLY)")
    is_cancelled: bool = False

    @model_validator(mode='after')
    def validate_time_range(self) -> 'CalendarEventBase':
        if self.start_time is not None:
            if self.end_time is None:
                from datetime import timedelta
                self.end_time = self.start_time + timedelta(minutes=15)
            else:
                if self.start_time >= self.end_time:
                    raise ValueError('end_time bắt buộc phải diễn ra sau start_time')
        return self
    
    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def ensure_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
class CalendarEventCreate(CalendarEventBase):
    source: EventSource = EventSource.VOICE_AI
    
class CalendarEventUpdate(CalendarEventBase):
    """Update event khong can cap nhat toan bo bang"""
    summary: Optional[str] = Field(None, min_length=1, max_length=255)
    start_time: Optional[AwareDatetime] = None 
    end_time: Optional[AwareDatetime] = None
    is_cancelled: Optional[bool] = None

class CalendarEventResponse(CalendarEventBase):
    """Schema schema gui du lieu len web"""
    id: str
    source: EventSource
    tz_info: str
    created_at: AwareDatetime
    updated_at: AwareDatetime

    # Cho phép Pydantic đọc thẳng từ Object SQLAlchemy
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_response_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class EventLiteESP32(BaseModel):
    """Scheme gui du lieu cho esp"""
    id: str
    t: int = Field(..., description="UNIX Timestamp")
    
    a: Literal["CLASS", "MEET", "VOICE", "ALARM", "DEVICE_CMD"] 
    
    msg: str = Field(..., max_length=64, description="sieu ngan")

    @model_validator(mode='after')
    def validate_future_timestamp(self) -> 'EventLiteESP32':
        """Đảm bảo không gửi lịch trong quá khứ xuống làm vi điều khiển bị nhiễu loạn"""
        # Cho phép trễ tối đa 15 phút (900 giây) để bù trừ độ trễ mạng
        current_unix = int(datetime.now(timezone.utc).timestamp())
        if self.t < (current_unix - 900):
            raise ValueError(f'Timestamp {self.t} đã là quá khứ. Không hợp lệ cho MCU.')
        return self