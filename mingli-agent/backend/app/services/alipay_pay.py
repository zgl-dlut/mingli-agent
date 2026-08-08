import base64
import json
import time

from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256

from app.config import settings


def generate_alipay_order_params(order_id: int, amount: float, return_url: str, notify_url: str) -> dict:
    params = {
        "app_id": settings.ALIPAY_APP_ID,
        "method": "alipay.trade.page.pay",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "biz_content": json.dumps({
            "out_trade_no": f"ML{order_id}{int(time.time())}",
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "total_amount": str(amount),
            "subject": f"命理Agent充值{int(amount * 10)}积分",
            "return_url": return_url,
            "notify_url": notify_url,
        }),
    }
    params["sign"] = generate_alipay_sign(params)
    return params


def generate_alipay_sign(params: dict) -> str:
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    private_key = RSA.import_key(settings.ALIPAY_PRIVATE_KEY)
    signer = PKCS1_v1_5.new(private_key)
    digest = SHA256.new(sign_str.encode("utf-8"))
    signature = signer.sign(digest)
    return base64.b64encode(signature).decode("utf-8")


def verify_alipay_notify(params: dict) -> bool:
    sign = params.pop("sign", "")
    sign_type = params.pop("sign_type", "")
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    
    public_key = RSA.import_key(settings.ALIPAY_PUBLIC_KEY)
    verifier = PKCS1_v1_5.new(public_key)
    digest = SHA256.new(sign_str.encode("utf-8"))
    signature = base64.b64decode(sign)
    
    return verifier.verify(digest, signature)
