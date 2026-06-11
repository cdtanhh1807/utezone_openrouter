from pydantic import BaseModel

class CheckFollowedRequest(BaseModel):
    requester_email: str
    post_owner_email: str