import logging
import asyncio
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
                logger.info("Day raw data thanh cong")

                
            else:
                logger.warning(f"[{device_id}] Hành động audio không xác định: {action}")

        except Exception as e:
            # Văng ngoại lệ ngược lên Router để bắt tại trung tâm
            raise RuntimeError(f"Lỗi khi xử lý luồng PCM từ {device_id}: {e}")
        
    
    async def process_pipeline(self, device_id: str, publish_cb):
        """stop_stream"""
        audio_data = bytes(self._audio_buffers.get(device_id, b""))
        self._audio_buffers[device_id] = bytearray()

        if len(audio_data) < 4000: # Audio qua ngan
            return

        try:
            logger.info(f"[{device_id}] Bắt đầu bóc tách luồng thoại với {len(audio_data)} bytes...")
            
            # Gọi Whisper Speech-to-Text Local xử lý
            user_text = await stt_api.transcribe(audio_data)

            logger.info(f"==================================================")
            logger.info(f"WHISPER LOCAL dịch là: '{user_text}'")
            logger.info(f"==================================================")
            # # Speech to Text
            # user_text = await stt_api.transcribe(audio_data)
            # logger.info(f"[{device_id}] Nhận diện: {user_text}")

            # # Sinh Prompt & Gọi LLM
            # prompt = get_assistant_prompt(device_id) # Trộn dữ liệu Database vào đây
            # bot_reply = await llm_api.generate_response(prompt, user_text)
            # logger.info(f"[{device_id}] Trả lời: {bot_reply}")

            # # Text to Speech
            # audio_response_bytes = await tts_api.synthesize(bot_reply)

            # # Băm nhỏ và gửi xuống ESP32
            # down_topic = MqttTopics.audio_down(device_id)
            # chunk_size = 4096
            # for i in range(0, len(audio_response_bytes), chunk_size):
            #     chunk = audio_response_bytes[i:i+chunk_size]
            #     publish_cb(down_topic, chunk, qos=0)
            #     await asyncio.sleep(0.01) # Tránh ngập lụt (flood) MQTT Broker
                
            # logger.info(f"[{device_id}] Đã stream xong luồng Audio xuống ESP32!")

        except Exception as e:
            logger.error(f"Lỗi Pipeline AI: {e}")

audio_engine_service = AudioEngineService()