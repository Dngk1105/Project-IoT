from pydantic import BaseModel, Field
from typing import Literal, Optional
import time, uuid

class AudioRequestESP32(BaseModel):
    """Esp xin am thanh"""
    action: Literal["request_tts"]
    event_id: str = Field(..., description="ID sự kiện cần đọc")
    session_id: str = Field(..., description="ID phiên làm việc để track luồng")

class AudioControlServer(BaseModel):
    """Nội dung bên trong 'data'"""
    action: Literal["start", "stop", "error", "idle"]
    session_id: str
    chunk_count: Optional[int] = Field(None, description="Tổng số chunk sẽ gửi")
    sample_rate: Optional[int] = Field(16000, description="Tần số lấy mẫu")
    keep_listening: Optional[bool] = Field(False, description="Co tu dong mo lai mic hay khong")
