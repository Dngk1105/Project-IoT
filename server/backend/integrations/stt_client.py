import io
import wave
import logging
import asyncio
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class STTClient:
    def __init__(self):
        self.model_size = "large-v3"
        self.device = "cuda" 
        self.compute_type = "float32" 
        
        logger.info(f"Đang tải Whisper ({self.model_size}) vào RAM...")
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        logger.info("Tải mô hình STT Local hoàn tất!")

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> io.BytesIO:
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)      
            wav_file.setsampwidth(2)      
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_io.seek(0)
        return wav_io

    def _run_whisper_sync(self, wav_io: io.BytesIO) -> str:
        """Hàm chạy đồng bộ (blocking) bọc lõi của Faster-Whisper"""
        segments, info = self.model.transcribe(
            wav_io, 
            language="vi", 
            beam_size=5,
            vad_filter=True,
        )
        
        # Gom các đoạn văn bản (segment) lại thành một câu hoàn chỉnh
        text = "".join([segment.text for segment in segments])
        return text.strip()

    async def transcribe(self, raw_pcm_data: bytes) -> str:
        try:
            logger.info(f"Chuyển đổi {len(raw_pcm_data)} bytes PCM->WAV...")
            wav_io = self._pcm_to_wav(raw_pcm_data)
            
            logger.info("Đang nhận diện giọng nói...")
            
            # Tạo luồng để xử lí, tránh block server
            user_text = await asyncio.to_thread(self._run_whisper_sync, wav_io)
            
            return user_text
        except Exception as e:
            logger.error(f"Lỗi Whisper Local: {e}")
            return ""

# Khởi tạo đối tượng duy nhất (Singleton) để Model chỉ phải load vào RAM đúng 1 lần khi bật Server
stt_api = STTClient()