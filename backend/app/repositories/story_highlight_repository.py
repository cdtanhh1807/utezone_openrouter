from bson import ObjectId
from core.database import db
from utils.base import bson_to_dict

class StoryHighlightRepository:
    collection = db["story_highlight"]

    @staticmethod
    async def add_highlight(data: dict) -> dict:
        result = await StoryHighlightRepository.collection.insert_one(data)
        inserted = await StoryHighlightRepository.collection.find_one({"_id": result.inserted_id})
        return bson_to_dict(inserted)

    @staticmethod
    async def find_by_user(user_email: str) -> list[dict]:
        cursor = StoryHighlightRepository.collection.find({
            "createdBy": user_email,
            "status": "active"
        })
        highlights = await cursor.to_list(length=None)
        return [bson_to_dict(hl) for hl in highlights]

    @staticmethod
    async def find_by_id(highlight_id: str) -> dict:
        hl = await StoryHighlightRepository.collection.find_one({
            "_id": ObjectId(highlight_id),
            "status": "active"
        })
        return bson_to_dict(hl) if hl else None

    @staticmethod
    async def update_highlight(highlight_id: str, data: dict) -> bool:
        result = await StoryHighlightRepository.collection.update_one(
            {"_id": ObjectId(highlight_id)},
            {"$set": data}
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_highlight(highlight_id: str) -> bool:
        result = await StoryHighlightRepository.collection.delete_one(
            {"_id": ObjectId(highlight_id)}
        )
        return result.deleted_count > 0
