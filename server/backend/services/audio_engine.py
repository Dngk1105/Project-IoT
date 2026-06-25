from core.logger import get_logger
import asyncio
import uuid
import time
import json
import wave
import numpy as np
from datetime import datetime
from integrations.stt_client import stt_api
from integrations.llm_client import llm_api
from integrations.tts_client import tts_api
from schemas.audio import AudioControlServer, AudioRequestESP32
from schemas.calendar import CalendarEventCreate, CalendarEventUpdate
from core.prompts.system_prompts import get_assistant_prompt
from core.mqtt_protocol import MqttTopics, PayloadBuilder
from core.mqtt_client import publish_message, fast_mqtt
from core.database import AsyncSessionLocal
from core.scheduler import push_sync_to_device
import crud.calendar as crud_calendar
from services.voice_agent import voice_agent

logger = get_logger(__name__, "audio_pipeline")

class AudioEngineService:
    def __init__(self):
        # Khoi tao buffer, AI,...
        self._audio_buffers = {}
        self._session_context = {}

    async def handle_stream(self, device_id: str, action: str, payload: bytes):
        """
        Hàm xử lý luồng âm thanh nhị phân (Binary) từ ESP32 gửi lên
        :param payload: Cục byte thô (PCM 16-bit, 16kHz, Mono)
        """
        try:
            if action == "stream_up":
                if device_id not in self._audio_buffers:
                    self._audio_buffers[device_id] = bytearray()
                self._audio_buffers[device_id].extend(payload)
            elif action == "request":
                try:
                    request = AudioRequestESP32.model_validate_json(payload)
                    if request.action == "request_tts":
                        logger.info(f"[{device_id}] Yêu cầu TTS - Event: {request.event_id} | Session: {request.session_id}")
                        
                        event_name = "Khong xac dinh"
                        async with AsyncSessionLocal() as db:
                            event = await crud_calendar.get_event(db, request.event_id)
                            if event:
                                event_name = event.summary
                                
                        text_to_speak = f"Xin chào, đã đến giờ cho sự kiện {event_name}. Huynh có chỉ thị gì thêm không?"
                        
                        asyncio.create_task(
                            self.stream_audio_to_device(
                                device_id, 
                                text_to_speak, 
                                publish_message, 
                                session_id = request.session_id))
                except Exception as e:   # ValidationError hoặc JSON error
                    logger.error(f"[{device_id}] Lỗi validate AudioRequestESP32: {e}")
                    return
            else:
                logger.warning(f"[{device_id}] Hành động audio không xác định: {action}")
        except json.JSONDecodeError:
            logger.error(f"[{device_id}] Lỗi parse JSON ở topic audio/request")
        except Exception as e:
            # Văng ngoại lệ ngược lên Router để bắt tại trung tâm
            raise RuntimeError(f"Lỗi khi xử lý luồng PCM từ {device_id}: {e}")
        
    
    async def process_pipeline(self, device_id: str, publish_cb):
        """stop_stream"""
        audio_data = bytes(self._audio_buffers.get(device_id, b""))
        self._audio_buffers[device_id] = bytearray()   #reset
            
        # # ===== Xuất file để debug =====
        # debug_filename = f"debug_{device_id}_{uuid.uuid4().hex[:8]}.wav"

        # with wave.open(debug_filename, "wb") as wf:
        #     wf.setnchannels(1)       # mono
        #     wf.setsampwidth(2)       # int16 = 2 bytes
        #     wf.setframerate(16000)   # sửa theo sample rate thực tế của bạn
        #     wf.writeframes(audio_data)

        # print(f"[DEBUG] Saved audio file: {debug_filename}")
        # # ==============================

        drop_session = f"drop_{uuid.uuid4().hex[:8]}"
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        max_amplitude = np.max(np.abs(audio_np))
        
        if max_amplitude < 500 or len(audio_data) < 4000:
            logger.warning(f"[{device_id}] Âm lượng quá bé ({max_amplitude}). Hủy gọi Whisper để tránh ảo giác!")
            await self.finish_session(device_id, publish_cb, session_id=drop_session, keep_listening = False)
            return
        
        session_id = f"chat_{uuid.uuid4().hex[:8]}"
        
        try:
            logger.info(f"[{device_id}] Bắt đầu Xử lí luồng thoại {len(audio_data)} bytes...")
            
            # Gọi Whisper Speech-to-Text Local xử lý
            user_text = await stt_api.transcribe(audio_data)
            logger.info("Whisper nhan dien giong noi thanh van ban:")
            logger.info(user_text);
            
            spoken_text, keep_mic_open = await voice_agent.process_user_intent(device_id, user_text)
            await self.stream_audio_to_device(device_id, spoken_text, publish_cb, session_id)
            
            # Truyen co keep_mic_open xuong finish_session de ESP32 biet duong bat lai Mic
            await self.finish_session(device_id, publish_cb, session_id, keep_listening=keep_mic_open)
            
            
        except Exception as e:
            logger.error(f"Loi he thong Audio: {e}", exc_info=True)
            await self.finish_session(device_id, publish_cb, session_id, keep_listening=False)
            
            
    async def stream_audio_to_device(self, device_id: str, text: str, publish_cb, session_id: str = None):
        """
        Truyen audio toi thiet bi
        """
        try:
            logger.info(f"[{device_id}] Đang tổng hợp giọng nói (TTS)...")
            
            # Lấy file Audio nhị phân (WAV/PCM thô) từ model TTS
            audio_bytes = await tts_api.synthesize(text)
            if not audio_bytes:
                raise ValueError("Model TTS không trả về dữ liệu")

            # chia file thanh tung chunk (4KB)
            chunk_size = 4096
            chunks = [audio_bytes[i:i + chunk_size] for i in range(0, len(audio_bytes), chunk_size)]
            
            # Start topic
            control_topic = MqttTopics.audio_control(device_id)
            start_data = AudioControlServer(
                action="start",
                session_id=session_id,
                chunk_count=len(chunks),
                sample_rate=16000
            ).model_dump()
            start_payload = PayloadBuilder.build_json(data = start_data)
            publish_cb(control_topic, start_payload, qos=1)
            
            # Chờ 200ms để I2S DMA trên ESP32 khởi động kịp
            await asyncio.sleep(0.2) 

            stream_topic = MqttTopics.audio_down(device_id)
            start_time = time.time() # Lấy mốc thời gian hệ thống
            
            for i, chunk in enumerate(chunks):
                if fast_mqtt.client:
                    fast_mqtt.client.publish(stream_topic, chunk, qos=0)
                
                # Tính toán mốc thời gian chính xác cần bắn gói tiếp theo
                # 4096 bytes = 0.128 giây âm thanh
                target_time = start_time + (i + 1) * 0.128 
                sleep_duration = target_time - time.time()
                
                # Bù trừ sai số của Windows: Chỉ ngủ phần thời gian còn lại
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
            
            #Gui stop   
            stop_data = AudioControlServer(
                action="stop",
                session_id=session_id
            ).model_dump()

            stop_payload = PayloadBuilder.build_json(data=stop_data)
            publish_cb(control_topic, stop_payload, qos=1)
            logger.info(f"[{device_id}] Đã truyền xong {len(chunks)} chunks âm thanh xuống loa.")

        except Exception as e:
            logger.error(f"[{device_id}] Lỗi stream âm thanh: {e}", exc_info=True)
            error_msg = AudioControlServer(
                action="error",
                session_id=session_id
            ).model_dump()
            error_payload = PayloadBuilder.build_json(data=error_msg)
            publish_cb(control_topic, error_payload, qos=1)
    
    
    
    async def finish_session(self, device_id: str, publish_cb, session_id: str, keep_listening: bool = False):
        """Esp32 ve IDLE"""
        control_topic = MqttTopics.audio_control(device_id)
        
        if not keep_listening:
            voice_agent.clear_session(device_id)
            
            
        idle_data = AudioControlServer(
            action="idle",
            session_id=session_id,
            keep_listening=keep_listening
        ).model_dump()
        idle_payload = PayloadBuilder.build_json(data=idle_data)
        publish_cb(control_topic, idle_payload, qos=1)

audio_engine_service = AudioEngineService()