import io
import wave
import logging
import asyncio
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class STTClient:
    def __init__(self):
        # Chọn size model: "tiny", "base", "small", "medium", "large-v3"
        # "small" hoặc "base" là điểm cân bằng tuyệt vời nhất giữa Tốc độ và Độ chính xác cho Tiếng Việt.
        self.model_size = "large-v3"
        
        # device="cuda" (nếu có card NVIDIA) hoặc "cpu"
        # compute_type="float16" (GPU) hoặc "int8" (CPU để giảm nửa RAM)
        self.device = "cpu" 
        self.compute_type = "int8" 
        
        logger.info(f"Đang tải Whisper ({self.model_size}) vào RAM...")
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        logger.info("Tải mô hình STT Local hoàn tất!")

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> io.BytesIO:
        """Đóng gói PCM thô thành định dạng WAV chuẩn ngay trên RAM"""
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
        # Tham số beam_size=5 giúp AI cân nhắc nhiều cụm từ để cho ra câu chuẩn ngữ pháp nhất
        segments, info = self.model.transcribe(wav_io, language="vi", beam_size=5)
        
        # Gom các đoạn văn bản (segment) lại thành một câu hoàn chỉnh
        text = "".join([segment.text for segment in segments])
        return text.strip()

    async def transcribe(self, raw_pcm_data: bytes) -> str:
        try:
            logger.info(f"Đang bọc {len(raw_pcm_data)} bytes PCM thành WAV...")
            wav_io = self._pcm_to_wav(raw_pcm_data)
            
            logger.info("Đang vắt óc nhận diện giọng nói (Local)...")
            
            # Đẩy tác vụ STT sang một Thread (luồng) khác để không khóa (block) Server
            user_text = await asyncio.to_thread(self._run_whisper_sync, wav_io)
            
            return user_text
        except Exception as e:
            logger.error(f"Lỗi Whisper Local: {e}")
            return ""

# Khởi tạo đối tượng duy nhất (Singleton) để Model chỉ phải load vào RAM đúng 1 lần khi bật Server
stt_api = STTClient()