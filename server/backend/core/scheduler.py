import json
import uuid
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from core.logger import get_logger
from core.mqtt_client import fast_mqtt, publish_message
from core.mqtt_protocol import MqttTopics, PayloadBuilder, PROJECT_PREFIX
from core.database import AsyncSessionLocal
from models.calendar import CalendarEvent
from models.device import Device
from models.shadow import DeviceEventShadow
from schemas.calendar import CalendarEventResponse
from services.delta_sync import delta_sync_service
from services.crawlers.hust_qldt_pipeline import run_sync_pipeline
from services.crawlers.google_pipeline import run_google_sync_pipeline


logger = get_logger("scheduler", log_file="scheduler.log")

scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

async def fetch_full_calendar_for_web() -> list:
    """
    Truy van toan bo lich hop le tu DB de day len Web Dashboard.
    Web can day du thong tin (ten, gio, dia diem, mau sac) de render FullCalendar.
    """
    async with AsyncSessionLocal() as session:
        # Lay cac su kien chua bi huy
        stmt = select(CalendarEvent).where(CalendarEvent.is_cancelled == False)
        result = await session.execute(stmt)
        events = result.scalars().all()
        
        # Ep kieu qua Pydantic Schema de tra ve JSON hop le
        return [CalendarEventResponse.model_validate(ev).model_dump(mode='json') for ev in events]

async def sync_and_broadcast_calendar():
    """
    Tac vu ngam (Cronjob): 
        Cao du lieu web (Tu dong goi)
        Tinh Delta va gui cho ESP32 (QoS 2)
        Day Full Data cho Frontend (QoS 1)
    """
    logger.info("[SCHEDULER] Bat dau tien trinh dong bo lich tong the...")
    
    await run_google_sync_pipeline()
    await run_sync_pipeline()   #hust-qldt


    #Todo: Phai truy van tu bang DEVICE
    async with AsyncSessionLocal() as session:
        stmt = select(Device.id)
        result = await session.execute(stmt)
        target_devices = result.scalars().all()

    if not target_devices:
        logger.info("Chưa có thiết bị ESP32 nào trong DB để đồng bộ.")
    
    for target_device in target_devices:
        delta_data = await delta_sync_service.calculate_delta(target_device)
        
        # Chi publish neu thuc su co su thay doi
        if delta_data["add"] or delta_data["upd"] or delta_data["del"]:
            # Cau truc Topic theo chuan MQTT v5 
            esp32_topic = MqttTopics.command(target_device, "sync_schedule")
            ack_topic = f"{PROJECT_PREFIX}/{target_device}/ack/sync_response"
            correlation_id = f"sync_{uuid.uuid4().hex[:8]}"

            esp32_payload = PayloadBuilder.build_json(data=delta_data)
            
            properties = {
                'response_topic': ack_topic,
                'correlation_data': correlation_id.encode('utf-8'),
                'message_expiry_interval': 3600 # Huy goi tin neu ESP offline qua 1 tieng
            }

            try:
                json_payload = json.dumps(esp32_payload) 
                
                # Bắn thẳng qua client gốc để truyền được properties MQTT v5
                if fast_mqtt.client:
                    fast_mqtt.client.publish(
                        esp32_topic, 
                        json_payload, 
                        qos=2, 
                        retain=False, 
                        **properties
                    )
                logger.info(f"[{target_device}] Da day Delta Sync xuong MCU (QoS 2) | Correlation: {correlation_id}")
            except Exception as e:
                logger.error(f"[{target_device}] Loi day Delta Sync qua MQTT: {e}", exc_info=True)
        else:
            logger.info(f"[{target_device}] Lich khong thay doi. Bo qua publish ESP32 de tiet kiem pin/mang.")


    #day len frontend
    frontend_topic = f"{PROJECT_PREFIX}/web_dashboard/events/calendar_sync"
    
    # Lay toan bo du lieu va dong goi
    full_events = await fetch_full_calendar_for_web()
    frontend_payload = PayloadBuilder.build_json(data={"events": full_events})
    
    # Su dung ham publish dung chung, set Retain = True de Web vua ket noi vao la co data
    publish_message(
        topic=frontend_topic,
        payload=frontend_payload,
        qos=1,
        retain=True 
    )
    logger.info(f"Da broadcast full {len(full_events)} su kien cho Frontend Dashboard.")


def setup_cronjobs():
    """Dang ky chu ky chay cho cac tac vu ngam"""
    
    # Chay lap lai moi 2 tieng de cap nhat lich
    scheduler.add_job(
        sync_and_broadcast_calendar, 
        trigger='interval', 
        hours=2,
        id='master_sync_job',
        replace_existing=True
    )