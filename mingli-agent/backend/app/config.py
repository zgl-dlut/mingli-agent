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
    WECHAT_APP_SECRET: Optional[str] = None  # 公众号AppSecret（OAuth网页授权用，非APIv3密钥）
    WECHAT_MCH_ID: Optional[str] = None
    WECHAT_API_KEY: Optional[str] = None
    WECHAT_CERT_PATH: Optional[str] = None
    WECHAT_KEY_PATH: Optional[str] = None
    WECHAT_SERIAL_NO: Optional[str] = None
    WECHAT_NOTIFY_URL: Optional[str] = None
    WECHAT_OAUTH_REDIRECT_URI: Optional[str] = None
    WECHAT_PUBLIC_KEY_ID: Optional[str] = None
    WECHAT_PUBLIC_KEY_PATH: Optional[str] = None

    # 支付宝
    ALIPAY_APP_ID: Optional[str] = None
    ALIPAY_PRIVATE_KEY: Optional[str] = None
    ALIPAY_PUBLIC_KEY: Optional[str] = None

    # 积分配置
    POINTS_FIRST_READING: int = 160
    POINTS_FOLLOW_UP: int = 40
    POINTS_PER_YUAN: int = 10
    
    # 白名单手机号赠送积分（逗号分隔）
    BONUS_PHONE_LIST: str = ""
    BONUS_POINTS: int = 1000

    # 新注册用户自动赠送积分（默认240 = 1次报告160 + 2次追问40×2）
    NEW_USER_BONUS_POINTS: int = 240

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Prompt 版本标记：每次生成端 prompt/检测器改动后手动递增，
# 随生产评测记录落库（monitor_detail.prompt_version），用于精确归因与跨版本对比
# 当前版本内容：数据边界声明 + 历史摘要问题清单化 + 权威命盘基准注入 +
#              凶月淡化/凶月行动矛盾/命盘外细节(薪资倍数/融资轮/offer集中/转化率/匹配度)检测器 +
#              大运兜底(大运列表按当前年提取) + 跨月时间段定性检测 +
#              编造边界调整：评测prompt区分演绎vs编造、代码层移除团队画像关键词(交评测LLM判依据链)、生成端鼓励现实演绎 +
#              评测命盘数据源修复：评测端用生成端重建的完整analysis_data(含大运列表+当前大运)做基准，不再用person旧版命盘(无大运列表)→消除大运等数据不一致误判
#              首次报告链路接入大运编造检测+重试(复用追问链路_detect_dayun_ganzhi_mismatch/_detect_dayun_period_mismatch纯函数，不改followup_structured.py)，此前首次报告无内容层检测导致大运编造直达用户
#              bazi_service大运方向gender兼容中英文(修DB存male/female致阴年女/阳年男应顺排被算成逆排，已重算29个命盘) + _extract_question_years补相对年份词识别(今年/明年/去年等→当前年偏移，修"今年"流月明细不注入致LLM编造流月，#155根因)
#              评测端structure_checker:首次报告跳过"标题未贴合用户原话"检测(首次报告用户仅输入生辰无具体问题、subtopic标题固定；追问保留该校验)+llm_scorer传is_first_reading
#              评测端首次报告再放宽2项: structure_checker block数量异常放宽2-6(原2-4) + narrative_checker keyword含术语跳过(首次报告讲命理维度术语是核心内容；追问2-4+保留术语检测不变)
#              评测端首次报告narrative上限放宽到160字(原130字)，与block放宽配套；追问仍130字
#              build_authoritative_chart_basis补充缺失字段(喜神/五行应用/大运完整序列+方向/神煞核心)，修复编造检测端基准不全致"喜神=土""大运丁巳"等合法引用被误判为编造high的系统性bug；生成端(首次+追问)prompt注入也同步受益，实现生成端+检测端命盘基准同源同构
#              v10: 时间线约束加"规则自检禁止外露"——LLM把质检公式"离职≤offer≤入职"原文照抄进报告(如"完全符合离职≤offer≤入职的现实逻辑")，生成端两处prompt(skill_prompts流月边界第5条+followup_structured时间线铁律末条)均加禁止外露条目
PROMPT_VERSION = "v2026.09.07-1"