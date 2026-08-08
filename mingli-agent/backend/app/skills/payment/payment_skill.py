"""
付费/计费 Skill
封装积分管理、订单创建、支付回调处理
"""
from typing import Any, Dict, Optional
from datetime import datetime

from app.skills import BaseSkill, SkillMetadata, SkillResult


class PaymentSkill(BaseSkill):
    """付费计费技能"""
    
    POINTS_PACKAGES = {
        40: 4.0,
        80: 8.0,
        120: 12.0,
        160: 16.0,
        200: 20.0,
    }
    
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="payment",
            display_name="积分支付",
            description="积分充值、消费、订单管理",
            version="2.0.0",
            category="payment",
        )
    
    async def execute(self, action: str = "check_points", **kwargs) -> SkillResult:
        """
        action: check_points | deduct_points | add_points | create_order | get_transactions
        """
        from app.services.payment_service import (
            check_points, deduct_points, add_points,
            create_order, get_transactions, get_user_points
        )
        
        try:
            if action == "check_points":
                result = await check_points(kwargs["session"], kwargs["user_id"], kwargs["required"])
                return SkillResult(success=result, data={"sufficient": result}, skill_name=self.metadata().name)
            
            elif action == "deduct_points":
                await deduct_points(
                    kwargs["session"], kwargs["user_id"],
                    kwargs["points"], kwargs.get("description", ""), kwargs.get("order_id")
                )
                new_balance = await get_user_points(kwargs["session"], kwargs["user_id"])
                return SkillResult(success=True, data={"balance": new_balance}, skill_name=self.metadata().name)
            
            elif action == "add_points":
                await add_points(
                    kwargs["session"], kwargs["user_id"],
                    kwargs["points"], kwargs.get("order_id"), kwargs.get("description", "充值")
                )
                new_balance = await get_user_points(kwargs["session"], kwargs["user_id"])
                return SkillResult(success=True, data={"balance": new_balance}, skill_name=self.metadata().name)
            
            elif action == "create_order":
                order = await create_order(
                    kwargs["session"], kwargs["user_id"],
                    kwargs["points"], kwargs["pay_method"]
                )
                return SkillResult(success=True, data={"order_id": order.id, "amount": order.amount}, skill_name=self.metadata().name)
            
            elif action == "get_transactions":
                transactions = await get_transactions(kwargs["session"], kwargs["user_id"])
                return SkillResult(
                    success=True,
                    data={"transactions": [{"id": t.id, "type": t.type, "points": t.points, "description": t.description, "created_at": str(t.created_at)} for t in transactions]},
                    skill_name=self.metadata().name
                )
            
            else:
                return SkillResult(success=False, error=f"未知操作: {action}", skill_name=self.metadata().name)
        except Exception as e:
            return SkillResult(success=False, error=str(e), skill_name=self.metadata().name)