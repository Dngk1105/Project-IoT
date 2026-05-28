import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.mqtt_client import fast_mqtt
from api.test_routes import router as test_router

logging.basicConfig(level=logging.INFO)

# Quản lý vòng đời: Chạy MQTT khi FastAPI khởi động
@asynccontextmanager
async def lifespan(app: FastAPI):
    await fast_mqtt.mqtt_startup()
    logging.info("Đang đánh thức bộ não STT...")
    from integrations.stt_client import stt_api
    yield
    await fast_mqtt.mqtt_shutdown()

app = FastAPI(lifespan=lifespan)

# Nhúng cái Router test vào
app.include_router(test_router)

@app.get("/")
def root():
    return {"status": "Backend đang chạy!"}