from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import json

from .base import Base

class DeviceEventShadow(Base):
    """Luu trang thai cac su kien cua esp"""    
    #Neu Device bi xoa trong bang devices
    #Record co devices.id se deu bi xoa
    device_id: Mapped[str] = mapped_column(String(50), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True) 
    event_id: Mapped[str] = mapped_column(String, ForeignKey("calendar_events.id"), primary_key=True)
    
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    def __repr__(self) -> str:
        return f"<Shadow Node: {self.device_id} | Event: {self.event_id}>"
    
class EndpointStateShadow(Base):
    """Luu trang thai cac thiet bi ngoai vi (den, quat) cua mcu"""
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(50), ForeignKey("devices.id", ondelete="CASCADE"))
    ep_id: Mapped[str] = mapped_column(String(50)) #id cua cam bien
    name: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50))
    supported_cmds: Mapped[str] = mapped_column(String(200), default="[]") #Luu JSON
    reported_state: Mapped[str] = mapped_column(String(20)) #Trang thai cua thiet bi
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    