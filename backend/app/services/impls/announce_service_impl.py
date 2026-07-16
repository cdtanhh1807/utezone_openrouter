from datetime import datetime
from typing import List, Optional
from dto.announce.request.get_all_announce_request import GetAllAnnounceRequest
from dto.announce.request.send_announce_request import SendAnnounceRequest
from dto.announce.response.get_all_announce_response import GetAllAnnounceResponse
from dto.announce.response.send_announce_response import SendAnnounceResponse
from dto.ban.request.get_all_ban_request import GetAllBanRequest
from dto.ban.response.get_all_ban_response import GetAllBanResponse, BanDetail
from models.announce_model import Announce
from models.ban_model import Ban
from models.policy_model import Policy
from models.violation_model import Violation
from repositories.announce_repository import AnnounceRepository
from repositories.ban_repository import BanRepository 
from repositories.policy_repository import PolicyRepository
from repositories.violation_repository import ViolationRepository
from services.interfaces.announce_service_interface import IAnnounceService
from services.impls.account_service_impl import AccountServiceImpl
from models.base_model import bson_to_dict



class AnnounceServiceImpl(IAnnounceService):
    
    async def get_all_by_receiver_email(self, req: GetAllAnnounceRequest) -> Optional[GetAllAnnounceResponse]:
        dic_ls = await AnnounceRepository.get_all_by_receiver_email(req.email)
        list_rs: List[Announce] = []
        if len(dic_ls) > 0:
            for dic_ann in dic_ls:
                cleaned_dic = bson_to_dict(dic_ann)
                if cleaned_dic and "id" in cleaned_dic:
                    del cleaned_dic["id"]
                ann: Announce = Announce(**cleaned_dic)
                list_rs.append(ann)
        return GetAllAnnounceResponse(announce_list=list_rs)
    
    async def add(self, req: SendAnnounceRequest) -> Optional[SendAnnounceResponse]:
        announceContent = "Gần đây hệ thống nghi ngờ bạn có những hành vi vi phạm các chính sách của Diễn đàn. Nếu còn tiếp diễn bạn sẽ bị hạn chế quyền hoạt động trên Diễn đàn!"
        announce = Announce(senderEmail="Hệ thống", receiverEmail=req.receiverEmail, type="warning", contentAnnounce=announceContent,
                                            isRead=False, createdAt=datetime.now())
        dic_announce_insert = await AnnounceRepository.insert(announce.model_dump())
        if dic_announce_insert:
            cleaned_dic = bson_to_dict(dic_announce_insert)
            if cleaned_dic and "id" in cleaned_dic:
                del cleaned_dic["id"]
            return SendAnnounceResponse(announce=Announce(**cleaned_dic))
        else: None

    async def mark_as_read(self, announce_id: str) -> Optional[dict]:
        res = await AnnounceRepository.mark_as_read(announce_id)
        if res:
            cleaned_dic = bson_to_dict(res)
            if cleaned_dic and "id" in cleaned_dic:
                del cleaned_dic["id"]
            return cleaned_dic
        return None