import time
from typing import Dict, Any, Callable
from sqlalchemy import select
import json
from datetime import datetime, timezone

from core.logger import get_logger
from core.mqtt_protocol import MqttTopics, PayloadBuilder
from core.database import AsyncSessionLocal
from core.scheduler import push_sync_to_device
from models.device import Device
from models.telemetry import Telemetry
from models.shadow import EndpointStateShadow

logger = get_logger(__name__)

class DeviceManagerService:
    def __init__(self):
        self._active_devices: Dict[str, Any] = {} # Trang thai off/on cua cac thiet bi ket noi tren RAM
        
    """Nhan cac goi tin Birth Message va LWT xu li trang thai ket noi cua thiet bi """
    async def process_lifecycle_status(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        core_data = payload.get("data", payload)
        status = core_data.get("status")
        timestamp = core_data.get("timestamp")

        if status == "online":
            self._active_devices[device_id] = {"status": "online", "last_seen": timestamp}
            logger.info(f"Thiet bi {device_id} vua ket noi. {len(self._active_devices)} thiet bi dang ket noi")
            
            # Phat lenh dong bo gio xuong ESP32
            time_payload = PayloadBuilder.build_json({"timestamp": int(time.time())})
            time_topic = MqttTopics.command(device_id, "time_sync")
            publish_cb(time_topic, time_payload, qos=1)
        
        elif status == "offline":
            if device_id in self._active_devices:
                self._active_devices[device_id]["status"] = "offline"
            reason = core_data.get("reason", "unknown")
            logger.warning(f"Thiết bị {device_id} vừa ngắt kết nối. Lý do: {reason}")
            
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Device).where(Device.id == device_id)
                result = await session.execute(stmt)
                device = result.scalar_one_or_none()

                if not device:
                    # Chua co trong DB thi dang ky moi
                    device = Device(
                        id=device_id, 
                        status=status, 
                        last_offline_reason=payload.get("reason") if status == "offline" else None
                    )
                    session.add(device)
                else:
                    # Da co thi cap nhat
                    device.status = status
                    if status == "offline" and "reason" in payload:
                        device.last_offline_reason = payload.get("reason")
                    device.last_seen = datetime.now(timezone.utc)
                    
                if status == "online":
                    endpoints = core_data.get("endpoints")
                    if endpoints and isinstance(endpoints, list):
                        from models.shadow import EndpointStateShadow
                        import json
                        
                        for ep in endpoints:
                            ep_id = ep.get("ep_id")
                            stmt_ep = select(EndpointStateShadow).where(
                                EndpointStateShadow.device_id == device_id,
                                EndpointStateShadow.ep_id == ep_id
                            )
                            res_ep = await session.execute(stmt_ep)
                            existing_ep = res_ep.scalar_one_or_none()

                            cmds_str = json.dumps(ep.get("supported_cmds", []))

                            if existing_ep:
                                existing_ep.reported_state = ep.get("state", "UNKNOWN")
                                existing_ep.name = ep.get("name", existing_ep.name)
                                existing_ep.supported_cmds = cmds_str
                            else:
                                new_ep = EndpointStateShadow(
                                    device_id=device_id,
                                    ep_id=ep_id,
                                    name=ep.get("name", "Unknown"),
                                    type=ep.get("type", "actuator"),
                                    supported_cmds=cmds_str,
                                    reported_state=ep.get("state", "UNKNOWN")
                                )
                                session.add(new_ep)

                await session.commit()
                
                if status == "online":
                    logger.info(f"[{device_id}] Bắt đầu đồng bộ lịch trình xuống ESP32...")
                    await push_sync_to_device(device_id, session)
            except Exception as e:
                await session.rollback()
                logger.error(f"[{device_id}] Lỗi DB khi cập nhật Lifecycle: {e}", exc_info=True)
    
    
    """Dinh ki xu li cac chi so cua he thong phan cung (RAM, Wifi,...)"""
    async def process_hardware_telemetry(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        if action == "ping":    # Neu ping -> pong lai
            pong_topic = MqttTopics.telemetry_pong(device_id)
            data = {"status": "alive"} # Da sua lai loi cu phap dict
            out_payload = PayloadBuilder.build_json(data)
            publish_cb(pong_topic, out_payload, qos = 0)
            logger.debug(f"Đã trả lời PONG cho [{device_id}]")
            return
            
        if action == "metrics":            
            # Khong can lay timestamp o day vi Schema DB auto generate
            metrics = payload.get("data", {})
            
            # Map voi format gui len tu ESP32
            free_heap_kb = metrics.get("free_heap_kb")
            rssi = metrics.get("rssi")
            uptime = metrics.get("uptime_s")
            audio_metrics = metrics.get("audio_metrics", {})
            
            # Du phong cac truong pin
            battery_voltage = metrics.get("battery_voltage")
            battery_percent = metrics.get("battery_percent")
            
            logger.info(
                f"Telemetry từ [{device_id}] | "
                f"Heap trống: {free_heap_kb}KB | RSSI: {rssi}dBm | Uptime: {uptime}s | "
                f"Peak DB: {audio_metrics.get('audio_peak_db')}dB"
            )
            
            async with AsyncSessionLocal() as session:
                try:
                    stmt = select(Device).where(Device.id == device_id)
                    result = await session.execute(stmt)
                    device = result.scalar_one_or_none()

                    if not device:
                        device = Device(id=device_id, status="online")
                        session.add(device)
                        await session.flush() # Đẩy tạm xuống DB để lấy ID

                    device.last_seen = datetime.now(timezone.utc)
                    device.status = "online"

                    telemetry_record = Telemetry(
                        device_id=device_id,
                        free_heap=int(free_heap_kb * 1024) if free_heap_kb else None,
                        wifi_rssi=rssi,
                        uptime_sec=uptime,
                        battery_voltage=battery_voltage,
                        battery_percent=battery_percent
                    )
                    session.add(telemetry_record)

                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error(f"[{device_id}] Lỗi DB khi lưu Telemetry: {e}", exc_info=True)
        
    async def process_device_shadow(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        """Xu li trang thai thiet bi ngoai vi"""
        core_data = payload.get("data", payload)
        ep_id = core_data.get("ep_id")
        new_state = core_data.get("reported_state")
        
        if ep_id and new_state:
            async with AsyncSessionLocal() as session:
                from models.shadow import EndpointStateShadow
                stmt = select(EndpointStateShadow).where(
                    EndpointStateShadow.device_id == device_id,
                    EndpointStateShadow.ep_id == ep_id
                )
                result = await session.execute(stmt)
                ep_record = result.scalar_one_or_none()
                
                if ep_record:
                    ep_record.reported_state = new_state
                    await session.commit()
                    logger.info(f"[{device_id}] Cập nhật Shadow: {ep_id} -> {new_state}")
        
device_manager_service = DeviceManagerService() # Doi tuong singleton duy nhat