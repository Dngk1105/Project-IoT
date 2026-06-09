from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum, Text, func
from sqlalchemy.orm import Mapped, mapped_column
import enum
import uuid
from datetime import datetime
from typing import Optional

from .base import Base

class EventSource(str, enum.Enum):
    """Gioi han du lieu dau vao cho cot Source trong db"""
    GOOGLE = "google"
    HUST_CTT = "hust_ctt"
    VOICE_AI = "voice_ai"
    LOCAL = "local"
    DEVICE_TIMER = "device_timer"
    
class CalendarEvent(Base):
    """Bang luu tru cho su kien lich (calendar_events)"""
    #id va nguon
    #uuidv4: Tao chuoi id ngau nhien, khong trung lap
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[EventSource] = mapped_column(SQLEnum(EventSource))
    
    #Thong tin co ban
    summary: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(255))
        
    #Thoi gian 
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tz_info: Mapped[str] = mapped_column(String(50), default="Asia/Ho_Chi_Minh")     
    
    #Lap lai
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    rrule: Mapped[Optional[str]] = mapped_column(String(255))
    
    #Lich nguoi dung xoa (van luu trong DB)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    #func.now() lay thoi gian hien tai
    #onupdate() cap nhat thoi gian neu ban ghi bi chinh sua
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<CalendarEvent {self.summary} | {self.start_time}>"