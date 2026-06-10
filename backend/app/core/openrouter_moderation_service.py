import os
import re
import json
import base64
import mimetypes
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv


load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

OPENROUTER_TEXT_MODEL = os.getenv(
    "OPENROUTER_TEXT_MODEL",
    "google/gemini-2.5-flash-lite",
)

OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "google/gemini-2.5-flash-lite",
)

APP_URL = os.getenv("APP_URL", "http://localhost:5173")
APP_NAME = os.getenv("APP_NAME", "UTEZone")

MODERATION_DEBUG = os.getenv("MODERATION_DEBUG", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

TEXT_CONCURRENCY = int(os.getenv("MODERATION_TEXT_CONCURRENCY", "3"))
IMAGE_CONCURRENCY = int(os.getenv("MODERATION_IMAGE_CONCURRENCY", "2"))

OPENROUTER_TIMEOUT = float(os.getenv("OPENROUTER_TIMEOUT", "60"))
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "1000"))

TEXT_THRESHOLDS = {
    "toxicity": 0.65,
    "hate_speech": 0.65,
    "violence": 0.65,
    "sexual_content": 0.65,
    "harassment": 0.65,
    "self_harm": 0.65,
    "spam": 0.80,
}

IMAGE_THRESHOLDS = {
    "nudity": 0.60,
    "sexual_content": 0.60,
    "violence": 0.60,
    "gore": 0.60,
    "hate_symbols": 0.60,
    "drugs": 0.70,
    "harassment": 0.65,
    "text_in_image": 0.75,
}

SERVICE_ERROR_CATEGORIES = {
    "invalid_ai_response",
    "moderation_error",
    "moderation_config_error",
    "invalid_moderation_result",
}


class OpenRouterModerationService:
    """
    OpenRouter moderation service cho web mạng xã hội.

    Bản FIXED:
    - Dùng httpx trực tiếp giống file meeting đang hoạt động.
    - KHÔNG dùng OpenAI SDK.
    - KHÔNG dùng response_format.
    - Prompt siết giống logic Ollama cũ.
    - Có scores / violated_categories / confidence để lưu DB.
    - Có retry 4 lần.
    - Có semaphore để xử lý song song nhưng vẫn giới hạn request.
    - Fail-closed: AI lỗi / JSON lỗi / thiếu field thì reject, không cho qua.
    - Nếu JSON bị cắt nhưng đã có approved=false hoặc score vi phạm thì vẫn reject.
    """

    def __init__(self):
        self.text_semaphore = asyncio.Semaphore(TEXT_CONCURRENCY)
        self.image_semaphore = asyncio.Semaphore(IMAGE_CONCURRENCY)

    # ============================================================
    # DEBUG
    # ============================================================
    def _debug(self, title: str, data: Any = None):
        if not MODERATION_DEBUG:
            return

        print(f"\n========== {title} ==========")
        if data is not None:
            if isinstance(data, (dict, list)):
                try:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                except Exception:
                    print(data)
            else:
                print(data)
        print(f"========== END {title} ==========\n")

    # ============================================================
    # RAW OPENROUTER CALL
    # ============================================================
    async def _call_openrouter(
        self,
        prompt: str,
        model: str,
        images: Optional[List[str]] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> str:
        if not OPENROUTER_API_KEY:
            print("[OpenRouter] Missing OPENROUTER_API_KEY")
            return json.dumps(
                {
                    "approved": False,
                    "reason": "Thiếu OPENROUTER_API_KEY cho hệ thống kiểm duyệt",
                    "scores": {},
                    "violated_categories": ["moderation_config_error"],
                    "confidence": 0.0,
                },
                ensure_ascii=False,
            )

        sem = semaphore or self.text_semaphore

        async with sem:
            last_error = "Service unavailable"
            last_partial_content = ""

            for attempt in range(4):
                try:
                    content: List[Dict[str, Any]] = []

                    if images:
                        for img_path in images:
                            mime_type = mimetypes.guess_type(img_path)[0] or "image/jpeg"

                            with open(img_path, "rb") as f:
                                base64_img = base64.b64encode(f.read()).decode("utf-8")

                            content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_img}"
                                    },
                                }
                            )

                    content.append(
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    )

                    payload = {
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": content,
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": OPENROUTER_MAX_TOKENS,
                    }

                    self._debug(
                        "[OPENROUTER REQUEST]",
                        {
                            "model": model,
                            "attempt": attempt + 1,
                            "has_images": bool(images),
                            "max_tokens": OPENROUTER_MAX_TOKENS,
                            "prompt_preview": prompt[:800],
                        },
                    )

                    async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                        response = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": APP_URL,
                                "X-Title": APP_NAME,
                            },
                            json=payload,
                        )

                    self._debug(
                        "[OPENROUTER HTTP RESPONSE]",
                        {
                            "status_code": response.status_code,
                            "text_preview": response.text[:1800],
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        choices = data.get("choices") or []

                        if not choices:
                            last_error = "OpenRouter response missing choices"
                            await asyncio.sleep(1.5)
                            continue

                        choice = choices[0]
                        message = choice.get("message") or {}
                        result = message.get("content")

                        self._debug(
                            "[OPENROUTER CHOICE]",
                            {
                                "finish_reason": choice.get("finish_reason"),
                                "native_finish_reason": choice.get("native_finish_reason"),
                                "has_content": bool(result),
                                "error": choice.get("error"),
                            },
                        )

                        if choice.get("finish_reason") == "error":
                            err = choice.get("error") or {}
                            if isinstance(err, dict):
                                last_error = err.get("message") or str(err)
                            else:
                                last_error = str(err)

                            self._debug("[OPENROUTER CHOICE ERROR]", choice)

                            if result and str(result).strip():
                                last_partial_content = str(result)

                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue

                        self._debug("[OPENROUTER RAW CONTENT]", result)

                        if result is None or not str(result).strip():
                            last_error = "AI moderation service unavailable: empty response"
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue

                        result_text = str(result)

                        if choice.get("finish_reason") == "length":
                            last_partial_content = result_text
                            last_error = "OpenRouter response truncated because max_tokens was too low"
                            self._debug("[OPENROUTER LENGTH TRUNCATED]", result_text)

                            if attempt == 3:
                                return result_text

                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue

                        return result_text

                    if response.status_code == 429:
                        retry_after = 5
                        try:
                            err_data = response.json()
                            retry_after = err_data.get("metadata", {}).get(
                                "retry_after_seconds",
                                5,
                            )
                        except Exception:
                            pass

                        last_error = "AI moderation service rate limited"
                        print(
                            f"[OpenRouter] Rate limited, waiting {retry_after}s "
                            f"(attempt {attempt + 1}/4)"
                        )
                        await asyncio.sleep(float(retry_after) + 2)
                        continue

                    last_error = f"OpenRouter HTTP {response.status_code}: {response.text[:500]}"
                    print(f"[OpenRouter] HTTP {response.status_code}: {response.text[:500]}")
                    await asyncio.sleep(2)

                except Exception as e:
                    last_error = str(e)
                    print(f"[OpenRouter] Attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2)

            if last_partial_content.strip():
                self._debug("[OPENROUTER RETURN LAST PARTIAL CONTENT]", last_partial_content)
                return last_partial_content

            return json.dumps(
                {
                    "approved": False,
                    "reason": f"AI moderation service unavailable or rate limited: {last_error}",
                    "scores": {},
                    "violated_categories": ["moderation_error"],
                    "confidence": 0.0,
                },
                ensure_ascii=False,
            )

    # ============================================================
    # PROMPTS - SIẾT THEO LOGIC OLLAMA CŨ
    # ============================================================
    def _text_prompt(self, content: str, content_type: str = "post") -> str:
        return f"""
Bạn là hệ thống kiểm duyệt nội dung văn bản cho diễn đàn/mạng xã hội sinh viên UTEZone.

NHIỆM VỤ:
Đánh giá nội dung {content_type} dưới đây và trả về DUY NHẤT JSON hợp lệ.
Không markdown. Không giải thích. Không thêm chữ trước hoặc sau JSON.

JSON BẮT BUỘC ĐÚNG CẤU TRÚC:
{{
  "approved": true,
  "scores": {{
    "toxicity": 0.0,
    "hate_speech": 0.0,
    "violence": 0.0,
    "sexual_content": 0.0,
    "harassment": 0.0,
    "self_harm": 0.0,
    "spam": 0.0
  }},
  "violated_categories": [],
  "reason": "",
  "confidence": 0.95
}}

QUY TẮC CHẤM ĐIỂM:
- toxicity: Nội dung thô tục, chửi thề, xúc phạm, hạ nhục, công kích cá nhân.
  Nếu toxicity >= 0.65 thì REJECT.
- hate_speech: Kích động thù địch, phân biệt chủng tộc, tôn giáo, giới tính, quốc tịch, vùng miền.
  Nếu hate_speech >= 0.65 thì REJECT.
- violence: Đe dọa đánh, giết, gây thương tích, làm hại người khác, cổ vũ bạo lực.
  Nếu violence >= 0.65 thì REJECT.
- sexual_content: Mô tả tường minh hành vi tình dục, khiêu dâm, gợi dục thô tục.
  Nếu sexual_content >= 0.65 thì REJECT.
- harassment: Quấy rối, bắt nạt, đe dọa cá nhân, nhắm vào một người để xúc phạm.
  Nếu harassment >= 0.65 thì REJECT.
- self_harm: Khuyến khích, hướng dẫn, cổ vũ tự làm hại bản thân hoặc tự tử.
  Nếu self_harm >= 0.65 thì REJECT.
- spam: Spam, lừa đảo, dụ click link độc hại, quảng cáo lặp lại gây hại.
  Nếu spam >= 0.80 thì REJECT.

QUY TẮC BẮT BUỘC:
- Nếu bất kỳ score nào vượt ngưỡng REJECT, approved bắt buộc phải là false.
- Nếu approved=false, violated_categories phải chứa đúng category vi phạm.
- Nếu approved=false, reason phải ngắn gọn bằng tiếng Việt.
- Nếu approved=true, reason phải là chuỗi rỗng "".
- Điểm số phải là số từ 0.0 đến 1.0.
- Không bỏ qua vi phạm chỉ vì nội dung ngắn.
- Không được trả lời bằng phân tích. Chỉ trả JSON.

CÁC NỘI DUNG SAU KHÔNG ĐƯỢC COI LÀ VI PHẠM:
- Danh sách công việc, kế hoạch, task list, ghi chú cá nhân.
- Nội dung học tập, thảo luận về công nghệ, lập trình, khoa học.
- Phân tích, so sánh, đánh giá sản phẩm/dịch vụ nếu không tấn công cá nhân.
- Tin tức, bài báo, tài liệu tham khảo.
- Câu hỏi, hướng dẫn, giải thích kỹ thuật.
- Tranh luận bình thường, phê bình lịch sự, góp ý học thuật.
- Nội dung nhắc tới từ nhạy cảm trong ngữ cảnh giáo dục, báo chí, phòng chống hoặc giải thích.

QUAN TRỌNG:
- Nếu không có yếu tố vi phạm rõ ràng với điểm số >= ngưỡng, tất cả điểm nên thấp và approved=true.
- Hãy khách quan, không phán xét quá mức nội dung bình thường.

NỘI DUNG CẦN KIỂM DUYỆT:
{content[:4000]}
""".strip()

    def _image_prompt(self) -> str:
        return """
Bạn là hệ thống kiểm duyệt hình ảnh cho mạng xã hội sinh viên UTEZone.

NHIỆM VỤ:
Đánh giá hình ảnh được gửi kèm và trả về DUY NHẤT JSON hợp lệ.
Không markdown. Không giải thích. Không thêm chữ trước hoặc sau JSON.

JSON BẮT BUỘC ĐÚNG CẤU TRÚC:
{
  "approved": true,
  "scores": {
    "nudity": 0.0,
    "sexual_content": 0.0,
    "violence": 0.0,
    "gore": 0.0,
    "hate_symbols": 0.0,
    "drugs": 0.0,
    "harassment": 0.0,
    "text_in_image": 0.0
  },
  "violated_categories": [],
  "reason": "",
  "confidence": 0.95
}

QUY TẮC CHẤM ĐIỂM:
- nudity: Khỏa thân, lộ bộ phận nhạy cảm.
  Nếu nudity >= 0.60 thì REJECT.
- sexual_content: Tư thế/hành vi tình dục, khiêu dâm rõ ràng.
  Nếu sexual_content >= 0.60 thì REJECT.
- violence: Đánh nhau, đe dọa bằng vũ khí, gây hại người khác.
  Nếu violence >= 0.60 thì REJECT.
- gore: Máu me, thương tích nghiêm trọng, hình ảnh ghê rợn.
  Nếu gore >= 0.60 thì REJECT.
- hate_symbols: Biểu tượng thù hận, cực đoan, kích động thù ghét.
  Nếu hate_symbols >= 0.60 thì REJECT.
- drugs: Ma túy, sử dụng hoặc mua bán chất cấm.
  Nếu drugs >= 0.70 thì REJECT.
- harassment: Chữ/hình ảnh bắt nạt, xúc phạm, quấy rối cá nhân.
  Nếu harassment >= 0.65 thì REJECT.
- text_in_image: Chữ trong ảnh có nội dung xúc phạm, thù ghét, tình dục, spam, lừa đảo.
  Nếu text_in_image >= 0.75 thì REJECT.

QUY TẮC BẮT BUỘC:
- Nếu bất kỳ score nào vượt ngưỡng REJECT, approved bắt buộc phải là false.
- Nếu approved=false, violated_categories phải chứa đúng category vi phạm.
- Nếu approved=false, reason phải ngắn gọn bằng tiếng Việt.
- Nếu approved=true, reason phải là chuỗi rỗng "".
- Điểm số phải là số từ 0.0 đến 1.0.
- Không được trả lời bằng phân tích. Chỉ trả JSON.

CÁC HÌNH ẢNH SAU KHÔNG ĐƯỢC COI LÀ VI PHẠM:
- Ảnh học tập, lớp học, sinh viên, hoạt động trường.
- Ảnh màn hình code, slide, tài liệu, bài giảng.
- Meme nhẹ không xúc phạm cá nhân/nhóm người.
- Ảnh tin tức hoặc giáo dục không cổ vũ hành vi xấu.
- Ảnh sản phẩm, đồ vật, giao diện ứng dụng bình thường.

QUAN TRỌNG:
- Không reject nếu không có dấu hiệu vi phạm rõ ràng với điểm số vượt ngưỡng.
""".strip()

    # ============================================================
    # PARSE JSON + HEURISTIC
    # ============================================================
    def _parse_json(self, response: str, mode: str = "text") -> Dict[str, Any]:
        if response is None or not str(response).strip():
            return {
                "approved": False,
                "reason": "AI moderation service unavailable: empty response",
                "scores": {},
                "violated_categories": ["invalid_ai_response"],
                "confidence": 0.0,
            }

        text = str(response).strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            json_part = text[start:end + 1]
            json_part = re.sub(r",\s*([}\]])", r"\1", json_part)

            try:
                return json.loads(json_part)
            except Exception as e:
                print(f"[MOD_PARSE] Full object parse error: {e}, response={text[:500]}")

        heuristic = self._parse_truncated_response(text, mode=mode)
        if heuristic is not None:
            return heuristic

        print(f"[MOD_PARSE] Cannot parse JSON object, response={text[:500]}")
        return {
            "approved": False,
            "reason": "AI moderation service unavailable: invalid response",
            "scores": {},
            "violated_categories": ["invalid_ai_response"],
            "confidence": 0.0,
        }

    def _parse_truncated_response(self, text: str, mode: str = "text") -> Optional[Dict[str, Any]]:
        lower = text.lower()

        approved_false = (
            '"approved": false' in lower
            or '"approved":false' in lower
            or "'approved': false" in lower
            or "'approved':false" in lower
        )

        approved_true = (
            '"approved": true' in lower
            or '"approved":true' in lower
            or "'approved': true" in lower
            or "'approved':true" in lower
        )

        thresholds = TEXT_THRESHOLDS if mode == "text" else IMAGE_THRESHOLDS
        scores: Dict[str, float] = {}

        for cat in thresholds:
            pattern = rf'["\']{re.escape(cat)}["\']\s*:\s*([0-9]*\.?[0-9]+)'
            match = re.search(pattern, text)
            if match:
                try:
                    scores[cat] = float(match.group(1))
                except Exception:
                    scores[cat] = 0.0

        violated = [
            cat
            for cat, threshold in thresholds.items()
            if scores.get(cat, 0.0) >= threshold
        ]

        if approved_false or violated:
            return {
                "approved": False,
                "reason": "Nội dung vi phạm quy định",
                "scores": scores,
                "violated_categories": violated or ["general"],
                "confidence": 0.8,
            }

        if approved_true and not violated:
            return {
                "approved": True,
                "reason": "",
                "scores": scores,
                "violated_categories": [],
                "confidence": 0.5,
            }

        return None

    # ============================================================
    # NORMALIZE
    # ============================================================
    def _normalize_text_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._invalid_result("AI response không phải JSON object", OPENROUTER_TEXT_MODEL)

        if self._is_service_error_result(data):
            return self._service_error_result(data, OPENROUTER_TEXT_MODEL)

        if "approved" not in data:
            return self._invalid_result("AI không trả về field approved", OPENROUTER_TEXT_MODEL)

        if "scores" not in data or not isinstance(data.get("scores"), dict):
            return self._invalid_result("AI không trả về field scores hợp lệ", OPENROUTER_TEXT_MODEL)

        scores = data.get("scores") or {}
        violated = data.get("violated_categories") or []

        if not isinstance(violated, list):
            violated = []

        normalized_scores: Dict[str, float] = {}
        for category in TEXT_THRESHOLDS:
            try:
                normalized_scores[category] = float(scores.get(category, 0.0))
            except Exception:
                normalized_scores[category] = 0.0

        approved = bool(data.get("approved"))

        for category, threshold in TEXT_THRESHOLDS.items():
            if normalized_scores[category] >= threshold:
                approved = False
                if category not in violated:
                    violated.append(category)

        high_scores = [
            category
            for category, threshold in TEXT_THRESHOLDS.items()
            if normalized_scores[category] >= threshold
        ]

        # Giống logic Ollama cũ: response hợp lệ nhưng approved=false mà không score cao thì cho qua.
        # Không áp dụng cho lỗi service/parser vì đã early return ở trên.
        if not approved and not high_scores:
            approved = True
            violated = []

        reason = data.get("reason") or ""
        if not approved and not reason:
            reason = "Nội dung vi phạm quy định"

        try:
            confidence = float(data.get("confidence", 0.5))
        except Exception:
            confidence = 0.5

        return {
            "approved": approved,
            "reason": "" if approved else reason,
            "scores": normalized_scores,
            "violated_categories": [] if approved else violated,
            "confidence": confidence,
            "provider": "openrouter",
            "model": OPENROUTER_TEXT_MODEL,
        }

    def _normalize_image_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._invalid_result("AI response không phải JSON object", OPENROUTER_VISION_MODEL)

        if self._is_service_error_result(data):
            return self._service_error_result(data, OPENROUTER_VISION_MODEL)

        if "approved" not in data:
            return self._invalid_result("AI không trả về field approved", OPENROUTER_VISION_MODEL)

        if "scores" not in data or not isinstance(data.get("scores"), dict):
            return self._invalid_result("AI không trả về field scores hợp lệ", OPENROUTER_VISION_MODEL)

        scores = data.get("scores") or {}
        violated = data.get("violated_categories") or []

        if not isinstance(violated, list):
            violated = []

        normalized_scores: Dict[str, float] = {}
        for category in IMAGE_THRESHOLDS:
            try:
                normalized_scores[category] = float(scores.get(category, 0.0))
            except Exception:
                normalized_scores[category] = 0.0

        approved = bool(data.get("approved"))

        for category, threshold in IMAGE_THRESHOLDS.items():
            if normalized_scores[category] >= threshold:
                approved = False
                if category not in violated:
                    violated.append(category)

        high_scores = [
            category
            for category, threshold in IMAGE_THRESHOLDS.items()
            if normalized_scores[category] >= threshold
        ]

        if not approved and not high_scores:
            approved = True
            violated = []

        reason = data.get("reason") or ""
        if not approved and not reason:
            reason = "Hình ảnh/video vi phạm quy định"

        try:
            confidence = float(data.get("confidence", 0.5))
        except Exception:
            confidence = 0.5

        return {
            "approved": approved,
            "reason": "" if approved else reason,
            "scores": normalized_scores,
            "violated_categories": [] if approved else violated,
            "confidence": confidence,
            "provider": "openrouter",
            "model": OPENROUTER_VISION_MODEL,
        }

    def _is_service_error_result(self, data: Dict[str, Any]) -> bool:
        categories = data.get("violated_categories") or []
        if isinstance(categories, list) and any(cat in SERVICE_ERROR_CATEGORIES for cat in categories):
            return True

        reason = str(data.get("reason", "")).lower()
        service_error_keywords = [
            "ai moderation service unavailable",
            "invalid response",
            "missing approved",
            "empty response",
            "rate limited",
            "thiếu openrouter",
        ]

        return any(keyword in reason for keyword in service_error_keywords)

    def _service_error_result(self, data: Dict[str, Any], model: str) -> Dict[str, Any]:
        return {
            "approved": False,
            "reason": data.get("reason", "AI moderation service unavailable"),
            "scores": data.get("scores", {}),
            "violated_categories": data.get("violated_categories", ["moderation_error"]),
            "confidence": data.get("confidence", 0.0),
            "provider": "openrouter",
            "model": model,
        }

    def _invalid_result(self, reason: str, model: str) -> Dict[str, Any]:
        return {
            "approved": False,
            "reason": reason,
            "scores": {},
            "violated_categories": ["invalid_ai_response"],
            "confidence": 0.0,
            "provider": "openrouter",
            "model": model,
        }

    # ============================================================
    # PUBLIC METHODS
    # ============================================================
    async def moderate_text(self, content: str, content_type: str = "post") -> Dict[str, Any]:
        content = (content or "").strip()

        if len(content) < 3:
            return {
                "approved": True,
                "reason": "",
                "scores": {
                    "toxicity": 0.0,
                    "hate_speech": 0.0,
                    "violence": 0.0,
                    "sexual_content": 0.0,
                    "harassment": 0.0,
                    "self_harm": 0.0,
                    "spam": 0.0,
                },
                "violated_categories": [],
                "confidence": 1.0,
                "provider": "openrouter",
                "model": OPENROUTER_TEXT_MODEL,
            }

        self._debug(
            "[TEXT MODERATION START]",
            {
                "model": OPENROUTER_TEXT_MODEL,
                "content_type": content_type,
                "content_preview": content[:500],
            },
        )

        raw_response = await self._call_openrouter(
            prompt=self._text_prompt(content, content_type),
            model=OPENROUTER_TEXT_MODEL,
            semaphore=self.text_semaphore,
        )

        self._debug("[TEXT RAW RESPONSE]", raw_response)

        parsed = self._parse_json(raw_response, mode="text")
        self._debug("[TEXT PARSED JSON]", parsed)

        result = self._normalize_text_result(parsed)
        self._debug("[TEXT NORMALIZED RESULT]", result)

        return result

    async def moderate_image_path(self, file_path: str) -> Dict[str, Any]:
        self._debug(
            "[IMAGE MODERATION START]",
            {
                "model": OPENROUTER_VISION_MODEL,
                "file_path": file_path,
            },
        )

        raw_response = await self._call_openrouter(
            prompt=self._image_prompt(),
            model=OPENROUTER_VISION_MODEL,
            images=[file_path],
            semaphore=self.image_semaphore,
        )

        self._debug("[IMAGE RAW RESPONSE]", raw_response)

        parsed = self._parse_json(raw_response, mode="image")
        self._debug("[IMAGE PARSED JSON]", parsed)

        result = self._normalize_image_result(parsed)
        self._debug("[IMAGE NORMALIZED RESULT]", result)

        return result

    @staticmethod
    def combine_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        valid_results = [r for r in results if isinstance(r, dict)]

        if not valid_results:
            return {
                "approved": False,
                "reason": "Không có kết quả kiểm duyệt hợp lệ",
                "scores": {},
                "violated_categories": ["invalid_moderation_result"],
                "confidence": 0.0,
                "provider": "openrouter",
                "model": OPENROUTER_VISION_MODEL,
            }

        rejected = [r for r in valid_results if not r.get("approved", True)]

        if rejected:
            worst = max(
                rejected,
                key=lambda r: float(r.get("confidence", 0.0) or 0.0),
            )

            return {
                "approved": False,
                "reason": worst.get("reason", "Video có nội dung vi phạm quy định"),
                "scores": worst.get("scores", {}),
                "violated_categories": worst.get("violated_categories", []),
                "confidence": worst.get("confidence", 0.0),
                "provider": "openrouter",
                "model": worst.get("model", OPENROUTER_VISION_MODEL),
            }

        merged_scores: Dict[str, float] = {}

        for result in valid_results:
            scores = result.get("scores") or {}
            for key, value in scores.items():
                try:
                    score = float(value)
                except Exception:
                    score = 0.0

                merged_scores[key] = max(merged_scores.get(key, 0.0), score)

        return {
            "approved": True,
            "reason": "",
            "scores": merged_scores,
            "violated_categories": [],
            "confidence": 1.0,
            "provider": "openrouter",
            "model": OPENROUTER_VISION_MODEL,
        }
