from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Dict, Any

from core.dependency import get_post_service
from crawl.converter.ffl_converter_service import CrawlToPostConverter
from dto.post.response.add_post_response import AddPostResponse
from services.impls.post_service_impl import PostServiceImpl
from services.interfaces.post_service_interface import IPostService


router = APIRouter(prefix="/crawl_import", tags=["Crawl Import"])


class CrawlImportService:
    def __init__(self, post_service: PostServiceImpl, converter: CrawlToPostConverter):
        self.post_service = post_service
        self.converter = converter

    async def import_single(self, crawl_doc: Dict[str, Any]) -> AddPostResponse:
        try:
            post_request = await self.converter.convert(crawl_doc)
            result = await self.post_service.add_from_crawl(post_request)
            return result

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")

    async def import_bulk(self, crawl_docs: List[Dict[str, Any]]) -> dict:
        results = {
            "success": [],
            "failed": []
        }

        for doc in crawl_docs:
            try:
                result = await self.import_single(doc)

                results["success"].append({
                    "article_id": doc.get("article_id"),
                    "title": doc.get("title"),
                    "result": result
                })

            except Exception as e:
                results["failed"].append({
                    "article_id": doc.get("article_id"),
                    "title": doc.get("title"),
                    "error": str(e)
                })

        return results


def get_crawl_converter():
    return CrawlToPostConverter(
        upload_endpoint="http://localhost:8000/file/upload_from_crawl"
    )


@router.post("/import_single", response_model=AddPostResponse)
async def import_crawled_post(
    crawl_doc: Dict[str, Any],
    service: IPostService = Depends(get_post_service),
    converter: CrawlToPostConverter = Depends(get_crawl_converter)
):
    import_service = CrawlImportService(service, converter)
    return await import_service.import_single(crawl_doc)


@router.post("/import_bulk")
async def import_bulk_posts(
    crawl_docs: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    service: IPostService = Depends(get_post_service),
    converter: CrawlToPostConverter = Depends(get_crawl_converter)
):
    import_service = CrawlImportService(service, converter)

    if len(crawl_docs) <= 5:
        return await import_service.import_bulk(crawl_docs)

    background_tasks.add_task(import_service.import_bulk, crawl_docs)

    return {
        "message": "Đang xử lý import trong background",
        "total": len(crawl_docs),
        "status": "processing"
    }