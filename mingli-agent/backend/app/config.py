from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    # AI 模型配置
    DASHSCOPE_API_KEY: str = ""
    AI_MODEL: str = "qwen-3.6-flash"
    AI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_API_KEY: str = ""

    # 短信服务配置（阿里云短信）
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = "北京维梦文化"
    SMS_TEMPLATE_CODE: str = "SMS_337485609"
    SMS_MOCK_MODE: bool = True

    # 多模型配置（逗号分隔，按优先级排序）
    AI_MODELS: str = "qwen-3.6-flash,qwen-2.5-7b,qwen2-7b-chat"
    AI_API_KEYS: str = ""
    AI_BASE_URLS: str = ""

    # 微信支付
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_MCH_ID: Optional[str] = None
    WECHAT_API_KEY: Optional[str] = None
    WECHAT_CERT_PATH: Optional[str] = None
    WECHAT_KEY_PATH: Optional[str] = None
    WECHAT_SERIAL_NO: Optional[str] = None
    WECHAT_NOTIFY_URL: Optional[str] = None

    # 支付宝
    ALIPAY_APP_ID: Optional[str] = None
    ALIPAY_PRIVATE_KEY: Optional[str] = None
    ALIPAY_PUBLIC_KEY: Optional[str] = None

    # 积分配置
    POINTS_FIRST_READING: int = 160
    POINTS_FOLLOW_UP: int = 40
    POINTS_PER_YUAN: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()