import json
import uuid
import time
from datetime import datetime, timedelta
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
from services.ack_manager import PENDING_ACKS
import crud.calendar as crud_calendar

logger = get_logger("scheduler", log_file="scheduler.log")

scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

async def push_sync_to_device(device_id: str, db_session=None):
    try:
        logger.info(f"[{device_id}] Dang tinh toan Delta Sync de dong bo...")
        
        delta_data = await delta_sync_service.calculate_delta(device_id)
        
        if not delta_data["add"] and not delta_data["upd"] and not delta_data["del"]:
            logger.info(f"[{device_id}] Lich khong thay doi. Bo qua publish ESP32 de tiet kiem tai nguyen.")
            return

        pending_ids = [ev["id"] for ev in delta_data["add"]] + [ev["id"] for ev in delta_data["upd"]]
        
        corr_id = f"sync_{uuid.uuid4().hex[:8]}"
        PENDING_ACKS[corr_id] = pending_ids
        
        payload = PayloadBuilder.build_delta_sync(
            msg_id=f"sync_now_{int(time.time())}",
            data=delta_data
        )
        
        topic = MqttTopics.command(device_id, "sync_schedule")
        resp_topic = MqttTopics.ack(device_id, "sync_response")
        
        publish_message(
            topic=topic,
            payload=payload,
            qos=2,
            response_topic=resp_topic,
            correlation_data=corr_id.encode('utf-8'),
            message_expiry_interval=3600
        )
        
        logger.info(f"[{device_id}] Da push Delta Sync! Add: {len(delta_data['add'])}, Upd: {len(delta_data['upd'])}, Del: {len(delta_data['del'])}. CorrID: {corr_id}")
    except Exception as e:
        logger.error(f"[{device_id}] Loi khi push Sync: {e}", exc_info=True)

async def fetch_full_calendar_for_web() -> list:
    async with AsyncSessionLocal() as session:
        stmt = select(CalendarEvent).where(CalendarEvent.is_cancelled == False)
        result = await session.execute(stmt)
        events = result.scalars().all()
        return [CalendarEventResponse.model_validate(ev).model_dump(mode='json') for ev in events]

async def sync_and_broadcast_calendar():
    logger.info("[SCHEDULER] Bat dau tien trinh dong bo lich tong the...")
    
    await run_google_sync_pipeline()
    await run_sync_pipeline()   

    async with AsyncSessionLocal() as session:
        stmt = select(Device.id)
        result = await session.execute(stmt)
        target_devices = result.scalars().all()

    if not target_devices:
        logger.info("Chua co thiet bi ESP32 nao trong DB de dong bo.")
        return
    
    for target_device in target_devices:
        await push_sync_to_device(target_device)

def setup_cronjobs():
    scheduler.add_job(
        sync_and_broadcast_calendar, 
        trigger='interval', 
        hours=2,
        id='master_sync_job',
        replace_existing=True
    )