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

    # 追问指代消解改写器（多轮对话"那个窗口/第二点"等指代AI上轮回答内容的补全）
    # off   = 完全不运行
    # shadow= 影子模式（默认）：并行运行改写器、结果只写日志对比，绝不替换线上问题，零影响
    # apply = 正式启用：改写后的自包含问题用于生成
    QUESTION_REWRITE_MODE: str = "shadow"

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

    # 分享赚积分：每邀请1个新用户注册，邀请人获得的积分
    SHARE_REWARD_POINTS: int = 80

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
# v2026.09.08-1: build_authoritative_chart_basis命盘骨架补入【十神分布】【格局(含依据)】【五行分布(含藏干)】，
#               llm_scorer编造检测加"十神/格局判定铁律"（禁止评测LLM自行重推十神生克，以命盘标注为唯一权威）
#               +"五行有无判断铁律"（含藏干，禁仅凭天干本气断言全局无某行）——修复癸日主年干丙火正财被评测LLM
#               误判"无正财依据"的high级误报（生成报告依据命盘shishen正确，误报根因是检测基准缺十神字段）
# v2026.09.09-1: 编造检测加"逐项核对明细"——LLM无论是否发现编造都必须返回8项核对过程
#               （大运/流年/流月/十神/格局/用神忌神/具体数字事件/越界年份），每项写明
#               "报告称X，命盘Y，一致/不一致"的依据，禁止只给"无编造"结论；前端详情页
#               可折叠展示核对清单，人工抽检时可直接看到裁判查了什么（裁判自证机制）
# v2026.09.14-1: 新增神煞编造检测(_detect_shensha_mismatch)——报告中提到的神煞必须在命盘
#               神煞字段内，否则判编造（如"你日柱己卯自带天乙贵人"但命盘日柱无天乙贵人）；
#               追问链路三处聚合登记+retry hint，首次报告链路独立检测+重试块；
#               修复LLM为迎合用户"太乙贵人"问题凭空捏造神煞，此前仅靠LLM语义层抓取
# v2026.09.14-2: 评测端LLM编造检测逐项核对明细从8项扩为9项，新增第9项"神煞"专项核对
#               （报告提到的神煞是否在命盘神煞字段四柱列表中），与生成端代码层检测呼应
PROMPT_VERSION = "v2026.09.14-2"