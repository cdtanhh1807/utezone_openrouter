from fastapi import APIRouter, Depends, HTTPException
from services.interfaces.story_highlight_service_interface import IStoryHighlightService
from services.interfaces.story_service_interface import IStoryService
from core.dependency import get_story_highlight_service, get_story_service
from utils.security import get_current_user
from datetime import datetime, timezone

router = APIRouter()

@router.post("/add")
async def add_highlight(
    highlight_data: dict,
    current_user: dict = Depends(get_current_user),
    service: IStoryHighlightService = Depends(get_story_highlight_service)
):
    user_email = current_user.get("sub")
    highlight_data["createdBy"] = user_email
    highlight_data["createdAt"] = datetime.now(timezone.utc)
    highlight_data["status"] = "active"
    
    result = await service.add(highlight_data)
    if result:
        return {"success": True, "message": "Story Highlight added successfully", "data": result}
    raise HTTPException(status_code=400, detail="Failed to add Story Highlight")

@router.get("/user/{email}")
async def get_user_highlights(
    email: str,
    service: IStoryHighlightService = Depends(get_story_highlight_service)
):
    highlights = await service.get_user_highlights(email)
    return {"success": True, "data": highlights}

@router.put("/update/{highlight_id}")
async def update_highlight(
    highlight_id: str,
    highlight_data: dict,
    current_user: dict = Depends(get_current_user),
    service: IStoryHighlightService = Depends(get_story_highlight_service)
):
    # Xác thực người sở hữu
    existing = await service.get_user_highlights(current_user.get("sub"))
    owned_ids = [hl.get("_id") or hl.get("id") for hl in existing]
    if highlight_id not in owned_ids:
        raise HTTPException(status_code=403, detail="Not authorized to edit this Story Highlight")
    
    success = await service.update(highlight_id, highlight_data)
    if success:
        return {"success": True, "message": "Story Highlight updated successfully"}
    raise HTTPException(status_code=400, detail="Failed to update Story Highlight")

@router.delete("/delete/{highlight_id}")
async def delete_highlight(
    highlight_id: str,
    current_user: dict = Depends(get_current_user),
    service: IStoryHighlightService = Depends(get_story_highlight_service)
):
    # Xác thực người sở hữu
    existing = await service.get_user_highlights(current_user.get("sub"))
    owned_ids = [hl.get("_id") or hl.get("id") for hl in existing]
    if highlight_id not in owned_ids:
        raise HTTPException(status_code=403, detail="Not authorized to delete this Story Highlight")
    
    success = await service.delete(highlight_id)
    if success:
        return {"success": True, "message": "Story Highlight deleted successfully"}
    raise HTTPException(status_code=400, detail="Failed to delete Story Highlight")

@router.get("/archive")
async def get_story_archive(
    current_user: dict = Depends(get_current_user),
    story_service: IStoryService = Depends(get_story_service)
):
    user_email = current_user.get("sub")
    archive = await story_service.get_archive_stories(user_email)
    return {"success": True, "data": archive}
