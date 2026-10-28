"""
支付 API - DB 版：订单持久化到 orders 表。
支持真实微信支付下单与回调。
"""
import time
import uuid
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.config import settings
from app.core.exceptions import V3APIError
from app.db.session import get_db
from app.models.order import Order
from app.models.user import User
from app.services import payment_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["payment"])


def _wechat_configured() -> bool:
    """微信支付关键配置是否就绪（key 审批通过后配置环境变量即启用真实支付）"""
    result = bool(
        settings.WECHAT_APP_ID
        and settings.WECHAT_MCH_ID
        and (settings.WECHAT_API_KEY or settings.WECHAT_SERIAL_NO)
    )
    logger.info(
        f"[payment][配置检查] _wechat_configured={result} | "
        f"APP_ID={settings.WECHAT_APP_ID!r} | MCH_ID={settings.WECHAT_MCH_ID!r} | "
        f"API_KEY={'已配置' if settings.WECHAT_API_KEY else '空'} | "
        f"SERIAL_NO={'已配置' if settings.WECHAT_SERIAL_NO else '空'}"
    )
    return result


class CreateWechatOrderRequest(BaseModel):
    points: int
    pay_type: str = "native"  # "jsapi" / "native" / "h5"
    openid: Optional[str] = None  # JSAPI 支付需要


@router.post("/create-wechat-order")
async def create_wechat_order(
    request: Request,
    body: CreateWechatOrderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """创建充值订单（DB 持久化）。微信未配置时返回 mock=true，前端模拟支付后调 mock-pay 确认"""
    if not settings.POINTS_RECHARGE_ENABLED:
        raise V3APIError(
            410,
            "points_recharge_disabled",
            "积分充值已停用，请查看订阅方案",
        )
    logger.info(f"[payment][入口] 创建订单: user={current_user.id} points={body.points} pay_type={body.pay_type} openid={body.openid}")

    order = await payment_service.create_order(db, current_user.id, body.points, "wechat")
    logger.info(f"[payment][订单创建] order_id={order.id} amount={order.amount} status={order.status}")

    if not _wechat_configured():
        logger.error(f"[payment][错误] 微信支付配置不完整 order_id={order.id}")
        raise HTTPException(status_code=503, detail="微信支付服务暂不可用，请稍后重试")

    # 真实微信支付分支
    try:
        from app.services.wechat_pay_service import (
            create_jsapi_order,
            create_native_order,
            create_h5_order,
            generate_jsapi_pay_params,
        )
        logger.info("[payment][导入] wechat_pay_service 导入成功")
    except ImportError as e:
        logger.error(f"[payment][错误] wechat_pay_service 导入失败: {e}")
        raise HTTPException(status_code=503, detail="微信支付服务暂不可用，请稍后重试")

    out_trade_no = f"ML{int(time.time())}{order.id}{uuid.uuid4().hex[:4]}"
    amount_fen = int(round(order.amount * 100))
    description = f"命理推算充值{order.points}积分"
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "")
    logger.info(f"[payment][参数] out_trade_no={out_trade_no} amount_fen={amount_fen} pay_type={body.pay_type} client_ip={client_ip}")

    try:
        if body.pay_type == "jsapi":
            logger.info("[payment][JSAPI] 开始JSAPI下单...")
            if not body.openid:
                raise HTTPException(status_code=400, detail="JSAPI 支付需要 openid")
            result = create_jsapi_order(description, amount_fen, body.openid, out_trade_no)
            logger.info(f"[payment][JSAPI] 下单返回: code={result.get('code')} prepay_id={result.get('prepay_id','')[:20]}...")
            pay_params = generate_jsapi_pay_params(result.get("prepay_id", ""))
            order.trade_no = out_trade_no
            await db.commit()
            logger.info(f"[payment][JSAPI] 支付参数生成成功，返回前端")
            return {
                "order_id": order.id,
                "points": order.points,
                "amount": order.amount,
                "mock": False,
                "pay_type": "jsapi",
                "pay_params": pay_params,
            }
        elif body.pay_type == "native":
            logger.info("[payment][Native] 开始Native下单...")
            result = create_native_order(description, amount_fen, out_trade_no)
            logger.info(f"[payment][Native] 下单返回: code={result.get('code')} code_url={result.get('code_url','')[:50]}...")
            order.trade_no = out_trade_no
            await db.commit()
            logger.info(f"[payment][Native] 二维码URL生成成功，返回前端")
            return {
                "order_id": order.id,
                "points": order.points,
                "amount": order.amount,
                "mock": False,
                "pay_type": "native",
                "code_url": result.get("code_url", ""),
            }
        logger.info("[payment][H5] 开始H5下单...")
        result = create_h5_order(description, amount_fen, out_trade_no, client_ip, user_agent)
        logger.info(f"[payment][H5] 下单返回: code={result.get('code')} h5_url={result.get('h5_url','')[:50]}...")
        order.trade_no = out_trade_no
        await db.commit()
        return {
            "order_id": order.id,
            "points": order.points,
            "amount": order.amount,
            "mock": False,
            "pay_type": "h5",
            "h5_url": result.get("h5_url", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[payment][错误] 微信下单失败: {type(e).__name__}: {e}\n{tb}")
        raise HTTPException(status_code=502, detail=f"微信支付下单失败: {str(e)}")


@router.post("/wechat/callback")
async def wechat_pay_callback(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """微信支付回调通知（真实接入后生效）：验签、按商户单号查订单、发放积分；幂等"""
    body = await request.body()
    headers = dict(request.headers)

    logger.warning(f"[payment][回调] 收到回调, headers_keys={list(headers.keys())}, body_length={len(body)}")
    logger.warning(f"[payment][回调] body内容: {body.decode('utf-8', errors='replace')}")

    try:
        from app.services.wechat_pay_service import verify_callback
        result = verify_callback(headers, body)
        logger.warning(f"[payment][回调] 验签解密结果: {result}")
    except Exception as e:
        import traceback
        logger.error(f"[payment][回调] 验签失败: {e}\n{traceback.format_exc()}")
        return {"code": "FAIL", "message": str(e)}

    # 微信支付回调结构：顶层是事件信息，实际交易数据在 resource 里
    if isinstance(result, dict) and "resource" in result:
        resource = result["resource"]
    else:
        resource = result if isinstance(result, dict) else {}

    out_trade_no = resource.get("out_trade_no", "")
    trade_state = resource.get("trade_state", "")
    transaction_id = resource.get("transaction_id", "")

    logger.warning(f"[payment][回调] out_trade_no={out_trade_no} trade_state={trade_state} transaction_id={transaction_id}")

    if trade_state == "SUCCESS" and out_trade_no:
        res = await db.execute(select(Order).where(Order.trade_no == out_trade_no))
        order = res.scalar_one_or_none()
        if order:
            # update_order_paid 幂等：已 paid 直接返回，不重复发积分
            await payment_service.update_order_paid(db, order.id, transaction_id)
            logger.info(f"[payment][回调] 订单 {order.id} 支付成功，积分已发放 trade_no={transaction_id}")
        else:
            logger.warning(f"[payment][回调] 回调订单不存在: {out_trade_no}")
    else:
        logger.warning(f"[payment][回调] 非成功状态: trade_state={trade_state}")

    return {"code": "SUCCESS", "message": "OK"}


@router.get("/order-status/{order_id}")
async def get_order_status(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """查询订单状态"""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="订单不存在")

    return {
        "order_id": order.id,
        "points": order.points,
        "amount": order.amount,
        "status": order.status,
        "trade_no": order.trade_no,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }
