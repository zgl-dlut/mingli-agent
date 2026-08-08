import hashlib
import time

from app.config import settings


def generate_wechat_pay_sign(params: dict) -> str:
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    sign_str += f"&key={settings.WECHAT_API_KEY}"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def generate_order_no() -> str:
    return f"ML{int(time.time())}{time.strftime('%m%d%H%M%S')}"


def build_unified_order_params(order_id: int, amount: float, notify_url: str) -> dict:
    params = {
        "appid": settings.WECHAT_APP_ID,
        "mch_id": settings.WECHAT_MCH_ID,
        "nonce_str": generate_order_no()[:32],
        "body": f"命理Agent充值{int(amount * 10)}积分",
        "out_trade_no": f"ML{order_id}{int(time.time())}",
        "total_fee": int(amount * 100),
        "spbill_create_ip": "127.0.0.1",
        "notify_url": notify_url,
        "trade_type": "JSAPI",
    }
    params["sign"] = generate_wechat_pay_sign(params)
    return params


def verify_wechat_pay_notify(params: dict) -> bool:
    sign = params.pop("sign", "")
    expected_sign = generate_wechat_pay_sign(params)
    return sign == expected_sign
