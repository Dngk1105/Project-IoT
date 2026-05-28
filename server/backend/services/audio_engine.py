import logging
import asyncio
import wave
import time
from integrations.stt_client import stt_api
#from integrations.llm_client import llm_api
#from integrations.tts_client import tts_api
#from core.prompts.system_prompts import get_assistant_prompt
from core.mqtt_protocol import MqttTopics

logger = logging.getLogger(__name__)

class AudioEngineService:
    def __init__(self):
        # Khoi tao buffer, AI,...
        self._audio_buffers = {}
        pass

    async def handle_stream(self, device_id: str, action: str, raw_pcm_data: bytes):
        """
        Hàm xử lý luồng âm thanh nhị phân (Binary) từ ESP32 gửi lên
        :param raw_pcm_data: Cục byte thô (PCM 16-bit, 16kHz, Mono)
        """
        try:
            if action == "stream_up":
                if device_id not in self._audio_buffers:
                    self._audio_buffers[device_id] = bytearray()
                self._audio_buffers[device_id].extend(raw_pcm_data)
                
            else:
                logger.warning(f"[{device_id}] Hành động audio không xác định: {action}")

        except Exception as e:
            # Văng ngoại lệ ngược lên Router để bắt tại trung tâm
            raise RuntimeError(f"Lỗi khi xử lý luồng PCM từ {device_id}: {e}")
        
    
    async def process_pipeline(self, device_id: str, publish_cb):
        """stop_stream"""
        audio_data = bytes(self._audio_buffers.get(device_id, b""))
        self._audio_buffers[device_id] = bytearray()   #reset

        if len(audio_data) < 4000: # Audio qua ngan
            return
        
        try:
            logger.info(f"[{device_id}] Bắt đầu Xử lí luồng thoại {len(audio_data)} bytes...")
            
            # Gọi Whisper Speech-to-Text Local xử lý
            user_text = await stt_api.transcribe(audio_data)
            logger.info("Whisper nhan dien giong noi thanh van ban:")
            logger.info(user_text);
        except Exception as e:
            logger.error(f"Lỗi Pipeline AI: {e}")

audio_engine_service = AudioEngineService()