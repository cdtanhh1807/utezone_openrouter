from datetime import datetime
from io import BytesIO
import os

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from fastapi.encoders import jsonable_encoder
from typing import Optional
from meeting.services.channel_service import channel_service
from meeting.models.channel_model import (
    AskAIConversationRequest, CreateAIConversationRequest, CreateChannelRequest, UpdateChannelRequest,
    CreateChatRoomRequest, UpdateChatRoomRequest,
    JoinChannelRequest, ApproveMemberRequest,
    SendMessageRequest,
    AskDocumentRequest
)
from utils.security import get_current_user
import httpx

from fastapi import BackgroundTasks
from meeting.services.moderation_service import moderate_text_message

from meeting.services.document_rag_service import document_rag_service
from meeting.models.channel_model import AskDocumentRequest

router = APIRouter(prefix="/channels", tags=["channels"])

#=================
from meeting.websocket.manager import ws_manager

async def get_user_profile_for_presence(email: str, token: str = "") -> dict:
    """Lấy tên/avatar để gửi presence cho frontend.

    Nếu API account_info lỗi thì fallback về username đang lưu trong channel member.
    """
    profile = {
        "email": email,
        "username": email.split('@')[0],
        "avatar": None,
    }

    if not token or not token.strip():
        return profile

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8000/account/account_info?email={email}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                data = response.json()
                profile["username"] = (
                    data.get("fullName")
                    or data.get("username")
                    or data.get("name")
                    or profile["username"]
                )
                profile["avatar"] = data.get("avatar")
    except Exception as e:
        print(f"Error fetching profile for presence: {e}")

    return profile

@router.websocket("/ws/{channel_id}")
async def channel_websocket(websocket: WebSocket, channel_id: str):
    token = websocket.query_params.get("token")

    if not token:
        print("[WS] No token")
        await websocket.close(code=1008)
        return

    try:
        print(f"[WS] New connection attempt, channel_id={channel_id}, token={token[:20]}...")
        current_user = await get_current_user(token)
        email = current_user["sub"]
        print(f"[WS] Authenticated user: {email}")
    except Exception as e:
        print(f"[WS] Auth error: {e}")
        await websocket.close(code=1008)
        return

    channel = await channel_service.get_channel(channel_id)
    if not channel:
        print(f"[WS] Channel {channel_id} not found")
        await websocket.close(code=1008, reason="Channel không tồn tại")
        return

    member = next(
        (m for m in channel.members if m.email == email and m.status == "approved"),
        None
    )

    if not member:
        print(f"[WS] User {email} not member of channel {channel_id}")
        await websocket.close(code=1008, reason="Bạn không phải thành viên")
        return

    profile = await get_user_profile_for_presence(email, token)
    user_data = {
        "email": email,
        "username": profile.get("username") or member.username or email.split('@')[0],
        "avatar": profile.get("avatar"),
        "role": member.role,
        "status": member.status,
    }

    await ws_manager.connect(websocket, channel_id, email, user_data)
    print(f"[WS] User {email} connected to channel {channel_id}")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except Exception:
                data = {}

            msg_type = data.get("type")

            if msg_type == "ping":
                await ws_manager.touch(websocket)
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Channel websocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket, channel_id, email)
        print(f"[WS] User {email} disconnected from channel {channel_id}")

@router.websocket("/ws-user")
async def user_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008)
        return

    try:
        current_user = await get_current_user(token)
        email = current_user["sub"].strip().lower()
    except Exception as e:
        print(f"[USER_WS] Auth error: {e}")
        await websocket.close(code=1008)
        return

    await ws_manager.connect_user(websocket, email)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except Exception:
                data = {}

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[USER_WS] error: {e}")
    finally:
        await ws_manager.disconnect_user(websocket)

#=================
def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return ""

def serialize_datetime_fields(data) -> dict:
    return jsonable_encoder(data)

async def get_fullname_from_api(email: str, token: str = "") -> str:
    if not token or not token.strip():
        return email.split('@')[0]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8000/account/account_info?email={email}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("fullName") or email.split('@')[0]
    except Exception as e:
        print(f"Error fetching fullName from API: {e}")
    return email.split('@')[0]


# ==================== CHANNEL CRUD ====================

@router.post("/create")
async def create_channel(
    req: CreateChannelRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]
    token = _extract_token(request)
    full_name = await get_fullname_from_api(email, token)
    try:
        channel = await channel_service.create_channel(
            owner_email=email, owner_name=full_name,
            name=req.name, description=req.description,
            require_approval=req.require_approval
        )
        return channel.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-channels")
async def get_my_channels(current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    channels = await channel_service.get_my_channels(email)
    return {"channels": channels}


@router.get("/{channel_id}")
async def get_channel(channel_id: str, current_user: dict = Depends(get_current_user)):
    channel = await channel_service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")
    email = current_user["sub"]
    is_member = any(m.email == email and m.status == "approved" for m in channel.members)
    is_owner = channel.owner_email == email
    result = channel.model_dump()
    result["is_member"] = is_member
    result["is_owner"] = is_owner
    if not is_member and not is_owner:
        result["members"] = [{"role": m.role, "status": m.status} for m in channel.members if m.status == "approved"]
        result["member_count"] = len([m for m in channel.members if m.status == "approved"])
    return result


@router.put("/{channel_id}")
async def update_channel(
    channel_id: str,
    req: UpdateChannelRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    try:
        channel = await channel_service.update_channel(
            channel_id=channel_id,
            owner_email=email,
            name=req.name,
            description=req.description,
            avatar=req.avatar,
            require_approval=req.require_approval
        )

        channel_dict = serialize_datetime_fields(channel.model_dump())

        message = {
            "type": "channel_updated",
            "channel_id": channel_id,
            "channel": channel_dict
        }

        member_emails = [
            m.email.strip().lower()
            for m in channel.members
            if m.status == "approved"
        ]

        # Gửi cho user đang đứng trong channel đó
        await ws_manager.broadcast(channel_id, message)

        # Gửi cho sidebar của tất cả member, dù đang ở channel khác
        await ws_manager.broadcast_to_accounts(member_emails, message)

        print("[CHANNEL_UPDATED] sent to accounts:", member_emails)

        return channel_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{channel_id}/invite-code")
async def get_invite_code(channel_id: str, current_user: dict = Depends(get_current_user)):
    channel = await channel_service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")
    email = current_user["sub"]
    if channel.owner_email != email:
        raise HTTPException(status_code=403, detail="Chỉ chủ channel mới có thể xem invite code")
    return {"invite_code": channel.invite_code, "invite_url": f"/channels/join?code={channel.invite_code}"}


# ==================== CHANNEL MEMBERSHIP ====================

@router.post("/join")
async def join_channel(
    req: JoinChannelRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()
    token = _extract_token(request)
    full_name = await get_fullname_from_api(email, token)

    result = await channel_service.join_channel(
        email=email,
        username=full_name,
        invite_code=req.invite_code,
        channel_id=None
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Không thể tham gia channel")
        )

    channel_id = result.get("channel_id")
    channel = await channel_service.get_channel(channel_id) if channel_id else None

    if channel:
        member_info = {
            "channel_id": channel.channel_id,
            "email": email,
            "username": full_name,
            "role": "member",
            "status": result.get("status", "approved"),
            "avatar": None,
            "is_online": False
        }

        if result.get("status") == "pending":
            await ws_manager.send_to_account(
                channel.owner_email,
                {
                    "type": "pending_member_request",
                    "channel_id": channel.channel_id,
                    "member": member_info
                }
            )

        elif result.get("status") == "approved":
            channel_dict = serialize_datetime_fields(channel.model_dump())

            await ws_manager.send_to_account(
                email,
                {
                    "type": "channel_joined",
                    "channel_id": channel.channel_id,
                    "channel": channel_dict
                }
            )

            approved_emails = [
                m.email.strip().lower()
                for m in channel.members
                if m.status == "approved"
            ]

            await ws_manager.broadcast_to_accounts(
                approved_emails,
                {
                    "type": "member_joined",
                    "channel_id": channel.channel_id,
                    "member": member_info
                }
            )

    return result


@router.post("/join/{channel_id}")
async def join_channel_by_id(
    channel_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()
    token = _extract_token(request)
    full_name = await get_fullname_from_api(email, token)

    result = await channel_service.join_channel(
        email=email,
        username=full_name,
        channel_id=channel_id
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Không thể tham gia channel")
        )

    channel = await channel_service.get_channel(channel_id)

    if channel:
        member_info = {
            "channel_id": channel.channel_id,
            "email": email,
            "username": full_name,
            "role": "member",
            "status": result.get("status", "approved"),
            "avatar": None,
            "is_online": False
        }

        if result.get("status") == "pending":
            await ws_manager.send_to_account(
                channel.owner_email,
                {
                    "type": "pending_member_request",
                    "channel_id": channel.channel_id,
                    "member": member_info
                }
            )

        elif result.get("status") == "approved":
            channel_dict = serialize_datetime_fields(channel.model_dump())

            await ws_manager.send_to_account(
                email,
                {
                    "type": "channel_joined",
                    "channel_id": channel.channel_id,
                    "channel": channel_dict
                }
            )

            approved_emails = [
                m.email.strip().lower()
                for m in channel.members
                if m.status == "approved"
            ]

            await ws_manager.broadcast_to_accounts(
                approved_emails,
                {
                    "type": "member_joined",
                    "channel_id": channel.channel_id,
                    "member": member_info
                }
            )

    return result


@router.post("/{channel_id}/leave")
async def leave_channel(
    channel_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    result = await channel_service.leave_channel(email, channel_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    message = {
        "type": "member_left",
        "channel_id": channel_id,
        "member_email": email
    }

    # Báo cho các user đang mở channel đó cập nhật danh sách thành viên.
    await ws_manager.broadcast(channel_id, message)

    # Báo cho chính user rời channel nếu họ còn mở global socket.
    await ws_manager.send_to_account(email, {
        "type": "you_left_channel",
        "channel_id": channel_id
    })

    # Nếu user còn channel socket trong channel này thì đóng luôn.
    await ws_manager.force_disconnect_user(
        channel_id,
        email,
        code=4002,
        reason="Bạn đã rời khỏi kênh này"
    )

    print("[LEAVE_CHANNEL] user left:", email, "from channel:", channel_id)

    return result

@router.get("/{channel_id}/members")
async def get_channel_members(channel_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    channel = await channel_service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")
    is_member = any(m.email == email and m.status == "approved" for m in channel.members)
    is_owner = channel.owner_email == email
    if not is_member and not is_owner:
        raise HTTPException(status_code=403, detail="Bạn không phải thành viên")
    
    members = []
    for m in channel.members:
        # Gọi API account_info để lấy avatar
        avatar_url = None
        try:
            async with httpx.AsyncClient() as client:
                token = _extract_token(request)
                resp = await client.get(
                    f"http://localhost:8000/account/account_info?email={m.email}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    avatar_url = data.get("avatar")
        except Exception as e:
            print(f"Error fetching avatar for {m.email}: {e}")
        
        members.append({
            "email": m.email,
            "username": m.username or m.email.split('@')[0],
            "role": m.role,
            "status": m.status,
            "is_online": False,  # sẽ được gán sau
            "avatar": avatar_url
        })
    return {"members": members}


@router.get("/{channel_id}/pending-members")
async def get_pending_members(channel_id: str, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    pending = await channel_service.get_pending_members(channel_id, email)
    return {"pending_members": pending}

@router.post("/{channel_id}/approve")
async def approve_member(
    channel_id: str,
    req: ApproveMemberRequest,
    current_user: dict = Depends(get_current_user)
):
    owner_email = current_user["sub"].strip().lower()
    target_email = req.email.strip().lower()

    result = await channel_service.approve_member(
        channel_id,
        owner_email,
        req.email,
        req.approve
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    channel = await channel_service.get_channel(channel_id)

    if not channel:
        return result

    if req.approve:
        member_info = None

        for m in channel.members:
            if m.email.strip().lower() == target_email and m.status == "approved":
                member_info = {
                    "channel_id": channel_id,
                    "email": m.email,
                    "username": m.username,
                    "role": m.role,
                    "status": m.status,
                    "avatar": None,
                    "is_online": ws_manager.is_online(channel_id, m.email)
                }
                break

        channel_dict = serialize_datetime_fields(channel.model_dump())

        if member_info:
            await ws_manager.broadcast(channel_id, {
                "type": "member_approved",
                "channel_id": channel_id,
                "member": member_info
            })

            await ws_manager.send_to_account(target_email, {
                "type": "join_request_approved",
                "channel_id": channel_id,
                "channel": channel_dict,
                "member": member_info
            })

            await ws_manager.send_to_account(owner_email, {
                "type": "pending_member_resolved",
                "channel_id": channel_id,
                "member_email": target_email,
                "approved": True
            })

            print("[APPROVE_MEMBER] approved sent to:", target_email)

    else:
        await ws_manager.send_to_account(target_email, {
            "type": "join_request_rejected",
            "channel_id": channel_id
        })

        await ws_manager.send_to_account(owner_email, {
            "type": "pending_member_resolved",
            "channel_id": channel_id,
            "member_email": target_email,
            "approved": False
        })

        print("[APPROVE_MEMBER] rejected sent to:", target_email)

    return result


@router.post("/{channel_id}/kick/{member_email}")
async def kick_member(
    channel_id: str,
    member_email: str,
    current_user: dict = Depends(get_current_user)
):
    owner_email = current_user["sub"].strip().lower()
    target_email = member_email.strip().lower()

    result = await channel_service.kick_member(
        channel_id,
        owner_email,
        member_email
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    message = {
        "type": "member_kicked",
        "channel_id": channel_id,
        "member_email": target_email,
        "kicked_by": owner_email
    }

    # Cho user đang ở trong channel đó biết realtime.
    await ws_manager.broadcast(channel_id, message)

    # Cho user bị kick biết realtime dù đang ở channel khác.
    await ws_manager.send_to_account(target_email, {
        "type": "you_were_kicked",
        "channel_id": channel_id,
        "member_email": target_email,
        "kicked_by": owner_email
    })

    # Nếu user bị kick đang mở đúng channel đó thì đóng channel socket.
    await ws_manager.force_disconnect_user(
        channel_id,
        target_email,
        code=4001,
        reason="Bạn đã bị kick khỏi kênh này"
    )

    print("[KICK_MEMBER] kicked user:", target_email, "from channel:", channel_id)

    return result


# ==================== CHAT ROOM CRUD ====================
@router.post("/{channel_id}/chatrooms")
async def create_chat_room(
    channel_id: str,
    req: CreateChatRoomRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]

    try:
        chatroom = await channel_service.create_chat_room(
            channel_id=channel_id,
            owner_email=email,
            name=req.name,
            description=req.description,
            room_type=req.room_type
        )

        chatroom_dict = chatroom.model_dump()

        if isinstance(chatroom_dict.get("created_at"), datetime):
            chatroom_dict["created_at"] = chatroom_dict["created_at"].isoformat()

        if isinstance(chatroom_dict.get("updated_at"), datetime):
            chatroom_dict["updated_at"] = chatroom_dict["updated_at"].isoformat()

        await ws_manager.broadcast(channel_id, {
            "type": "chatroom_created",
            "channel_id": channel_id,
            "chatroom": chatroom_dict
        })

        return chatroom_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{channel_id}/chatrooms")
async def get_channel_chat_rooms(channel_id: str, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    channel = await channel_service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")
    is_member = any(m.email == email and m.status == "approved" for m in channel.members)
    if not is_member:
        raise HTTPException(status_code=403, detail="Bạn không phải thành viên của channel này")
    chatrooms = await channel_service.get_channel_chat_rooms(channel_id)
    return {"chatrooms": chatrooms}


@router.put("/chatrooms/{room_id}")
async def update_chat_room(
    room_id: str,
    req: UpdateChatRoomRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]

    try:
        chatroom = await channel_service.update_chat_room(
            room_id=room_id,
            owner_email=email,
            name=req.name,
            description=req.description
        )

        chatroom_dict = chatroom.model_dump()

        if isinstance(chatroom_dict.get("created_at"), datetime):
            chatroom_dict["created_at"] = chatroom_dict["created_at"].isoformat()

        if isinstance(chatroom_dict.get("updated_at"), datetime):
            chatroom_dict["updated_at"] = chatroom_dict["updated_at"].isoformat()

        await ws_manager.broadcast(chatroom.channel_id, {
            "type": "chatroom_updated",
            "channel_id": chatroom.channel_id,
            "chatroom": chatroom_dict
        })

        return chatroom_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/chatrooms/{room_id}")
async def delete_chat_room(room_id: str, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    # Lấy channel_id trước khi xóa
    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")
    channel_id = chatroom.channel_id
    success = await channel_service.delete_chat_room(room_id, email)
    if not success:
        raise HTTPException(status_code=403, detail="Không có quyền hoặc chat room không tồn tại")
    await ws_manager.broadcast(channel_id, {"type": "chatroom_deleted", "room_id": room_id})
    return {"status": "deleted"}


@router.post("/chatrooms/{room_id}/start-meeting")
async def start_meeting_in_chatroom(room_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    token = _extract_token(request)
    full_name = await get_fullname_from_api(email, token)
    try:
        result = await channel_service.start_meeting_in_chatroom(room_id=room_id, owner_email=email, host_name=full_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== MESSAGES ====================
@router.get("/{channel_id}/mute-status")
async def get_my_mute_status(
    channel_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    channel = await channel_service.get_channel(channel_id)

    if not channel:
        raise HTTPException(
            status_code=404,
            detail="Channel không tồn tại"
        )

    is_member = any(
        (m.email or "").strip().lower() == email
        and m.status == "approved"
        for m in channel.members
    )

    if not is_member:
        raise HTTPException(
            status_code=403,
            detail="Bạn không phải thành viên của channel này"
        )

    mute_status = await channel_service.get_member_mute_status(
        channel_id=channel_id,
        member_email=email
    )

    if not mute_status:
        return {
            "muted": False
        }

    muted_until = mute_status.get("muted_until")

    return {
        "muted": True,
        "reason": mute_status.get("reason"),
        "muted_until": muted_until.isoformat() if muted_until else None
    }

@router.post("/chatrooms/{room_id}/messages")
async def send_message(
    room_id: str,
    req: SendMessageRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()
    token = _extract_token(request)
    full_name = await get_fullname_from_api(email, token)

    chatroom = await channel_service.get_chat_room(room_id)

    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")

    mute_status = await channel_service.get_member_mute_status(
        channel_id=chatroom.channel_id,
        member_email=email
    )

    if mute_status:
        muted_until = mute_status.get("muted_until")
        reason = mute_status.get("reason") or "Bạn đang bị cấm gửi tin nhắn trong kênh này"

        raise HTTPException(
            status_code=403,
            detail={
                "error": "muted",
                "message": "Bạn đang bị cấm gửi tin nhắn trong kênh này",
                "reason": reason,
                "muted_until": muted_until.isoformat() if muted_until else None
            }
        )

    try:
        message = await channel_service.send_message(
            room_id=room_id,
            channel_id=chatroom.channel_id,
            sender_email=email,
            sender_name=full_name,
            content=req.content,
            msg_type=req.msg_type,
            file_name=req.file_name
        )

        message_dict = message.model_dump()

        print(
            f"[BROADCAST] Sending to channel {chatroom.channel_id}, "
            f"message_id={message.message_id}"
        )

        if isinstance(message_dict.get("created_at"), datetime):
            message_dict["created_at"] = message_dict["created_at"].isoformat()

        await ws_manager.broadcast(chatroom.channel_id, {
            "type": "new_message",
            "message": message_dict
        })

        if req.msg_type == "text":
            rules = await channel_service.get_channel_rules(chatroom.channel_id)

            if rules and rules.enabled and "text" in rules.enabled_types:
                background_tasks.add_task(
                    moderate_text_message,
                    channel_id=chatroom.channel_id,
                    message_id=message.message_id,
                    content=req.content,
                    sender_email=email,
                    room_id=room_id
                )

        return message_dict

    except PermissionError as e:
        detail = e.args[0] if e.args else {
            "error": "muted",
            "message": "Bạn đang bị cấm gửi tin nhắn trong kênh này"
        }

        raise HTTPException(
            status_code=403,
            detail=detail
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/chatrooms/{room_id}/messages")
async def get_messages(room_id: str, limit: int = 50, before: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room khong ton tai")
    messages = await channel_service.get_messages(room_id, limit, before)
    return {"messages": messages}


@router.delete("/messages/{message_id}")
async def delete_message_by_owner(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]

    result = await channel_service.delete_message_by_owner(
        message_id=message_id,
        owner_email=email
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    await ws_manager.broadcast(result["channel_id"], {
        "type": "message_removed",
        "message_id": result["message_id"],
        "room_id": result["room_id"],
        "user_email": email,
        "reason": "Tin nhắn đã bị chủ channel xóa"
    })

    return {
        "success": True,
        "message": "Đã xóa tin nhắn",
        "message_id": result["message_id"]
    }

# ==================== USER SESSION ====================

@router.post("/session/set")
async def set_user_session(channel_id: Optional[str] = None, chat_room_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    try:
        result = await channel_service.set_user_session(email, channel_id, chat_room_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/my")
async def get_my_session(current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    session = await channel_service.get_user_session(email)
    return session or {"email": email, "current_channel_id": None, "current_chat_room_id": None}


@router.post("/session/clear")
async def clear_my_session(current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    await channel_service.clear_user_session(email)
    return {"status": "cleared"}


@router.get("/{channel_id}/online-users")
async def get_online_users_in_channel(channel_id: str, current_user: dict = Depends(get_current_user)):
    # Endpoint giữ lại để tương thích, nhưng nguồn online chính là WebSocket manager.
    return {"online_users": ws_manager.get_online_users(channel_id)}


@router.get("/chatrooms/{room_id}/online-users")
async def get_online_users_in_chatroom(room_id: str, current_user: dict = Depends(get_current_user)):
    sessions = await channel_service.get_online_users_in_chatroom(room_id)
    return {"online_users": sessions}

@router.get("/files/{file_id}")
async def get_file(file_id: str, current_user: dict = Depends(get_current_user)):
    """Lấy URL tạm thời của file (yêu cầu đăng nhập)"""
    try:
        from services.other.file_service import FileService
        url = FileService.get_file_url(file_id)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")

# ==================== FILE UPLOAD ====================

@router.post("/chatrooms/{room_id}/upload")
async def upload_chat_file(
    room_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload file cho chat trong channel room.

    Nếu channel bật kiểm duyệt cho loại file tương ứng thì kiểm duyệt trước khi upload.
    Quan trọng: moderation fail/429/parse lỗi sẽ bị chặn, không cho upload lọt qua.
    """
    email = current_user["sub"]

    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")

    channel = await channel_service.get_channel(chatroom.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")

    is_member = any(m.email == email and m.status == "approved" for m in channel.members)
    if not is_member:
        raise HTTPException(status_code=403, detail="Bạn không phải thành viên của channel này")

    try:
        from services.other.file_service import FileService
        from meeting.services.moderation_service import moderate_file
        import tempfile

        content_type = file.content_type or ""
        filename = file.filename or "uploaded_file"

        if content_type.startswith("image/"):
            media_type = "image"
        elif content_type.startswith("video/"):
            media_type = "video"
        else:
            media_type = "document"

        rules = await channel_service.get_channel_rules(chatroom.channel_id)
        should_moderate = False

        if rules and rules.enabled:
            if media_type == "image" and "image" in rules.enabled_types:
                should_moderate = True
            elif media_type == "video" and "video" in rules.enabled_types:
                should_moderate = True
            elif media_type == "document" and "file" in rules.enabled_types:
                should_moderate = True

        if should_moderate:
            content = await file.read()
            suffix = os.path.splitext(filename)[1] or ""
            tmp_path = None

            try:
                fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                with os.fdopen(fd, "wb") as tmp:
                    tmp.write(content)

                moderation = await moderate_file(
                    channel_id=chatroom.channel_id,
                    file_path=tmp_path,
                    filename=filename,
                    media_type=media_type,
                    sender_email=email,
                    room_id=room_id
                )

                print(f"[FILE_MODERATION] {filename}: {moderation}")

                if not moderation.get("approved", False):
                    reason = moderation.get(
                        "reason",
                        "Nội dung vi phạm hoặc hệ thống kiểm duyệt đang quá tải"
                    )
                    reason_lower = str(reason).lower()

                    service_error_keywords = [
                        "rate limited",
                        "unavailable",
                        "empty response",
                        "invalid response",
                        "unexpected response",
                        "missing approved",
                        "not boolean",
                        "cannot extract",
                        "file moderation error",
                        "service unavailable",
                        "không thể đọc kết quả",
                        "không khả dụng",
                        "quá tải",
                    ]

                    if any(keyword in reason_lower for keyword in service_error_keywords):
                        raise HTTPException(status_code=503, detail={
                            "error": "AI kiểm duyệt không khả dụng",
                            "reason": "Không thể kiểm duyệt file lúc này, vui lòng thử lại sau"
                        })

                    raise HTTPException(status_code=400, detail={
                        "error": "File không được phép upload",
                        "reason": reason
                    })

            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception as cleanup_err:
                        print(f"[UPLOAD_CLEANUP] Không thể xóa file tạm {tmp_path}: {cleanup_err}")

            # Reset stream để FileService có thể đọc lại file sau khi moderation đã đọc hết.
            file.file = BytesIO(content)
            file.size = len(content)

        file_id = await FileService.upload_file(file)
        url = FileService.get_file_url(file_id)

        return {
            "file_id": file_id,
            "url": url,
            "filename": filename,
            "content_type": content_type
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[UPLOAD_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    channel = await channel_service.get_channel(channel_id)

    if not channel:
        raise HTTPException(
            status_code=404,
            detail="Channel không tồn tại"
        )

    member_emails = [
        m.email.strip().lower()
        for m in channel.members
        if m.status == "approved"
    ]

    success = await channel_service.delete_channel(channel_id, email)

    if not success:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền hoặc channel không tồn tại"
        )

    message = {
        "type": "channel_deleted",
        "channel_id": channel_id,
        "deleted_by": email
    }

    await ws_manager.broadcast(channel_id, message)
    await ws_manager.broadcast_to_accounts(member_emails, message)

    print("[CHANNEL_DELETED] sent to accounts:", member_emails)

    return {
        "status": "deleted",
        "channel_id": channel_id
    }

@router.post("/chatrooms/{room_id}/mark-read")
async def mark_room_read(room_id: str, current_user: dict = Depends(get_current_user)):
    """Đánh dấu user đã đọc tin nhắn trong room"""
    email = current_user["sub"]
    # Lấy tin nhắn mới nhất để lưu last_read_message_id (tuỳ chọn)
    last_msg = await channel_service.get_last_message(room_id)  # cần implement
    msg_id = last_msg.message_id if last_msg else None
    await channel_service.update_read_status(email, room_id, msg_id)
    return {"status": "ok"}

@router.get("/{channel_id}/unread-counts")
async def get_unread_counts(channel_id: str, current_user: dict = Depends(get_current_user)):
    """Lấy số tin nhắn chưa đọc cho từng room trong channel"""
    email = current_user["sub"]
    counts = await channel_service.get_unread_counts_for_channel(email, channel_id)
    return {"unread_counts": counts}

# @router.post("/{channel_id}/avatar")
# async def upload_channel_avatar(
#     channel_id: str,
#     request: Request,
#     file: UploadFile = File(...),
#     current_user: dict = Depends(get_current_user)
# ):
#     email = current_user["sub"]
#     channel = await channel_service.get_channel(channel_id)
#     if not channel:
#         raise HTTPException(status_code=404, detail="Channel không tồn tại")
#     if channel.owner_email != email:
#         raise HTTPException(status_code=403, detail="Chỉ chủ channel mới có thể thay đổi avatar")
    
#     try:
#         from services.other.file_service import FileService
#         file_id = await FileService.upload_file(file)
#         avatar_url = FileService.get_file_url(file_id)
#         # Cập nhật avatar trong database
#         await channel_service.update_channel(channel_id, email, avatar=avatar_url)
#         # Broadcast cập nhật avatar đến tất cả member
#         await ws_manager.broadcast(channel_id, {
#             "type": "channel_avatar_updated",
#             "avatar_url": avatar_url
#         })
#         return {"avatar_url": avatar_url}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
@router.post("/{channel_id}/avatar")
async def upload_channel_avatar(
    channel_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]
    channel = await channel_service.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel không tồn tại")
    if channel.owner_email != email:
        raise HTTPException(status_code=403, detail="Chỉ chủ channel mới có thể thay đổi avatar")
    
    try:
        from services.other.file_service import FileService
        file_id = await FileService.upload_file(file)
        # Lưu file_id thay vì URL
        await channel_service.update_channel(channel_id, email, avatar=file_id)
        # Broadcast file_id (không phải URL)
        await ws_manager.broadcast(channel_id, {
            "type": "channel_avatar_updated",
            "file_id": file_id
        })
        return {"file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @router.delete("/{channel_id}/avatar")
# async def delete_channel_avatar(
#     channel_id: str,
#     current_user: dict = Depends(get_current_user)
# ):
#     email = current_user["sub"]
#     channel = await channel_service.get_channel(channel_id)
#     if not channel or channel.owner_email != email:
#         raise HTTPException(status_code=403, detail="Không có quyền")
#     await channel_service.update_channel(channel_id, email, avatar=None)
#     await ws_manager.broadcast(channel_id, {
#         "type": "channel_avatar_updated",
#         "avatar_url": None
#     })
#     return {"status": "deleted"}
@router.delete("/{channel_id}/avatar")
async def delete_channel_avatar(
    channel_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"]
    channel = await channel_service.get_channel(channel_id)
    if not channel or channel.owner_email != email:
        raise HTTPException(status_code=403, detail="Không có quyền")
    await channel_service.update_channel(channel_id, email, avatar=None)
    await ws_manager.broadcast(channel_id, {
        "type": "channel_avatar_updated",
        "file_id": None
    })
    return {"status": "deleted"}

@router.get("/chatrooms/{room_id}/media")
async def get_room_media(room_id: str, current_user: dict = Depends(get_current_user)):
    """Lấy danh sách ảnh và video trong room"""
    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")
    messages = await channel_service.get_messages(room_id, limit=1000)
    media = []
    for msg in messages:
        if msg.get("msg_type") in ["image", "video"] and msg.get("content"):
            media.append({
                "message_id": msg["message_id"],
                "type": msg["msg_type"],
                "file_id": msg["content"],
                "file_name": msg.get("file_name", ""),
                "sender_name": msg.get("sender_name", ""),
                "created_at": msg["created_at"].isoformat() if msg.get("created_at") else None
            })
    return {"media": media}

@router.get("/chatrooms/{room_id}/files")
async def get_room_files(room_id: str, current_user: dict = Depends(get_current_user)):
    """Lấy danh sách file tài liệu trong room (không bao gồm ảnh/video)"""
    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")
    messages = await channel_service.get_messages(room_id, limit=1000)
    files = []
    for msg in messages:
        if msg.get("msg_type") == "file" and msg.get("content"):
            files.append({
                "message_id": msg["message_id"],
                "file_id": msg["content"],
                "file_name": msg.get("file_name", "Tải file"),
                "sender_name": msg.get("sender_name", ""),
                "created_at": msg["created_at"].isoformat() if msg.get("created_at") else None
            })
    return {"files": files}

@router.get("/chatrooms/{room_id}/search")
async def search_messages(room_id: str, q: str, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Tìm kiếm tin nhắn theo từ khóa"""
    chatroom = await channel_service.get_chat_room(room_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chat room không tồn tại")
    messages = await channel_service.search_messages(room_id, q, limit)
    return {"results": messages}

@router.get("/{channel_id}/rules")
async def get_channel_rules(channel_id: str, current_user: dict = Depends(get_current_user)):
    rules = await channel_service.get_channel_rules(channel_id)
    if not rules:
        return {"channel_id": channel_id, "enabled": False, "rules": []}
    return rules.model_dump()

@router.put("/{channel_id}/rules")
async def update_channel_rules(channel_id: str, req: dict, current_user: dict = Depends(get_current_user)):
    email = current_user["sub"]
    channel = await channel_service.get_channel(channel_id)
    if not channel or channel.owner_email != email:
        raise HTTPException(403, "Chỉ chủ kênh mới có quyền")
    from meeting.models.channel_model import ChannelRules
    rules = ChannelRules(
        channel_id=channel_id,
        enabled=req.get("enabled", False),
        rules_text=req.get("rules_text", ""),
        enabled_types=req.get("enabled_types", []),
        action=req.get("action", "warn"),
        max_violations=req.get("max_violations", 3),
        penalty_time=req.get("penalty_time"),
        updated_by=email
    )
    await channel_service.save_channel_rules(rules)
    return rules.model_dump()

#RAG
@router.post("/documents/{file_id}/prepare")
async def prepare_document_for_ai(
    file_id: str,
    message_id: Optional[str] = None,
    room_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    if not room_id:
        raise HTTPException(status_code=400, detail="Thiếu room_id")

    try:
        result = await document_rag_service.prepare_document(
            file_id=file_id,
            message_id=message_id or "",
            room_id=room_id,
            user_email=email
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"[DOCUMENT_PREPARE_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{file_id}/ai-history")
async def get_document_ai_history(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    history = await document_rag_service.get_history(
        file_id=file_id,
        user_email=email
    )

    return {"messages": history}


@router.post("/documents/{file_id}/ask")
async def ask_document_ai(
    file_id: str,
    req: AskDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

    try:
        result = await document_rag_service.ask_document(
            file_id=file_id,
            user_email=email,
            question=req.question.strip()
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"[DOCUMENT_ASK_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
#Nâng cấp lên thành đoạn hội thoại với UTEZoneAI
@router.get("/chatrooms/{room_id}/ai-conversations")
async def list_room_ai_conversations(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    return {
        "conversations": await document_rag_service.list_ai_conversations(
            room_id=room_id,
            user_email=email
        )
    }

@router.post("/chatrooms/{room_id}/ai-conversations")
async def create_room_ai_conversation(
    room_id: str,
    req: CreateAIConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    room = await channel_service.get_chat_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng chat")

    try:
        conversation = await document_rag_service.create_ai_conversation(
            room_id=room_id,
            channel_id=room.channel_id,
            user_email=email,
            title=req.title,
            documents=req.documents
        )

        return conversation

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"[AI_CONVERSATION_CREATE_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/ai-conversations/{conversation_id}")
async def get_ai_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    try:
        return await document_rag_service.get_conversation_history(
            conversation_id=conversation_id,
            user_email=email
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.post("/ai-conversations/{conversation_id}/ask")
async def ask_ai_conversation(
    conversation_id: str,
    req: AskAIConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

    try:
        return await document_rag_service.ask_ai_conversation(
            conversation_id=conversation_id,
            user_email=email,
            question=req.question.strip()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"[AI_CONVERSATION_ASK_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/chatrooms/{room_id}/ai-conversations/from-file")
async def create_ai_conversation_from_file(
    room_id: str,
    req: dict,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    room = await channel_service.get_chat_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng chat")

    conversation = await document_rag_service.get_or_create_single_file_conversation(
        room_id=room_id,
        channel_id=room.channel_id,
        user_email=email,
        file_id=req.get("file_id"),
        file_name=req.get("file_name") or "Tài liệu",
        message_id=req.get("message_id") or ""
    )

    return conversation

@router.delete("/ai-conversations/{conversation_id}")
async def delete_ai_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    try:
        return await document_rag_service.delete_ai_conversation(
            conversation_id=conversation_id,
            user_email=email
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        print(f"[AI_CONVERSATION_DELETE_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch("/ai-conversations/{conversation_id}/rename")
async def rename_ai_conversation(
    conversation_id: str,
    req: dict,
    current_user: dict = Depends(get_current_user)
):
    email = current_user["sub"].strip().lower()

    title = (req.get("title") or "").strip()

    try:
        return await document_rag_service.rename_ai_conversation(
            conversation_id=conversation_id,
            user_email=email,
            title=title
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"[AI_CONVERSATION_RENAME_ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))