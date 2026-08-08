from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
import os
import psutil
from app.db.session import async_session
from app.models.person import Person
from app.models.message import ChatMessage

router = APIRouter(prefix="/monitor", tags=["监控"])


@router.get("/health")
async def health_check():
    """完整健康检查，包含数据库、AI模型、各模块状态"""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "ok",
        "version": "2.0.0",
        "components": {}
    }

    try:
        async with async_session() as session:
            person_count = await session.scalar(Person.__table__.count())
            message_count = await session.scalar(ChatMessage.__table__.count())
        results["components"]["database"] = {
            "status": "ok",
            "person_count": person_count,
            "message_count": message_count
        }
    except Exception as e:
        results["components"]["database"] = {"status": "error", "error": str(e)}
        results["status"] = "degraded"

    ai_api_key = os.getenv("DASHSCOPE_API_KEY", "")
    ai_models = os.getenv("AI_MODELS", "")
    from app.services.ai_service import get_model_status
    model_status = get_model_status()
    
    results["components"]["ai_model"] = {
        "status": "ok" if ai_api_key else "warning",
        "current_model": model_status["current_model"],
        "model_count": model_status["count"],
        "models": model_status["models"],
        "has_api_key": bool(ai_api_key),
        "model_list": ai_models.split(",") if ai_models else []
    }

    results["components"]["payment"] = {
        "wechat_configured": bool(os.getenv("WECHAT_APP_ID")),
        "alipay_configured": bool(os.getenv("ALIPAY_APP_ID"))
    }

    process = psutil.Process()
    memory_info = process.memory_info()
    results["components"]["system"] = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 2),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage_percent": psutil.disk_usage("/").percent
    }

    return results


@router.get("/stats")
async def get_stats():
    """获取应用统计数据"""
    async with async_session() as session:
        person_count = await session.scalar(Person.__table__.count())
        message_count = await session.scalar(ChatMessage.__table__.count())

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {
            "total_users": person_count,
            "total_messages": message_count,
            "api_calls": 0,
            "ai_requests": 0
        }
    }


@router.get("/ping")
async def ping():
    """简单心跳检查"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/dashboard", response_class=HTMLResponse)
async def monitor_dashboard(request: Request):
    """监控仪表盘页面"""
    with open("app/templates/monitor.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)