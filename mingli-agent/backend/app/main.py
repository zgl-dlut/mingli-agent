from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.skills import registry
from app.skills.divination import BaziSkill, AstrologySkill
from app.skills.auth import SmsAuthSkill
from app.skills.payment import PaymentSkill
from app.skills.content import AiContentSkill, FormatSkill
from app.skills.security import SecuritySkill

from app.api.auth import router as auth_router
from app.api.bazi import router as bazi_router
from app.api.astrology import router as astrology_router
from app.api.person import router as person_router
from app.api.chat import router as chat_router
from app.api.chat_lite import router as chat_lite_router
from app.api.payment import router as payment_router
from app.api.user import router as user_router
from app.api.monitor import router as monitor_router
from app.api.legal import router as legal_router
from app.api.admin import router as admin_router
from app.api.eval import router as eval_router
from app.api.wx_jssdk import router as wx_jssdk_router
from app.api.daily import router as daily_router
from app.api.chart import router as chart_router
from app.api.deep_reading import router as deep_reading_router
from app.api.subscription import router as subscription_router
from app.api.report import router as report_router
from app.api.persona import router as persona_router
from app.core.exceptions import V3APIError
from app.services.feature_flag_service import feature_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：注册并初始化所有 Skill"""
    # 注册 Skill
    registry.register(BaziSkill())
    registry.register(AstrologySkill())
    registry.register(SmsAuthSkill())
    registry.register(PaymentSkill())
    registry.register(AiContentSkill())
    registry.register(FormatSkill())
    registry.register(SecuritySkill())
    
    # 初始化所有 Skill
    await registry.initialize_all()
    
    print(f"已注册 {len(registry.list_skills())} 个 Skill:")
    for meta in registry.list_skills():
        print(f"  [{meta.category}] {meta.display_name} (v{meta.version})")
    
    yield
    
    # 关闭所有 Skill
    await registry.shutdown_all()


app = FastAPI(title="命理Agent API", version="2.0.0", lifespan=lifespan)


@app.exception_handler(V3APIError)
async def handle_v3_api_error(_, exc: V3APIError):
    return JSONResponse(status_code=exc.status_code, content=exc.payload)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(bazi_router)
app.include_router(astrology_router)
app.include_router(person_router)
app.include_router(chat_router)
app.include_router(chat_lite_router)
app.include_router(payment_router)
app.include_router(user_router)
app.include_router(monitor_router)
app.include_router(legal_router)
app.include_router(admin_router)
app.include_router(eval_router)
app.include_router(wx_jssdk_router)
app.include_router(daily_router)
app.include_router(chart_router)
app.include_router(deep_reading_router)
app.include_router(subscription_router)
app.include_router(report_router)
app.include_router(persona_router)


@app.get("/api/skills")
async def list_skills():
    """列出所有已注册的 Skill"""
    return [meta.model_dump() for meta in registry.list_skills()]


@app.get("/api/features")
async def get_features():
    return feature_snapshot()


@app.get("/")
async def root():
    return {"message": "命理Agent API v2.0 (Skill Architecture)"}
