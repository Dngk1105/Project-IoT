from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.calendar import CalendarEvent
from models.device import Device
from models.telemetry import Telemetry
from models.shadow import DeviceEventShadow
from models.base import Base

 
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./iot_calendar.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}  #Bất dồng bộ
)

AsyncSessionLocal = async_sessionmaker(
    bind= engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
) 


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)