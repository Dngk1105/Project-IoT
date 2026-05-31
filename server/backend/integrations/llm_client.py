import google.generativeai as genai
import logging
from integrations.API_GEMINI import GEMINI_API_KEY
from core.logger import get_logger

logger = get_logger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

class LLMClient:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-3.1-flash-lite')

    async def chat(self, system_prompt: str, user_text: str) -> str:
        try:
            # Gộp system prompt để định hình nhân vật cho AI
            full_prompt = f"{system_prompt}\n\nNgười dùng nói: {user_text}\nTrợ lý trả lời:"
            
            # Gọi API bất đồng bộ
            response = await self.model.generate_content_async(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Lỗi khi gọi LLM Gemini: {e}", exc_info=True)
            return "Xin lỗi, tôi đang gặp sự cố mạng, không thể suy nghĩ lúc này."

llm_api = LLMClient()