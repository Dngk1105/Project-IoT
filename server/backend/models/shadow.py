from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from .base import Base

class DeviceEventShadow(Base):
    """Luu trang thai cac su kien cua esp"""
    __tablename__ = "device_event_shadow"
    
    #Neu Device bi xoa trong bang devices
    #Record co devices.id se deu bi xoa
    device_id: Mapped[str] = mapped_column(String(50), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True) 
    event_id: Mapped[str] = mapped_column(String, ForeignKey("calendar_events.id"), primary_key=True)
    
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    def __repr__(self) -> str:
        return f"<Shadow Node: {self.device_id} | Event: {self.event_id}>"