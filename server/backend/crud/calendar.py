from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta, UTC
from typing import List, Optional

from models.calendar import CalendarEvent, EventSource
from schemas.calendar import CalendarEventCreate, CalendarEventUpdate
from core.logger import get_logger

logger = get_logger("crud_calendar", log_file="database.log")

async def check_collision(db: AsyncSession, start_dt: datetime, end_dt: datetime) -> List[CalendarEvent]:
    """Tim cac event dang co lich trung voi nhau"""
    try:
        stmt = select(CalendarEvent).where(
            CalendarEvent.is_cancelled == False,
            CalendarEvent.start_time < end_dt, 
            CalendarEvent.end_time > start_dt
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Loi check trung lich: {str(e)}")
        return []

async def create_event(db: AsyncSession, event_in: CalendarEventCreate, source: EventSource = EventSource.VOICE_AI) -> CalendarEvent:
    """Chuyen schema -> model va luu vao database"""
    try:
        #Kiem tra co phai dang tao mot su kien da bi soft delete
        stmt = select(CalendarEvent).where(
            CalendarEvent.summary == event_in.summary,
            CalendarEvent.start_time == event_in.start_time,
            CalendarEvent.is_cancelled == True
        )
        ghost = await db.execute(stmt)
        if ghost.scalars().first():
            logger.info(f"Su kien '{event_in.summary}' da bi xoa mem tu truoc, tu choi nap lai.")
            return None # Bỏ qua, không tạo mới 
        
        #Check xung dot, ghi log chua lam gi
        collisions = await check_collision(db, event_in.start_time, event_in.end_time)
        if collisions:
            logger.warning(f"Phat hien trung {len(collisions)} lich cho su kien: {event_in.summary}")
        
        # Ép kiểu dữ liệu từ Pydantic Schema sang SQLAlchemy Model bằng model_dump()
        event_data = event_in.model_dump()
        event_data['source'] = source
        db_event = CalendarEvent(**event_in.model_dump())
        db.add(db_event)
        await db.commit()          # Lưu thay đổi xuống ổ cứng
        await db.refresh(db_event) # Nạp lại ID và created_at vừa được DB tự sinh ra
        
        logger.info(f"Da them su kien: {db_event.summary} [{db_event.id}]")
        return db_event
    except Exception as e:
        await db.rollback()
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
            CalendarEvent.is_cancelled == False,
            CalendarEvent.start_time >= start_dt,
            CalendarEvent.start_time <= end_dt
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Loi lay danh sach su kien: {str(e)}")
        return []
    
async def get_events_in_range_ordered(db: AsyncSession, start_dt: datetime, end_dt: datetime) -> List[CalendarEvent]:
    """Lấy sự kiện trong khoảng thời gian và sắp xếp theo giờ"""
    try:
        stmt = select(CalendarEvent).where(
            CalendarEvent.is_cancelled == False,
            CalendarEvent.start_time < end_dt, 
            CalendarEvent.end_time > start_dt
        ).order_by(CalendarEvent.start_time)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Lỗi khi lấy sự kiện có sắp xếp: {str(e)}")
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
    """Chi set is_cancelled = True"""
    db_event = await get_event(db, event_id)
    if not db_event:
        logger.warning(f"Khong tim thay su kien de xoa: {event_id}")
        return False
    
    try:
        db_event.is_cancelled = True
        await db.commit()
        logger.info(f"Da xoa (soft) su kien: {event_id}")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Loi khi Soft-Delete DB: {str(e)}")
        raise e
    
async def clear_future_events_by_source(db: AsyncSession, source: EventSource):
    """#bulk delete theo source"""
    now = datetime.now(UTC)
    try:
        stmt = delete(CalendarEvent).where(
            CalendarEvent.source == source,
            CalendarEvent.end_time >= now,
            CalendarEvent.is_cancelled == False #Du lai su kien da bi xoa de tranh cao lai
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        logger.info(f"Da don dep {result.rowcount} su kien tuong lai cua nguon {source.value}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Loi khi don dep DB: {str(e)}")
        raise e

async def find_free_slots(db: AsyncSession, start_dt: datetime, end_dt: datetime, duration_minutes: int) -> List[dict]:
    """
    Tìm các khoảng thời gian trống (Gap) >= duration_minutes.
    """
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=UTC)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=UTC)
        
    events = await get_events_in_range_ordered(db, start_dt, end_dt)
    free_slots = []
    
    current_time = start_dt
    
    for evt in events:
        if evt.start_time.tzinfo is None:
            evt.start_time = evt.start_time.replace(tzinfo=UTC)
        if evt.end_time.tzinfo is None:
            evt.end_time = evt.end_time.replace(tzinfo=UTC)
            
        # Nếu khoảng trống giữa thời điểm hiện tại và sự kiện tiếp theo đủ lớn
        if evt.start_time > current_time:
            gap_minutes = (evt.start_time - current_time).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append({
                    "start": current_time,
                    "end": evt.start_time
                })
        
        # Nhảy con trỏ thời gian tới lúc sự kiện này kết thúc
        current_time = max(current_time, evt.end_time)

    # Kiểm tra khoảng trống từ sự kiện cuối cùng đến lúc kết thúc (end_dt)
    if current_time < end_dt:
        gap_minutes = (end_dt - current_time).total_seconds() / 60
        if gap_minutes >= duration_minutes:
            free_slots.append({
                "start": current_time,
                "end": end_dt
            })
            
    # Giới hạn trả về 5 slot tốt nhất để LLM không bị ngợp Context
    return free_slots[:5]