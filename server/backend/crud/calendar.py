from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Optional

from models.calendar import CalendarEvent, EventSource
from schemas.calendar import CalendarEventCreate, CalendarEventUpdate
from core.logger import get_logger

logger = get_logger("crud_calendar", log_file="database.log")

async def create_event(db: AsyncSession, event_in: CalendarEventCreate) -> CalendarEvent:
    """Chuyen schema -> model va luu vao database"""
    try:
        # Ép kiểu dữ liệu từ Pydantic Schema sang SQLAlchemy Model bằng model_dump()
        db_event = CalendarEvent(**event_in.model_dump())
        db.add(db_event)
        
        await db.commit()          # Lưu thay đổi xuống ổ cứng
        await db.refresh(db_event) # Nạp lại ID và created_at vừa được DB tự sinh ra
        logger.info(f"Da them su kien: {db_event.summary} [{db_event.id}]")
        return db_event
    except Exception as e:
        db.rollback()
        logger.error (f"Loi khi luu vao DB: {str(e)}")
        raise e
        
async def get_event(db: AsyncSession, event_id: str) -> Optional[CalendarEvent]:
    """Lấy 1 sự kiện duy nhất theo ID"""
    try:
        stmt = select(CalendarEvent).where(
            CalendarEvent.id == event_id
        )
        result = await db.execute(stmt)
        
        return result.scalars().first()
    except Exception as e:
        logger.error(f"Loi truy van su kien {event_id}: {str(e)}")
        return None


async def get_events_in_range(db: AsyncSession, start_dt: datetime, end_dt: datetime) -> List[CalendarEvent]:
    """Truy vấn các sự kiện nằm trong khoảng thời gian nhất định"""
    try:
        stmt = select(CalendarEvent).where(
            CalendarEvent.start_time >= start_dt,
            CalendarEvent.start_time <= end_dt
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Loi lay danh sach su kien: {str(e)}")
        return []
    
    
async def update_event(db: AsyncSession, event_id: str, event_in: CalendarEventUpdate) -> Optional[CalendarEvent]:
    db_event = await get_event(db, event_id)
    if not db_event:
        logger.warning(f"Khong tim thay su kien de Update: {event_id}")
        return None
    
    #exclude_unset=True: Chi lay truong du lieu duoc truyen vao
    update_data = event_in.model_dump(exclude_unset=True)
    
    try:
        for key, val in update_data.items():
            setattr(db_event, key, val) #setattr(x,y,z) <=> x.y = z 
            
        await db.commit()
        await db.refresh(db_event) #Nap lai db_event tu db->ram
        logger.info(f"Da cap nhat su kien: {db_event.summary} [{db_event.id}]")
        return db_event
    except Exception as e:
        await db.rollback()
        logger.error(f"Loi khi Update DB: {str(e)}")
        raise e
    
async def delete_event(db: AsyncSession, event_id: str) -> bool:
    db_event = await get_event(db, event_id)
    if not db_event:
        logger.warning(f"Khong tim thay su kien de xoa: {event_id}")
        return False
    
    try:
        await db.delete(db_event)
        await db.commit()
        logger.info(f"Da xoa su kien: {event_id}")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Loi khi Delete DB: {str(e)}")
        raise e
    
#bulk delete theo source
async def clear_future_events_by_source(db: AsyncSession, source: EventSource):
    now = datetime.now()
    try:
        stmt = delete(CalendarEvent).where(
            CalendarEvent.source == source,
            CalendarEvent.end_time >= now
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        logger.info(f"Da don dep {result.rowcount} su kien tuong lai cua nguon {source.value}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Loi khi don dep DB: {str(e)}")
        raise e