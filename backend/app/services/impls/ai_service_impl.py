import json
import re
import os
import asyncio
import logging
import base64
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx
from bson import ObjectId
from dotenv import load_dotenv

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None

from services.interfaces.ai_service_interface import IAIService
from dto.ai.request.summarize_post_request import SummarizePostRequest
from dto.ai.response.summarize_post_response import SummarizePostResponse
from dto.ai.request.moderate_content_request import ModerateContentRequest
from dto.ai.response.moderate_content_response import (
    ModerateContentResponse,
    ModerationScores,
)
from repositories.post_repository import PostRepository
from core.database import db
from services.other.file_service import FileService


load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

OPENROUTER_TEXT_MODEL = os.getenv(
    "OPENROUTER_TEXT_MODEL",
    "z-ai/glm-4.5-air:free",
)

OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "google/gemini-2.5-flash-lite",
)

APP_URL = os.getenv("APP_URL", "http://localhost:5173")
APP_NAME = os.getenv("APP_NAME", "UTEZone")

AI_DEBUG = os.getenv("AI_SERVICE_DEBUG", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

AI_TEXT_CONCURRENCY = int(os.getenv("AI_TEXT_CONCURRENCY", "3"))
AI_VISION_CONCURRENCY = int(os.getenv("AI_VISION_CONCURRENCY", "2"))
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "60"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "800"))

AI_MAX_IMAGE_BYTES = int(os.getenv("AI_MAX_IMAGE_BYTES", str(6 * 1024 * 1024)))
AI_MAX_VIDEO_BYTES = int(os.getenv("AI_MAX_VIDEO_BYTES", str(80 * 1024 * 1024)))
AI_VIDEO_FRAME_COUNT = int(os.getenv("AI_VIDEO_FRAME_COUNT", "3"))

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "")


class AIServiceImpl(IAIService):
    """
    AI service dùng OpenRouter thay cho Ollama.

    Chức năng:
    - summarize_post(): tóm tắt bài đăng text, ảnh hoặc video.
    - get_existing_summary(): lấy cache summary.
    - moderate_content(): giữ lại để tương thích nếu nơi khác còn gọi IAIService cũ.

    Media flow:
    - Ảnh localhost/private MinIO:
      backend tải ảnh -> convert data:image/...;base64,... -> gửi OpenRouter.
    - Video localhost/private MinIO:
      backend tải video -> dùng FFmpeg trích frame -> convert frame data:image/jpeg;base64,... -> gửi OpenRouter.

    FFmpeg lookup:
    - FFMPEG_PATH trong .env
    - ffmpeg trong PATH
    - imageio_ffmpeg.get_ffmpeg_exe()
    - một số đường dẫn phổ biến trên Windows
    """

    MODEL = OPENROUTER_TEXT_MODEL
    VISION_MODEL = OPENROUTER_VISION_MODEL
    TEMPERATURE = 0.3
    MAX_TOKENS = AI_MAX_TOKENS

    THRESHOLD_REJECT = 0.65
    THRESHOLD_SPAM = 0.70
    THRESHOLD_SEXUAL = 0.70
    THRESHOLD_VIOLENCE = 0.60

    SYSTEM_PROMPT_SUMMARY = """Bạn là trợ lý AI cho diễn đàn sinh viên Trường Đại học Sư phạm Kỹ thuật Thành phố Hồ Chí Minh (HCMUTE).
Tóm tắt bài đăng ngắn gọn, súc tích bằng tiếng Việt trong tối đa 5 câu.
Không thêm thông tin không có trong bài viết."""

    SYSTEM_PROMPT_VISION = """Bạn là trợ lý AI cho diễn đàn sinh viên HCMUTE.
Hãy phân tích bài đăng dựa trên tiêu đề, nội dung văn bản và các hình ảnh/frame video đính kèm nếu có thể xem được.
Tóm tắt ngắn gọn, súc tích bằng tiếng Việt, tối đa 5 câu.
Không bịa nội dung nếu ảnh/frame không đọc được hoặc không liên quan."""

    SYSTEM_PROMPT_MODERATION = """Bạn là hệ thống kiểm duyệt nội dung AI cho diễn đàn sinh viên HCMUTE.
Chỉ trả về JSON hợp lệ, không markdown, không giải thích ngoài JSON."""

    def __init__(self):
        self.text_semaphore = asyncio.Semaphore(AI_TEXT_CONCURRENCY)
        self.vision_semaphore = asyncio.Semaphore(AI_VISION_CONCURRENCY)

        self._debug(
            "[AI SERVICE INIT]",
            {
                "text_model": OPENROUTER_TEXT_MODEL,
                "vision_model": OPENROUTER_VISION_MODEL,
                "ffmpeg": self._get_ffmpeg_exe(),
                "ffprobe": self._get_ffprobe_exe(),
                "imageio_ffmpeg_available": imageio_ffmpeg is not None,
            },
        )

    # ============================================================
    # DEBUG
    # ============================================================
    def _debug(self, title: str, data: Any = None):
        if not AI_DEBUG:
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
    # FFMPEG HELPERS
    # ============================================================
    def _get_ffmpeg_exe(self) -> Optional[str]:
        if FFMPEG_PATH and Path(FFMPEG_PATH).exists():
            return FFMPEG_PATH

        found = shutil.which("ffmpeg")
        if found:
            return found

        if imageio_ffmpeg is not None:
            try:
                imageio_path = imageio_ffmpeg.get_ffmpeg_exe()
                if imageio_path and Path(imageio_path).exists():
                    return imageio_path
            except Exception as e:
                logger.warning("[AI] imageio_ffmpeg get_ffmpeg_exe failed: %s", e)

        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            r"C:\Users\cdtan\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
        ]

        for p in common_paths:
            if Path(p).exists():
                return p

        return None

    def _get_ffprobe_exe(self) -> Optional[str]:
        if FFPROBE_PATH and Path(FFPROBE_PATH).exists():
            return FFPROBE_PATH

        found = shutil.which("ffprobe")
        if found:
            return found

        # imageio_ffmpeg thường chỉ đảm bảo có ffmpeg.exe, không đảm bảo ffprobe.exe.
        # Nếu không có ffprobe, service vẫn trích frame theo mốc cố định 0.5s, 2s, 5s.
        common_paths = [
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
            r"C:\Users\cdtan\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe",
        ]

        for p in common_paths:
            if Path(p).exists():
                return p

        return None

    async def _get_video_duration(self, video_path: str) -> Optional[float]:
        ffprobe = self._get_ffprobe_exe()

        if not ffprobe:
            return None

        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )

            if proc.returncode != 0:
                logger.warning("[AI] ffprobe failed: %s", proc.stderr[:300])
                return None

            value = proc.stdout.strip()
            return float(value) if value else None

        except Exception as e:
            logger.warning("[AI] Cannot get video duration: %s", e)
            return None

    async def _extract_video_frames_as_data_urls(
        self,
        *,
        video_bytes: bytes,
        source_name: str = "video.mp4",
        frame_count: int = AI_VIDEO_FRAME_COUNT,
    ) -> List[str]:
        ffmpeg = self._get_ffmpeg_exe()

        if not ffmpeg:
            logger.warning("[AI] FFmpeg not found, cannot summarize video frames")
            return []

        suffix = Path(source_name).suffix or ".mp4"

        with tempfile.TemporaryDirectory(prefix="utezone_ai_video_") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            video_path = tmp_dir_path / f"input{suffix}"
            video_path.write_bytes(video_bytes)

            duration = await self._get_video_duration(str(video_path))

            if duration and duration > 0:
                positions = [0.15, 0.50, 0.85]
                if frame_count == 1:
                    positions = [0.50]
                elif frame_count == 2:
                    positions = [0.25, 0.75]
                elif frame_count > 3:
                    positions = [
                        (i + 1) / (frame_count + 1)
                        for i in range(frame_count)
                    ]

                timestamps = [
                    max(0.0, min(duration - 0.1, duration * p))
                    for p in positions[:frame_count]
                ]
            else:
                timestamps = [0.5, 2.0, 5.0][:frame_count]

            frame_data_urls: List[str] = []

            for index, timestamp in enumerate(timestamps):
                out_path = tmp_dir_path / f"frame_{index + 1}.jpg"

                try:
                    proc = await asyncio.to_thread(
                        subprocess.run,
                        [
                            ffmpeg,
                            "-y",
                            "-ss", str(timestamp),
                            "-i", str(video_path),
                            "-frames:v", "1",
                            "-q:v", "3",
                            "-vf", "scale='min(768,iw)':-2",
                            str(out_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if proc.returncode != 0 or not out_path.exists():
                        logger.warning(
                            "[AI] ffmpeg extract frame failed at %.2fs: %s",
                            timestamp,
                            proc.stderr[:300],
                        )
                        continue

                    frame_bytes = out_path.read_bytes()

                    if not frame_bytes:
                        continue

                    if len(frame_bytes) > AI_MAX_IMAGE_BYTES:
                        logger.warning(
                            "[AI] Extracted frame too large: %s bytes",
                            len(frame_bytes),
                        )
                        continue

                    b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    frame_data_urls.append(f"data:image/jpeg;base64,{b64}")

                except Exception as e:
                    logger.warning(
                        "[AI] Extract frame exception at %.2fs: %s",
                        timestamp,
                        e,
                    )

            self._debug(
                "[AI VIDEO FRAMES EXTRACTED]",
                {
                    "ffmpeg": ffmpeg,
                    "source_name": source_name,
                    "duration": duration,
                    "requested_frames": frame_count,
                    "extracted_frames": len(frame_data_urls),
                },
            )

            return frame_data_urls

    # ============================================================
    # OPENROUTER CALL
    # ============================================================
    async def _call_openrouter(
        self,
        *,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        image_data_urls: Optional[List[str]] = None,
        temperature: float = 0.3,
        max_tokens: int = AI_MAX_TOKENS,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> str:
        if not OPENROUTER_API_KEY:
            raise RuntimeError("Thiếu OPENROUTER_API_KEY trong .env")

        sem = semaphore or self.text_semaphore

        async with sem:
            last_error = "Service unavailable"
            last_partial_content = ""

            for attempt in range(4):
                try:
                    content: List[Dict[str, Any]] = []

                    if image_data_urls:
                        for data_url in image_data_urls:
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url
                                }
                            })

                    if image_urls:
                        for url in image_urls:
                            content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": url
                                }
                            })

                    content.append({
                        "type": "text",
                        "text": prompt
                    })

                    messages: List[Dict[str, Any]] = []

                    if system_prompt:
                        messages.append({
                            "role": "system",
                            "content": system_prompt
                        })

                    messages.append({
                        "role": "user",
                        "content": content
                    })

                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }

                    self._debug(
                        "[OPENROUTER AI REQUEST]",
                        {
                            "model": model,
                            "attempt": attempt + 1,
                            "has_images": bool(image_urls or image_data_urls),
                            "image_url_count": len(image_urls or []),
                            "image_data_url_count": len(image_data_urls or []),
                            "max_tokens": max_tokens,
                            "prompt_preview": prompt[:800],
                        },
                    )

                    async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
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
                        "[OPENROUTER AI HTTP RESPONSE]",
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
                            "[OPENROUTER AI CHOICE]",
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

                            if result and str(result).strip():
                                last_partial_content = str(result)

                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue

                        if result is None or not str(result).strip():
                            last_error = "OpenRouter returned empty response"
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue

                        result_text = str(result).strip()

                        if choice.get("finish_reason") == "length":
                            last_partial_content = result_text
                            last_error = "OpenRouter response truncated because max_tokens was too low"

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

                        last_error = "OpenRouter rate limited"
                        logger.warning(
                            "[AI] Rate limited, waiting %ss attempt %s/4",
                            retry_after,
                            attempt + 1,
                        )
                        await asyncio.sleep(float(retry_after) + 2)
                        continue

                    last_error = f"OpenRouter HTTP {response.status_code}: {response.text[:500]}"
                    logger.warning("[AI] %s", last_error)
                    await asyncio.sleep(2)

                except Exception as e:
                    last_error = str(e)
                    logger.error("[AI] OpenRouter attempt %s failed: %s", attempt + 1, e)
                    await asyncio.sleep(2)

            if last_partial_content.strip():
                return last_partial_content

            raise RuntimeError(f"OpenRouter unavailable: {last_error}")

    async def _url_to_media_data_urls(self, url: str, source_name: str = "") -> List[str]:
        try:
            self._debug("[AI FETCH MEDIA URL]", url)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)

            if response.status_code != 200:
                logger.warning(
                    "[AI] Cannot fetch media URL %s: HTTP %s",
                    url,
                    response.status_code
                )
                return []

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            media_bytes = response.content

            if not media_bytes:
                logger.warning("[AI] Empty media bytes: %s", url)
                return []

            lowered = (source_name or url).lower()

            if not content_type or content_type == "application/octet-stream":
                if ".png" in lowered:
                    content_type = "image/png"
                elif ".webp" in lowered:
                    content_type = "image/webp"
                elif ".gif" in lowered:
                    content_type = "image/gif"
                elif ".jpg" in lowered or ".jpeg" in lowered:
                    content_type = "image/jpeg"
                elif ".mp4" in lowered:
                    content_type = "video/mp4"
                elif ".mov" in lowered:
                    content_type = "video/quicktime"
                elif ".webm" in lowered:
                    content_type = "video/webm"
                elif ".avi" in lowered:
                    content_type = "video/x-msvideo"

            if content_type.startswith("image/"):
                if len(media_bytes) > AI_MAX_IMAGE_BYTES:
                    logger.warning(
                        "[AI] Image too large: %s bytes, max=%s, url=%s",
                        len(media_bytes),
                        AI_MAX_IMAGE_BYTES,
                        url
                    )
                    return []

                b64 = base64.b64encode(media_bytes).decode("utf-8")
                data_url = f"data:{content_type};base64,{b64}"

                self._debug(
                    "[AI IMAGE CONVERTED TO DATA URL]",
                    {
                        "content_type": content_type,
                        "bytes": len(media_bytes),
                        "data_url_length": len(data_url),
                    }
                )

                return [data_url]

            if content_type.startswith("video/") or any(
                ext in lowered for ext in [".mp4", ".mov", ".webm", ".avi", ".mkv"]
            ):
                if len(media_bytes) > AI_MAX_VIDEO_BYTES:
                    logger.warning(
                        "[AI] Video too large: %s bytes, max=%s, url=%s",
                        len(media_bytes),
                        AI_MAX_VIDEO_BYTES,
                        url
                    )
                    return []

                return await self._extract_video_frames_as_data_urls(
                    video_bytes=media_bytes,
                    source_name=source_name or "video.mp4",
                    frame_count=AI_VIDEO_FRAME_COUNT,
                )

            logger.warning(
                "[AI] Unsupported media type: %s url=%s",
                content_type,
                url
            )
            return []

        except Exception as e:
            logger.warning("[AI] Convert media URL to data URLs failed: %s", e)
            return []

    # ============================================================
    # SUMMARIZATION
    # ============================================================
    async def summarize_post(self, req: SummarizePostRequest) -> SummarizePostResponse:
        try:
            try:
                obj_id = ObjectId(req.post_id)
            except Exception:
                return self._error_response(req.post_id, "Invalid post_id format")

            post = await PostRepository.find_by_id(req.post_id)

            if not post:
                return self._error_response(req.post_id, "Post not found")

            title = post.get("title", "")
            content = post.get("content", "")
            media_files = post.get("thumbnails", []) or []

            if not req.force_refresh and post.get("ai_summary"):
                return SummarizePostResponse(
                    success=True,
                    post_id=req.post_id,
                    title=title,
                    summary=post["ai_summary"],
                    original_content=content,
                    generated_at=str(post.get("ai_summary_generated_at", "")),
                    cached=True
                )

            if media_files and len(media_files) > 0:
                summary = await self._call_openrouter_with_media(
                    title=title,
                    content=content,
                    media_files=media_files
                )
                has_vision = True
                model_used = OPENROUTER_VISION_MODEL
            else:
                text_to_summarize = content if content else title

                if len(text_to_summarize.strip()) < 30:
                    summary = text_to_summarize if text_to_summarize else "Không có nội dung"
                else:
                    summary = await self._call_openrouter_text(
                        title=title,
                        content=content
                    )

                has_vision = False
                model_used = OPENROUTER_TEXT_MODEL

            await db.post.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "ai_summary": summary,
                        "ai_summary_generated_at": datetime.utcnow(),
                        "ai_summary_model": model_used,
                        "ai_summary_provider": "openrouter",
                        "ai_summary_has_vision": has_vision,
                    }
                }
            )

            return SummarizePostResponse(
                success=True,
                post_id=req.post_id,
                title=title,
                summary=summary,
                original_content=content,
                generated_at=datetime.utcnow().isoformat(),
                cached=False
            )

        except Exception as e:
            logger.error("[AI] summarize_post failed: %s", e)
            return self._error_response(req.post_id, str(e))

    async def get_existing_summary(self, post_id: str) -> Optional[SummarizePostResponse]:
        try:
            post = await PostRepository.find_by_id(post_id)

            if not post or not post.get("ai_summary"):
                return None

            return SummarizePostResponse(
                success=True,
                post_id=post_id,
                title=post.get("title", ""),
                summary=post["ai_summary"],
                original_content=post.get("content", ""),
                generated_at=str(post.get("ai_summary_generated_at", "")),
                cached=True
            )

        except Exception:
            return None

    async def _call_openrouter_text(self, title: str, content: str) -> str:
        truncated = content[:1500] + "..." if len(content) > 1500 else content

        prompt = f"""Tóm tắt bài đăng sau bằng tiếng Việt.

YÊU CẦU:
- Tối đa 5 câu.
- Ngắn gọn, dễ hiểu.
- Không bịa thêm thông tin.
- Nếu nội dung quá ngắn thì diễn đạt lại ngắn gọn.
- Không markdown, không bullet nếu không cần thiết.

TIÊU ĐỀ:
{title}

NỘI DUNG:
{truncated}

TÓM TẮT:"""

        try:
            response = await self._call_openrouter(
                prompt=prompt,
                model=OPENROUTER_TEXT_MODEL,
                system_prompt=self.SYSTEM_PROMPT_SUMMARY,
                temperature=self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
                semaphore=self.text_semaphore,
            )

            summary = self._clean_summary(response)

            if len(summary) > 500:
                summary = summary[:497] + "..."

            return summary if summary else "Không thể tóm tắt bài viết này"

        except Exception as e:
            logger.error("[AI] OpenRouter text summary error: %s", e)
            fallback = content[:100] + "..." if len(content) > 100 else content
            return fallback if fallback else title or "Không có nội dung"

    async def _call_openrouter_with_media(
        self,
        title: str,
        content: str,
        media_files: List[str]
    ) -> str:
        image_data_urls: List[str] = []
        media_count = 0

        for file_id in media_files[:3]:
            try:
                url = FileService.get_file_url(file_id, expires_seconds=300)
                print("[AI SUMMARY MEDIA URL]", url)

                data_urls = await self._url_to_media_data_urls(
                    url,
                    source_name=str(file_id),
                )

                if data_urls:
                    image_data_urls.extend(data_urls)
                    media_count += 1
                else:
                    logger.warning("[AI] Cannot convert media to data URLs: %s", file_id)

            except Exception as e:
                logger.warning("[AI] Error getting media for %s: %s", file_id, e)

        max_visual_inputs = max(1, min(6, AI_VIDEO_FRAME_COUNT * 2))
        image_data_urls = image_data_urls[:max_visual_inputs]

        if not image_data_urls:
            logger.warning("[AI] No readable media frames/images, fallback to text summary")
            return await self._call_openrouter_text(title, content)

        truncated = content[:1000] + "..." if len(content) > 1000 else content

        prompt = f"""Phân tích và tóm tắt bài đăng sau bằng tiếng Việt.

YÊU CẦU:
- Tối đa 5 câu.
- Kết hợp thông tin từ tiêu đề, nội dung văn bản và hình ảnh/frame video.
- Nếu tiêu đề/nội dung rỗng, hãy tóm tắt dựa trên hình ảnh/frame video.
- Nếu đây là video, các hình ảnh gửi kèm là một vài frame đại diện, hãy mô tả nội dung có thể quan sát được từ các frame đó.
- Không bịa thêm thông tin ngoài những gì quan sát được.
- Không markdown, không bullet nếu không cần thiết.

TIÊU ĐỀ:
{title}

NỘI DUNG:
{truncated}

SỐ MEDIA GỐC:
{media_count}

SỐ ẢNH/FRAME GỬI CHO MODEL:
{len(image_data_urls)}

TÓM TẮT:"""

        try:
            response = await self._call_openrouter(
                prompt=prompt,
                model=OPENROUTER_VISION_MODEL,
                system_prompt=self.SYSTEM_PROMPT_VISION,
                image_data_urls=image_data_urls,
                temperature=self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
                semaphore=self.vision_semaphore,
            )

            summary = self._clean_summary(response)

            if len(summary) > 800:
                summary = summary[:797] + "..."

            return summary if summary else "Không thể phân tích bài viết này"

        except Exception as e:
            logger.error("[AI] OpenRouter media summary error: %s", e)
            return await self._call_openrouter_text(title, content)

    def _clean_summary(self, text: str) -> str:
        text = (text or "").strip()

        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        prefixes = [
            "TÓM TẮT:",
            "Tóm tắt:",
            "Summary:",
            "SUMMARY:",
        ]

        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        return text.strip()

    def _error_response(self, post_id: str, error: str) -> SummarizePostResponse:
        return SummarizePostResponse(
            success=False,
            post_id=post_id,
            title="",
            summary="",
            original_content="",
            error_message=error
        )
