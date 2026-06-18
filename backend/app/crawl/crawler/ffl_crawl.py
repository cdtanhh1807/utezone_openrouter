import json
import re
import os
import asyncio
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
from playwright.async_api import async_playwright

from crawl.importdata.ffl.ffl_import import import_single_article


@dataclass
class ArticleDetail:
    article_id: str
    title: str
    date: str
    image_url: str
    article_url: str
    description: str
    category: str
    full_content: str = ""
    html_content: str = ""
    structured_content: List[Dict] = field(default_factory=list)
    author: str = ""
    views: str = ""
    attachments: List[Dict] = field(default_factory=list)
    crawled_at: str = ""

    def __post_init__(self):
        if not self.crawled_at:
            self.crawled_at = datetime.now().isoformat()


class FFLPlaywrightCrawler:
    BASE_URL = "https://ffl.hcmute.edu.vn"

    # Web FFL không chia category như FME, nên chỉ dùng 1 category duy nhất
    CATEGORIES = {
        "tin-tuc": {
            "name": "Ngoại ngữ",
            "url": "https://ffl.hcmute.edu.vn/"
        }
    }

    # Chỉ dùng để loại các ảnh/icon hệ thống của Drupal/social share.
    # Không thay đổi logic crawl nội dung như ban đầu.
    IGNORED_IMAGE_PATTERNS = [
        "/modules/share_everywhere/",
        "share-icon.svg",
        "facebook-share.svg",
        "messenger.svg",
        "twitter.svg",
        "linkedin.svg",
        "logo.svg",
        "favicon",
        "sprite",
        "placeholder",
    ]

    def __init__(self, headless: bool = True, delay: float = 0.5):
        self.headless = headless
        self.delay = delay
        self.browser = None
        self.context = None
        self.playwright = None

    async def init(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        print("Browser initialized")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Browser closed")

    def normalize_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def is_ignored_image_url(self, url: str) -> bool:
        """
        Bỏ qua icon/share/svg của giao diện web.
        Mục tiêu: giữ nguyên logic crawl cũ, chỉ không đưa các icon này vào image_url/structured_content.
        """
        if not url:
            return True

        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path

        if path.endswith(".svg"):
            return True

        return any(pattern.lower() in url_lower for pattern in self.IGNORED_IMAGE_PATTERNS)

    def extract_article_id(self, article_url: str) -> str:
        """
        FFL thường là Drupal, có thể có URL dạng:
        - /vi/node/586
        - /node/586
        - /index.php/vi/node/586
        - hoặc alias tiếng Việt
        """
        node_match = re.search(r"/node/(\d+)", article_url)
        if node_match:
            return node_match.group(1)

        parsed = urlparse(article_url)
        path = parsed.path.strip("/")

        if path:
            return re.sub(r"[^a-zA-Z0-9_-]+", "-", path)

        return re.sub(r"[^a-zA-Z0-9_-]+", "-", article_url)

    def extract_date_from_text(self, text: str) -> str:
        if not text:
            return ""

        text = self.normalize_text(text)

        # Dạng dd/mm/yyyy hoặc d/m/yyyy
        match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
        if match:
            day, month, year = match.groups()
            return f"{int(day):02d}/{int(month):02d}/{year}"

        # Dạng dd-mm-yyyy
        match = re.search(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", text)
        if match:
            day, month, year = match.groups()
            return f"{int(day):02d}/{int(month):02d}/{year}"

        # Dạng ngày 30 tháng 05 năm 2026
        match = re.search(
            r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            text,
            re.IGNORECASE
        )
        if match:
            day, month, year = match.groups()
            return f"{int(day):02d}/{int(month):02d}/{year}"

        return ""

    def is_valid_article_url(self, href: str) -> bool:
        if not href:
            return False

        href_lower = href.lower().strip()

        invalid_patterns = [
            "facebook.com",
            "youtube.com",
            "twitter.com",
            "linkedin.com",
            "mailto:",
            "tel:",
            "javascript:",
            "#",
            "/user/",
            "/taxonomy/",
            "/search",
            "/rss",
            "/feed",
            "/login",
            "/admin"
        ]

        if any(pattern in href_lower for pattern in invalid_patterns):
            return False

        # Bài Drupal thường có /node/
        if "/node/" in href_lower:
            return True

        # Một số bài có thể dùng alias /vi/...
        if href_lower.startswith("/vi/") or "/vi/" in href_lower:
            return True

        # URL absolute cùng domain
        if href_lower.startswith(self.BASE_URL.lower()):
            return True

        return False

    def parse_list_item(self, html: str, category_key: str) -> List[ArticleDetail]:
        soup = BeautifulSoup(html, "lxml")

        articles = []
        seen_urls = set()

        # Ưu tiên parse theo từng item Drupal
        containers = soup.select(
            ".view-content .views-row, "
            ".views-row, "
            "article, "
            ".node, "
            ".post, "
            ".content .item"
        )

        if not containers:
            containers = soup.select("main h2, main h3, .region-content h2, .region-content h3")

        for container in containers:
            try:
                link_elem = container.select_one(
                    "h1 a[href], h2 a[href], h3 a[href], "
                    ".field-content a[href], "
                    "a[href*='/node/'], "
                    "a[href*='/vi/']"
                )

                if not link_elem:
                    continue

                href = link_elem.get("href", "").strip()
                if not self.is_valid_article_url(href):
                    continue

                article_url = urljoin(self.BASE_URL, href)

                if article_url in seen_urls:
                    continue

                title = self.normalize_text(link_elem.get_text(" ", strip=True))
                if not title:
                    continue

                # Bỏ qua menu/header/footer
                menu_titles = {
                    "TRANG CHỦ",
                    "GIỚI THIỆU",
                    "TIN TỨC",
                    "ĐÀO TẠO",
                    "SINH VIÊN",
                    "NGHIÊN CỨU",
                    "LIÊN HỆ",
                    "ENGLISH",
                    "VIETNAMESE"
                }

                if title.upper() in menu_titles:
                    continue

                seen_urls.add(article_url)

                # Lấy ảnh trong item, nhưng bỏ icon/share/svg của giao diện
                image_url = ""
                for img_elem in container.select("img"):
                    img_src = (
                        img_elem.get("src", "")
                        or img_elem.get("data-src", "")
                        or img_elem.get("data-original", "")
                    )
                    if not img_src:
                        continue

                    full_img_url = urljoin(self.BASE_URL, img_src)
                    if self.is_ignored_image_url(full_img_url):
                        continue

                    image_url = full_img_url
                    break

                # Lấy mô tả
                description = ""

                desc_candidates = container.select(
                    ".field--name-body, "
                    ".node__content, "
                    ".views-field-body, "
                    ".field-content, "
                    ".summary, "
                    ".description, "
                    "p"
                )

                for desc_elem in desc_candidates:
                    desc_text = self.normalize_text(desc_elem.get_text(" ", strip=True))
                    if desc_text and desc_text != title and len(desc_text) > 20:
                        description = desc_text
                        break

                if not description:
                    container_text = self.normalize_text(container.get_text(" ", strip=True))
                    if container_text:
                        description = container_text.replace(title, "", 1).strip()[:500]

                date = self.extract_date_from_text(f"{title} {description}")
                article_id = self.extract_article_id(article_url)

                articles.append(
                    ArticleDetail(
                        article_id=article_id,
                        title=title,
                        date=date,
                        image_url=image_url,
                        article_url=article_url,
                        description=description,
                        category=self.CATEGORIES[category_key]["name"]
                    )
                )

            except Exception as e:
                print(f"    Parse error: {e}")

        # Fallback nếu container không bắt được bài nào
        if not articles:
            links = soup.select("main h1 a[href], main h2 a[href], main h3 a[href], .region-content a[href]")

            for link_elem in links:
                try:
                    href = link_elem.get("href", "").strip()

                    if not self.is_valid_article_url(href):
                        continue

                    article_url = urljoin(self.BASE_URL, href)

                    if article_url in seen_urls:
                        continue

                    title = self.normalize_text(link_elem.get_text(" ", strip=True))
                    if not title:
                        continue

                    seen_urls.add(article_url)

                    article_id = self.extract_article_id(article_url)
                    date = self.extract_date_from_text(title)

                    articles.append(
                        ArticleDetail(
                            article_id=article_id,
                            title=title,
                            date=date,
                            image_url="",
                            article_url=article_url,
                            description="",
                            category=self.CATEGORIES[category_key]["name"]
                        )
                    )

                except Exception as e:
                    print(f"    Fallback parse error: {e}")

        return articles

    async def crawl_category(self, category_key: str, max_pages: int = 0) -> List[ArticleDetail]:
        cat = self.CATEGORIES[category_key]

        print(f"\n[{category_key}] {cat['name']}")

        all_articles = []
        seen_article_ids = set()

        page = await self.context.new_page()

        try:
            print("   Opening page 1...")
            await page.goto(cat["url"], wait_until="networkidle")
            await asyncio.sleep(1)

            current_page = 1

            while True:
                print(f"\n   Page {current_page}")

                html = await page.content()
                articles = self.parse_list_item(html, category_key)

                new_articles = []

                for article in articles:
                    if article.article_id in seen_article_ids:
                        continue

                    seen_article_ids.add(article.article_id)
                    new_articles.append(article)
                    all_articles.append(article)

                print(f"      Found {len(new_articles)} new items")

                for article in new_articles:
                    print(f"      {article.title[:70]}...")

                if max_pages > 0 and current_page >= max_pages:
                    print("      Max pages reached")
                    break

                next_selectors = [
                    "a[rel='next']",
                    "li.pager__item--next a",
                    ".pager__item--next a",
                    "a[title*='Go to next page']",
                    "a[aria-label*='Next']",
                    "a:has-text('Next')",
                    "a:has-text('›')",
                    "a:has-text('Sau')",
                    "a:has-text('Tiếp')"
                ]

                next_btn = None

                for selector in next_selectors:
                    try:
                        next_btn = await page.query_selector(selector)
                        if next_btn:
                            break
                    except Exception:
                        continue

                if not next_btn:
                    print("      No next button")
                    break

                try:
                    next_href = await next_btn.get_attribute("href")

                    if not next_href:
                        print("      Next button has no href")
                        break

                    next_url = urljoin(self.BASE_URL, next_href)
                    print(f"      Next page: {next_url}")

                    await page.goto(next_url, wait_until="networkidle")
                    await asyncio.sleep(1.5)
                    current_page += 1

                except Exception as e:
                    print(f"      Next failed: {e}")
                    break

            print(f"\n   Total: {len(all_articles)} articles")

        finally:
            await page.close()

        return all_articles

    def extract_structured_content(self, element) -> List[Dict]:
        content_blocks = []

        for child in element.descendants:
            if isinstance(child, NavigableString):
                continue

            if child.name not in [
                "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                "ul", "ol", "table", "img", "a", "br", "hr", "span"
            ]:
                continue

            if child.name in ["script", "style"]:
                continue

            parent = child.find_parent([
                "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                "li", "td", "th", "span"
            ])

            if parent and parent != element and parent.name not in ["div", "p"]:
                if parent.name in ["h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"]:
                    continue

            block = self._process_element(child)

            if block and block not in content_blocks:
                content_blocks.append(block)

        if not content_blocks:
            for link in element.find_all("a", href=True):
                href = link.get("href", "")
                text = self.normalize_text(link.get_text(" ", strip=True))

                if text and href:
                    content_blocks.append({
                        "type": "link",
                        "url": urljoin(self.BASE_URL, href),
                        "text": text
                    })

        return content_blocks

    def _process_element(self, elem) -> Optional[Dict]:
        if elem.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            content = self.normalize_text(elem.get_text(" ", strip=True))

            if content:
                return {
                    "type": "heading",
                    "level": int(elem.name[1]),
                    "content": content
                }

        if elem.name in ["ul", "ol"]:
            items = []

            for li in elem.find_all("li", recursive=False):
                item_text = self.normalize_text(li.get_text(" ", strip=True))
                if item_text:
                    items.append(item_text)

            if items:
                return {
                    "type": "list",
                    "list_type": "bullet" if elem.name == "ul" else "numbered",
                    "items": items
                }

            return None

        if elem.name == "table":
            rows = []

            for tr in elem.find_all("tr"):
                row_data = []

                for td in tr.find_all(["td", "th"]):
                    row_data.append(self.normalize_text(td.get_text(" ", strip=True)))

                if row_data:
                    rows.append(row_data)

            if rows:
                return {
                    "type": "table",
                    "rows": rows
                }

            return None

        if elem.name == "img":
            src = (
                elem.get("src", "")
                or elem.get("data-src", "")
                or elem.get("data-original", "")
            )

            if src:
                full_src = urljoin(self.BASE_URL, src)

                # Chỉ bỏ icon/share/svg; giữ nguyên logic ảnh như file ban đầu
                if self.is_ignored_image_url(full_src):
                    return None

                return {
                    "type": "image",
                    "src": full_src,
                    "alt": elem.get("alt", ""),
                    "title": elem.get("title", "")
                }

            return None

        if elem.name == "a":
            href = elem.get("href", "")
            text = self.normalize_text(elem.get_text(" ", strip=True))

            if text and href and not elem.find_parent("p"):
                return {
                    "type": "link",
                    "url": urljoin(self.BASE_URL, href),
                    "text": text
                }

        if elem.name in ["p", "div", "span"]:
            children = [
                c for c in elem.children
                if not isinstance(c, NavigableString) or str(c).strip()
            ]

            if (
                len(children) == 1
                and getattr(children[0], "name", None) in ["div", "p", "ul", "ol", "table"]
            ):
                return None

            text = self.normalize_text(elem.get_text(" ", strip=True))

            if text:
                links = []

                for a in elem.find_all("a"):
                    href = a.get("href", "")
                    link_text = self.normalize_text(a.get_text(" ", strip=True))

                    if href and link_text:
                        links.append({
                            "text": link_text,
                            "url": urljoin(self.BASE_URL, href)
                        })

                return {
                    "type": "paragraph",
                    "content": text,
                    "links": links if links else ""
                }

        return None

    def find_main_article_content(self, soup: BeautifulSoup):
        selectors = [
            "article .field--name-body",
            "article .node__content",
            "article",
            ".field--name-body",
            ".node__content",
            "main .region-content",
            ".region-content",
            "main"
        ]

        for selector in selectors:
            elem = soup.select_one(selector)

            if elem:
                text = self.normalize_text(elem.get_text(" ", strip=True))

                if len(text) > 30:
                    return elem

        return None

    async def crawl_detail(self, article: ArticleDetail) -> ArticleDetail:
        print(f"      {article.title[:60]}...")

        page = await self.context.new_page()

        try:
            await page.goto(article.article_url, wait_until="networkidle")
            await asyncio.sleep(0.5)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            title_elem = soup.select_one("main h1, article h1, h1")
            if title_elem:
                title_text = self.normalize_text(title_elem.get_text(" ", strip=True))
                if title_text:
                    article.title = title_text

            article_content = self.find_main_article_content(soup)

            if article_content:
                print("      Found article content")

                for tag in article_content([
                    "script",
                    "style",
                    "iframe",
                    "nav",
                    "form"
                ]):
                    tag.decompose()

                for social in article_content.select(
                    ".se-block, .se-container, .se-links-container, .se-links, "
                    ".share, .social, .addtoany, .a2a_kit, .breadcrumb, .tabs"
                ):
                    try:
                        social.decompose()
                    except Exception:
                        pass

                article.html_content = str(article_content)
                article.full_content = article_content.get_text(separator="\n", strip=True)
                article.structured_content = self.extract_structured_content(article_content)

                print(f"      Structured: {len(article.structured_content)} blocks")

                if not article.date:
                    article.date = self.extract_date_from_text(
                        f"{article.title} {article.description} {article.full_content[:1500]}"
                    )

                if not article.image_url:
                    for img_elem in article_content.select("img"):
                        image_src = (
                            img_elem.get("src", "")
                            or img_elem.get("data-src", "")
                            or img_elem.get("data-original", "")
                        )

                        if not image_src:
                            continue

                        full_image_url = urljoin(self.BASE_URL, image_src)
                        if self.is_ignored_image_url(full_image_url):
                            continue

                        article.image_url = full_image_url
                        break

                seen_attachments = set()

                for link in article_content.find_all("a", href=True):
                    href = link.get("href", "").strip()
                    text = self.normalize_text(link.get_text(" ", strip=True))

                    if not href:
                        continue

                    full_url = urljoin(self.BASE_URL, href)
                    lower_url = full_url.lower()

                    if self.is_ignored_image_url(full_url):
                        continue

                    if full_url in seen_attachments:
                        continue

                    is_file = any(
                        lower_url.endswith(ext)
                        for ext in [
                            ".pdf", ".doc", ".docx",
                            ".xls", ".xlsx",
                            ".ppt", ".pptx",
                            ".zip", ".rar"
                        ]
                    )

                    is_download_text = re.search(
                        r"(tải|download|đính kèm|file|biểu mẫu|mẫu|xem chi tiết)",
                        text,
                        re.IGNORECASE
                    )

                    if is_file or is_download_text:
                        article.attachments.append({
                            "filename": os.path.basename(urlparse(full_url).path) or "download",
                            "url": full_url,
                            "text": text
                        })
                        seen_attachments.add(full_url)

            else:
                print("      Không tìm thấy article content")

            views_elem = soup.select_one(".statistics-counter, .views, [class*='view']")
            if views_elem:
                article.views = self.normalize_text(views_elem.get_text(" ", strip=True))

            author_elem = soup.select_one(".field--name-uid, .author, .submitted")
            if author_elem:
                article.author = self.normalize_text(author_elem.get_text(" ", strip=True))

        except Exception as e:
            print(f"      Error: {e}")

        finally:
            await page.close()

        return article

    async def crawl_details(self, articles: List[ArticleDetail]) -> List[ArticleDetail]:
        print(f"\nCrawling details for {len(articles)} articles...")

        results = []

        for i, article in enumerate(articles, 1):
            print(f"   [{i}/{len(articles)}]")
            result = await self.crawl_detail(article)
            results.append(result)
            await asyncio.sleep(self.delay)

        return results

    async def save(
        self,
        articles: List[ArticleDetail],
        output_file: str = "crawl/output/ffl_output/articles.json",
        auto_import: bool = True
    ):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        existing_data = []
        existing_ids = set()

        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_ids = set(a.get("article_id") for a in existing_data)
            except Exception as e:
                print(f"⚠️ Không thể đọc file cũ: {e}")

        valid_articles = []
        skip_count = 0

        for article in articles:
            full_content_empty = not article.full_content or not article.full_content.strip()
            html_empty = not article.html_content or not article.html_content.strip()
            structured_empty = not article.structured_content or len(article.structured_content) == 0

            if full_content_empty and html_empty and structured_empty:
                print(f"⏩ Skip thiếu nội dung: {article.article_id} - {article.title[:50]}...")
                skip_count += 1
                continue

            valid_articles.append(article)

        if skip_count > 0:
            print(f"\n⚠️ Đã loại {skip_count} bài không đủ nội dung")

        if not valid_articles:
            print("❌ Không có bài nào hợp lệ")
            return []

        newly_saved = []

        for article in valid_articles:
            article_id = article.article_id

            if article_id in existing_ids:
                print(f"⏩ Skip đã tồn tại trong JSON: {article_id}")
                continue

            article_dict = asdict(article)

            if auto_import:
                print(f"\n📤 Đang import: {article.title[:60]}...")
                success, result = await import_single_article(article_dict)

                if success:
                    newly_saved.append(article_dict)
                    existing_ids.add(article_id)
                    print("✅ Import OK -> Thêm vào JSON")
                else:
                    print("❌ Import FAILED -> Bỏ qua, không lưu JSON")
            else:
                newly_saved.append(article_dict)
                existing_ids.add(article_id)
                print(f"💾 Lưu JSON, không import: {article.title[:60]}...")

            await asyncio.sleep(1)

        if newly_saved:
            all_data = existing_data + newly_saved

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)

            print(f"\n💾 Đã lưu {len(newly_saved)} bài mới vào {output_file}")
            print(f"📊 Tổng số bài trong JSON: {len(all_data)}")
        else:
            print("\n⚠️ Không có bài mới nào để lưu")

        return newly_saved

    async def run(
        self,
        category: str = "tin-tuc",
        max_pages: int = 0,
        fetch_detail: bool = True,
        auto_import: bool = True
    ) -> List[ArticleDetail]:
        print("FFL.HCMUTE Crawler")
        print(f"   Category: {category}")
        print(f"   Max pages: {'unlimited' if max_pages == 0 else max_pages}")
        print(f"   Fetch detail: {'Bật' if fetch_detail else 'Tắt'}")
        print(f"   Auto import: {'Bật' if auto_import else 'Tắt'}")

        await self.init()

        try:
            if category not in self.CATEGORIES:
                raise ValueError(f"Category không hợp lệ: {category}")

            all_articles = await self.crawl_category(category, max_pages)

            print(f"\n📥 Tổng từ lists: {len(all_articles)} articles")

            if fetch_detail and all_articles:
                all_articles = await self.crawl_details(all_articles)

            if all_articles:
                await self.save(
                    all_articles,
                    output_file="crawl/output/ffl_output/articles.json",
                    auto_import=auto_import
                )

                print("\n✅ DONE!")

                by_cat = {}

                for article in all_articles:
                    by_cat[article.category] = by_cat.get(article.category, 0) + 1

                for cat, count in by_cat.items():
                    print(f"   - {cat}: {count}")

                with_structured = sum(1 for article in all_articles if article.structured_content)
                print(f"   Có structured content: {with_structured}")

            return all_articles

        finally:
            await self.close()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="FFL.HCMUTE Crawler")

    parser.add_argument(
        "-c",
        "--category",
        choices=["tin-tuc"],
        default="tin-tuc",
        help="FFL chỉ có 1 category: tin-tuc"
    )

    parser.add_argument(
        "-p",
        "--pages",
        type=int,
        default=0,
        help="Max pages, 0 = unlimited"
    )

    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="Chỉ crawl list, không vào detail"
    )

    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Chỉ lưu JSON, không import DB"
    )

    parser.add_argument(
        "--visible",
        "-v",
        action="store_true",
        help="Show browser window"
    )

    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.5
    )

    args = parser.parse_args()

    crawler = FFLPlaywrightCrawler(
        headless=not args.visible,
        delay=args.delay
    )

    await crawler.run(
        category=args.category,
        max_pages=args.pages,
        fetch_detail=not args.no_detail,
        auto_import=not args.no_import
    )


if __name__ == "__main__":
    asyncio.run(main())