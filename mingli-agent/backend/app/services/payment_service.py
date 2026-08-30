from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.order import Order
from app.models.transaction import Transaction
from app.models.user import User
from app.core.exceptions import InsufficientPoints, BusinessError


# 固定档位供前端快捷选择参考，自定义充值不再受限于此
POINTS_PACKAGES = {
    40: 4.0,
    80: 8.0,
    120: 12.0,
    160: 16.0,
    200: 20.0,
    400: 40.0,
    800: 80.0,
    1000: 100.0,
    2000: 200.0,
}

MIN_RECHARGE_POINTS = 10
MAX_RECHARGE_POINTS = 10000
POINTS_PER_YUAN = 10  # 1元 = 10积分


async def check_points(session: AsyncSession, user_id: int, required_points: int) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise BusinessError("用户不存在")
    if user.points < required_points:
        return False
    return True


async def deduct_points(session: AsyncSession, user_id: int, points: int, description: str, order_id: Optional[int] = None, biz_type: Optional[str] = None) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise BusinessError("用户不存在")
    if user.points < points:
        raise InsufficientPoints(f"积分不足，需要{points}积分，当前{user.points}积分")
    
    user.points -= points
    
    transaction = Transaction(
        user_id=user_id,
        type="consume",
        points=points,
        order_id=order_id,
        description=description,
        biz_type=biz_type,
    )
    session.add(transaction)
    
    await session.commit()
    return True


async def add_points(session: AsyncSession, user_id: int, points: int, order_id: int, description: str, biz_type: str = "recharge") -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise BusinessError("用户不存在")
    
    user.points += points
    
    transaction = Transaction(
        user_id=user_id,
        type="recharge",
        points=points,
        order_id=order_id,
        description=description,
        biz_type=biz_type,
    )
    session.add(transaction)
    
    await session.commit()
    return True


async def create_order(session: AsyncSession, user_id: int, points: int, pay_method: str) -> Order:
    if points < MIN_RECHARGE_POINTS or points > MAX_RECHARGE_POINTS:
        raise BusinessError(f"充值积分需在{MIN_RECHARGE_POINTS}~{MAX_RECHARGE_POINTS}之间")
    if pay_method not in ["wechat", "alipay"]:
        raise BusinessError("无效的支付方式")

    amount = round(points / POINTS_PER_YUAN, 1)
    
    order = Order(
        user_id=user_id,
        points=points,
        amount=amount,
        pay_method=pay_method,
        status="pending",
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    
    return order


async def update_order_paid(session: AsyncSession, order_id: int, trade_no: str) -> bool:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise BusinessError("订单不存在")
    if order.status == "paid":
        return True
    if order.status != "pending":
        raise BusinessError("订单状态异常")
    
    order.status = "paid"
    # 仅在下单时未写商户单号（如mock支付）时写入；已有商户单号则保留，
    # 避免被微信transaction_id覆盖导致回调重试时按out_trade_no查不到订单
    if not order.trade_no:
        order.trade_no = trade_no
    order.paid_at = datetime.now()
    
    await add_points(session, order.user_id, order.points, order.id, f"充值{order.points}积分")
    
    await session.commit()
    return True


async def admin_recharge_points(
    session: AsyncSession,
    phone: str,
    points: int,
    remark: str = "",
) -> dict:
    """管理员通过手机号给用户充值积分：创建已支付订单 + 加积分 + 写流水"""
    # 1. 查找用户
    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        raise BusinessError(f"手机号 {phone} 未注册")

    # 2. 创建订单（直接标记为已支付）
    amount = round(points / POINTS_PER_YUAN, 1)
    order = Order(
        user_id=user.id,
        points=points,
        amount=amount,
        pay_method="admin",
        status="paid",
        trade_no=f"ADMIN_{int(datetime.now().timestamp())}",
        paid_at=datetime.now(),
    )
    session.add(order)
    await session.flush()

    # 3. 加积分
    user.points += points

    # 4. 写交易流水
    description = f"管理员充值{points}积分" + (f"（{remark}）" if remark else "")
    transaction = Transaction(
        user_id=user.id,
        type="recharge",
        points=points,
        order_id=order.id,
        description=description,
        biz_type="admin_recharge",
    )
    session.add(transaction)
    await session.commit()

    return {
        "user_id": user.id,
        "user_name": user.name,
        "phone": user.phone,
        "points_added": points,
        "balance": user.points,
        "order_id": order.id,
    }


async def get_user_points(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return 0
    return user.points


async def get_transactions(session: AsyncSession, user_id: int, limit: int = 20) -> list:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
