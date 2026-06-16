from datetime import datetime as dt, timedelta
from typing import Optional, List, Dict
import uuid
from core.database import db
from meeting.models.channel_model import Channel, ChannelRules, ChatRoom, ChannelMember, UserSession, Message
from meeting.services.meeting_service import meeting_service


class ChannelService:
    def __init__(self):
        self.db = db
        self.channels_col = db.channels
        self.chatrooms_col = db.chat_rooms
        self.sessions_col = db.user_sessions
        self.messages_col = db.messages
        self.channel_ai_messages_col = db.channel_ai_messages

    # ==================== CHANNEL CRUD ====================

    async def create_channel(self, owner_email: str, owner_name: str,
                              name: str, description: Optional[str] = None,
                              require_approval: bool = False) -> Channel:
        # existing = await self.channels_col.find_one({"owner_email": owner_email})
        # if existing:
        #     raise ValueError("Mỗi tài khoản chỉ có thể tạo 1 channel")

        channel = Channel(
            owner_email=owner_email,
            name=name,
            description=description,
            require_approval=require_approval,
            members=[ChannelMember(
                email=owner_email,
                username=owner_name,
                role="owner",
                status="approved"
            )]
        )

        await self.channels_col.insert_one(channel.model_dump())

        general_room = ChatRoom(
            channel_id=channel.channel_id,
            name="Phòng chung",
            description="Phòng trò chuyện chung",
            room_type="text",
            created_by=owner_email
        )
        await self.chatrooms_col.insert_one(general_room.model_dump())

        ai_room = ChatRoom(
            channel_id=channel.channel_id,
            name="UTEZoneAI",
            description="Phòng điều khiển bằng UTEZoneAI dành cho chủ kênh",
            room_type="ai",
            created_by=owner_email
        )
        await self.chatrooms_col.insert_one(ai_room.model_dump())

        return channel

    async def get_channel(self, channel_id: str) -> Optional[Channel]:
        data = await self.channels_col.find_one({"channel_id": channel_id})
        if data:
            data.pop("_id", None)
            return Channel(**data)
        return None

    async def get_channel_by_owner(self, owner_email: str) -> Optional[Channel]:
        data = await self.channels_col.find_one({"owner_email": owner_email})
        if data:
            data.pop("_id", None)
            return Channel(**data)
        return None

    async def get_channel_by_invite_code(self, invite_code: str) -> Optional[Channel]:
        data = await self.channels_col.find_one({"invite_code": invite_code})
        if data:
            data.pop("_id", None)
            return Channel(**data)
        return None

    async def update_channel(self, channel_id: str, owner_email: str, **kwargs) -> Optional[Channel]:
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError("Channel không tồn tại")
        if channel.owner_email != owner_email:
            raise ValueError("Chỉ chủ channel mới có thể cập nhật")

        update_data = {}
        for key, value in kwargs.items():
            if value is not None or key == 'avatar':
                update_data[key] = value

        if update_data:
            update_data["updated_at"] = dt.now()
            await self.channels_col.update_one(
                {"channel_id": channel_id},
                {"$set": update_data}
            )

        return await self.get_channel(channel_id)

    async def delete_channel(self, channel_id: str, owner_email: str) -> bool:
        channel = await self.get_channel(channel_id)
        if not channel or channel.owner_email != owner_email:
            return False

        chatrooms = await self.chatrooms_col.find({"channel_id": channel_id}).to_list(length=1000)
        for cr in chatrooms:
            if cr.get("meeting_room_id"):
                try:
                    await meeting_service.end_room(cr["meeting_room_id"], owner_email)
                except:
                    pass

        await self.chatrooms_col.delete_many({"channel_id": channel_id})
        await self.messages_col.delete_many({"channel_id": channel_id})
        await self.channels_col.delete_one({"channel_id": channel_id})
        await self.sessions_col.delete_many({"current_channel_id": channel_id})

        return True

    async def get_my_channels(self, email: str) -> List[dict]:
        channels = []
        cursor = self.channels_col.find({
            "members": {"$elemMatch": {"email": email, "status": "approved"}}
        })
        async for data in cursor:
            data.pop("_id", None)
            channels.append(data)
        return channels

    # ==================== CHANNEL MEMBERSHIP ====================

    async def join_channel(self, email: str, username: str,
                           invite_code: Optional[str] = None,
                           channel_id: Optional[str] = None) -> dict:
        channel = None
        if invite_code:
            channel = await self.get_channel_by_invite_code(invite_code)
        elif channel_id:
            channel = await self.get_channel(channel_id)

        if not channel:
            return {"success": False, "error": "Channel không tồn tại"}

        for m in channel.members:
            if m.email == email:
                if m.status == "approved":
                    return {"success": True, "channel_id": channel.channel_id, "message": "Đã là thành viên"}
                elif m.status == "pending":
                    return {"success": False, "error": "Đang chờ phê duyệt"}
                elif m.status == "rejected":
                    break

        new_member = ChannelMember(
            email=email,
            username=username,
            role="member",
            status="pending" if channel.require_approval else "approved"
        )

        await self.channels_col.update_one(
            {"channel_id": channel.channel_id},
            {"$pull": {"members": {"email": email}}}
        )

        await self.channels_col.update_one(
            {"channel_id": channel.channel_id},
            {"$push": {"members": new_member.model_dump()}}
        )

        if channel.require_approval:
            return {"success": True, "channel_id": channel.channel_id, "status": "pending", "message": "Đã gửi yêu cầu tham gia, chờ phê duyệt"}
        else:
            return {"success": True, "channel_id": channel.channel_id, "status": "approved", "message": "Tham gia channel thành công"}

    async def leave_channel(self, email: str, channel_id: str) -> dict:
        channel = await self.get_channel(channel_id)
        if not channel:
            return {"success": False, "error": "Channel không tồn tại"}

        if channel.owner_email == email:
            return {"success": False, "error": "Chủ channel không thể rời channel. Hãy xóa channel nếu muốn."}

        await self.channels_col.update_one(
            {"channel_id": channel_id},
            {"$pull": {"members": {"email": email}}}
        )

        await self.clear_user_session(email)

        return {"success": True, "message": "Đã rời channel"}

    async def approve_member(self, channel_id: str, owner_email: str,
                              member_email: str, approve: bool) -> dict:
        channel = await self.get_channel(channel_id)
        if not channel:
            return {"success": False, "error": "Channel không tồn tại"}
        if channel.owner_email != owner_email:
            return {"success": False, "error": "Chỉ chủ channel mới có thể phê duyệt"}

        new_status = "approved" if approve else "rejected"
        await self.channels_col.update_one(
            {"channel_id": channel_id, "members.email": member_email},
            {"$set": {"members.$.status": new_status}}
        )

        if not approve:
            await self.channels_col.update_one(
                {"channel_id": channel_id},
                {"$pull": {"members": {"email": member_email}}}
            )

        return {"success": True, "member_email": member_email, "status": new_status}

    async def get_pending_members(self, channel_id: str, owner_email: str) -> List[dict]:
        channel = await self.get_channel(channel_id)
        if not channel or channel.owner_email != owner_email:
            return []

        pending = [m.model_dump() for m in channel.members if m.status == "pending"]
        return pending

    async def kick_member(self, channel_id: str, owner_email: str, member_email: str) -> dict:
        channel = await self.get_channel(channel_id)
        if not channel:
            return {"success": False, "error": "Channel không tồn tại"}
        if channel.owner_email != owner_email:
            return {"success": False, "error": "Chỉ chủ channel mới có thể kick"}
        if channel.owner_email == member_email:
            return {"success": False, "error": "Không thể kick chủ channel"}

        await self.channels_col.update_one(
            {"channel_id": channel_id},
            {"$pull": {"members": {"email": member_email}}}
        )

        # Nếu user đang được ghi session ở channel/chatroom này thì xóa luôn.
        await self.clear_user_session(member_email)

        return {"success": True, "message": f"Đã kick {member_email}"}

    # ==================== CHAT ROOM CRUD ====================

    async def create_chat_room(self, channel_id: str, owner_email: str,
                                name: str, description: Optional[str] = None,
                                room_type: str = "text") -> ChatRoom:
        channel = await self.get_channel(channel_id)
        if not channel:
            raise ValueError("Channel không tồn tại")
        if channel.owner_email != owner_email:
            raise ValueError("Chỉ chủ channel mới có thể tạo chat room")

        if room_type == "ai":
            raise ValueError("Không thể tạo phòng UTEZoneAI thủ công")

        chatroom = ChatRoom(
            channel_id=channel_id,
            name=name,
            description=description,
            room_type=room_type,
            created_by=owner_email
        )

        await self.chatrooms_col.insert_one(chatroom.model_dump())
        return chatroom

    async def get_chat_room(self, room_id: str) -> Optional[ChatRoom]:
        data = await self.chatrooms_col.find_one({"room_id": room_id})
        if data:
            data.pop("_id", None)
            return ChatRoom(**data)
        return None

    async def get_channel_chat_rooms(self, channel_id: str, user_email: str = "") -> List[dict]:
        channel = await self.get_channel(channel_id)

        if not channel:
            return []

        is_owner = channel.owner_email.strip().lower() == user_email.strip().lower()

        if is_owner:
            await self.ensure_channel_ai_room(channel_id, user_email)

        chatrooms = []
        cursor = self.chatrooms_col.find({"channel_id": channel_id}).sort("created_at", 1)

        async for data in cursor:
            data.pop("_id", None)

            # Chỉ chủ channel mới thấy phòng UTEZoneAI
            if data.get("room_type") == "ai" and not is_owner:
                continue

            chatrooms.append(data)

        return chatrooms

    async def update_chat_room(self, room_id: str, owner_email: str, **kwargs) -> Optional[ChatRoom]:
        chatroom = await self.get_chat_room(room_id)
        if not chatroom:
            raise ValueError("Chat room không tồn tại")

        channel = await self.get_channel(chatroom.channel_id)
        if not channel or channel.owner_email != owner_email:
            raise ValueError("Chỉ chủ channel mới có thể cập nhật chat room")

        update_data = {}
        for key, value in kwargs.items():
            if value is not None:
                update_data[key] = value

        if update_data:
            update_data["updated_at"] = dt.now()
            await self.chatrooms_col.update_one(
                {"room_id": room_id},
                {"$set": update_data}
            )

        return await self.get_chat_room(room_id)

    async def delete_chat_room(self, room_id: str, owner_email: str) -> bool:
        chatroom = await self.get_chat_room(room_id)
        if not chatroom:
            return False

        channel = await self.get_channel(chatroom.channel_id)
        if not channel or channel.owner_email != owner_email:
            return False

        if chatroom.meeting_room_id:
            try:
                await meeting_service.end_room(chatroom.meeting_room_id, owner_email)
            except:
                pass

        await self.chatrooms_col.delete_one({"room_id": room_id})
        await self.messages_col.delete_many({"room_id": room_id})
        await self.sessions_col.delete_many({"current_chat_room_id": room_id})

        return True

    async def start_meeting_in_chatroom(self, room_id: str, owner_email: str,
                                         host_name: str) -> dict:
        chatroom = await self.get_chat_room(room_id)
        if not chatroom:
            raise ValueError("Chat room không tồn tại")

        channel = await self.get_channel(chatroom.channel_id)
        if not channel:
            raise ValueError("Channel không tồn tại")

        is_member = any(m.email == owner_email and m.status == "approved" for m in channel.members)
        if not is_member:
            raise ValueError("Bạn không phải thành viên của channel này")

        if chatroom.meeting_room_id:
            meeting_room = await meeting_service.get_room(chatroom.meeting_room_id)
            if meeting_room and meeting_room.status != "ended":
                return {
                    "meeting_room_id": chatroom.meeting_room_id,
                    "room_id": chatroom.meeting_room_id,
                    "status": meeting_room.status
                }

        meeting_room = await meeting_service.create_room(
            room_type="instant",
            host_email=owner_email,
            host_name=host_name,
            title=f"{chatroom.name} - Meeting"
        )

        await self.chatrooms_col.update_one(
            {"room_id": room_id},
            {"$set": {"meeting_room_id": meeting_room.room_id}}
        )

        return {
            "meeting_room_id": meeting_room.room_id,
            "room_id": meeting_room.room_id,
            "status": "active"
        }

    # ==================== USER SESSION ====================

    async def set_user_session(self, email: str, channel_id: Optional[str],
                                chat_room_id: Optional[str]) -> dict:
        if channel_id:
            channel = await self.get_channel(channel_id)
            if not channel:
                raise ValueError("Channel không tồn tại")
            is_member = any(m.email == email and m.status == "approved" for m in channel.members)
            if not is_member:
                raise ValueError("Bạn không phải thành viên của channel này")

        if chat_room_id:
            chatroom = await self.get_chat_room(chat_room_id)
            if not chatroom:
                raise ValueError("Chat room không tồn tại")
            if chatroom.channel_id != channel_id:
                raise ValueError("Chat room không thuộc channel này")

        session = UserSession(
            email=email,
            current_channel_id=channel_id,
            current_chat_room_id=chat_room_id
        )

        await self.sessions_col.update_one(
            {"email": email},
            {"$set": session.model_dump()},
            upsert=True
        )

        return {"success": True, "channel_id": channel_id, "chat_room_id": chat_room_id}

    async def get_user_session(self, email: str) -> Optional[dict]:
        data = await self.sessions_col.find_one({"email": email})
        if data:
            data.pop("_id", None)
            return data
        return None

    async def clear_user_session(self, email: str) -> bool:
        result = await self.sessions_col.delete_one({"email": email})
        return result.deleted_count > 0

    async def get_online_users_in_channel(self, channel_id: str) -> List[dict]:
        sessions = []
        cursor = self.sessions_col.find({"current_channel_id": channel_id})
        async for data in cursor:
            data.pop("_id", None)
            sessions.append(data)
        return sessions

    async def get_online_users_in_chatroom(self, chat_room_id: str) -> List[dict]:
        sessions = []
        cursor = self.sessions_col.find({"current_chat_room_id": chat_room_id})
        async for data in cursor:
            data.pop("_id", None)
            sessions.append(data)
        return sessions


    # ==================== MESSAGES ====================

    async def send_message(
        self,
        room_id: str,
        channel_id: str,
        sender_email: str,
        sender_name: str,
        content: str,
        msg_type: str = "text",
        file_name: str = None
    ) -> Message:
        sender_email_key = (sender_email or "").strip().lower()

        chatroom = await self.get_chat_room(room_id)

        if not chatroom:
            raise ValueError("Chat room không tồn tại")

        if chatroom.room_type == "voice":
            raise ValueError("Không thể gửi tin nhắn trong phòng voice")

        channel = await self.get_channel(channel_id)

        if not channel:
            raise ValueError("Channel không tồn tại")

        is_member = any(
            (m.email or "").strip().lower() == sender_email_key
            and m.status == "approved"
            for m in channel.members
        )

        if not is_member:
            raise ValueError("Bạn không phải thành viên của channel này")

        mute_status = await self.get_member_mute_status(
            channel_id=channel_id,
            member_email=sender_email_key
        )

        if mute_status:
            muted_until = mute_status.get("muted_until")
            reason = mute_status.get("reason") or "Bạn đang bị cấm gửi tin nhắn trong kênh này"

            raise PermissionError({
                "error": "muted",
                "message": "Bạn đang bị cấm gửi tin nhắn trong kênh này",
                "reason": reason,
                "muted_until": muted_until.isoformat() if muted_until else None
            })

        message = Message(
            room_id=room_id,
            channel_id=channel_id,
            sender_email=sender_email,
            sender_name=sender_name,
            content=content,
            msg_type=msg_type,
            file_name=file_name
        )

        await self.messages_col.insert_one(message.model_dump())

        return message

    async def get_messages(self, room_id: str, limit: int = 50, before: Optional[str] = None) -> List[dict]:
        query = {"room_id": room_id}
        if before:
            query["message_id"] = {"$lt": before}
        messages = []
        cursor = self.messages_col.find(query).sort("created_at", 1).limit(limit)
        async for data in cursor:
            data.pop("_id", None)
            messages.append(data)
        return messages
    
    async def delete_message(self, message_id: str, channel_id: str) -> bool:
        result = await self.messages_col.delete_one({
            "message_id": message_id,
            "channel_id": channel_id
        })
        return result.deleted_count > 0

    async def update_read_status(self, email: str, room_id: str, message_id: str = None):
        """Cập nhật thời gian đọc cuối cùng của user trong room"""
        await self.db.user_read_status.update_one(
            {"email": email, "room_id": room_id},
            {"$set": {
                "last_read_at": dt.now(),
                "last_read_message_id": message_id
            }},
            upsert=True
        )

    async def get_unread_count(self, email: str, room_id: str) -> int:
        """Lấy số tin nhắn chưa đọc trong room"""
        status = await self.db.user_read_status.find_one(
            {"email": email, "room_id": room_id}
        )
        last_read = status["last_read_at"] if status else dt.now() - timedelta(days=365)
        # Đếm tin nhắn trong room có created_at > last_read
        count = await self.db.messages.count_documents({
            "room_id": room_id,
            "created_at": {"$gt": last_read}
        })
        return count

    async def get_unread_counts_for_channel(self, email: str, channel_id: str) -> dict:
        """Lấy unread count cho tất cả room trong channel"""
        rooms = await self.get_channel_chat_rooms(channel_id)
        result = {}
        for room in rooms:
            room_id = room["room_id"]
            result[room_id] = await self.get_unread_count(email, room_id)
        return result

    async def get_last_message(self, room_id: str):
        """Lấy tin nhắn mới nhất trong room"""
        data = await self.messages_col.find_one(
            {"room_id": room_id},
            sort=[("created_at", -1)]
        )
        if data:
            return Message(**data)
        return None
    
    async def search_messages(self, room_id: str, keyword: str, limit: int = 50) -> List[dict]:
        """Tìm kiếm tin nhắn trong room (case-insensitive)"""
        query = {
            "room_id": room_id,
            "content": {"$regex": keyword, "$options": "i"}
        }
        cursor = self.messages_col.find(query).sort("created_at", -1).limit(limit)
        messages = []
        async for doc in cursor:
            doc.pop("_id", None)
            messages.append(doc)
        return messages
    
    # ==================== AI MODERATION ====================
    async def get_channel_rules(self, channel_id: str) -> Optional['ChannelRules']:
        data = await self.db.channel_rules.find_one({"channel_id": channel_id})
        if not data:
            return None
        from meeting.models.channel_model import ChannelRules
        return ChannelRules(**data)

    async def save_channel_rules(self, rules: 'ChannelRules'):
        await self.db.channel_rules.update_one(
            {"channel_id": rules.channel_id},
            {"$set": rules.model_dump()},
            upsert=True
        )

    async def add_violation(self, email: str, channel_id: str, rule_type: str) -> int:
        from datetime import datetime, timedelta
        one_day_ago = datetime.now() - timedelta(days=1)
        count = await self.db.violations_meet.count_documents({
            "email": email,
            "channel_id": channel_id,
            "rule_type": rule_type,
            "created_at": {"$gt": one_day_ago}
        })
        await self.db.violations_meet.insert_one({
            "email": email,
            "channel_id": channel_id,
            "rule_type": rule_type,
            "created_at": datetime.now()
        })
        return count + 1

    async def mute_user(
        self,
        email: str,
        channel_id: str,
        minutes: int,
        reason: str = ""
    ):
        expire_at = dt.now() + timedelta(minutes=minutes)

        success = await self.mute_member_in_channel(
            channel_id=channel_id,
            member_email=email,
            muted_until=expire_at,
            reason=reason or "Vi phạm quy tắc kiểm duyệt"
        )

        return {
            "success": success,
            "email": email,
            "channel_id": channel_id,
            "muted_until": expire_at,
            "reason": reason or "Vi phạm quy tắc kiểm duyệt"
        }

    async def is_muted(self, email: str, channel_id: str) -> bool:
        mute_status = await self.get_member_mute_status(
            channel_id=channel_id,
            member_email=email
        )

        return mute_status is not None
    
    async def get_message_by_id(self, message_id: str) -> Optional[dict]:
        data = await self.messages_col.find_one({"message_id": message_id})
        if data:
            data.pop("_id", None)
            return data
        return None


    async def delete_message_by_owner(self, message_id: str, owner_email: str) -> dict:
        message = await self.get_message_by_id(message_id)

        if not message:
            return {
                "success": False,
                "error": "Tin nhắn không tồn tại"
            }

        channel_id = message.get("channel_id")
        channel = await self.get_channel(channel_id)

        if not channel:
            return {
                "success": False,
                "error": "Channel không tồn tại"
            }

        if channel.owner_email != owner_email:
            return {
                "success": False,
                "error": "Chỉ chủ channel mới có thể xóa tin nhắn"
            }

        result = await self.messages_col.delete_one({
            "message_id": message_id,
            "channel_id": channel_id
        })

        if result.deleted_count <= 0:
            return {
                "success": False,
                "error": "Không thể xóa tin nhắn"
            }

        return {
            "success": True,
            "message_id": message_id,
            "room_id": message.get("room_id"),
            "channel_id": channel_id
        }
    
    async def mute_member_in_channel(
        self,
        channel_id: str,
        member_email: str,
        muted_until: dt,
        reason: str = ""
    ) -> bool:
        email_key = (member_email or "").strip().lower()

        result = await self.channels_col.update_one(
            {
                "channel_id": channel_id,
                "members.email": email_key
            },
            {
                "$set": {
                    "members.$.muted_until": muted_until,
                    "members.$.mute_reason": reason or "Vi phạm quy tắc kiểm duyệt"
                }
            }
        )

        return result.modified_count > 0


    async def clear_member_mute(
        self,
        channel_id: str,
        member_email: str
    ) -> bool:
        email_key = (member_email or "").strip().lower()

        result = await self.channels_col.update_one(
            {
                "channel_id": channel_id,
                "members.email": email_key
            },
            {
                "$set": {
                    "members.$.muted_until": None,
                    "members.$.mute_reason": None
                }
            }
        )

        return result.modified_count > 0


    async def get_member_mute_status(
        self,
        channel_id: str,
        member_email: str
    ) -> Optional[dict]:
        email_key = (member_email or "").strip().lower()

        channel = await self.get_channel(channel_id)

        if not channel:
            return None

        member = next(
            (
                m for m in channel.members
                if (m.email or "").strip().lower() == email_key
                and m.status == "approved"
            ),
            None
        )

        if not member:
            return None

        muted_until = getattr(member, "muted_until", None)

        if not muted_until:
            return None

        # Nếu dữ liệu cũ lỡ lưu dạng string thì parse lại.
        if isinstance(muted_until, str):
            try:
                muted_until = dt.fromisoformat(muted_until.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                await self.clear_member_mute(channel_id, email_key)
                return None

        now = dt.now()

        if muted_until <= now:
            await self.clear_member_mute(channel_id, email_key)
            return None

        return {
            "muted": True,
            "muted_until": muted_until,
            "reason": getattr(member, "mute_reason", None) or "Bạn đang bị cấm gửi tin nhắn trong kênh này"
        }

    async def ensure_channel_ai_room(self, channel_id: str, owner_email: str) -> Optional[ChatRoom]:
        channel = await self.get_channel(channel_id)

        if not channel:
            return None

        if channel.owner_email.strip().lower() != owner_email.strip().lower():
            return None

        existing = await self.chatrooms_col.find_one({
            "channel_id": channel_id,
            "room_type": "ai"
        })

        if existing:
            existing.pop("_id", None)
            return ChatRoom(**existing)

        ai_room = ChatRoom(
            channel_id=channel_id,
            name="UTEZoneAI",
            description="Phòng điều khiển bằng UTEZoneAI dành cho chủ kênh",
            room_type="ai",
            created_by=owner_email
        )

        await self.chatrooms_col.insert_one(ai_room.model_dump())

        return ai_room

channel_service = ChannelService()
