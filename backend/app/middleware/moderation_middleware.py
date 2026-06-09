from fastapi import HTTPException

from core.openrouter_moderation_service import OpenRouterModerationService


class ModerationMiddleware:
    """
    Middleware kiểm duyệt text cho post/comment bằng OpenRouter.
    Trả về dict thống nhất thay vì Pydantic response cũ để giảm phụ thuộc vào AIServiceImpl/Ollama.
    """

    def __init__(self):
        self._service = OpenRouterModerationService()

    async def check_and_enforce(
        self,
        content: str,
        content_type: str = "post",
        author_id: str = None,
        skip_short_content: bool = True,
    ) -> dict:
        if skip_short_content and len((content or "").strip()) < 3:
            return {
                "success": True,
                "content_type": content_type,
                "approved": True,
                "reason": "Nội dung quá ngắn",
                "confidence": 1.0,
                "scores": {},
                "violated_categories": [],
                "provider": "openrouter",
                "model": None,
            }

        result = await self._service.moderate_text(
            content=content,
            content_type=content_type,
        )

        if not result["approved"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Nội dung không được phép đăng",
                    "reason": result["reason"],
                    "violated_categories": result["violated_categories"],
                    "scores": result["scores"],
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "suggestion": "Vui lòng chỉnh sửa nội dung theo hướng dẫn và thử lại.",
                },
            )

        return result

    async def check_only(
        self,
        content: str,
        content_type: str = "post",
    ) -> dict:
        if len((content or "").strip()) < 3:
            return {
                "success": True,
                "content_type": content_type,
                "approved": True,
                "reason": "Nội dung quá ngắn",
                "confidence": 1.0,
                "scores": {},
                "violated_categories": [],
                "provider": "openrouter",
                "model": None,
            }

        return await self._service.moderate_text(
            content=content,
            content_type=content_type,
        )


_moderation_instance = None


def get_moderation_middleware() -> ModerationMiddleware:
    global _moderation_instance
    if _moderation_instance is None:
        _moderation_instance = ModerationMiddleware()
    return _moderation_instance
