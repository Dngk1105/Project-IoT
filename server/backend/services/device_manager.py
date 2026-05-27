import logging 
from typing import Dict, Any, Callable
from core.mqtt_protocol import MqttTopics, PayloadBuilder


logger = logging.getLogger(__name__) #Ghi log

class DeviceManagerService:
    def __init__(self):
        self._active_devices: Dict[str, Any] = {} #Trang thai off/on cua cac thiet bi ket noi 
        
    """Nhan cac goi tin Birth Message va LWT xu li trang thai ket noi cua thiet bi """
    async def process_lifecycle_status(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
       status = payload.get("status")
       timestamp = payload.get("timestamp")
       
       if status == "online":
           self._active_devices[device_id] = {"status": "online", "last_seen": timestamp}
           logger.info(f"Thiet bi {device_id} vua ket noi. {len(self._active_devices)} thiet bi dang ket noi")
        
       elif status == "offline":
           if device_id in self._active_devices:
               self._active_devices[device_id]["status"] = "offline"
           reason = payload.get("reason", "unknown")
           logger.warning(f"Thiết bị {device_id} vừa ngắt kết nối. Lý do: {reason}")
        #TODO: Cap nhat som toi DB
    
    
    """Dinh ki xu li cac chi so cua he thong phan cung (RAM, Wifi,...)"""
    async def process_hardware_telemetry(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        if action == "ping":    #Neu ping -> pong lai
            
            pong_topic = MqttTopics.telemetry_pong(device_id)
            data = {{"status": "alive"}}
            payload = PayloadBuilder.build_json(data)
            publish_cb(pong_topic, payload, qos = 0)
            logger.debug(f"Đã trả lời PONG cho [{device_id}]")
            return
        if action == "metrics":            
            timestamp = payload.get("timestamp") 
            metrics = payload.get("data", {})
            
            free_heap = metrics.get("free_heap_kb")
            rssi = metrics.get("rssi")
            uptime = metrics.get("uptime_s")
            audio_metrics = metrics.get("audio_metrics", {})
            
            logger.info(
                f"Telemetry từ [{device_id}] | "
                f"Heap trống: {free_heap}KB | RSSI: {rssi}dBm | Uptime: {uptime}s | "
                f"Peak DB: {audio_metrics.get('audio_peak_db')}dB"
            )
            #TODO: Ghi vao DB, hoac xu li gi thi tuy
        
    async def process_device_shadow(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        """Xu li trang thai thiet bi ngoai vi"""
        logger.info(f"Thiết bị [{device_id}] báo cáo trạng thái thiet bi ngoại vi [{action}]: {payload}")
        # TODO: Đồng bộ trạng thái thực tế của phần cứng lên giao diện Web Dashboard qua WebSocket
        
device_manager_service = DeviceManagerService() # Doi tuong singleton duy nhat