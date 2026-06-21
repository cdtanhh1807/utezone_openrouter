from services.interfaces.story_highlight_service_interface import IStoryHighlightService
from repositories.story_highlight_repository import StoryHighlightRepository
from repositories.story_repository import StoryRepository
from services.other.file_service import FileService
from bson import ObjectId
from utils.base import bson_to_dict
from typing import List

class StoryHighlightServiceImpl(IStoryHighlightService):

    def _extract_file_id(self, url_or_id: str) -> str:
        if not url_or_id:
            return ""
        if url_or_id.startswith("http://") or url_or_id.startswith("https://"):
            try:
                from urllib.parse import urlparse
                path = urlparse(url_or_id).path
                parts = path.strip("/").split("/")
                if len(parts) >= 2:
                    return parts[-1]
                elif len(parts) == 1:
                    return parts[0]
            except Exception:
                pass
        return url_or_id

    async def add(self, highlight_data: dict) -> dict:
        if "coverUrl" in highlight_data:
            highlight_data["coverUrl"] = self._extract_file_id(highlight_data["coverUrl"])
        return await StoryHighlightRepository.add_highlight(highlight_data)

    async def get_user_highlights(self, email: str) -> List[dict]:
        highlights = await StoryHighlightRepository.find_by_user(email)
        result = []
        for hl in highlights:
            # Lấy chi tiết của từng story trong highlight
            story_list = []
            for s_id in hl.get("storyIds", []):
                try:
                    story = await StoryRepository.collection.find_one({
                        "_id": ObjectId(s_id),
                        "status": "active"
                    })
                    if story:
                        story_dict = bson_to_dict(story)
                        # Xử lý đường dẫn file từ MinIO qua FileService
                        if story_dict.get("thumbnails") and len(story_dict["thumbnails"]) > 0:
                            story_dict["mediaUrls"] = [
                                FileService.get_file_url(file_id) for file_id in story_dict["thumbnails"]
                            ]
                        elif story_dict.get("mediaUrls"):
                            story_dict["mediaUrls"] = [
                                FileService.get_file_url(file_id) for file_id in story_dict["mediaUrls"]
                            ]
                        else:
                            story_dict["mediaUrls"] = []

                        if story_dict.get("music") and story_dict["music"].get("fileid"):
                            story_dict["music"]["url"] = FileService.get_file_url(story_dict["music"]["fileid"])

                        story_list.append(story_dict)
                except Exception as e:
                    print(f"❌ Lỗi populate story {s_id} trong highlight: {e}")
            
            hl["stories"] = story_list
            
            # Resolve coverUrl if it is a file_id
            cover_id = hl.get("coverUrl")
            if cover_id and not cover_id.startswith("http") and cover_id != "/default-avatar.png":
                try:
                    hl["coverUrl"] = FileService.get_file_url(cover_id)
                except Exception as e:
                    print(f"❌ Lỗi get file url cho cover {cover_id}: {e}")

            result.append(hl)
        return result

    async def update(self, highlight_id: str, highlight_data: dict) -> bool:
        # Loại bỏ trường _id khỏi dữ liệu cập nhật
        highlight_data.pop("_id", None)
        highlight_data.pop("id", None)
        if "coverUrl" in highlight_data:
            highlight_data["coverUrl"] = self._extract_file_id(highlight_data["coverUrl"])
        return await StoryHighlightRepository.update_highlight(highlight_id, highlight_data)

    async def delete(self, highlight_id: str) -> bool:
        return await StoryHighlightRepository.delete_highlight(highlight_id)
