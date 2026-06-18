from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from contextlib import asynccontextmanager
from controllers import ai_controller, announce_controller, ban_controller, comment_controller, complaint_controller, incident_report_controller, message_controller, policy_controller, post_catalog_controller, post_controller, post_saved_controller, report_controller, search_controller, story_controller
from controllers import account_controller
from core.database import init_db 
from controllers import file_controller
from fastapi.middleware.cors import CORSMiddleware
# from controllers.websocket_controller import websocket_endpoint
from controllers.websocket_controller import router as websocket_router

from crawl.importdata.fit.fit_import_router import router as fit_crawl_router
from crawl.importdata.feet.feet_import_router import router as feet_crawl_router
from crawl.importdata.feee.feee_import_router import router as feee_crawl_router
from crawl.importdata.fme.fme_import_router import router as fme_crawl_router
from crawl.importdata.ffl.ffl_import_router import router as ffl_crawl_router
from crawl.importdata.fas.fas_import_router import router as fas_crawl_router
from crawl.importdata.fce.fce_import_router import router as fce_crawl_router
from crawl.importdata.fe.fe_import_router import router as fe_crawl_router
from crawl.importdata.fcft.fcft_import_router import router as fcft_crawl_router
from crawl.importdata.fgam.fgam_import_router import router as fgam_crawl_router
from crawl.importdata.fgtfd.fgtfd_import_router import router as fgtfd_crawl_router
from crawl.importdata.fpi.fpi_import_router import router as fpi_crawl_router
from crawl.importdata.fae.fae_import_router import router as fae_crawl_router
from crawl.importdata.ite.ite_import_router import router as ite_crawl_router

import asyncio  
from meeting.controllers import meeting_controller
from meeting.controllers import channel_controller
from meeting.websocket import meeting_websocket
from utils.permission_watcher import permission_watcher_loop 

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    perm_task = asyncio.create_task(permission_watcher_loop())     # <── thêm
    # yield
    try:
        yield
    finally:
        perm_task.cancel()                                         # <── thêm
        await perm_task

app = FastAPI(
    title="UTE Zone",
    description="Simple UTE Forum backend using FastAPI + MongoDB",
    version="1.0.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hoặc chỉ định ['http://localhost:5173']
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(post_controller.router, prefix="/post", tags=["post"])
app.include_router(policy_controller.router, prefix="/policy", tags=["policy"])
app.include_router(ban_controller.router, prefix="/ban", tags=["ban"])
app.include_router(report_controller.router, prefix="/report", tags=["report"])
app.include_router(complaint_controller.router, prefix="/complaint", tags=["complaint"])
app.include_router(account_controller.router, prefix="/account", tags=["account"])
app.include_router(search_controller.router, prefix="/search", tags=["search"])
app.include_router(file_controller.router, prefix="/file", tags=["file"])
app.include_router(comment_controller.router, prefix="/comment", tags=["comment"])
app.include_router(message_controller.router, prefix="/message", tags=["message"])
app.include_router(announce_controller.router, prefix="/announce", tags=["announce"])
app.include_router(story_controller.router, prefix="/story", tags=["story"])
app.include_router(ai_controller.router, prefix="/ai", tags=["ai"])

app.include_router(incident_report_controller.router, prefix="/incident_report", tags=["incident_report"])
# app.add_websocket_route("/ws", websocket_endpoint)
app.include_router(websocket_router)

app.include_router(post_saved_controller.router, prefix="/post_saved", tags=["post_saved"])
app.include_router(post_catalog_controller.router, prefix="/post_catalog", tags=["post_catalog"])

#crawl
app.include_router(fit_crawl_router, prefix="/fit_crawl", tags=["crawl"])
app.include_router(feet_crawl_router, prefix="/feet_crawl", tags=["crawl"])
app.include_router(feee_crawl_router, prefix="/feee_crawl", tags=["crawl"])
app.include_router(fme_crawl_router, prefix="/fme_crawl", tags=["crawl"])
app.include_router(ffl_crawl_router, prefix="/ffl_crawl", tags=["crawl"])
app.include_router(fas_crawl_router, prefix="/fas_crawl", tags=["crawl"])
app.include_router(fce_crawl_router, prefix="/fce_crawl", tags=["crawl"])
app.include_router(fe_crawl_router, prefix="/fe_crawl", tags=["crawl"])
app.include_router(fcft_crawl_router, prefix="/fcft_crawl", tags=["crawl"])
app.include_router(fgam_crawl_router, prefix="/fgam_crawl", tags=["crawl"])
app.include_router(fgtfd_crawl_router, prefix="/fgtfd_crawl", tags=["crawl"])
app.include_router(fpi_crawl_router, prefix="/fpi_crawl", tags=["crawl"])
app.include_router(fae_crawl_router, prefix="/fae_crawl", tags=["crawl"])
app.include_router(ite_crawl_router, prefix="/ite_crawl", tags=["crawl"])

#Meeting
app.include_router(meeting_controller.router)
app.include_router(meeting_websocket.router)

#Channel
app.include_router(channel_controller.router)
