import logging
import asyncio

logger = logging.getLogger(__name__)

class AudioEngineService:
    def __init__(self):
        # Khoi tao buffer, AI,...
        pass

    async def handle_stream(self, device_id: str, action: str, raw_pcm_data: bytes):
        """
        Hàm xử lý luồng âm thanh nhị phân (Binary) từ ESP32 gửi lên
        :param raw_pcm_data: Cục byte thô (PCM 16-bit, 16kHz, Mono)
        """
        try:
            if action == "stream_up":
                data_length = len(raw_pcm_data)
                
                # CHỖ NÀY SẼ GẮN AI ORCHESTRATOR SAU
                # Tích lũy buffer
                # Đẩy qua STT (Speech to Text)
                # Kéo Prompt -> Đẩy qua LLM (Gemini)
                # LLM Text -> Đẩy qua TTS (Text to Speech)
                # Dùng publish_cb ném file TTS trả lại xuống ESP32
                
                logger.debug(f"[{device_id}] Nhận luồng âm thanh: {data_length} bytes")
                
                # thao tác I/O nặng dùng await:
                # await self._save_to_file(device_id, raw_pcm_data)
                
            else:
                logger.warning(f"[{device_id}] Hành động audio không xác định: {action}")

        except Exception as e:
            # Văng ngoại lệ ngược lên Router để bắt tại trung tâm
            raise RuntimeError(f"Lỗi khi xử lý luồng PCM từ {device_id}: {e}")

audio_engine_service = AudioEngineService()