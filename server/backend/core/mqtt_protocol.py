import time
import uuid
from typing import Dict, Any
import json

PROJECT_PREFIX = "iot_schedule"

class MqttTopics:
    """Lớp sinh Topic tự động định dạng: prefix/<device_id>/<category>/<action>"""
    
    @staticmethod
    def command(device_id: str, action: str) -> str:
        """Gửi lệnh bắt buộc xuống ESP32 (VD: time_sync, sync_schedule, reboot)"""
        return f"{PROJECT_PREFIX}/{device_id}/commands/{action}"

    @staticmethod
    def audio_down(device_id: str) -> str:
        """Gửi luồng âm thanh nhị phân xuống loa"""
        return f"{PROJECT_PREFIX}/{device_id}/audio/stream_down"
    
    @staticmethod 
    def audio_control(device_id: str) -> str:
        """Gui lenh xu li ve am thanh (start/stop/error)"""
        return f"{PROJECT_PREFIX}/{device_id}/audio/control"
    @staticmethod
    def shadow_desired(device_id: str) -> str:
        """Gửi cấu hình ngoại vi xuống ESP32 (VD: vol_max, led_color)"""
        return f"{PROJECT_PREFIX}/{device_id}/shadow/desired"
        
    @staticmethod
    def telemetry_pong(device_id: str) -> str:
        """Trả lời nhịp tim (Pong) cho ESP32"""
        return f"{PROJECT_PREFIX}/{device_id}/telemetry/pong"
    
    @staticmethod
    def calendar_sync_frontend() -> str:
        """Dong bo lich voi WebDashboard"""
        return f"{PROJECT_PREFIX}/frontend/calendar/sync"
    
    @staticmethod
    def ack(device_id: str, action: str) -> str:
        """ack co action can doi de phan hoi"""
        return f"{PROJECT_PREFIX}/{device_id}/ack/{action}"
        


class PayloadBuilder:
    """Lớp đóng gói dữ liệu"""
    
    @staticmethod
    def build_json(data: Dict[str, Any], version: str = "1.0") -> dict:
        """
        Gói dữ liệu vào Envelope có msg_id tự động sinh và timestamp.
        """
        return {
            "msg_id": f"msg_{uuid.uuid4().hex[:12]}",  
            "timestamp": int(time.time()),             
            "v": version,
            "data": data                               
        }

    @staticmethod
    def build_delta_sync(msg_id: str, data: Dict[str, Any], version: str = "1.0") -> dict:
        """
        Tạo payload chuyên dụng cho gói Delta Sync (đồng bộ lịch).
        Trả về kiểu 'dict' để hàm publish_message tự động dumps ra chuỗi.
        """
        return {
            "msg_id": msg_id,
            "timestamp": int(time.time()),
            "v": version,
            "data": data  
        }