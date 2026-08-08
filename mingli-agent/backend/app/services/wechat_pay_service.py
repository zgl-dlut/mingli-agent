import logging
from app.config import settings

logger = logging.getLogger(__name__)

# 延迟初始化，避免没有证书时报错
_wxpay = None

def _get_wxpay():
    """延迟初始化微信支付客户端"""
    global _wxpay
    if _wxpay is None:
        if not all([settings.WECHAT_MCH_ID, settings.WECHAT_API_KEY,
                     settings.WECHAT_CERT_PATH, settings.WECHAT_KEY_PATH,
                     settings.WECHAT_SERIAL_NO, settings.WECHAT_APP_ID]):
            raise ValueError("微信支付配置不完整，请检查 .env 文件")
        from wechatpayv3 import WeChatPay, WeChatPayType
        _wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=settings.WECHAT_MCH_ID,
            private_key=open(settings.WECHAT_KEY_PATH).read(),
            cert_serial_no=settings.WECHAT_SERIAL_NO,
            appid=settings.WECHAT_APP_ID,
            apiv3_key=settings.WECHAT_API_KEY,
            notify_url=settings.WECHAT_NOTIFY_URL,
            private_key_path=settings.WECHAT_KEY_PATH,
            cert_path=settings.WECHAT_CERT_PATH,
        )
    return _wxpay


def create_jsapi_order(description: str, amount_fen: int, openid: str, out_trade_no: str) -> dict:
    """
    创建 JSAPI 支付订单
    返回包含 prepay_id 的字典
    """
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount_fen, 'currency': 'CNY'},
        payer={'openid': openid},
    )
    # code 应该是 200，message 包含 prepay_id
    return {"code": code, "prepay_id": message.get("prepay_id", ""), "raw": message}


def create_h5_order(description: str, amount_fen: int, out_trade_no: str,
                     client_ip: str, user_agent: str = "") -> dict:
    """
    创建 H5 支付订单
    返回包含 h5_url 的字典
    """
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount_fen, 'currency': 'CNY'},
        scene_info={
            'payer_client_ip': client_ip,
            'h5_info': {'type': 'Wap', 'wap_url': '', 'wap_name': '命理推算'},
        },
    )
    return {"code": code, "h5_url": message.get("h5_url", ""), "raw": message}


def generate_jsapi_pay_params(prepay_id: str) -> dict:
    """
    生成前端 wx.requestPayment 需要的参数
    """
    import time
    import random
    import string

    wxpay = _get_wxpay()
    nonce_str = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    timestamp = str(int(time.time()))

    # 使用 SDK 签名
    params = wxpay.get_pay_params(prepay_id)
    return params


def verify_callback(headers: dict, body: bytes) -> dict:
    """
    验证微信支付回调签名并解析内容
    返回解密后的订单信息
    """
    wxpay = _get_wxpay()
    # wechatpayv3 SDK 提供回调验证
    result = wxpay.callback(headers, body)
    return result