from sqlalchemy import String, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import Base

class Device(Base):
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="New mcu")
    status: Mapped[str] = mapped_column(String(20), default="offline")
    last_offline_reason: Mapped[str] = mapped_column(String(100), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    telemetries = relationship("Telemetry", back_populates="device", cascade="all, delete-orphan")  #tu dong xoa neu bang devices mat

    def __repr__(self) -> str:
        return f"<Device {self.id} | Status: {self.status}>"    