import google.generativeai as genai
import json
from integrations.API_GEMINI import GEMINI_API_KEY
from core.logger import get_logger

logger = get_logger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

class LLMClient:
    def __init__(self):
        self.model = genai.GenerativeModel(
            'gemini-3.1-flash-lite',
            generation_config={"response_mime_type": "application/json"}
        )

    async def chat(self, system_prompt: str, user_text: str) -> str:
        try:
            # Gộp system prompt để định hình nhân vật cho AI
            full_prompt = f"{system_prompt}\n\nNgười dùng nói: {user_text}\nTrợ lý trả lời:"
            
            # Gọi API bất đồng bộ
            response = await self.model.generate_content_async(full_prompt)
            return json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("LLM khong tra ve JSON hop le", exc_info=True)
            return {"intent": "CHAT", "action": "NONE", "spoken_response": "Xin loi, de xu li thong tin bi loi."}
        except Exception as e:
            logger.error(f"Loi LLM Gemini: {e}", exc_info=True)
            return {"intent": "CHAT", "action": "NONE", "spoken_response": "Xin loi, de dang mat ket noi mang."}

llm_api = LLMClient()

llm_api = LLMClient()