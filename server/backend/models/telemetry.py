from sqlalchemy import Integer, Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .device import Device

from .base import Base

class Telemetry(Base):
    __tablename__ = "telemetries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    device_id: Mapped[str] = mapped_column(String(50), ForeignKey("devices.id", ondelete="CASCADE"))
    
    
    free_heap: Mapped[int] = mapped_column(Integer, nullable=True)
    wifi_rssi: Mapped[int] = mapped_column(Integer, nullable=True)
    battery_voltage: Mapped[float] = mapped_column(Float, nullable=True)
    battery_percent: Mapped[int] = mapped_column(Integer, nullable=True)
    
    uptime_sec: Mapped[int] = mapped_column(Integer, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    device: Mapped["Device"] = relationship("Device", back_populates="telemetries")

    def __repr__(self) -> str:
        return f"<Telemetry {self.device_id} | RAM: {self.free_heap} | Bat: {self.battery_voltage}V>"