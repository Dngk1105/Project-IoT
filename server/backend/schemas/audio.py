from pydantic import BaseModel, Field
from typing import Literal, Optional

class AudioRequestESP32(BaseModel):
    """Bản tin ESP32 gửi lên để xin file âm thanh cho một sự kiện"""
    action: Literal["request_tts"]
    event_id: str = Field(..., description="ID sự kiện cần đọc")
    session_id: str = Field(..., description="ID phiên làm việc để track luồng")

class AudioControlServer(BaseModel):
    """Bản tin Server gửi xuống để điều khiển bộ đệm I2S trên ESP32"""
    action: Literal["start", "stop", "error"]
    session_id: str
    chunk_count: Optional[int] = Field(None, description="Tổng số mảnh binary sẽ gửi (để ESP32 canh)")
    sample_rate: Optional[int] = Field(16000, description="Tần số lấy mẫu (Thường dùng 16kHz Mono)")