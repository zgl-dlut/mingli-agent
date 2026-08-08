from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.order import Order
from app.models.transaction import Transaction
from app.models.user import User
from app.core.exceptions import InsufficientPoints, BusinessError


POINTS_PACKAGES = {
    40: 4.0,
    80: 8.0,
    120: 12.0,
    160: 16.0,
    200: 20.0,
}


async def check_points(session: AsyncSession, user_id: int, required_points: int) -> bool:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise BusinessError("用户不存在")
    if user.points < required_points:
        return False
    return True


async def deduct_points(session: AsyncSession, user_id: int, points: int, description: str, order_id: Optional[int] = None) -> bool:
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
    )
    session.add(transaction)
    
    await session.commit()
    return True


async def add_points(session: AsyncSession, user_id: int, points: int, order_id: int, description: str) -> bool:
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
    )
    session.add(transaction)
    
    await session.commit()
    return True


async def create_order(session: AsyncSession, user_id: int, points: int, pay_method: str) -> Order:
    if points not in POINTS_PACKAGES:
        raise BusinessError("无效的充值档位")
    if pay_method not in ["wechat", "alipay"]:
        raise BusinessError("无效的支付方式")
    
    amount = POINTS_PACKAGES[points]
    
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
    order.trade_no = trade_no
    order.paid_at = datetime.now()
    
    await add_points(session, order.user_id, order.points, order.id, f"充值{order.points}积分")
    
    await session.commit()
    return True


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
