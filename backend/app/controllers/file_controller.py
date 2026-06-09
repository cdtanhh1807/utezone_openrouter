from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from services.other.file_service import FileService
from core.openrouter_moderation_service import OpenRouterModerationService

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

router = APIRouter()

_ffmpeg_exe = None
moderation_service = OpenRouterModerationService()

# Tách semaphore theo loại để không còn chạy tuần tự toàn hệ thống.
# Với free model, nên để thấp để tránh 429. Khi nạp credit/pay-as-you-go có thể tăng dần.
text_semaphore = asyncio.Semaphore(int(os.getenv("MODERATION_TEXT_CONCURRENCY", "3")))
image_semaphore = asyncio.Semaphore(int(os.getenv("MODERATION_IMAGE_CONCURRENCY", "2")))
video_semaphore = asyncio.Semaphore(int(os.getenv("MODERATION_VIDEO_CONCURRENCY", "1")))
batch_semaphore = asyncio.Semaphore(int(os.getenv("UPLOAD_BATCH_CONCURRENCY", "3")))


# ==================== FFMPEG helpers ====================
def get_ffmpeg_exe():
    global _ffmpeg_exe

    if _ffmpeg_exe:
        return _ffmpeg_exe

    try:
        import imageio_ffmpeg
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[FFMPEG] Found: {_ffmpeg_exe}")
        return _ffmpeg_exe
    except ImportError:
        pass
    except Exception as e:
        print(f"[FFMPEG] imageio_ffmpeg error: {e}")

    _ffmpeg_exe = shutil.which("ffmpeg")
    if _ffmpeg_exe:
        print(f"[FFMPEG] Found in PATH: {_ffmpeg_exe}")
        return _ffmpeg_exe

    raise FileNotFoundError("ffmpeg not found")


def get_video_duration(file_path: str) -> float:
    ffmpeg = get_ffmpeg_exe()
    cmd = [ffmpeg, "-i", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    output = result.stderr + result.stdout

    match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", output)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)

    raise ValueError("Cannot parse duration")


def extract_text_from_file(file_path: str, file_ext: str) -> str:
    text = ""

    try:
        if file_ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        elif file_ext == ".docx":
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])

        elif file_ext == ".pdf":
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""

        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

    except Exception as e:
        print(f"[EXTRACT] Error: {e}")
        text = ""

    return text[:8000]


def _approved_result(reason: str = "") -> dict:
    return {
        "approved": True,
        "reason": reason,
        "scores": {},
        "violated_categories": [],
        "confidence": 1.0,
        "provider": "openrouter",
        "model": None,
    }


def _failed_result(reason: str, category: str = "moderation_unavailable") -> dict:
    return {
        "approved": False,
        "reason": reason,
        "scores": {},
        "violated_categories": [category],
        "confidence": 0.0,
        "provider": "openrouter",
        "model": None,
    }


# ==================== MODERATION TEXT/DOCUMENT ====================
async def _moderate_text_file(file_path: str, filename: str) -> dict:
    ext = os.path.splitext(filename)[1].lower()
    content = extract_text_from_file(file_path, ext)

    if not content.strip():
        return _approved_result("Không trích xuất được text hoặc file không có nội dung text")

    async with text_semaphore:
        for attempt in range(2):
            try:
                return await moderation_service.moderate_text(
                    content=content,
                    content_type="document",
                )
            except Exception as e:
                print(f"[TEXT_MOD] Attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    await asyncio.sleep(1)

    return _failed_result("Không thể kiểm duyệt file văn bản lúc này")


# ==================== MODERATION IMAGE ====================
async def _moderate_image_file(file_path: str, filename: str) -> dict:
    async with image_semaphore:
        for attempt in range(2):
            try:
                return await moderation_service.moderate_image_path(file_path)
            except Exception as e:
                print(f"[IMAGE_MOD] Attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    await asyncio.sleep(1)

    return _failed_result("Không thể kiểm duyệt hình ảnh lúc này")


# ==================== MODERATION VIDEO ====================
async def _moderate_video_file(file_path: str, filename: str) -> dict:
    print(f"[VIDEO_MOD] Start {filename}")
    frame_paths = []

    try:
        duration = get_video_duration(file_path)
        ffmpeg = get_ffmpeg_exe()

        # Free model dễ bị limit, nên lấy 3 frame trước. Có thể tăng lên 5 nếu đã nạp credit.
        positions = [duration * 0.1, duration * 0.5, duration * 0.9]

        for i, pos in enumerate(positions):
            frame_path = f"{file_path}_frame_{i}.jpg"
            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(pos),
                "-i", file_path,
                "-vframes", "1",
                "-q:v", "2",
                "-vf", "scale=640:-1",
                frame_path,
            ]

            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                timeout=30
            )

            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 100:
                frame_paths.append(frame_path)
                print(f"[VIDEO_MOD] Frame {i + 1} OK")
            else:
                print(f"[VIDEO_MOD] Frame {i + 1} FAILED")

        if not frame_paths:
            return _failed_result("Không thể trích xuất frame từ video", "video_frame_extract_failed")

        async with video_semaphore:
            # Các frame trong 1 video được gửi song song,
            # nhưng video_semaphore giới hạn số video cùng lúc.
            tasks = [
                moderation_service.moderate_image_path(p)
                for p in frame_paths
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []

        for r in results:
            if isinstance(r, Exception):
                print(f"[VIDEO_MOD] Frame moderation error: {r}")
            else:
                valid_results.append(r)

        if not valid_results:
            return _failed_result("Không thể kiểm duyệt video lúc này")

        return moderation_service.combine_results(valid_results)

    except Exception as e:
        print(f"[VIDEO_MOD] Error: {e}")
        return _failed_result(f"Lỗi xử lý video: {str(e)}", "video_processing_error")

    finally:
        for p in frame_paths:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


def _detect_media_type(filename: str, content_type: str) -> str:
    ext = Path(filename).suffix.lower()

    if content_type:
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"

    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return "image"

    if ext in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        return "video"

    if ext in {".txt", ".docx", ".pdf", ".md", ".rtf"}:
        return "document"

    return "other"


async def _upload_to_storage_from_bytes(file: UploadFile, file_content: bytes) -> dict:
    file.file = BytesIO(file_content)
    file.size = len(file_content)

    try:
        file.file.seek(0)
    except Exception:
        pass

    print("[UPLOAD_TO_STORAGE] filename =", file.filename)
    print("[UPLOAD_TO_STORAGE] size =", len(file_content))

    file_id = await FileService.upload_file(file)

    print("[UPLOAD_TO_STORAGE] file_id =", file_id)
    print("[UPLOAD_TO_STORAGE] url =", FileService.get_file_url(file_id))

    return {
        "file_id": file_id,
        "url": FileService.get_file_url(file_id),
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    defer_moderation: bool = Query(False)
):
    """
    Upload file.

    Mặc định:
    - /file/upload
    - defer_moderation=False
    - Kiểm duyệt đồng bộ trước khi upload.
    - Dùng cho đăng bài.

    Optimistic comment/reply:
    - /file/upload?defer_moderation=true
    - Upload ngay, không chờ AI.
    - Trả file_id với pending_moderation=True.
    - CommentServiceImpl sẽ kiểm duyệt file_id trong background.
    """
    filename = file.filename or ""
    content_type = file.content_type or ""
    media_type = _detect_media_type(filename, content_type)

    print(
        f"[UPLOAD] {filename} -> {media_type}, "
        f"defer_moderation={defer_moderation}"
    )

    file_content = await file.read()

    if len(file_content) == 0:
        raise HTTPException(400, "File rỗng")

    # ========================================================
    # DEFER MODERATION FLOW
    # Dùng cho comment/reply để UX mượt:
    # upload ngay, trả file_id ngay, không gọi AI ở endpoint upload.
    # ========================================================
    if defer_moderation:
        uploaded = await _upload_to_storage_from_bytes(file, file_content)

        return {
            **uploaded,
            "pending_moderation": True,
            "media_type": media_type,
            "moderation_mode": "deferred",
        }

    # ========================================================
    # STRICT MODERATION FLOW
    # Giữ nguyên cho đăng bài và các chỗ gọi cũ.
    # ========================================================
    ext = os.path.splitext(filename)[1].lower()
    fd, tmp_path = tempfile.mkstemp(suffix=ext)

    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(file_content)
            tmp.flush()
            os.fsync(fd)

        if media_type == "image":
            result = await _moderate_image_file(tmp_path, filename)

        elif media_type == "video":
            result = await _moderate_video_file(tmp_path, filename)

        elif media_type == "document":
            result = await _moderate_text_file(tmp_path, filename)

        else:
            result = _approved_result("Loại file không kiểm duyệt bằng AI")

        print(
            f"[UPLOAD] Result: approved={result['approved']}, "
            f"reason={result.get('reason', '')}"
        )

        if not result["approved"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File không được phép upload",
                    "reason": result.get("reason", "Nội dung vi phạm quy định"),
                    "violated_categories": result.get("violated_categories", []),
                    "scores": result.get("scores", {}),
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                },
            )

    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    uploaded = await _upload_to_storage_from_bytes(file, file_content)

    return {
        **uploaded,
        "pending_moderation": False,
        "media_type": media_type,
        "moderation_mode": "strict",
    }


@router.post("/upload/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    defer_moderation: bool = Query(False)
):
    """
    Batch upload.

    - /file/upload/batch
      strict moderation, dùng cho đăng bài.

    - /file/upload/batch?defer_moderation=true
      upload nhanh, dùng cho comment/reply nhiều file.
    """
    print(
        f"[BATCH] Processing {len(files)} files, "
        f"defer_moderation={defer_moderation}"
    )

    async def process_one(f: UploadFile):
        async with batch_semaphore:
            try:
                r = await upload_file(
                    f,
                    defer_moderation=defer_moderation
                )

                return {
                    "success": True,
                    "filename": f.filename,
                    "data": r,
                }

            except HTTPException as e:
                if isinstance(e.detail, dict):
                    detail = (
                        e.detail.get("reason")
                        or e.detail.get("error")
                        or str(e.detail)
                    )
                    violated = e.detail.get("violated_categories", [])
                    scores = e.detail.get("scores", {})
                else:
                    detail = str(e.detail)
                    violated = []
                    scores = {}

                return {
                    "success": False,
                    "filename": f.filename,
                    "error": detail,
                    "violated_categories": violated,
                    "scores": scores,
                }

            except Exception as e:
                return {
                    "success": False,
                    "filename": f.filename,
                    "error": f"System: {str(e)}",
                }

    results = await asyncio.gather(
        *[process_one(f) for f in files],
        return_exceptions=False
    )

    return {
        "success": all(r["success"] for r in results),
        "total": len(files),
        "passed": sum(r["success"] for r in results),
        "rejected": sum(not r["success"] for r in results),
        "pending_moderation": defer_moderation,
        "moderation_mode": "deferred" if defer_moderation else "strict",
        "results": results,
    }


@router.get("/file/{file_id}")
async def get_file(file_id: str):
    return {"url": FileService.get_file_url(file_id)}


@router.post("/upload_from_crawl")
async def upload_file_from_crawl(file: UploadFile = File(...)):
    file_id = await FileService.upload_file(file)

    return {
        "file_id": file_id,
        "url": FileService.get_file_url(file_id),
        "pending_moderation": False,
        "media_type": _detect_media_type(file.filename or "", file.content_type or ""),
        "moderation_mode": "bypass_crawl",
    }
