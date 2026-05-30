from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from typing import Optional, Literal
from datetime import datetime

# Import Enum từ Model DB của huynh
from models.calendar import EventSource

class CalendarEventBase(BaseModel):
    summary: str = Field(..., min_length=1, max_length=255, description="Tiêu đề sự kiện")
    description: Optional[str] = Field(None, max_length=2000, description="Mô tả chi tiết")
    location: Optional[str] = Field(None, max_length=255, description="Địa điểm")
    
    # Bắt buộc chuỗi thời gian gửi lên phải có Timezone
    start_time: AwareDatetime
    end_time: AwareDatetime
    
    is_recurring: bool = False
    rrule: Optional[str] = Field(None, max_length=255, description="Luật lặp lại iCal (VD: FREQ=WEEKLY)")
    is_cancelled: bool = False

    @model_validator(mode='after')
    def validate_time_range(self) -> 'CalendarEventBase':
        """Hook kiểm tra logic: Thời gian kết thúc phải lớn hơn thời gian bắt đầu"""
        if self.start_time >= self.end_time:
            raise ValueError('end_time bắt buộc phải diễn ra sau start_time')
        return self
    
class CalendarEventCreate(CalendarEventBase):
    source: EventSource = EventSource.VOICE_AI
    
class CalendarEventUpdate(CalendarEventBase):
    """Bản Update cho phép gửi các trường tùy ý (PATCH method)"""
    summary: Optional[str] = Field(None, min_length=1, max_length=255)
    start_time: Optional[AwareDatetime] = None 
    end_time: Optional[AwareDatetime] = None
    is_cancelled: Optional[bool] = None

class CalendarEventResponse(CalendarEventBase):
    """Schema đẩy dữ liệu đầy đủ lên Web Dashboard"""
    id: str
    source: EventSource
    tz_info: str
    created_at: AwareDatetime
    updated_at: AwareDatetime

    # Cho phép Pydantic đọc thẳng từ Object SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


class EventLiteESP32(BaseModel):
    """Schema vắt kiệt dữ liệu (Minified) dành riêng cho cấu trúc RAM của MCU"""
    id: str
    t: int = Field(..., description="UNIX Timestamp nguyên thủy (Epoch Time)")
    
    # Giới hạn chặt chẽ mã Action để code C++ parse switch-case không bị lỗi typo
    a: Literal["CLASS", "MEET", "VOICE", "ALARM"] 
    
    msg: str = Field(..., max_length=32, description="Tóm tắt siêu ngắn để hiển thị OLED/LCD")

    @model_validator(mode='after')
    def validate_future_timestamp(self) -> 'EventLiteESP32':
        """Đảm bảo không gửi lịch trong quá khứ xuống làm vi điều khiển bị nhiễu loạn"""
        # Cho phép trễ tối đa 15 phút (900 giây) để bù trừ độ trễ mạng
        current_unix = int(datetime.now().timestamp())
        if self.t < (current_unix - 900):
            raise ValueError(f'Timestamp {self.t} đã là quá khứ. Không hợp lệ cho MCU.')
        return self