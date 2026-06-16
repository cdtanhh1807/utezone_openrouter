import json
import re
from datetime import datetime as dt
from typing import List, Dict, Any, Optional
import textwrap

from core.database import db
from meeting.services.channel_service import channel_service
from meeting.websocket.manager import ws_manager
from meeting.services.moderation_service import _call_openrouter, TEXT_MODEL
from core.mailer import send_email


class ChannelAIService:
    def __init__(self):
        self.db = db
        self.messages_col = db.channel_ai_messages

    async def save_message(
        self,
        channel_id: str,
        user_email: str,
        role: str,
        content: str,
        actions: Optional[List[Dict[str, Any]]] = None
    ) -> dict:
        doc = {
            "channel_id": channel_id,
            "user_email": user_email,
            "role": role,
            "content": content,
            "actions": actions or [],
            "created_at": dt.now()
        }

        result = await self.messages_col.insert_one(doc)

        doc["_id"] = str(result.inserted_id)
        if isinstance(doc.get("created_at"), dt):
            doc["created_at"] = doc["created_at"].isoformat()

        return doc

    async def get_history(
        self,
        channel_id: str,
        user_email: str,
        limit: int = 80
    ) -> List[dict]:
        cursor = self.messages_col.find({
            "channel_id": channel_id,
            "user_email": user_email
        }).sort("created_at", 1).limit(limit)

        items = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])

            if isinstance(doc.get("created_at"), dt):
                doc["created_at"] = doc["created_at"].isoformat()

            items.append(doc)

        return items

    def _extract_json(self, raw: str) -> dict:
        if not raw:
            return {}

        text = str(raw).strip()

        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}

        return {}

    async def _plan_actions(self, message: str, channel) -> dict:
        members = [
            {
                "email": m.email,
                "username": m.username,
                "role": m.role,
                "status": m.status
            }
            for m in channel.members
            if m.status == "approved"
        ]

        members_json = json.dumps(members, ensure_ascii=False)

        prompt = f"""
Bạn là UTEZoneAI, trợ lý quản trị channel trong hệ thống UTEZone.

Nhiệm vụ:
- Phân tích câu lệnh tiếng Việt của chủ channel.
- Trả về JSON duy nhất, không markdown, không giải thích ngoài JSON.
- Chỉ chọn action nằm trong danh sách hợp lệ.
- Nếu người dùng yêu cầu nhiều việc cùng lúc, trả về nhiều action trong mảng actions theo đúng thứ tự cần làm.

Các action hợp lệ:

1. create_room:
{{
  "type": "create_room",
  "room_type": "text" hoặc "voice",
  "name": "tên phòng",
  "description": "mô tả ngắn hoặc rỗng"
}}

Quy ước:
- "phòng trò chuyện", "chat room", "text room", "phòng chat" => room_type = "text".
- "phòng họp", "voice room", "phòng voice", "meeting" => room_type = "voice".

2. send_email:
{{
  "type": "send_email",
  "recipients_mode": "all" hoặc "emails" hoặc "names" hoặc "query",
  "emails": ["a@gmail.com"],
  "names": ["Liam"],
  "query": "@gmail.com hoặc Liam hoặc chuỗi tìm kiếm",
  "subject": "tiêu đề email",
  "body": "nội dung email"
}}

Quy ước gửi email:
- Nếu người dùng nói gửi cho tất cả/toàn bộ/mọi thành viên trong kênh => recipients_mode = "all".
- Nếu người dùng nêu email cụ thể => recipients_mode = "emails".
- Nếu người dùng nêu tên người nhận cụ thể => recipients_mode = "names".
- Nếu người dùng nêu điều kiện tìm kiếm như @gmail.com, tên gần đúng, domain email => recipients_mode = "query".
- Nếu người dùng không nói rõ tiêu đề, hãy tự tạo subject phù hợp bằng tiếng Việt.
- Body phải giữ đúng ý người dùng.
- Trong subject và body, luôn dùng từ tiếng Việt:
  + "channel" => "kênh"
  + "room" => "phòng"
  + "chat room" => "phòng trò chuyện"
  + "voice room" => "phòng họp"
- Không tự thêm Channel ID, email chủ kênh, hoặc thông tin kỹ thuật vào body.

3. search_members:
{{
  "type": "search_members",
  "query": "chuỗi cần tìm, ví dụ Liam hoặc @gmail.com",
  "all": true hoặc false
}}

Quy ước tìm thành viên:
- Nếu người dùng yêu cầu "tìm tất cả thành viên", "liệt kê tất cả thành viên", "danh sách thành viên",
  "show all members", "tất cả member", "toàn bộ thành viên" thì trả:
{{
  "type": "search_members",
  "query": "",
  "all": true
}}
- Nếu người dùng tìm theo tên/email/domain thì all = false và query là từ khóa cần tìm.

4. ask_clarification:
{{
  "type": "ask_clarification",
  "message": "câu hỏi cần hỏi lại người dùng"
}}

Chỉ dùng ask_clarification khi câu lệnh không đủ thông tin để thực hiện.

JSON output format bắt buộc:
{{
  "summary": "mô tả ngắn điều sẽ làm",
  "actions": []
}}

Thông tin channel:
- channel_id: {channel.channel_id}
- channel_name: {channel.name}
- owner_email: {channel.owner_email}
- members: {members_json}

Câu lệnh của chủ channel:
{message}
"""

        raw = await _call_openrouter(prompt=prompt, model=TEXT_MODEL)
        data = self._extract_json(raw)

        if not data or not isinstance(data.get("actions"), list):
            return {
                "summary": "Mình chưa hiểu rõ yêu cầu. Bạn có thể nói rõ hơn không?",
                "actions": [
                    {
                        "type": "ask_clarification",
                        "message": "Bạn muốn tạo phòng, gửi email hay tìm thành viên?"
                    }
                ]
            }

        return data

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _match_members(
        self,
        channel,
        query: str = "",
        all_members: bool = False
    ) -> List[Any]:
        q = self._normalize(query)

        approved_members = [
            m for m in channel.members
            if m.status == "approved"
        ]

        all_keywords = [
            "*",
            "all",
            "tất cả",
            "tat ca",
            "toàn bộ",
            "toan bo",
            "danh sách",
            "danh sach",
            "mọi người",
            "moi nguoi",
            "thành viên",
            "thanh vien"
        ]

        if all_members or q in all_keywords:
            return approved_members

        if not q:
            return []

        results = []

        for m in approved_members:
            email = self._normalize(m.email)
            username = self._normalize(m.username or "")

            if q in email or q in username:
                results.append(m)

        return results

    def _resolve_email_recipients(self, channel, action: dict) -> List[str]:
        mode = action.get("recipients_mode") or "emails"

        approved_members = [
            m for m in channel.members
            if m.status == "approved"
        ]

        if mode == "all":
            return list(dict.fromkeys([
                m.email for m in approved_members
                if m.email
            ]))

        if mode == "emails":
            requested = {
                self._normalize(str(e))
                for e in action.get("emails", [])
                if self._normalize(str(e))
            }

            return list(dict.fromkeys([
                m.email for m in approved_members
                if self._normalize(m.email) in requested
            ]))

        if mode == "names":
            names = [
                self._normalize(str(n))
                for n in action.get("names", [])
                if self._normalize(str(n))
            ]

            matched = []

            for m in approved_members:
                username = self._normalize(m.username or "")
                email = self._normalize(m.email or "")

                if any(n in username or n in email for n in names):
                    matched.append(m.email)

            return list(dict.fromkeys(matched))

        if mode == "query":
            matches = self._match_members(
                channel=channel,
                query=action.get("query") or "",
                all_members=False
            )

            return list(dict.fromkeys([
                m.email for m in matches
                if m.email
            ]))

        return []

    def _build_channel_email_body(
        self,
        channel,
        owner_email: str,
        body: str
    ) -> str:
        channel_name = channel.name or "Kênh UTEZone"

        clean_body = textwrap.dedent(body or "").strip()

        return (
            f"[UTEZone - Kênh: {channel_name}]\n\n"
            f"Người gửi: Chủ kênh {channel_name}\n\n"
            f"Nội dung:\n"
            f"{clean_body}\n\n"
            f"---\n"
            f"Email này được gửi tự động từ UTEZoneAI theo yêu cầu của Chủ kênh {channel_name}."
        )

    def _render_mail_preview(
        self,
        subject: str,
        body: str,
        recipients: List[str]
    ) -> str:
        preview_recipients = ", ".join(recipients[:5])

        if len(recipients) > 5:
            preview_recipients += f", ... và {len(recipients) - 5} người khác"

        return (
            "Preview email đã gửi:\n"
            f"Người nhận: {preview_recipients}\n"
            f"Tiêu đề: {subject}\n"
            "Nội dung:\n"
            f"{body}"
        )

    async def _broadcast_chatroom_created(self, channel_id: str, chatroom):
        chatroom_dict = chatroom.model_dump()

        for key in ["created_at", "updated_at"]:
            if isinstance(chatroom_dict.get(key), dt):
                chatroom_dict[key] = chatroom_dict[key].isoformat()

        await ws_manager.broadcast(channel_id, {
            "type": "chatroom_created",
            "channel_id": channel_id,
            "chatroom": chatroom_dict
        })

    def _vietnamese_terms(self, text: str) -> str:
        if not text:
            return ""

        replacements = {
            "chat text room": "phòng trò chuyện",
            "text room": "phòng trò chuyện",
            "chat room": "phòng trò chuyện",
            "voice room": "phòng họp",
            "meeting room": "phòng họp",
            "room": "phòng",
            "Room": "Phòng",
            "channel": "kênh",
            "Channel": "Kênh",
        }

        result = str(text)

        for old, new in replacements.items():
            result = result.replace(old, new)

        return result

    async def execute_command(
        self,
        channel_id: str,
        owner_email: str,
        message: str
    ) -> dict:
        owner_email = owner_email.strip().lower()

        channel = await channel_service.get_channel(channel_id)

        if not channel:
            raise ValueError("Channel không tồn tại")

        if channel.owner_email.strip().lower() != owner_email:
            raise ValueError("Chỉ chủ channel mới có thể dùng UTEZoneAI")

        await self.save_message(
            channel_id=channel_id,
            user_email=owner_email,
            role="user",
            content=message
        )

        plan = await self._plan_actions(message, channel)
        actions = plan.get("actions", [])

        result_lines = []

        for action in actions:
            action_type = action.get("type")

            if action_type == "create_room":
                room_type = action.get("room_type", "text")
                name = (action.get("name") or "").strip()

                if room_type not in ["text", "voice"]:
                    result_lines.append("Không thể thực hiện: Loại phòng không hợp lệ. Chỉ hỗ trợ text hoặc voice.")
                    continue

                if not name:
                    result_lines.append("Không thể thực hiện: Thiếu tên phòng cần tạo.")
                    continue

                chatroom = await channel_service.create_chat_room(
                    channel_id=channel_id,
                    owner_email=owner_email,
                    name=name,
                    description=action.get("description") or "",
                    room_type=room_type
                )

                await self._broadcast_chatroom_created(channel_id, chatroom)

                label = "trò chuyện" if room_type == "text" else "họp"
                result_lines.append(f"Đã tạo phòng {label}: {chatroom.name}")

            elif action_type == "search_members":
                query = action.get("query") or ""
                all_members = bool(action.get("all", False))

                matches = self._match_members(
                    channel=channel,
                    query=query,
                    all_members=all_members
                )

                if not matches:
                    if all_members:
                        result_lines.append("Không tìm thấy thành viên nào trong channel.")
                    else:
                        result_lines.append(f"Không tìm thấy thành viên phù hợp với: {query}")
                else:
                    if all_members:
                        result_lines.append(f"Danh sách tất cả thành viên trong channel ({len(matches)}):")
                    else:
                        result_lines.append(f"Tìm thấy {len(matches)} thành viên:")

                    for m in matches[:50]:
                        role_label = "chủ channel" if m.role == "owner" else "thành viên"
                        result_lines.append(
                            f"- {m.username or m.email.split('@')[0]} ({m.email}) - {role_label}"
                        )

                    if len(matches) > 50:
                        result_lines.append(f"... và {len(matches) - 50} thành viên khác.")

            elif action_type == "send_email":
                recipients = self._resolve_email_recipients(channel, action)

                subject = action.get("subject") or f"Thông báo từ kênh {channel.name}"
                subject = self._vietnamese_terms(subject)

                raw_body = self._vietnamese_terms(action.get("body") or message)

                final_body = self._build_channel_email_body(
                    channel=channel,
                    owner_email=owner_email,
                    body=raw_body
                )

                if not recipients:
                    result_lines.append("Không tìm thấy người nhận email phù hợp.")
                    continue

                sent = 0
                failed = 0

                for recipient_email in recipients:
                    try:
                        await send_email("UTEZone Meet", recipient_email, subject, final_body)
                        sent += 1
                    except Exception as e:
                        print(f"[CHANNEL_AI][MAIL] Failed to send to {recipient_email}: {e}")
                        failed += 1

                result_lines.append(f"Đã gửi email cho {sent} người nhận. Lỗi: {failed}.")

                if sent > 0:
                    result_lines.append("")
                    result_lines.append(
                        self._render_mail_preview(
                            subject=subject,
                            body=final_body,
                            recipients=recipients
                        )
                    )

            elif action_type == "ask_clarification":
                result_lines.append(
                    action.get("message") or "Bạn cần cung cấp thêm thông tin."
                )

            else:
                result_lines.append(f"Mình chưa hỗ trợ thao tác: {action_type}")

        if not result_lines:
            result_lines.append(
                plan.get("summary") or "Mình chưa thực hiện thao tác nào."
            )

        assistant_text = "\n".join(result_lines)

        await self.save_message(
            channel_id=channel_id,
            user_email=owner_email,
            role="assistant",
            content=assistant_text,
            actions=actions
        )

        return {
            "reply": assistant_text,
            "actions": actions
        }


channel_ai_service = ChannelAIService()
