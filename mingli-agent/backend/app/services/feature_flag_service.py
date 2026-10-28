from app.config import settings
from app.core.exceptions import V3APIError


async def require_v3_enabled() -> None:
    if not settings.V3_ENABLED:
        raise V3APIError(403, "feature_disabled", "V3 功能尚未对当前环境开放")


def feature_snapshot() -> dict:
    return {
        "v3_enabled": settings.V3_ENABLED,
        "persona_enabled": settings.V3_ENABLED and settings.PERSONA_ENABLED,
        "other_persona_enabled": (
            settings.V3_ENABLED
            and settings.PERSONA_ENABLED
            and settings.OTHER_PERSONA_ENABLED
        ),
        "points_recharge_enabled": settings.POINTS_RECHARGE_ENABLED,
        "subscription_mock_enabled": settings.SUBSCRIPTION_MOCK_ENABLED,
    }
