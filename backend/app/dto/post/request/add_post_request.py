from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from models.post_model import PollData


class AddPostRequest(BaseModel):
    title: str
    content: str
    # createdAt: datetime = datetime.now(timezone.utc)
    createdAt: datetime = Field(default_factory=datetime.now)
    postType: str              
    visibility: str
    comment_visibility: Optional[str] = None            
    status: str
    createdBy: Optional[str] = None 
    category: Optional[List[str]] = None
    pollData: Optional[PollData] = None
    thumbnails: Optional[List[str]] = None

