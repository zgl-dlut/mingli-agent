"""
支付 API - 轻量版（无数据库依赖）
"""
import time
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["payment"])

# 内存存储订单（生产环境应替换为数据库）
_orders: dict = {}


class CreateWechatOrderRequest(BaseModel):
    points: int
    pay_type: str = "h5"  # "jsapi" 或 "h5"
    openid: Optional[str] = None  # JSAPI 支付需要


@router.post("/create-wechat-order")
async def create_wechat_order(request: Request, body: CreateWechatOrderRequest):
    """创建微信支付订单"""
    try:
        from app.services.wechat_pay_service import create_jsapi_order, create_h5_order, generate_jsapi_pay_params
    except ImportError:
        raise HTTPException(status_code=503, detail="微信支付 SDK 未安装")

    # 生成订单号
    out_trade_no = f"ML{int(time.time())}{uuid.uuid4().hex[:6]}"
    amount_fen = body.points * 10  # 1元=10积分，即1积分=0.1元=10分
    description = f"命理推算充值{body.points}积分"

    # 获取客户端 IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "")

    try:
        if body.pay_type == "jsapi":
            if not body.openid:
                raise HTTPException(status_code=400, detail="JSAPI 支付需要 openid")
            result = create_jsapi_order(description, amount_fen, body.openid, out_trade_no)
            pay_params = generate_jsapi_pay_params(result.get("prepay_id", ""))

            _orders[out_trade_no] = {
                "order_id": out_trade_no,
                "points": body.points,
                "amount_fen": amount_fen,
                "status": "pending",
                "pay_type": "jsapi",
                "created_at": time.time(),
            }

            return {
                "order_id": out_trade_no,
                "points": body.points,
                "amount": amount_fen / 100,
                "pay_type": "jsapi",
                "pay_params": pay_params,
            }
        else:
            result = create_h5_order(description, amount_fen, out_trade_no, client_ip, user_agent)

            _orders[out_trade_no] = {
                "order_id": out_trade_no,
                "points": body.points,
                "amount_fen": amount_fen,
                "status": "pending",
                "pay_type": "h5",
                "created_at": time.time(),
            }

            return {
                "order_id": out_trade_no,
                "points": body.points,
                "amount": amount_fen / 100,
                "pay_type": "h5",
                "h5_url": result.get("h5_url", ""),
            }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"创建微信支付订单失败: {e}")
        raise HTTPException(status_code=500, detail=f"支付下单失败: {str(e)}")


@router.post("/wechat/callback")
async def wechat_pay_callback(request: Request):
    """微信支付回调通知"""
    body = await request.body()
    headers = dict(request.headers)

    try:
        from app.services.wechat_pay_service import verify_callback
        result = verify_callback(headers, body)
    except Exception as e:
        logger.error(f"微信回调验签失败: {e}")
        return {"code": "FAIL", "message": str(e)}

    # 解析订单信息
    out_trade_no = result.get("out_trade_no", "")
    trade_state = result.get("trade_state", "")
    transaction_id = result.get("transaction_id", "")

    if trade_state == "SUCCESS" and out_trade_no in _orders:
        _orders[out_trade_no]["status"] = "paid"
        _orders[out_trade_no]["trade_no"] = transaction_id
        _orders[out_trade_no]["paid_at"] = time.time()
        logger.info(f"订单 {out_trade_no} 支付成功, trade_no={transaction_id}")

    return {"code": "SUCCESS", "message": "OK"}


@router.get("/order-status/{order_id}")
async def get_order_status(order_id: str):
    """查询订单状态"""
    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return {
        "order_id": order["order_id"],
        "points": order["points"],
        "amount": order["amount_fen"] / 100,
        "status": order["status"],
        "trade_no": order.get("trade_no"),
        "pay_type": order.get("pay_type"),
    }