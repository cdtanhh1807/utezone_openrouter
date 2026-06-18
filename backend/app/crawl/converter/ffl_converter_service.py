import httpx
import mimetypes
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse
import uuid

from dto.post.request.add_post_request import AddPostRequest


class CrawlToPostConverter:
    IMAGE_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".bmp", ".svg", ".ico"
    }

    VIDEO_EXTENSIONS = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm",
        ".flv", ".wmv", ".m4v"
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".rar"
    }

    def __init__(self, upload_endpoint: str, timeout: int = 30):
        self.upload_endpoint = upload_endpoint
        self.timeout = timeout
        self.max_file_size = 50 * 1024 * 1024

    def get_file_type(self, url: str) -> Tuple[str, str]:
        parsed = urlparse(url)
        path = parsed.path.lower()
        filename = path.split("/")[-1] if "/" in path else "unknown"

        if "." in filename:
            ext = "." + filename.split(".")[-1].lower()
        else:
            ext = ""

        if ext in self.IMAGE_EXTENSIONS:
            return "image", filename

        if ext in self.VIDEO_EXTENSIONS:
            return "video", filename

        if ext in self.DOCUMENT_EXTENSIONS:
            return "document", filename

        return "document", filename or "unknown"

    async def download_media(self, url: str) -> Tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with client.stream("GET", url.strip(), headers=headers) as response:
                response.raise_for_status()

                content_length = response.headers.get("content-length")

                if content_length and int(content_length) > self.max_file_size:
                    raise ValueError(f"File quá lớn: {int(content_length) / 1024 / 1024:.2f}MB")

                chunks = []

                async for chunk in response.aiter_bytes(chunk_size=8192):
                    chunks.append(chunk)

                file_bytes = b"".join(chunks)

                parsed = urlparse(url)
                filename = parsed.path.split("/")[-1].split("?")[0]

                if not filename or "." not in filename:
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    ext = mimetypes.guess_extension(content_type) or ".bin"
                    filename = f"media_{uuid.uuid4().hex[:8]}{ext}"

                return file_bytes, filename

    async def upload_to_minio(self, file_bytes: bytes, filename: str) -> str:
        file_obj = BytesIO(file_bytes)

        content_type, _ = mimetypes.guess_type(filename)

        if not content_type:
            content_type = "application/octet-stream"

        files = {
            "file": (filename, file_obj, content_type)
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.upload_endpoint, files=files)
            response.raise_for_status()

            result = response.json()
            file_id = result.get("file_id")

            if not file_id:
                raise ValueError("Upload response không chứa file_id")

            return file_id

    def parse_date(self, date_str: str, crawled_at: Optional[str] = None) -> datetime:
        """
        Logic giống FME:
        - Lấy ngày từ field date crawl được
        - Lấy giờ/phút/giây từ thời điểm import hiện tại bằng datetime.now()
        """
        now = datetime.now()

        if date_str:
            date_str = date_str.strip()

            if "/" in date_str:
                try:
                    day, month, year = date_str.split("/")

                    return datetime(
                        int(year),
                        int(month),
                        int(day),
                        now.hour,
                        now.minute,
                        now.second,
                        now.microsecond
                    )
                except Exception:
                    pass

            if "-" in date_str:
                try:
                    day, month, year = date_str.split("-")

                    return datetime(
                        int(year),
                        int(month),
                        int(day),
                        now.hour,
                        now.minute,
                        now.second,
                        now.microsecond
                    )
                except Exception:
                    pass

            try:
                parsed_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                return datetime(
                    parsed_date.year,
                    parsed_date.month,
                    parsed_date.day,
                    now.hour,
                    now.minute,
                    now.second,
                    now.microsecond
                )
            except Exception:
                pass

        if crawled_at:
            try:
                parsed_crawled_at = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
                return parsed_crawled_at.replace(tzinfo=None)
            except Exception:
                pass

        return now

    def map_category(self, crawl_category: str) -> str:
        category_mapping = {
            "Ngoại ngữ": "NGOẠI NGỮ",
            "Tin tức": "NGOẠI NGỮ",
            "Thông báo": "NGOẠI NGỮ",
            "tin-tuc": "NGOẠI NGỮ"
        }

        return category_mapping.get(crawl_category, "NGOẠI NGỮ")

    def build_content_with_links(self, full_content: str, document_links: List[Dict[str, str]]) -> str:
        parts = []

        if full_content and full_content.strip():
            parts.append(full_content.strip())

        if document_links:
            parts.append("\n\n📎 Tài liệu đính kèm:")

            for link in document_links:
                text = link.get("text", "Tải xuống")
                url = link.get("url", "")

                if url:
                    parts.append(f"• {text}")
                    parts.append(f"  {url}")

        return "\n".join(parts)

    async def convert(self, crawl_doc: Dict[str, Any]) -> AddPostRequest:
        thumbnails = []
        document_links = []
        seen_urls = set()

        # 1. Xử lý structured_content
        for item in crawl_doc.get("structured_content", []):
            item_type = item.get("type")

            if item_type == "image":
                src = item.get("src", "").strip()

                if not src or src in seen_urls:
                    continue

                file_type, filename = self.get_file_type(src)

                if file_type == "image":
                    try:
                        print(f"📥 Đang tải ảnh: {filename}")
                        file_bytes, real_filename = await self.download_media(src)
                        file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                        thumbnails.append(file_id)
                        seen_urls.add(src)
                        print(f"✅ Ảnh uploaded: {file_id}")
                    except Exception as e:
                        print(f"❌ Lỗi tải ảnh {src}: {e}")

                elif file_type == "video":
                    try:
                        print(f"🎥 Đang tải video: {filename}")
                        file_bytes, real_filename = await self.download_media(src)
                        file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                        thumbnails.append(file_id)
                        seen_urls.add(src)
                        print(f"✅ Video uploaded: {file_id}")
                    except Exception as e:
                        print(f"❌ Lỗi tải video {src}: {e}")

            elif item_type == "link":
                url = item.get("url", "").strip()
                text = item.get("text", "").strip() or url

                if not url or url in seen_urls:
                    continue

                file_type, filename = self.get_file_type(url)

                if file_type == "image":
                    try:
                        print(f"📥 Đang tải ảnh từ link: {filename}")
                        file_bytes, real_filename = await self.download_media(url)
                        file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                        thumbnails.append(file_id)
                        seen_urls.add(url)
                        print(f"✅ Ảnh uploaded: {file_id}")
                    except Exception as e:
                        print(f"❌ Lỗi tải ảnh link {url}: {e}")

                elif file_type == "video":
                    try:
                        print(f"🎥 Đang tải video từ link: {filename}")
                        file_bytes, real_filename = await self.download_media(url)
                        file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                        thumbnails.append(file_id)
                        seen_urls.add(url)
                        print(f"✅ Video uploaded: {file_id}")
                    except Exception as e:
                        print(f"❌ Lỗi tải video link {url}: {e}")

                else:
                    document_links.append({
                        "text": text or filename,
                        "url": url
                    })
                    seen_urls.add(url)

        # 2. Xử lý attachments
        for att in crawl_doc.get("attachments", []):
            url = att.get("url", "").strip()
            filename = att.get("filename", "") or att.get("text", "Tải xuống")

            if not url or url in seen_urls:
                continue

            file_type, detected_filename = self.get_file_type(url)

            if file_type == "image":
                try:
                    print(f"📥 Đang tải attachment ảnh: {filename}")
                    file_bytes, real_filename = await self.download_media(url)
                    file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                    thumbnails.append(file_id)
                    seen_urls.add(url)
                    print(f"✅ Attachment ảnh uploaded: {file_id}")
                except Exception as e:
                    print(f"❌ Lỗi tải attachment ảnh {url}: {e}")

            elif file_type == "video":
                try:
                    print(f"🎥 Đang tải attachment video: {filename}")
                    file_bytes, real_filename = await self.download_media(url)
                    file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                    thumbnails.append(file_id)
                    seen_urls.add(url)
                    print(f"✅ Attachment video uploaded: {file_id}")
                except Exception as e:
                    print(f"❌ Lỗi tải attachment video {url}: {e}")

            else:
                document_links.append({
                    "text": filename or detected_filename,
                    "url": url
                })
                seen_urls.add(url)

        # 3. Xử lý image_url chính
        if crawl_doc.get("image_url"):
            img_url = crawl_doc["image_url"].strip()

            if img_url and img_url not in seen_urls:
                file_type, filename = self.get_file_type(img_url)

                if file_type == "image":
                    try:
                        print(f"📥 Đang tải thumbnail chính: {filename}")
                        file_bytes, real_filename = await self.download_media(img_url)
                        file_id = await self.upload_to_minio(file_bytes, real_filename or filename)
                        thumbnails.insert(0, file_id)
                        seen_urls.add(img_url)
                        print(f"✅ Thumbnail uploaded: {file_id}")
                    except Exception as e:
                        print(f"❌ Lỗi tải thumbnail {img_url}: {e}")

        # 4. Build content
        content = self.build_content_with_links(
            crawl_doc.get("full_content", ""),
            document_links
        )

        if not content.strip() and crawl_doc.get("description"):
            content = crawl_doc["description"]

        post_type = "long" if len(content) > 800 else "short"

        categories = []
        crawl_cat = crawl_doc.get("category")

        if crawl_cat:
            categories.append(self.map_category(crawl_cat))

        if not categories:
            categories = ["NGOẠI NGỮ"]

        return AddPostRequest(
            title=crawl_doc.get("title", "").strip(),
            content=content,
            createdAt=self.parse_date(crawl_doc.get("date"), crawl_doc.get("crawled_at")),
            postType=post_type,
            visibility="public",
            comment_visibility="public",
            status="active",
            createdBy="ffl.hcmute@utezone.com",
            category=categories,
            pollData=None,
            thumbnails=thumbnails if thumbnails else None
        )