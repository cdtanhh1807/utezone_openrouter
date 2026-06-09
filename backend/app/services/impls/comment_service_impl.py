from datetime import datetime, timezone
import uuid
import asyncio
import tempfile
import os
from typing import List, Optional, Any, Dict, Tuple

import httpx

from dto.comment.request.add_comment_request import AddCommentRequest
from dto.comment.request.add_commentreply_request import AddCommentReplyRequest
from dto.comment.request.get_commentreply_request import GetCommentReplyRequest
from dto.comment.request.update_status_comment_reply_request import UpdateStatusCommentReplyRequest
from dto.comment.response.add_comment_response import AddCommentResponse
from dto.comment.response.add_commentreply_response import AddCommentReplyResponse
from dto.comment.response.get_commentreply_response import GetCommentReplyResponse
from dto.comment.response.update_status_comment_reply_response import UpdateStatusCommentReplyResponse

from middleware.moderation_middleware import get_moderation_middleware

from models.account_model import Account
from models.announce_model import Announce
from models.commentreply_model import CommentReply
from models.post_model import CommentReact, Post
from models.base_model import bson_to_dict

from repositories.account_repository import AccountRepository
from repositories.announce_repository import AnnounceRepository
from repositories.comment_repository import CommentRepository
from repositories.commentreply_repository import CommentReplyRepository
from repositories.post_repository import PostRepository

from services.interfaces.comment_service_interface import ICommentService
from services.other.file_service import FileService


class CommentServiceImpl(ICommentService):
    """
    Comment service với flow optimistic moderation cho cả text + media.

    Flow:
    - Frontend upload file comment/reply bằng:
        /file/upload?defer_moderation=true
      hoặc:
        /file/upload/batch?defer_moderation=true

    - Upload API trả file_id ngay, không chờ AI.
    - Frontend gửi comment/reply với thumbnails=[file_id,...].
    - Backend lưu comment/reply ngay để UX mượt.
    - Background task kiểm duyệt:
        + text content
        + media trong thumbnails: image/video/document
    - Nếu vi phạm thì đổi status comment/reply thành hidden.

    Lưu ý:
    - asyncio.create_task chỉ sống theo process FastAPI hiện tại.
    - Production nên chuyển sang Celery/RQ/Redis để tránh mất task khi restart server.
    """

    # ============================================================
    # TEXT MODERATION HELPERS
    # ============================================================
    def _get_mod_value(self, mod_result: Any, key: str, default: Any = None) -> Any:
        if isinstance(mod_result, dict):
            return mod_result.get(key, default)
        return getattr(mod_result, key, default)

    def _get_scores(self, mod_result: Any) -> Dict[str, Any]:
        if isinstance(mod_result, dict):
            return mod_result.get("scores", {}) or {}

        scores = getattr(mod_result, "scores", None)
        if scores is None:
            return {}

        if hasattr(scores, "model_dump"):
            return scores.model_dump()

        if isinstance(scores, dict):
            return scores

        return {}

    async def _check_comment_text_only(
        self,
        content: str,
        content_type: str = "comment"
    ) -> Dict[str, Any]:
        """
        Chỉ kiểm duyệt text và trả kết quả, không raise.
        Dùng cho background task.
        """
        content = (content or "").strip()

        if not content:
            return {
                "approved": True,
                "reason": "",
                "scores": {},
                "violated_categories": [],
                "confidence": 1.0,
                "provider": "openrouter",
                "model": None,
            }

        moderation = get_moderation_middleware()
        mod_result = await moderation.check_only(
            content=content,
            content_type=content_type
        )

        if not isinstance(mod_result, dict):
            return {
                "approved": self._get_mod_value(mod_result, "approved", False),
                "reason": self._get_mod_value(mod_result, "reason", ""),
                "scores": self._get_scores(mod_result),
                "violated_categories": self._get_mod_value(mod_result, "violated_categories", []),
                "confidence": self._get_mod_value(mod_result, "confidence", 0.0),
                "provider": self._get_mod_value(mod_result, "provider", None),
                "model": self._get_mod_value(mod_result, "model", None),
            }

        return mod_result

    # ============================================================
    # MEDIA MODERATION HELPERS
    # ============================================================
    async def _download_file_id_to_temp(self, file_id: str) -> Tuple[Optional[str], str, str]:
        """
        Tải file đã upload từ FileService presigned URL về temp file.

        Lý do:
        - Comment/reply dùng defer_moderation=true nên file đã nằm trong MinIO.
        - Background task chỉ có file_id trong thumbnails.
        - Cần tải file đó về temp path để dùng lại các hàm moderation trong file_controller.
        """
        url = FileService.get_file_url(file_id, expires_seconds=300)

        print("\n========== [COMMENT MEDIA FETCH URL] ==========")
        print(url)
        print("========== END [COMMENT MEDIA FETCH URL] ==========\n")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)

        if response.status_code != 200:
            print(
                f"[COMMENT_MEDIA_MOD] Cannot fetch file_id={file_id}, "
                f"HTTP={response.status_code}"
            )
            return None, str(file_id), ""

        content_type = response.headers.get("content-type", "")
        filename = str(file_id).split("?")[0].split("/")[-1]

        ext = os.path.splitext(filename)[1].lower()

        if not ext:
            if content_type.startswith("image/"):
                ext = ".jpg"
            elif content_type.startswith("video/"):
                ext = ".mp4"
            elif content_type == "application/pdf":
                ext = ".pdf"
            else:
                ext = ".bin"

        fd, tmp_path = tempfile.mkstemp(suffix=ext)

        with os.fdopen(fd, "wb") as f:
            f.write(response.content)
            f.flush()
            os.fsync(fd)

        return tmp_path, filename, content_type

    async def _moderate_one_uploaded_file(self, file_id: str) -> Dict[str, Any]:
        """
        Kiểm duyệt 1 file đã upload.

        Import lazy từ controllers.file_controller để tận dụng lại logic hiện có:
        - _detect_media_type
        - _moderate_image_file
        - _moderate_video_file
        - _moderate_text_file

        Lưu ý:
        - Đây là background task, không raise ra ngoài request.
        """
        tmp_path = None

        try:
            from controllers.file_controller import (
                _detect_media_type,
                _moderate_image_file,
                _moderate_video_file,
                _moderate_text_file,
            )

            tmp_path, filename, content_type = await self._download_file_id_to_temp(file_id)

            if not tmp_path:
                return {
                    "approved": False,
                    "reason": "Không thể tải file để kiểm duyệt",
                    "scores": {},
                    "violated_categories": ["file_fetch_error"],
                    "confidence": 0.0,
                    "file_id": file_id,
                }

            media_type = _detect_media_type(filename, content_type)

            print("\n========== [COMMENT MEDIA MODERATION START] ==========")
            print(f"[FILE_ID] {file_id}")
            print(f"[FILENAME] {filename}")
            print(f"[CONTENT_TYPE] {content_type}")
            print(f"[MEDIA_TYPE] {media_type}")
            print("========== END [COMMENT MEDIA MODERATION START] ==========\n")

            if media_type == "image":
                result = await _moderate_image_file(tmp_path, filename)

            elif media_type == "video":
                result = await _moderate_video_file(tmp_path, filename)

            elif media_type == "document":
                result = await _moderate_text_file(tmp_path, filename)

            else:
                result = {
                    "approved": True,
                    "reason": "Loại file không kiểm duyệt bằng AI",
                    "scores": {},
                    "violated_categories": [],
                    "confidence": 1.0,
                    "provider": "openrouter",
                    "model": None,
                }

            result["file_id"] = file_id
            result["media_type"] = media_type

            print("\n========== [COMMENT MEDIA MODERATION RESULT] ==========")
            print(result)
            print("========== END [COMMENT MEDIA MODERATION RESULT] ==========\n")

            return result

        except Exception as e:
            print(f"[COMMENT_MEDIA_MOD_ERROR] file_id={file_id}: {e}")

            return {
                "approved": False,
                "reason": f"Lỗi kiểm duyệt file: {str(e)}",
                "scores": {},
                "violated_categories": ["media_moderation_error"],
                "confidence": 0.0,
                "file_id": file_id,
            }

        finally:
            if tmp_path:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass

    async def _check_comment_media_files(
        self,
        file_ids: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Kiểm duyệt tất cả file trong thumbnails.
        Nếu bất kỳ file nào reject => reject comment/reply.
        """
        file_ids = file_ids or []

        if not file_ids:
            return {
                "approved": True,
                "reason": "",
                "violated_categories": [],
                "files": [],
            }

        tasks = [
            self._moderate_one_uploaded_file(file_id)
            for file_id in file_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        normalized_results = []
        rejected = []

        for item in results:
            if isinstance(item, Exception):
                result = {
                    "approved": False,
                    "reason": str(item),
                    "violated_categories": ["media_moderation_error"],
                    "file_id": None,
                }
            else:
                result = item

            normalized_results.append(result)

            if not result.get("approved", True):
                rejected.append(result)

        if rejected:
            first = rejected[0]
            return {
                "approved": False,
                "reason": first.get("reason", "File đính kèm vi phạm quy định"),
                "violated_categories": first.get("violated_categories", []),
                "files": normalized_results,
            }

        return {
            "approved": True,
            "reason": "",
            "violated_categories": [],
            "files": normalized_results,
        }

    # ============================================================
    # HIDE HELPERS
    # ============================================================
    async def _hide_root_comment(
        self,
        *,
        post_id: str,
        comment_id: str,
        reason: str
    ) -> None:
        """
        Ẩn comment gốc.

        Ưu tiên PostRepository.update_comment_status vì code hiện tại của bạn
        đang thử dùng hàm này ở background moderation.
        """
        try:
            await PostRepository.update_comment_status(
                post_id,
                comment_id,
                "hidden"
            )
            return

        except Exception as e:
            print(f"[COMMENT_MODERATION] PostRepository.update_comment_status failed: {e}")

        # Fallback nếu project của bạn có hàm ở CommentRepository.
        try:
            if hasattr(CommentRepository, "update_comment_status"):
                await CommentRepository.update_comment_status(
                    post_id,
                    comment_id,
                    "hidden"
                )
                return

        except Exception as e:
            print(f"[COMMENT_MODERATION] CommentRepository.update_comment_status failed: {e}")

        print(
            "[COMMENT_MODERATION] Missing repository method to hide root comment. "
            f"post_id={post_id}, comment_id={comment_id}, reason={reason}"
        )

    async def _hide_child_replies_by_parent(
        self,
        *,
        post_id: str,
        parent_comment_id: str
    ) -> None:
        """
        Nếu root comment bị ẩn thì nên ẩn luôn reply con.
        Nếu repository chưa có hàm này thì bỏ qua, không crash.
        """
        try:
            await CommentReplyRepository.update_comment_status_by_parent(
                post_id=post_id,
                parent_comment_id=parent_comment_id,
                status="hidden"
            )
        except Exception as e:
            print(f"[COMMENT_MODERATION] update_comment_status_by_parent skipped/failed: {e}")

    async def _hide_comment_reply(
        self,
        *,
        post_id: str,
        comment_id: str,
        path: str,
        reason: str
    ) -> None:
        try:
            await CommentReplyRepository.update_comment_status(
                post_id,
                comment_id,
                path,
                "hidden"
            )

        except Exception as e:
            print(f"[COMMENT_REPLY_MODERATION] update_comment_status failed: {e}")

    # ============================================================
    # BACKGROUND MODERATION
    # ============================================================
    async def _moderate_root_comment_in_background(
        self,
        *,
        post_id: str,
        comment_id: str,
        content: str,
        user_id: str,
        thumbnails: Optional[List[str]] = None,
    ) -> None:
        """
        Background moderation cho comment gốc.

        Kiểm duyệt:
        - text content
        - media thumbnails

        Nếu vi phạm:
        - đổi status comment thành hidden
        - cố gắng ẩn reply con
        """
        try:
            print("\n========== [COMMENT BACKGROUND MODERATION START] ==========")
            print(f"[POST_ID] {post_id}")
            print(f"[COMMENT_ID] {comment_id}")
            print(f"[USER_ID] {user_id}")
            print(f"[CONTENT_PREVIEW] {(content or '')[:500]}")
            print(f"[THUMBNAILS] {thumbnails or []}")
            print("========== END [COMMENT BACKGROUND MODERATION START] ==========\n")

            text_result = await self._check_comment_text_only(
                content=content,
                content_type="comment"
            )

            media_result = await self._check_comment_media_files(thumbnails)

            print("\n========== [COMMENT BACKGROUND MODERATION RESULT] ==========")
            print({
                "text": text_result,
                "media": media_result,
            })
            print("========== END [COMMENT BACKGROUND MODERATION RESULT] ==========\n")

            text_approved = bool(text_result.get("approved", False))
            media_approved = bool(media_result.get("approved", False))

            if text_approved and media_approved:
                return

            if not text_approved:
                reason = text_result.get("reason", "Nội dung bình luận vi phạm quy định")
            else:
                reason = media_result.get("reason", "File đính kèm vi phạm quy định")

            print("\n========== [COMMENT REMOVED BY BACKGROUND MODERATION] ==========")
            print(f"[POST_ID] {post_id}")
            print(f"[COMMENT_ID] {comment_id}")
            print(f"[REASON] {reason}")
            print("========== END [COMMENT REMOVED BY BACKGROUND MODERATION] ==========\n")

            await self._hide_root_comment(
                post_id=post_id,
                comment_id=comment_id,
                reason=reason
            )

            await self._hide_child_replies_by_parent(
                post_id=post_id,
                parent_comment_id=comment_id
            )

            # TODO websocket:
            # await ws_manager.broadcast_post(post_id, {
            #     "type": "comment_removed",
            #     "post_id": post_id,
            #     "comment_id": comment_id,
            #     "reason": reason,
            # })

        except Exception as e:
            print(f"[COMMENT_BACKGROUND_MODERATION_ERROR] {post_id}/{comment_id}: {e}")

    async def _moderate_comment_reply_in_background(
        self,
        *,
        post_id: str,
        comment_id: str,
        path: str,
        content: str,
        user_id: str,
        thumbnails: Optional[List[str]] = None,
    ) -> None:
        """
        Background moderation cho comment reply.

        Kiểm duyệt:
        - text content
        - media thumbnails

        Nếu vi phạm:
        - đổi status reply thành hidden.
        """
        try:
            print("\n========== [COMMENT REPLY BACKGROUND MODERATION START] ==========")
            print(f"[POST_ID] {post_id}")
            print(f"[COMMENT_ID] {comment_id}")
            print(f"[PATH] {path}")
            print(f"[USER_ID] {user_id}")
            print(f"[CONTENT_PREVIEW] {(content or '')[:500]}")
            print(f"[THUMBNAILS] {thumbnails or []}")
            print("========== END [COMMENT REPLY BACKGROUND MODERATION START] ==========\n")

            text_result = await self._check_comment_text_only(
                content=content,
                content_type="comment"
            )

            media_result = await self._check_comment_media_files(thumbnails)

            print("\n========== [COMMENT REPLY BACKGROUND MODERATION RESULT] ==========")
            print({
                "text": text_result,
                "media": media_result,
            })
            print("========== END [COMMENT REPLY BACKGROUND MODERATION RESULT] ==========\n")

            text_approved = bool(text_result.get("approved", False))
            media_approved = bool(media_result.get("approved", False))

            if text_approved and media_approved:
                return

            if not text_approved:
                reason = text_result.get("reason", "Nội dung phản hồi bình luận vi phạm quy định")
            else:
                reason = media_result.get("reason", "File đính kèm vi phạm quy định")

            print("\n========== [COMMENT REPLY REMOVED BY BACKGROUND MODERATION] ==========")
            print(f"[POST_ID] {post_id}")
            print(f"[COMMENT_ID] {comment_id}")
            print(f"[PATH] {path}")
            print(f"[REASON] {reason}")
            print("========== END [COMMENT REPLY REMOVED BY BACKGROUND MODERATION] ==========\n")

            await self._hide_comment_reply(
                post_id=post_id,
                comment_id=comment_id,
                path=path,
                reason=reason
            )

            # TODO websocket:
            # await ws_manager.broadcast_post(post_id, {
            #     "type": "comment_reply_removed",
            #     "post_id": post_id,
            #     "comment_id": comment_id,
            #     "path": path,
            #     "reason": reason,
            # })

        except Exception as e:
            print(f"[COMMENT_REPLY_BACKGROUND_MODERATION_ERROR] {post_id}/{comment_id}: {e}")

    # ============================================================
    # COMMENT
    # ============================================================
    async def add(self, post_req: AddCommentRequest, user_id: str) -> AddCommentResponse:
        content = post_req.content.strip() if post_req.content else ""

        # Không chờ moderation nữa.
        # Lưu comment ngay để UX mượt hơn.
        new_comment = await CommentRepository.add_comment(
            post_id=post_req.postId,
            user_id=user_id,
            comment_data=post_req.model_dump(),
            thumb=post_req.thumbnails
        )

        if not new_comment:
            return AddCommentResponse(
                success=False,
                message="Post not found."
            )

        # Lấy commentId từ repository trả về.
        comment_id = (
            new_comment.get("commentId")
            or new_comment.get("id")
            or new_comment.get("_id")
        )

        if comment_id:
            asyncio.create_task(
                self._moderate_root_comment_in_background(
                    post_id=post_req.postId,
                    comment_id=str(comment_id),
                    content=content,
                    user_id=user_id,
                    thumbnails=post_req.thumbnails or [],
                )
            )
        else:
            print("[COMMENT_MODERATION] Cannot start background moderation: missing commentId")

        # Notification:
        # Để tránh gửi thông báo cho comment vi phạm, có thể chuyển notification vào sau khi moderation approved.
        # Nhưng để ít thay đổi flow hiện tại, vẫn giữ thông báo ngay như code cũ.
        dic_post = await PostRepository.find_by_id(post_req.postId)
        if not dic_post:
            return AddCommentResponse(
                success=True,
                message="Comment added successfully, but post not found for notification.",
                comment=new_comment
            )

        post: Post = Post(**bson_to_dict(dic_post))

        dic_acc = await AccountRepository.find_by_email(post.createdBy)
        dic_acc_tp = await AccountRepository.find_by_email(user_id)

        if not dic_acc or not dic_acc_tp:
            return AddCommentResponse(
                success=True,
                message="Comment added successfully, but notification skipped.",
                comment=new_comment
            )

        acc: Account = Account(**bson_to_dict(dic_acc))
        acc_tp: Account = Account(**bson_to_dict(dic_acc_tp))

        contentAnnounce: str = (
            str(acc_tp.userInfo.fullName)
            + " đã bình luận bài viết của bạn"
        )

        announce = Announce(
            senderEmail=user_id,
            receiverEmail=post.createdBy,
            type="comment",
            contentAnnounce=contentAnnounce,
            isRead=False,
            createdAt=datetime.now(timezone.utc),
            contentId=new_comment.get("commentId"),
            contentParentId=str(post.id),
            content=new_comment.get("content")
        )

        dic_announce_insert = await AnnounceRepository.insert(
            announce.model_dump()
        )

        if dic_announce_insert:
            return AddCommentResponse(
                success=True,
                message="Comment added successfully.",
                comment=new_comment
            )

        return AddCommentResponse(
            success=True,
            message="Comment added successfully, but notification failed.",
            comment=new_comment
        )

    async def update_react(
        self,
        post_id: str,
        comment_id: str,
        react: CommentReact
    ) -> Optional[dict]:
        updated_post = await CommentRepository.update_comment_react(
            post_id,
            comment_id,
            react
        )
        return bson_to_dict(updated_post) if updated_post else None

    async def find_by_id(self, post_id: str) -> Optional[dict]:
        return await CommentRepository.find_by_id(post_id)

    # ============================================================
    # COMMENT REPLY
    # ============================================================
    async def add_comment_reply(
        self,
        comment_req: AddCommentReplyRequest
    ) -> Optional[AddCommentReplyResponse]:
        # Không chờ moderation nữa.
        # Tạo comment reply ngay.
        commentId = str(uuid.uuid4())

        if not comment_req.path:
            path = comment_req.parentId + ";" + commentId
        else:
            path = comment_req.path + ";" + commentId

        commentReply: CommentReply = CommentReply(
            commentId=commentId,
            commentBy=comment_req.commentBy,
            postId=comment_req.postId,
            path=path,
            content=comment_req.content,
            createdAt=datetime.now(timezone.utc),
            status="active",
            thumbnails=comment_req.thumbnails
        )

        rs = await CommentReplyRepository.insert(commentReply.model_dump())

        if not rs:
            return None

        content = comment_req.content.strip() if comment_req.content else ""

        asyncio.create_task(
            self._moderate_comment_reply_in_background(
                post_id=comment_req.postId,
                comment_id=commentId,
                path=path,
                content=content,
                user_id=comment_req.commentBy,
                thumbnails=comment_req.thumbnails or [],
            )
        )

        return AddCommentReplyResponse(
            commentReply=CommentReply(**bson_to_dict(rs))
        )

    async def get_comment_reply(
        self,
        req: GetCommentReplyRequest
    ) -> Optional[GetCommentReplyResponse]:
        dic = await CommentReplyRepository.find_by_path(
            req.postId,
            req.parentId
        )

        rs = GetCommentReplyResponse(
            commentReplys=[
                CommentReply(**c)
                for c in dic
                if c.get("status") == "active"
            ]
        )

        for c in rs.commentReplys:
            if c.thumbnails:
                c.thumbnails_url = [
                    FileService.get_file_url(file_id)
                    for file_id in c.thumbnails
                ]
            else:
                c.thumbnails_url = []

        return rs

    async def update_status_comment_reply(
        self,
        req: UpdateStatusCommentReplyRequest
    ) -> List[UpdateStatusCommentReplyResponse]:
        updated_cmts = await CommentReplyRepository.update_comment_status(
            req.postId,
            req.commentId,
            req.path,
            req.status
        )

        if updated_cmts:
            return [
                UpdateStatusCommentReplyResponse(
                    commentReply=CommentReply(**bson_to_dict(cmt))
                )
                for cmt in updated_cmts
            ]

        return []

    async def update_react_comment_reply(
        self,
        post_id: str,
        comment_id: str,
        react: CommentReact
    ) -> Optional[dict]:
        updated_comment = await CommentReplyRepository.update_comment_reply_react(
            post_id,
            comment_id,
            react
        )
        return bson_to_dict(updated_comment) if updated_comment else None
