from typing import Dict, Optional, Set
from fastapi import WebSocket


class ChannelWebSocketManager:
    """
    WebSocket manager cho channel chat + presence.

    Cấu trúc lưu trữ:
    - active_connections[channel_id][email][socket_id] = WebSocket
    - online_users[channel_id][email] = user data để gửi snapshot cho frontend

    Lý do dùng socket_id theo từng email:
    - Một user có thể mở nhiều tab.
    - Chỉ đánh dấu offline khi user không còn socket nào trong channel.
    """

    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Dict[str, WebSocket]]] = {}
        self.online_users: Dict[str, Dict[str, dict]] = {}
        self.socket_to_channel: Dict[str, str] = {}
        self.socket_to_email: Dict[str, str] = {}
        self.user_connections = {}
        self.user_socket_to_email = {}

    def _socket_id(self, websocket: WebSocket) -> str:
        return str(id(websocket))

    async def connect(
        self,
        websocket: WebSocket,
        channel_id: str,
        email: str,
        user_data: Optional[dict] = None,
    ):
        await websocket.accept()

        socket_id = self._socket_id(websocket)
        email_key = (email or "").strip().lower()

        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = {}
        if email_key not in self.active_connections[channel_id]:
            self.active_connections[channel_id][email_key] = {}

        was_offline = len(self.active_connections[channel_id][email_key]) == 0

        self.active_connections[channel_id][email_key][socket_id] = websocket
        self.socket_to_channel[socket_id] = channel_id
        self.socket_to_email[socket_id] = email_key

        presence_user = {
            "email": email,
            "username": (user_data or {}).get("username") or email.split("@")[0],
            "role": (user_data or {}).get("role") or "member",
            "status": (user_data or {}).get("status") or "approved",
            "avatar": (user_data or {}).get("avatar"),
        }

        if channel_id not in self.online_users:
            self.online_users[channel_id] = {}
        self.online_users[channel_id][email_key] = presence_user

        # Gửi snapshot danh sách online hiện tại cho socket vừa vào.
        await websocket.send_json({
            "type": "presence_snapshot",
            "online_users": list(self.online_users.get(channel_id, {}).values())
        })

        # Chỉ broadcast online khi đây là socket đầu tiên của user trong channel.
        if was_offline:
            await self.broadcast(
                channel_id,
                {
                    "type": "presence_update",
                    "action": "online",
                    "user": presence_user,
                },
                exclude_websocket=websocket,
            )

        total_connections = sum(
            len(sockets)
            for sockets in self.active_connections.get(channel_id, {}).values()
        )
        print(
            f"[WS] Connected channel={channel_id}, email={email_key}, "
            f"connections={total_connections}, online_users={len(self.online_users.get(channel_id, {}))}"
        )

    async def disconnect(
        self,
        websocket: WebSocket,
        channel_id: Optional[str] = None,
        email: Optional[str] = None,
    ):
        socket_id = self._socket_id(websocket)
        channel_id = channel_id or self.socket_to_channel.get(socket_id)
        email_key = (email or self.socket_to_email.get(socket_id) or "").strip().lower()

        self.socket_to_channel.pop(socket_id, None)
        self.socket_to_email.pop(socket_id, None)

        if not channel_id or not email_key:
            return

        channel_connections = self.active_connections.get(channel_id)
        if not channel_connections:
            return

        user_sockets = channel_connections.get(email_key)
        if user_sockets and socket_id in user_sockets:
            user_sockets.pop(socket_id, None)

        # Nếu user không còn tab/socket nào trong channel thì offline.
        if not user_sockets:
            channel_connections.pop(email_key, None)

            if channel_id in self.online_users:
                self.online_users[channel_id].pop(email_key, None)
                if not self.online_users[channel_id]:
                    self.online_users.pop(channel_id, None)

            await self.broadcast(channel_id, {
                "type": "presence_update",
                "action": "offline",
                "user_email": email_key,
            })

        if not channel_connections:
            self.active_connections.pop(channel_id, None)

        print(f"[WS] Disconnected channel={channel_id}, email={email_key}")

    async def broadcast(
        self,
        channel_id: str,
        message: dict,
        exclude_websocket: Optional[WebSocket] = None,
    ):
        channel_connections = self.active_connections.get(channel_id, {})
        if not channel_connections:
            print(f"[BROADCAST] channel {channel_id} not in active_connections")
            return

        dead_sockets = []

        total_connections = sum(len(sockets) for sockets in channel_connections.values())
        print(f"[BROADCAST] channel {channel_id} has {total_connections} connections")

        for email, sockets in list(channel_connections.items()):
            for socket_id, conn in list(sockets.items()):
                if exclude_websocket is not None and conn is exclude_websocket:
                    continue
                try:
                    await conn.send_json(message)
                except Exception as e:
                    print(f"[BROADCAST] error: {e}")
                    dead_sockets.append((email, socket_id, conn))

        for email, socket_id, conn in dead_sockets:
            await self.disconnect(conn, channel_id, email)

    async def send_to_user(self, channel_id: str, email: str, message: dict):
        email_key = (email or "").strip().lower()
        sockets = self.active_connections.get(channel_id, {}).get(email_key, {})

        for socket_id, ws in list(sockets.items()):
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(ws, channel_id, email_key)

    async def connect_user(self, websocket: WebSocket, email: str):
        await websocket.accept()

        socket_id = self._socket_id(websocket)
        email_key = (email or "").strip().lower()

        if not email_key:
            await websocket.close(code=1008, reason="Email không hợp lệ")
            return

        if email_key not in self.user_connections:
            self.user_connections[email_key] = {}

        self.user_connections[email_key][socket_id] = websocket
        self.user_socket_to_email[socket_id] = email_key

        print(
            f"[USER_WS] Connected email={email_key}, "
            f"connections={len(self.user_connections[email_key])}"
        )

    async def disconnect_user(self, websocket: WebSocket):
        socket_id = self._socket_id(websocket)
        email_key = self.user_socket_to_email.get(socket_id)

        self.user_socket_to_email.pop(socket_id, None)

        if not email_key:
            return

        user_sockets = self.user_connections.get(email_key)

        if user_sockets and socket_id in user_sockets:
            user_sockets.pop(socket_id, None)

        if user_sockets is not None and not user_sockets:
            self.user_connections.pop(email_key, None)

        print(f"[USER_WS] Disconnected email={email_key}")

    async def send_to_account(self, email: str, message: dict):
        email_key = (email or "").strip().lower()

        if not email_key:
            return

        sockets = self.user_connections.get(email_key, {})

        if not sockets:
            print(f"[USER_WS] user {email_key} has no global websocket")
            return

        dead_sockets = []

        print(
            f"[USER_WS] send_to_account email={email_key}, "
            f"type={message.get('type')}, sockets={len(sockets)}"
        )

        for socket_id, ws in list(sockets.items()):
            try:
                await ws.send_json(message)
            except Exception as e:
                print(
                    f"[USER_WS] send_to_account error "
                    f"email={email_key}, type={message.get('type')}: {e}"
                )
                dead_sockets.append((socket_id, ws))

        for socket_id, ws in dead_sockets:
            try:
                await self.disconnect_user(ws)
            except Exception:
                self.user_socket_to_email.pop(socket_id, None)
                sockets.pop(socket_id, None)

    async def broadcast_to_accounts(self, emails: list, message: dict):
        sent = set()

        print(
            f"[USER_WS] broadcast_to_accounts type={message.get('type')}, "
            f"emails={emails}"
        )

        for email in emails or []:
            email_key = (email or "").strip().lower()

            if not email_key or email_key in sent:
                continue

            sent.add(email_key)
            await self.send_to_account(email_key, message)

    async def force_disconnect_user(
        self,
        channel_id: str,
        email: str,
        code: int = 4001,
        reason: str = "Disconnected",
    ):
        email_key = (email or "").strip().lower()
        sockets = list(self.active_connections.get(channel_id, {}).get(email_key, {}).values())

        for ws in sockets:
            try:
                await ws.close(code=code, reason=reason)
            except Exception:
                pass
            await self.disconnect(ws, channel_id, email_key)

    def get_online_users(self, channel_id: str):
        return list(self.online_users.get(channel_id, {}).values())

    def is_online(self, channel_id: str, email: str) -> bool:
        email_key = (email or "").strip().lower()
        return email_key in self.online_users.get(channel_id, {})

    async def touch(self, websocket: WebSocket):
        # Hook để sau này cập nhật Redis TTL/last_active nếu cần.
        return True


ws_manager = ChannelWebSocketManager()
