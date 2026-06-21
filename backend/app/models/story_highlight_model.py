from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from models.story_model import PyObjectId
from bson import ObjectId

class StoryHighlight(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    createdBy: str  # email of the creator
    title: str      # name/theme of the highlight (e.g. "Family")
    coverUrl: Optional[str] = None  # custom cover image or default
    storyIds: List[str] = Field(default_factory=list) # string list of Story ObjectIds
    createdAt: datetime
    status: str = "active"  # "active" or "off" (deleted)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
