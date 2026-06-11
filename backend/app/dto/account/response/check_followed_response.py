from pydantic import BaseModel

class CheckFollowedResponse(BaseModel):
    is_following: bool