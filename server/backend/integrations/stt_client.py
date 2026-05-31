import io
import numpy as np
import logging
import asyncio
import gc #garbage 
import torch
from transformers import pipeline, Pipeline

logger = logging.getLogger(__name__)

class STTClient:
    def __init__(self, idle_timeout: int = 300):
        self.model_name = "vinai/PhoWhisper-large"
        self.device = 0 if torch.cuda.is_available() else -1 
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32        
        self.model = None
        
        self.idle_timeout = idle_timeout
        self.idle_timer = None
        
        self.lock = asyncio.Lock() #giong mutex, tranh' xung dot load/unload model cung luc
        
        logger.info("Dang khoi tao STT...")
        
    async def _get_model(self) -> Pipeline:
        """Neu idle thi tu dong bat lai"""
        #async with: acquire() lock xong roi release() no luon
        async with self.lock:
            #Huy timer hien tai
            if self.idle_timer:
                self.idle_timer.cancel()
                self.idle_timer = None
            
            if self.model is None:
                logger.info(f"Đang tải PhoWhisper ({self.model_name}) vào VRAM/RAM...")
                self.model = pipeline(
                    "automatic-speech-recognition",
                    model= self.model_name,
                    device= self.device,
                    torch_dtype = self.torch_dtype,
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

    def _pcm_to_float32_array(self, pcm_data: bytes) -> np.ndarray:
        """Chuyen truc tiep pcm 16bit sang float32 [-1,1]
            pcm16 bit -> int -> float -> chuan hoa 
        """
        audio_arr = np.frombuffer(pcm_data, dtype= np.int16)
        audio_float32 = audio_arr.astype(np.float32) / 32768.0
        return audio_float32

    def _run_whisper_sync(self, model: Pipeline, audio_input: np.ndarray) -> str:
        """Hàm chạy đồng bộ (blocking) bọc lõi của Faster-Whisper"""
        result = model(
            {
            "sampling_rate": 16000,
            "raw": audio_input
        },
        generate_kwargs={
            "language": "vi",
            "task": "transcribe"
            }
        )
        
        return result["text"].strip()

    async def transcribe(self, raw_pcm_data: bytes) -> str:
        try:
            model = await self._get_model()
            
            logger.info(f"Chuyển đổi {len(raw_pcm_data)} bytes...")
            audio_input = self._pcm_to_float32_array(raw_pcm_data)
            
            logger.info("Đang nhận diện giọng nói...")
            # Tạo luồng để xử lí, tránh block server
            user_text = await asyncio.to_thread(self._run_whisper_sync, model, audio_input)
            
            self._reset_idle_timer() #reset timer

            return user_text
        except Exception as e:
            logger.error(f"Lỗi Whisper Local: {e}")
            self._reset_idle_timer()
            return ""

# Khởi tạo đối tượng duy nhất (Singleton) để Model chỉ phải load vào RAM đúng 1 lần khi bật Server
stt_api = STTClient()