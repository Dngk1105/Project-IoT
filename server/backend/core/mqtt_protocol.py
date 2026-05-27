import time
import uuid
from typing import Dict, Any

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
    def shadow_desired(device_id: str) -> str:
        """Gửi cấu hình ngoại vi xuống ESP32 (VD: vol_max, led_color)"""
        return f"{PROJECT_PREFIX}/{device_id}/shadow/desired"
        
    @staticmethod
    def telemetry_pong(device_id: str) -> str:
        """Trả lời nhịp tim (Pong) cho ESP32"""
        return f"{PROJECT_PREFIX}/{device_id}/telemetry/pong"


class PayloadBuilder:
    """Lớp đóng gói dữ liệu thành Phong bì (Envelope) chuẩn hóa"""
    
    @staticmethod
    def build_json(data: Dict[str, Any], version: str = "1.0") -> dict:
        """
        Gói dữ liệu vào Envelope có msg_id để tracking và timestamp để ESP32 đối chiếu.
        """
        return {
            "msg_id": f"msg_{uuid.uuid4().hex[:12]}",  # Tạo mã ID ngẫu nhiên không trùng lặp
            "timestamp": int(time.time()),             # Đóng dấu thời gian Server
            "v": version,
            "data": data                               # Dữ liệu lõi được nhét vào đây
        }