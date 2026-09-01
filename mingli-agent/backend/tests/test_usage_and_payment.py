"""
积分明细 / 支付链路 / 用量落库 集成测试。

使用开发 PostgreSQL：创建一次性测试用户，流程结束后删除全部测试数据。
覆盖：
- deduct_points 带 biz_type（first_reading / followup）
- 修改昵称接口校验（1-20 字符）
- _record_usage_log 用量落库（成功/失败）
- 管理后台 /api/admin/usage-logs、/api/admin/orders 查询

注意：每个测试用 asyncio.run 独立事件循环，结束前必须 dispose 引擎，
否则连接池会跨事件循环失效。
"""
import asyncio
import inspect
import time
from datetime import datetime

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.auth import get_current_user
from app.api.chat import _record_usage_log
from app.core.exceptions import InsufficientPoints
from app.db.session import async_session, engine, get_db
from app.main import app
from app.models.order import Order
from app.models.person import Person
from app.models.transaction import Transaction
from app.models.usage_log import AiUsageLog
from app.models.user import User
from app.services import payment_service


# ---------- 工具 ----------

def _run(coro):
    return asyncio.run(coro)


def _next_phone() -> str:
    """唯一测试手机号（20 字符内）"""
    return f"199{str(time.time_ns())[-17:]}"


async def _create_test_user(points: int = 200) -> int:
    async with async_session() as db:
        user = User(phone=_next_phone(), name="测试用户", points=points)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _cleanup(user_id: int) -> None:
    async with async_session() as db:
        await db.execute(delete(AiUsageLog).where(AiUsageLog.user_id == user_id))
        await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await db.execute(delete(Order).where(Order.user_id == user_id))
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()
    # 每个测试独立事件循环，必须释放连接池
    await engine.dispose()


def _login_as(user_id: int):
    """把 get_current_user 覆盖为从当前会话加载测试用户"""

    async def _override(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()

    app.dependency_overrides[get_current_user] = _override


def _logout():
    app.dependency_overrides.pop(get_current_user, None)


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------- 支付链路 ----------

def test_invalid_points_package_rejected():
    async def run():
        uid = await _create_test_user()
        _login_as(uid)
        try:
            async with _client() as client:
                res = await client.post(
                    "/api/payment/create-wechat-order",
                    json={"points": 123, "pay_type": "h5"},
                )
                assert res.status_code == 400  # BusinessError → 400
        finally:
            _logout()
            await _cleanup(uid)

    _run(run())


# ---------- 扣费 biz_type ----------

def test_deduct_points_biz_type():
    async def run():
        uid = await _create_test_user(points=200)
        try:
            async with async_session() as db:
                await payment_service.deduct_points(
                    db, uid, 160, "首次报告", biz_type="first_reading"
                )
                await payment_service.deduct_points(
                    db, uid, 40, "追问", biz_type="followup"
                )

            async with async_session() as db:
                user = (await db.execute(select(User).where(User.id == uid))).scalar_one()
                assert user.points == 0

                txs = (
                    await db.execute(
                        select(Transaction)
                        .where(Transaction.user_id == uid)
                        .order_by(Transaction.id)
                    )
                ).scalars().all()
                assert [t.biz_type for t in txs] == ["first_reading", "followup"]
                assert [t.type for t in txs] == ["consume", "consume"]
                assert [t.points for t in txs] == [160, 40]

            # 积分不足抛 InsufficientPoints
            async with async_session() as db:
                with pytest.raises(InsufficientPoints):
                    await payment_service.deduct_points(
                        db, uid, 40, "追问", biz_type="followup"
                    )
        finally:
            await _cleanup(uid)

    _run(run())


# ---------- 修改昵称 ----------

def test_update_profile_nickname():
    async def run():
        uid = await _create_test_user()
        _login_as(uid)
        try:
            async with _client() as client:
                # 合法昵称
                res = await client.put("/api/user/profile", json={"name": "新昵称"})
                assert res.status_code == 200, res.text
                assert res.json()["name"] == "新昵称"

                # 空昵称
                res = await client.put("/api/user/profile", json={"name": "   "})
                assert res.status_code == 400

                # 超长昵称（21 字符）
                res = await client.put("/api/user/profile", json={"name": "名" * 21})
                assert res.status_code == 400
        finally:
            _logout()
            await _cleanup(uid)

    _run(run())


# ---------- 用量落库 ----------

def test_record_usage_log():
    async def run():
        uid = await _create_test_user()
        try:
            # 成功请求
            t0 = time.time() - 2.5
            holder_ok = {
                "success": True,
                "model": "test-model",
                "input_chars": 100,
                "input_tokens": 200,
                "output_chars": 300,
                "output_tokens": 400,
                "total_tokens": 600,
                "cached_tokens": 150,
            }
            async with async_session() as db:
                await _record_usage_log(db, uid, 999999, "first_reading", holder_ok, t0)

            # 失败请求（holder 无 success）
            async with async_session() as db:
                await _record_usage_log(db, uid, 999999, "followup", {}, time.time())

            async with async_session() as db:
                logs = (
                    await db.execute(
                        select(AiUsageLog)
                        .where(AiUsageLog.user_id == uid)
                        .order_by(AiUsageLog.id)
                    )
                ).scalars().all()
                assert len(logs) == 2

                ok_log = logs[0]
                assert ok_log.biz_type == "first_reading"
                assert ok_log.model == "test-model"
                assert ok_log.success is True
                assert ok_log.total_tokens == 600
                assert ok_log.cached_tokens == 150
                assert ok_log.duration_ms >= 2000

                fail_log = logs[1]
                assert fail_log.biz_type == "followup"
                assert fail_log.success is False
                assert fail_log.total_tokens == 0
        finally:
            await _cleanup(uid)

    _run(run())


def test_usage_holder_param_exists():
    """生成器函数必须支持 usage_holder 钩子参数"""
    from app.services.ai_service import generate_first_reading_structured
    from app.services.followup_structured import generate_followup_structured

    for fn in (generate_first_reading_structured, generate_followup_structured):
        assert "usage_holder" in inspect.signature(fn).parameters, fn.__name__


# ---------- 管理后台接口 ----------

def test_admin_usage_logs_and_orders_api():
    async def run():
        uid = await _create_test_user()
        _login_as(uid)
        try:
            # 直接操作数据库创建已支付订单和用量记录
            async with async_session() as db:
                order = Order(
                    user_id=uid,
                    points=40,
                    amount=4.0,
                    pay_method="wechat",
                    status="paid",
                    trade_no=f"TEST{int(time.time())}",
                    paid_at=datetime.now()
                )
                db.add(order)
                await db.commit()
                await db.refresh(order)
                order_id = order.id

                await _record_usage_log(
                    db, uid, 888888, "followup",
                    {"success": True, "model": "m", "total_tokens": 10,
                     "input_tokens": 6, "output_tokens": 4,
                     "input_chars": 5, "output_chars": 5},
                    time.time(),
                )

            async with _client() as client:
                # 用量记录（按 user_id 筛选）
                res = await client.get("/api/admin/usage-logs", params={"user_id": uid})
                assert res.status_code == 200, res.text
                body = res.json()
                assert body["total"] == 1
                item = body["items"][0]
                assert item["biz_type"] == "followup"
                assert item["total_tokens"] == 10
                assert item["user_id"] == uid

                # 订单记录（按 user_id 筛选）
                res = await client.get("/api/admin/orders", params={"user_id": uid})
                assert res.status_code == 200, res.text
                body = res.json()
                assert body["total"] == 1
                item = body["items"][0]
                assert item["id"] == order_id
                assert item["status"] == "paid"
                assert item["points"] == 40
                assert item["pay_method"] == "wechat"

                # 状态筛选
                res = await client.get(
                    "/api/admin/orders", params={"user_id": uid, "status": "pending"}
                )
                assert res.json()["total"] == 0
        finally:
            _logout()
            await _cleanup(uid)

    _run(run())


# ---------- 创建人物去重（防止重复扣费） ----------

def test_create_person_dedup_no_double_charge():
    """同一用户相同生辰重复创建，只扣一次费"""
    async def run():
        uid = await _create_test_user(points=500)
        _login_as(uid)
        try:
            async with _client() as client:
                payload = {
                    "name": "测试人物",
                    "gender": "male",
                    "birth_date": "1994-10-13",
                    "birth_time": "18:03",
                    "birth_location": "北京市 北京市",
                    "birth_lat": 39.9042,
                    "birth_lng": 116.4074,
                    "calendar_type": "solar",
                    "province": "北京市",
                    "city": "北京市",
                }

                # 第1次创建：正常扣费
                res1 = await client.post("/api/persons", json=payload)
                assert res1.status_code == 200, res1.text
                assert res1.json().get("duplicated") is None or res1.json().get("duplicated") is False

                # 第2次创建（相同生辰）：应返回 duplicated=True，不扣费
                res2 = await client.post("/api/persons", json=payload)
                assert res2.status_code == 200, res2.text
                assert res2.json().get("duplicated") is True

                # 第3次创建：同样不扣费
                res3 = await client.post("/api/persons", json=payload)
                assert res3.status_code == 200, res3.text
                assert res3.json().get("duplicated") is True

            # 验证只扣了1次费（160积分）
            async with async_session() as db:
                user = (await db.execute(select(User).where(User.id == uid))).scalar_one()
                assert user.points == 340, f"期望340积分，实际{user.points}（应只扣160）"

                txs = (
                    await db.execute(
                        select(Transaction)
                        .where(Transaction.user_id == uid, Transaction.biz_type == "first_reading")
                    )
                ).scalars().all()
                assert len(txs) == 1, f"期望1条first_reading流水，实际{len(txs)}条"
        finally:
            _logout()
            await _cleanup(uid)

    _run(run())


# ---------- 用户注册赠送积分 ----------

def test_bonus_phone_first_login_gets_points():
    """白名单用户首次登录：新用户赠送240 + 白名单赠送积分"""
    async def run():
        from app.models.bonus_phone import BonusPhone
        from app.skills.auth.sms_auth_skill import SmsCodeCache
        from app.config import settings

        phone = _next_phone()
        bonus_points = 1000
        expected = settings.NEW_USER_BONUS_POINTS + bonus_points

        async with async_session() as db:
            db.add(BonusPhone(phone=phone, points=bonus_points))
            await db.commit()

        # Mock 验证码
        SmsCodeCache.set(phone, "111111")

        user_id = None
        try:
            async with _client() as client:
                res = await client.post("/api/auth/login", json={"phone": phone, "code": "111111"})
                assert res.status_code == 200, res.text
                body = res.json()
                assert body["points"] == expected, f"期望{expected}积分，实际{body['points']}"
                user_id = body["user_id"]

            # 验证流水：白名单bonus流水1条 + 新用户赠送流水1条
            async with async_session() as db:
                txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "bonus")
                )).scalars().all()
                assert len(txs) == 1, f"期望1条bonus流水，实际{len(txs)}条"
                assert txs[0].points == bonus_points
                new_txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "new_user_bonus")
                )).scalars().all()
                assert len(new_txs) == 1, f"期望1条new_user_bonus流水，实际{len(new_txs)}条"
                assert new_txs[0].points == settings.NEW_USER_BONUS_POINTS
        finally:
            if user_id:
                async with async_session() as db:
                    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
                    await db.execute(delete(User).where(User.id == user_id))
                    await db.execute(delete(BonusPhone).where(BonusPhone.phone == phone))
                    await db.commit()
                await engine.dispose()

    _run(run())


def test_bonus_phone_second_login_no_double_bonus():
    """内测用户非首次登录不应重复赠送积分"""
    async def run():
        from app.models.bonus_phone import BonusPhone
        from app.skills.auth.sms_auth_skill import SmsCodeCache
        from app.config import settings

        phone = _next_phone()
        bonus_points = 1000
        expected = settings.NEW_USER_BONUS_POINTS + bonus_points

        async with async_session() as db:
            db.add(BonusPhone(phone=phone, points=bonus_points))
            await db.commit()

        SmsCodeCache.set(phone, "111111")

        user_id = None
        try:
            async with _client() as client:
                # 第1次登录：赠送积分
                res1 = await client.post("/api/auth/login", json={"phone": phone, "code": "111111"})
                assert res1.status_code == 200
                assert res1.json()["points"] == expected
                user_id = res1.json()["user_id"]

                # 第2次登录：不应再赠送
                SmsCodeCache.set(phone, "111111")
                res2 = await client.post("/api/auth/login", json={"phone": phone, "code": "111111"})
                assert res2.status_code == 200
                assert res2.json()["points"] == expected, f"第2次登录积分应为{expected}，实际{res2.json()['points']}"

            # 验证只有1条bonus流水
            async with async_session() as db:
                txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "bonus")
                )).scalars().all()
                assert len(txs) == 1, f"期望1条bonus流水，实际{len(txs)}条（重复赠送了）"
        finally:
            if user_id:
                async with async_session() as db:
                    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
                    await db.execute(delete(User).where(User.id == user_id))
                    await db.execute(delete(BonusPhone).where(BonusPhone.phone == phone))
                    await db.commit()
                await engine.dispose()

    _run(run())


def test_non_bonus_phone_gets_new_user_bonus():
    """非白名单新用户注册自动赠送240积分"""
    async def run():
        from app.skills.auth.sms_auth_skill import SmsCodeCache
        from app.config import settings

        phone = _next_phone()

        SmsCodeCache.set(phone, "111111")

        user_id = None
        try:
            async with _client() as client:
                res = await client.post("/api/auth/login", json={"phone": phone, "code": "111111"})
                assert res.status_code == 200, res.text
                assert res.json()["points"] == settings.NEW_USER_BONUS_POINTS, \
                    f"新用户积分应为{settings.NEW_USER_BONUS_POINTS}，实际{res.json()['points']}"
                user_id = res.json()["user_id"]

            async with async_session() as db:
                txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "bonus")
                )).scalars().all()
                assert len(txs) == 0, f"非白名单用户不应有bonus流水，实际{len(txs)}条"
                new_txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "new_user_bonus")
                )).scalars().all()
                assert len(new_txs) == 1, f"期望1条new_user_bonus流水，实际{len(new_txs)}条"
        finally:
            if user_id:
                async with async_session() as db:
                    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
                    await db.execute(delete(User).where(User.id == user_id))
                    await db.commit()
                await engine.dispose()

    _run(run())


def test_bonus_phone_removed_from_list_no_bonus():
    """手机号从内测名单移除后，仍获得新用户赠送但无白名单赠送"""
    async def run():
        from app.models.bonus_phone import BonusPhone
        from app.skills.auth.sms_auth_skill import SmsCodeCache
        from app.config import settings

        phone = _next_phone()

        # 先加入再移除，模拟名单变更
        async with async_session() as db:
            db.add(BonusPhone(phone=phone, points=1000))
            await db.commit()
            await db.execute(delete(BonusPhone).where(BonusPhone.phone == phone))
            await db.commit()

        SmsCodeCache.set(phone, "111111")

        user_id = None
        try:
            async with _client() as client:
                res = await client.post("/api/auth/login", json={"phone": phone, "code": "111111"})
                assert res.status_code == 200
                assert res.json()["points"] == settings.NEW_USER_BONUS_POINTS, \
                    f"名单移除后应仅有新用户赠送{settings.NEW_USER_BONUS_POINTS}，实际{res.json()['points']}"
                user_id = res.json()["user_id"]

            async with async_session() as db:
                txs = (await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id, Transaction.biz_type == "bonus")
                )).scalars().all()
                assert len(txs) == 0
        finally:
            if user_id:
                async with async_session() as db:
                    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
                    await db.execute(delete(User).where(User.id == user_id))
                    await db.commit()
                await engine.dispose()

    _run(run())
