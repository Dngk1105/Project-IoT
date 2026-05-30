import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.mqtt_client import fast_mqtt
from core.scheduler import setup_cronjobs, scheduler
from api.test_routes import router as test_router

logging.basicConfig(level=logging.INFO)

# Quản lý vòng đời: Chạy MQTT khi FastAPI khởi động
@asynccontextmanager
async def lifespan(app: FastAPI):
    await fast_mqtt.mqtt_startup()
    
    # Khởi động Bộ lập lịch
    setup_cronjobs()
    scheduler.start()
    logging.info("Hệ thống Lập lịch nền đã được kích hoạt.")
    
    logging.info("Đang đánh thức bộ não STT...")
    from integrations.stt_client import stt_api
    yield
    
    
    scheduler.shutdown()
    await fast_mqtt.mqtt_shutdown()

app = FastAPI(lifespan=lifespan)

# Nhúng cái Router test vào
app.include_router(test_router)

@app.get("/")
def root():
    return {"status": "Backend đang chạy!"}