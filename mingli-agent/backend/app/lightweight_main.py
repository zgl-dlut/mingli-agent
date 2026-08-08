"""
轻量级独立服务，提供命理分析 API + AI 报告生成（不需要数据库）
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bazi import router as bazi_router
from app.api.chat_lite import router as chat_lite_router
from app.api.payment import router as payment_router
from app.api.auth_lite import router as auth_lite_router
from app.api.feedback import router as feedback_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="命理分析 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bazi_router)
app.include_router(chat_lite_router)
app.include_router(payment_router)
app.include_router(auth_lite_router)
app.include_router(feedback_router)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "qwen-3.6-flash"}
