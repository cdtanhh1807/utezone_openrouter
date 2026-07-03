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
        self.messages_col = db.ai_room_messages

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

    def _build_context(self, history: List[dict], max_turns: int = 10) -> str:
        """Xây dựng context từ lịch sử hội thoại gần nhất, giàu thông tin để AI tham chiếu."""
        if not history:
            return ""

        recent = history[-max_turns:] if len(history) > max_turns else history

        lines = []
        for msg in recent:
            role_label = "Chủ kênh" if msg.get("role") == "user" else "UTEZoneAI"
            content = msg.get("content", "")
            actions = msg.get("actions", [])
            
            if actions and msg.get("role") == "assistant":
                action_details = []
                for a in actions:
                    atype = a.get("type")
                    if atype == "create_room":
                        detail = (f"[Đã tạo phòng '{a.get('name', 'không tên')}' "
                                  f"(room_id: {a.get('room_id', 'N/A')}, "
                                  f"loại: {a.get('room_type', 'text')}, "
                                  f"mô tả: {a.get('description') or 'không có'})]")
                        action_details.append(detail)
                    elif atype == "update_room":
                        detail = (f"[Đã sửa phòng '{a.get('name', 'không tên')}' "
                                  f"(room_id: {a.get('room_id', 'N/A')})]")
                        action_details.append(detail)
                    elif atype == "delete_room":
                        detail = (f"[Đã xóa phòng '{a.get('room_name', 'không tên')}' "
                                  f"(room_id: {a.get('room_id', 'N/A')})]")
                        action_details.append(detail)
                    elif atype == "send_email":
                        detail = (f"[Đã gửi email: tiêu đề '{a.get('subject', 'không tiêu đề')}', "
                                  f"người nhận: {a.get('recipients_mode', 'unknown')}]")
                        action_details.append(detail)
                    else:
                        action_details.append(f"[{atype}]")
                
                if action_details:
                    lines.append(f"{role_label}: {content}\n" + "\n".join(action_details))
                else:
                    lines.append(f"{role_label}: {content}")
            else:
                lines.append(f"{role_label}: {content}")

        return "\n".join(lines)

    async def _plan_actions(self, message: str, channel, history: List[dict] = None) -> dict:
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

        # Lấy danh sách phòng hiện có để AI biết
        chatrooms = await channel_service.get_channel_chat_rooms(channel.channel_id, channel.owner_email)
        chatrooms_json = json.dumps([
            {"room_id": r.get("room_id"), "name": r.get("name"), "room_type": r.get("room_type"), "description": r.get("description")}
            for r in (chatrooms or [])
        ], ensure_ascii=False)

        # Lấy rules hiện tại
        current_rules = await channel_service.get_channel_rules(channel.channel_id)
        rules_json = ""
        if current_rules:
            rules_json = json.dumps({
                "enabled": current_rules.enabled,
                "rules_text": current_rules.rules_text,
                "enabled_types": current_rules.enabled_types,
                "action": current_rules.action,
                "max_violations": current_rules.max_violations,
                "penalty_time": current_rules.penalty_time
            }, ensure_ascii=False)

        context = ""
        if history:
            context = self._build_context(history)

        prompt = f"""
Bạn là UTEZoneAI, trợ lý quản trị channel trong hệ thống UTEZone.

Nhiệm vụ:
- Phân tích câu lệnh tiếng Việt của chủ channel.
- TRẢ LỜI DỰA TRÊN NGỮ CẢNH (context) nếu có. Nếu chủ kênh nói "xóa hết", "sửa lại", "đổi tên thành..." mà không nêu rõ đối tượng, HÃY HIỂU ĐÓ LÀ TIẾP NỐI CÂU HỎI TRƯỚC ĐÓ.
- Trả về JSON duy nhất, không markdown, không giải thích ngoài JSON.
- Chỉ chọn action nằm trong danh sách hợp lệ.
- Nếu người dùng yêu cầu nhiều việc cùng lúc, trả về nhiều action trong mảng actions theo đúng thứ tự cần làm.

QUAN TRỌNG - Phân biệt mô tả phòng và nội dung email:
- Khi người dùng nói "tạo phòng ... với mô tả ... và gửi thông báo/email ...", phần "mô tả" chỉ bao gồm nội dung mô tả phòng (thời gian, nội dung buổi họp...). Phần "gửi thông báo/email" là yêu cầu riêng, KHÔNG phải mô tả phòng.
- Ví dụ: "tạo phòng họp tên A với mô tả 8h tối nay và gửi thông báo đến toàn bộ" → description = "8h tối nay", email body = thông báo về buổi họp lúc 8h tối nay.
- KHÔNG đưa nguyên văn cả câu lệnh vào mô tả phòng hay nội dung email.

QUAN TRỌNG - Tham chiếu phòng bằng ngữ cảnh:
- Nếu người dùng nói "phòng vừa tạo", "phòng mới tạo", "phòng đó", "phòng họp vừa tạo", "phòng trò chuyện vừa tạo", "phòng vừa rồi" → HÃY dùng room_id hoặc room_name chính xác từ context gần nhất.
- Nếu context cho thấy vừa tạo/sửa một phòng cụ thể, hãy dùng room_id đó trong action update_room/delete_room.
- KHÔNG đoán tên phòng là "Phòng họp" hay "Phòng trò chuyện" khi người dùng dùng từ tham chiếu.

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

2. update_room:
{{
  "type": "update_room",
  "room_id": "id phòng (nếu biết) hoặc null",
  "room_name": "tên phòng hiện tại (nếu không biết room_id)",
  "name": "tên mới",
  "description": "mô tả mới hoặc giữ nguyên nếu không đổi"
}}

Quy ước:
- Nếu người dùng nói "sửa phòng X", "đổi tên phòng X", "cập nhật phòng X" => dùng room_name để tìm.
- Nếu người dùng chỉ nói "sửa lại", "đổi tên" mà không nói rõ phòng nào => DÙNG NGỮ CẢNH (context) để xác định phòng vừa được nhắc đến.
- Nếu người dùng nói "phòng họp vừa tạo", "phòng trò chuyện vừa tạo", "phòng vừa rồi", "phòng đó" => DÙNG NGỮ CẢNH, lấy room_id hoặc room_name chính xác từ context gần nhất. KHÔNG đặt tên phòng là "Phòng họp" hay "Phòng trò chuyện".
- Nếu chỉ đổi tên thì chỉ cần trường name, không cần description.

3. delete_room:
{{
  "type": "delete_room",
  "room_id": "id phòng (nếu biết) hoặc null",
  "room_name": "tên phòng hiện tại (nếu không biết room_id)"
}}

Quy ước:
- "xóa phòng X", "xoá phòng chat X" => dùng room_name.
- Nếu người dùng nói "xóa hết", "xóa tất cả phòng" => TẠO NHIỀU ACTION delete_room cho từng phòng (trừ phòng UTEZoneAI).
- Nếu người dùng nói "xóa hết thành viên" => ĐÓ LÀ delete_member KHÔNG PHẢI delete_room.

4. send_email:
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
- Body phải giữ đúng ý người dùng, NHƯNG KHÔNG copy nguyên văn câu lệnh tạo phòng vào body.
- Nếu người dùng yêu cầu gửi thông báo về phòng vừa tạo/sửa, hãy tự suy luận nội dung email dựa trên TÊN và MÔ TẢ phòng (từ ngữ cảnh). KHÔNG copy nguyên văn câu lệnh của người dùng vào body.
- Ví dụ: người dùng nói "tạo phòng họp tên A mô tả 8h tối và gửi thông báo" → subject: "Thông báo phòng họp A", body: "Phòng họp A sẽ diễn ra vào 8h tối nay. Mọi người vui lòng tham gia đúng giờ."
- Trong subject và body, luôn dùng từ tiếng Việt:
  + "channel" => "kênh"
  + "room" => "phòng"
  + "chat room" => "phòng trò chuyện"
  + "voice room" => "phòng họp"
- Không tự thêm Channel ID, email chủ kênh, hoặc thông tin kỹ thuật vào body.

5. search_members:
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

6. delete_member:
{{
  "type": "delete_member",
  "query": "tên/email/điều kiện tìm thành viên cần xóa",
  "all_except_owner": true hoặc false
}}

Quy ước xóa thành viên:
- Nếu người dùng nói "xóa hết thành viên", "xóa tất cả thành viên trừ chủ kênh", "kick hết", "xóa toàn bộ member" => all_except_owner = true, query = "".
- Nếu người dùng nói "xóa thành viên A", "kick A" => query = "A", all_except_owner = false.
- Nếu người dùng nói "xóa hết" mà trong context trước đó đang nói về thành viên => HIỂU LÀ xóa thành viên.
- Nếu người dùng nói "xóa hết" mà trong context trước đó đang nói về phòng => HIỂU LÀ xóa phòng.
- LUÔN giữ lại chủ kênh, không bao giờ xóa chủ kênh.

7. update_channel:
{{
  "type": "update_channel",
  "name": "tên kênh mới hoặc null nếu không đổi",
  "description": "mô tả mới hoặc null nếu không đổi",
  "require_approval": true/false hoặc null,
  "moderation": {{
    "enabled": true/false hoặc null,
    "rules_text": "luật kiểm duyệt, mỗi dòng một quy tắc" hoặc null,
    "enabled_types": ["text", "image", "video", "file"] hoặc null,
    "action": "warn" hoặc "mute" hoặc "kick" hoặc "ban" hoặc null,
    "max_violations": số nguyên hoặc null,
    "penalty_time": số phút (chỉ khi action = "mute") hoặc null
  }}
}}

Quy ước sửa kênh:
- Nếu người dùng nói "đổi tên kênh thành X" => name = "X".
- Nếu người dùng nói "sửa mô tả kênh thành X" => description = "X".
- Nếu người dùng nói "bật kiểm duyệt" => moderation.enabled = true.
- Nếu người dùng nói "tắt kiểm duyệt" => moderation.enabled = false.
- Nếu người dùng nói "bật phê duyệt thành viên" => require_approval = true.
- Nếu người dùng nói "tắt phê duyệt thành viên" => require_approval = false.
- Khi bật kiểm duyệt, nếu người dùng KHÔNG cung cấp luật, hãy dùng luật mặc định:
  "Không được gửi nội dung phản cảm, xúc phạm, spam hoặc vi phạm pháp luật."
- Nếu người dùng không nói rõ loại nội dung kiểm duyệt, mặc định: ["text"].
- Nếu người dùng không nói rõ hình phạt, mặc định: "warn", max_violations: 3.
- Nếu người dùng chỉ nói "sửa kênh" mà không rõ chi tiết => dùng ask_clarification.

8. get_invite_code:
{{
  "type": "get_invite_code"
}}

Quy ước:
- "lấy mã mời", "xem mã mời", "invite code", "mã tham gia" => get_invite_code.

9. ask_clarification:
{{
  "type": "ask_clarification",
  "message": "câu hỏi cần hỏi lại người dùng"
}}

Chỉ dùng ask_clarification khi câu lệnh không đủ thông tin để thực hiện VÀ không thể suy luận từ ngữ cảnh.

JSON output format bắt buộc:
{{
  "summary": "mô tả ngắn điều sẽ làm",
  "actions": []
}}

Thông tin channel:
- channel_id: {channel.channel_id}
- channel_name: {channel.name}
- owner_email: {channel.owner_email}
- require_approval: {channel.require_approval}
- invite_code: {channel.invite_code}
- members: {members_json}

Danh sách phòng hiện có:
{chatrooms_json}

Luật kiểm duyệt hiện tại:
{rules_json if rules_json else "Chưa có luật (kiểm duyệt đang tắt)"}

{("Ngữ cảnh hội thoại gần đây:" + chr(10) + context) if context else ""}

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
                        "message": "Bạn muốn tạo phòng, sửa phòng, xóa phòng, gửi email, tìm/xóa thành viên, sửa kênh, hay lấy mã mời?"
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

    def _is_valid_email(self, email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        # Regex đơn giản: có @ và domain hợp lệ
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None

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
            raw_emails = [
                e.strip() for e in action.get("emails", [])
                if e and e.strip()
            ]
            valid_emails = [e for e in raw_emails if self._is_valid_email(e)]
            return list(dict.fromkeys(valid_emails))

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

    async def _broadcast_chatroom_updated(self, channel_id: str, chatroom):
        chatroom_dict = chatroom.model_dump()

        for key in ["created_at", "updated_at"]:
            if isinstance(chatroom_dict.get(key), dt):
                chatroom_dict[key] = chatroom_dict[key].isoformat()

        await ws_manager.broadcast(channel_id, {
            "type": "chatroom_updated",
            "channel_id": channel_id,
            "chatroom": chatroom_dict
        })

    async def _broadcast_chatroom_deleted(self, channel_id: str, room_id: str, room_name: str):
        await ws_manager.broadcast(channel_id, {
            "type": "chatroom_deleted",
            "room_id": room_id,
            "room_name": room_name
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
        message: str,
        base_url: str = None
    ) -> dict:
        owner_email = owner_email.strip().lower()

        channel = await channel_service.get_channel(channel_id)

        if not channel:
            raise ValueError("Channel không tồn tại")

        if channel.owner_email.strip().lower() != owner_email:
            raise ValueError("Chỉ chủ channel mới có thể dùng UTEZoneAI")

        # Lấy lịch sử để có context
        history = await self.get_history(channel_id, owner_email, limit=20)

        await self.save_message(
            channel_id=channel_id,
            user_email=owner_email,
            role="user",
            content=message
        )

        plan = await self._plan_actions(message, channel, history)
        actions = plan.get("actions", [])

        result_lines = []
        executed_actions = []

        # Lấy danh sách phòng để resolve room_name -> room_id
        chatrooms = await channel_service.get_channel_chat_rooms(channel_id, owner_email)
        chatroom_map = {self._normalize(r.get("name", "")): r for r in (chatrooms or [])}

        for action in actions:
            action_type = action.get("type")
            executed_actions.append(action)

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

                # Cập nhật action để lưu vào history với thông tin thực tế
                action["room_id"] = chatroom.room_id
                action["room_type"] = chatroom.room_type
                action["name"] = chatroom.name
                action["description"] = chatroom.description or ""

                label = "trò chuyện" if room_type == "text" else "họp"
                result_lines.append(f"Đã tạo phòng {label}: {chatroom.name}")

            elif action_type == "update_room":
                room_id = action.get("room_id")
                room_name = action.get("room_name")
                target_room = None

                # Resolve room_id
                if room_id:
                    target_room = await channel_service.get_chat_room(room_id)
                elif room_name:
                    # Tìm theo tên
                    target_room_data = chatroom_map.get(self._normalize(room_name))
                    if target_room_data:
                        target_room = await channel_service.get_chat_room(target_room_data.get("room_id"))

                if not target_room:
                    result_lines.append(f"Không tìm thấy phòng \"{room_name or room_id}\" để cập nhật.")
                    continue

                if target_room.room_type == "ai":
                    result_lines.append("Không thể sửa phòng UTEZoneAI.")
                    continue

                new_name = action.get("name")
                new_desc = action.get("description")

                update_kwargs = {}
                if new_name is not None:
                    update_kwargs["name"] = new_name
                if new_desc is not None:
                    update_kwargs["description"] = new_desc

                if not update_kwargs:
                    result_lines.append("Không có thông tin nào để cập nhật.")
                    continue

                try:
                    updated = await channel_service.update_chat_room(
                        room_id=target_room.room_id,
                        owner_email=owner_email,
                        **update_kwargs
                    )
                    await self._broadcast_chatroom_updated(channel_id, updated)
                    
                    # Cập nhật action để lưu vào history
                    action["room_id"] = updated.room_id
                    action["name"] = updated.name
                    
                    result_lines.append(f"Đã cập nhật phòng \"{updated.name}\".")
                except Exception as e:
                    result_lines.append(f"Lỗi cập nhật phòng: {str(e)}")

            elif action_type == "delete_room":
                room_id = action.get("room_id")
                room_name = action.get("room_name")
                target_rooms = []

                if room_id:
                    room = await channel_service.get_chat_room(room_id)
                    if room:
                        target_rooms.append(room)
                elif room_name:
                    # Tìm theo tên
                    room_data = chatroom_map.get(self._normalize(room_name))
                    if room_data:
                        room = await channel_service.get_chat_room(room_data.get("room_id"))
                        if room:
                            target_rooms.append(room)
                else:
                    # "xóa hết" tất cả phòng (trừ AI room)
                    for r_data in (chatrooms or []):
                        if r_data.get("room_type") != "ai":
                            room = await channel_service.get_chat_room(r_data.get("room_id"))
                            if room:
                                target_rooms.append(room)

                if not target_rooms:
                    result_lines.append("Không tìm thấy phòng nào để xóa.")
                    continue

                deleted_count = 0
                for room in target_rooms:
                    if room.room_type == "ai":
                        continue
                    try:
                        success = await channel_service.delete_chat_room(room.room_id, owner_email)
                        if success:
                            await self._broadcast_chatroom_deleted(channel_id, room.room_id, room.name)
                            deleted_count += 1
                            # Cập nhật action để lưu vào history
                            action["room_id"] = room.room_id
                            action["room_name"] = room.name
                    except Exception as e:
                        result_lines.append(f"Lỗi xóa phòng \"{room.name}\": {str(e)}")

                if deleted_count > 0:
                    result_lines.append(f"Đã xóa {deleted_count} phòng.")

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

            elif action_type == "delete_member":
                query = action.get("query") or ""
                all_except_owner = bool(action.get("all_except_owner", False))

                if all_except_owner:
                    # Xóa tất cả thành viên trừ chủ kênh
                    targets = [
                        m for m in channel.members
                        if m.status == "approved"
                        and self._normalize(m.email) != self._normalize(channel.owner_email)
                    ]
                else:
                    # Tìm theo query
                    targets = self._match_members(channel=channel, query=query, all_members=False)
                    # Loại bỏ chủ kênh
                    targets = [
                        m for m in targets
                        if self._normalize(m.email) != self._normalize(channel.owner_email)
                    ]

                if not targets:
                    result_lines.append("Không tìm thấy thành viên nào để xóa (chủ kênh luôn được giữ lại).")
                    continue

                kicked_count = 0
                for m in targets:
                    try:
                        result = await channel_service.kick_member(channel_id, owner_email, m.email)
                        if result.get("success"):
                            # Broadcast kick event
                            await ws_manager.broadcast(channel_id, {
                                "type": "member_kicked",
                                "channel_id": channel_id,
                                "member_email": m.email,
                                "kicked_by": owner_email
                            })
                            await ws_manager.send_to_account(m.email, {
                                "type": "you_were_kicked",
                                "channel_id": channel_id,
                                "member_email": m.email,
                                "kicked_by": owner_email
                            })
                            kicked_count += 1
                    except Exception as e:
                        result_lines.append(f"Lỗi xóa {m.email}: {str(e)}")

                if kicked_count > 0:
                    result_lines.append(f"Đã xóa {kicked_count} thành viên khỏi kênh.")

            elif action_type == "send_email":
                recipients = self._resolve_email_recipients(channel, action)

                subject = action.get("subject") or f"Thông báo từ kênh {channel.name}"
                subject = self._vietnamese_terms(subject)

                raw_body = action.get("body")
                if not raw_body:
                    # Tự suy luận nội dung email dựa trên context phòng vừa tạo/sửa
                    room_context = None
                    for a in reversed(executed_actions):
                        if a.get("type") == "create_room":
                            room_context = a
                            break
                    if room_context:
                        room_name = room_context.get("name", "phòng họp")
                        room_desc = room_context.get("description", "")
                        room_type = room_context.get("room_type", "voice")
                        label = "họp" if room_type == "voice" else "trò chuyện"
                        raw_body = f"Phòng {label} '{room_name}' đã được tạo"
                        if room_desc:
                            raw_body += f" với nội dung: {room_desc}"
                        raw_body += ". Mọi người vui lòng tham gia đúng giờ."
                    else:
                        raw_body = message
                else:
                    raw_body = self._vietnamese_terms(raw_body)

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

            elif action_type == "update_channel":
                update_kwargs = {}
                if action.get("name") is not None:
                    update_kwargs["name"] = action["name"]
                if action.get("description") is not None:
                    update_kwargs["description"] = action["description"]
                if action.get("require_approval") is not None:
                    update_kwargs["require_approval"] = action["require_approval"]

                # Xử lý moderation
                mod_data = action.get("moderation")
                if mod_data is not None:
                    # Lấy rules hiện tại
                    current_rules = await channel_service.get_channel_rules(channel_id)
                    from meeting.models.channel_model import ChannelRules

                    if current_rules:
                        rules = ChannelRules(
                            channel_id=channel_id,
                            enabled=mod_data.get("enabled") if mod_data.get("enabled") is not None else current_rules.enabled,
                            rules_text=mod_data.get("rules_text") if mod_data.get("rules_text") is not None else current_rules.rules_text,
                            enabled_types=mod_data.get("enabled_types") if mod_data.get("enabled_types") is not None else current_rules.enabled_types,
                            action=mod_data.get("action") if mod_data.get("action") is not None else current_rules.action,
                            max_violations=mod_data.get("max_violations") if mod_data.get("max_violations") is not None else current_rules.max_violations,
                            penalty_time=mod_data.get("penalty_time") if mod_data.get("penalty_time") is not None else current_rules.penalty_time,
                            updated_by=owner_email
                        )
                    else:
                        # Tạo mới
                        rules = ChannelRules(
                            channel_id=channel_id,
                            enabled=mod_data.get("enabled", False),
                            rules_text=mod_data.get("rules_text") or "Không được gửi nội dung phản cảm, xúc phạm, spam hoặc vi phạm pháp luật.",
                            enabled_types=mod_data.get("enabled_types") or ["text"],
                            action=mod_data.get("action") or "warn",
                            max_violations=mod_data.get("max_violations") or 3,
                            penalty_time=mod_data.get("penalty_time"),
                            updated_by=owner_email
                        )

                    await channel_service.save_channel_rules(rules)

                if update_kwargs:
                    try:
                        updated = await channel_service.update_channel(
                            channel_id=channel_id,
                            owner_email=owner_email,
                            **update_kwargs
                        )

                        # Broadcast cập nhật channel
                        from fastapi.encoders import jsonable_encoder
                        channel_dict = jsonable_encoder(updated.model_dump())

                        member_emails = [
                            m.email.strip().lower()
                            for m in updated.members
                            if m.status == "approved"
                        ]

                        await ws_manager.broadcast(channel_id, {
                            "type": "channel_updated",
                            "channel_id": channel_id,
                            "channel": channel_dict
                        })
                        await ws_manager.broadcast_to_accounts(member_emails, {
                            "type": "channel_updated",
                            "channel_id": channel_id,
                            "channel": channel_dict
                        })

                        if "name" in update_kwargs:
                            result_lines.append(f"Đã đổi tên kênh thành: {updated.name}")
                        if "description" in update_kwargs:
                            result_lines.append(f"Đã cập nhật mô tả kênh.")
                        if "require_approval" in update_kwargs:
                            status = "bật" if update_kwargs["require_approval"] else "tắt"
                            result_lines.append(f"Đã {status} yêu cầu phê duyệt thành viên.")
                    except Exception as e:
                        result_lines.append(f"Lỗi cập nhật kênh: {str(e)}")

                if mod_data is not None:
                    mod_enabled = mod_data.get("enabled")
                    if mod_enabled is True:
                        result_lines.append("Đã bật kiểm duyệt nội dung.")
                        types = mod_data.get("enabled_types") or ["text"]
                        result_lines.append(f"Loại kiểm duyệt: {', '.join(types)}.")
                        action_type = mod_data.get("action") or "warn"
                        result_lines.append(f"Hình phạt vi phạm: {action_type}.")
                    elif mod_enabled is False:
                        result_lines.append("Đã tắt kiểm duyệt nội dung.")

            elif action_type == "get_invite_code":
                invite_code = channel.invite_code
                result_lines.append(f"Mã mời của kênh: {invite_code}")

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
            actions=executed_actions
        )

        return {
            "reply": assistant_text,
            "actions": executed_actions
        }




channel_ai_service = ChannelAIService()