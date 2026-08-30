import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# 延迟初始化，避免没有证书时报错
_wxpay = None

def _get_wxpay():
    """延迟初始化微信支付客户端（使用公钥模式）"""
    global _wxpay
    if _wxpay is None:
        if not all([settings.WECHAT_MCH_ID, settings.WECHAT_API_KEY,
                     settings.WECHAT_CERT_PATH, settings.WECHAT_KEY_PATH,
                     settings.WECHAT_SERIAL_NO, settings.WECHAT_APP_ID,
                     settings.WECHAT_PUBLIC_KEY_ID, settings.WECHAT_PUBLIC_KEY_PATH]):
            raise ValueError("微信支付配置不完整，请检查 .env 文件")
        from wechatpayv3 import WeChatPay, WeChatPayType
        logger.info(f"[wechat] 初始化微信支付客户端 (公钥模式)")
        logger.info(f"[wechat] public_key_id={settings.WECHAT_PUBLIC_KEY_ID}")
        logger.info(f"[wechat] public_key_path={settings.WECHAT_PUBLIC_KEY_PATH}")
        _wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=settings.WECHAT_MCH_ID,
            private_key=open(settings.WECHAT_KEY_PATH).read(),
            cert_serial_no=settings.WECHAT_SERIAL_NO,
            appid=settings.WECHAT_APP_ID,
            apiv3_key=settings.WECHAT_API_KEY,
            notify_url=settings.WECHAT_NOTIFY_URL,
            public_key=open(settings.WECHAT_PUBLIC_KEY_PATH).read(),
            public_key_id=settings.WECHAT_PUBLIC_KEY_ID,
        )
        logger.info("[wechat] 微信支付客户端初始化成功")
    return _wxpay


def create_jsapi_order(description: str, amount_fen: int, openid: str, out_trade_no: str) -> dict:
    """
    创建 JSAPI 支付订单
    返回包含 prepay_id 的字典
    """
    from wechatpayv3 import WeChatPayType
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount_fen, 'currency': 'CNY'},
        payer={'openid': openid},
        pay_type=WeChatPayType.JSAPI,
    )
    if isinstance(message, str):
        import json
        message = json.loads(message)
    return {"code": code, "prepay_id": message.get("prepay_id", ""), "raw": message}


def create_native_order(description: str, amount_fen: int, out_trade_no: str) -> dict:
    """
    创建 Native 支付订单（扫码支付）
    返回包含 code_url（二维码链接）的字典
    """
    from wechatpayv3 import WeChatPayType
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount_fen, 'currency': 'CNY'},
        pay_type=WeChatPayType.NATIVE,
    )
    if isinstance(message, str):
        import json
        message = json.loads(message)
    logger.info(f"[wechat] Native下单返回: code={code}, message={message}")
    if code != 200:
        error_msg = message.get("message", "未知错误") if isinstance(message, dict) else str(message)
        raise Exception(f"微信Native下单失败: code={code}, {error_msg}")
    return {"code": code, "code_url": message.get("code_url", ""), "raw": message}


def create_h5_order(description: str, amount_fen: int, out_trade_no: str,
                     client_ip: str, user_agent: str = "") -> dict:
    """
    创建 H5 支付订单
    返回包含 h5_url 的字典
    """
    from wechatpayv3 import WeChatPayType
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description,
        out_trade_no=out_trade_no,
        amount={'total': amount_fen, 'currency': 'CNY'},
        scene_info={
            'payer_client_ip': client_ip,
            'h5_info': {'type': 'Wap'},
        },
        pay_type=WeChatPayType.H5,
    )
    if isinstance(message, str):
        import json
        message = json.loads(message)
    logger.info(f"[wechat] H5下单返回: code={code}, message={message}")
    if code != 200:
        error_msg = message.get("message", "未知错误") if isinstance(message, dict) else str(message)
        raise Exception(f"微信H5下单失败: code={code}, {error_msg}")
    return {"code": code, "h5_url": message.get("h5_url", ""), "raw": message}


def generate_jsapi_pay_params(prepay_id: str) -> dict:
    """
    生成前端 wx.requestPayment / getBrandWCPayRequest 需要的参数
    按微信支付v3官方规则签名：appId\ntimeStamp\nnonceStr\npackage\n 用商户私钥RSA-SHA256签名
    """
    import time
    import uuid
    wxpay = _get_wxpay()
    appid = settings.WECHAT_APP_ID
    timestamp = str(int(time.time()))
    nonce_str = uuid.uuid4().hex.upper()
    package = f"prepay_id={prepay_id}"
    pay_sign = wxpay.sign([appid, timestamp, nonce_str, package])
    return {
        "appId": appid,
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


def verify_callback(headers: dict, body: bytes) -> dict:
    """
    验证微信支付回调签名并解析内容
    返回解密后的订单信息
    """
    wxpay = _get_wxpay()
    result = wxpay.callback(headers, body)
    # wechatpayv3库的callback可能返回 (code, message) 元组或直接返回dict
    if isinstance(result, tuple):
        code, message = result
        logger.info(f"[wechat] callback返回元组: code={code}, message={message}")
        if isinstance(message, str):
            import json
            message = json.loads(message)
        return message
    logger.info(f"[wechat] callback返回: {result}")
    return result


def query_order(out_trade_no: str) -> dict:
    """
    主动查询微信支付订单状态
    返回订单信息，包含 trade_state（SUCCESS/NOTPAY/CLOSED等）
    """
    wxpay = _get_wxpay()
    code, message = wxpay.query_order(out_trade_no=out_trade_no)
    if isinstance(message, str):
        import json
        message = json.loads(message)
    logger.info(f"[wechat] 查询订单状态: out_trade_no={out_trade_no}, code={code}, trade_state={message.get('trade_state', '')}")
    return {"code": code, "data": message}
