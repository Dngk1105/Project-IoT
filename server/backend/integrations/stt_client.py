import io
import wave
import logging
import asyncio
import gc #garbage 
import torch
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class STTClient:
    def __init__(self, idle_timeout: int = 300):
        self.model_size = "large-v3"
        self.device = "cuda" 
        self.compute_type = "float16"
        self.model = None
        self.idle_timeout = idle_timeout
        self.idle_timer = None
        self.lock = asyncio.Lock() #giong mutex, tranh' xung dot load/unload model cung luc
        
        logger.info("Dang khoi tao STT...")
        
    async def _get_model(self) -> WhisperModel:
        """Neu idle thi tu dong bat lai"""
        #async with: acquire() lock xong roi release() no luon
        async with self.lock:
            #Huy timer hien tai
            if self.idle_timer:
                self.idle_timer.cancel()
                self.idle_timer = None
            
            if self.model is None:
                logger.info(f"Đang tải Whisper ({self.model_size}) vào VRAM/RAM...")
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("Tai STT thanh cong")
            return self.model
    
    
    def _reset_idle_timer(self):
        """Neu khong dung -> IDLE"""
        if self.idle_timer:
            self.idle_timer.cancel()
        
        loop = asyncio.get_running_loop()
        self.idle_timer = loop.call_later(
            self.idle_timeout, 
            lambda: asyncio.create_task(self._go_to_idle())
        )
        
    async def _go_to_idle(self):
        """Giai phong bo nho"""
        async with self.lock:
            if self.model is not None:
                logger.info("Lau khong dung, chuyen sang IDLE...")
                # Giải phóng bộ nhớ của faster-whisper
                del self.model
                self.model = None
                
                # Ép Python và CUDA dọn dẹp bộ nhớ ngay lập tức
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info("Da giai phong VRAM")

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> io.BytesIO:
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)      
            wav_file.setsampwidth(2)      
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_io.seek(0)
        return wav_io

    def _run_whisper_sync(self, model: WhisperModel, wav_io: io.BytesIO) -> str:
        """Hàm chạy đồng bộ (blocking) bọc lõi của Faster-Whisper"""
        segments, info = self.model.transcribe(
            wav_io, 
            language="vi", 
            beam_size=10,
            best_of=5,
            vad_filter=True,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        )
        
        # Gom các đoạn văn bản (segment) lại thành một câu hoàn chỉnh
        text = "".join([segment.text for segment in segments])
        return text.strip()

    async def transcribe(self, raw_pcm_data: bytes) -> str:
        try:
            model = await self._get_model()
            
            logger.info(f"Chuyển đổi {len(raw_pcm_data)} bytes PCM->WAV...")
            wav_io = self._pcm_to_wav(raw_pcm_data)
            
            logger.info("Đang nhận diện giọng nói...")
            
            # Tạo luồng để xử lí, tránh block server
            user_text = await asyncio.to_thread(self._run_whisper_sync, model, wav_io)
            
            self._reset_idle_timer() #reset timer
            
            return user_text
        except Exception as e:
            logger.error(f"Lỗi Whisper Local: {e}")
            self._reset_idle_timer()
            return ""

# Khởi tạo đối tượng duy nhất (Singleton) để Model chỉ phải load vào RAM đúng 1 lần khi bật Server
stt_api = STTClient()