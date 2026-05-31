import asyncio
import io
import logging
import array
from gtts import gTTS
import miniaudio

logger = logging.getLogger(__name__)

def _sync_gtts_synthesize(text: str) -> bytes:
    if not text or text.strip() == "":
        return b""
        
    try:
        tts = gTTS(text=text, lang='vi')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        decoded = miniaudio.decode(
            mp3_fp.read(), 
            nchannels=1, 
            sample_rate=16000, 
            output_format=miniaudio.SampleFormat.SIGNED16
        )
        
        pcm_bytes = bytes(decoded.samples)
        samples = array.array('h', pcm_bytes) # 'h' = số nguyên có dấu 16-bit
        
        start_idx = 0
        for i, val in enumerate(samples):
            if abs(val) > 150: # Ngưỡng biên độ âm thanh
                start_idx = max(0, i - 1600) # Lùi lại 100ms (1600 mẫu) cho mượt
                break
                
        end_idx = len(samples)
        for i in range(len(samples)-1, -1, -1):
            if abs(samples[i]) > 150:
                end_idx = min(len(samples), i + 1600)
                break
        
        trimmed_samples = samples[start_idx:end_idx]
        return trimmed_samples.tobytes()
        
    except Exception as e:
        logger.error(f"Lỗi khi xử lý gTTS: {e}", exc_info=True)
        return b""

class TTSClient:
    async def synthesize(self, text: str) -> bytes:
        if not text or text.strip() == "":
            return b""
        logger.info(f"Đang gọi Google TTS (gTTS): {text}")
        try:
            return await asyncio.to_thread(_sync_gtts_synthesize, text)
        except Exception as e:
            logger.error(f"Lỗi Pipeline TTS: {e}", exc_info=True)
            return b""

tts_api = TTSClient()