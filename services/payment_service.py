import logging
import time
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order import PaymentOrder
from models.user import User

logger = logging.getLogger(__name__)


def _extract_plan_code(description: str) -> str:
    if "\u6548\u7387\u7248" in description:
        return "efficiency"
    elif "\u4e13\u4e1a\u7248" in description:
        return "professional"
    elif "\u4f01\u4e1a\u7248" in description:
        return "enterprise"
    return "efficiency"


def _parse_duration(duration: str) -> int:
    if "\u5e74" in duration:
        return 365
    elif "\u6708" in duration:
        return 30
    return 30


class PaymentService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def handle_payment_success(self, order_id: str) -> None:
        stmt = select(PaymentOrder).where(
            PaymentOrder.order_id == order_id,
        )
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError(f"\u8ba2\u5355\u4e0d\u5b58\u5728: {order_id}")

        if order.status == "SUCCESS":
            return

        current_time = int(time.time())
        order.status = "SUCCESS"
        order.updated_at = current_time

        plan_code = _extract_plan_code(order.description or "")
        duration_days = _parse_duration(order.duration or "\u6708")
        expiry = current_time + duration_days * 86400

        user = await self._session.get(User, order.user_id)
        if user:
            user.subscription_type = plan_code
            user.subscription_expires = expiry
            user.remaining_calculations = -1

    async def update_order_status(
        self,
        order_id: str,
        status: str,
    ) -> None:
        stmt = select(PaymentOrder).where(
            PaymentOrder.order_id == order_id,
        )
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if order:
            order.status = status
            order.updated_at = int(time.time())

    async def create_order(
        self,
        user_id: int,
        amount_cents: int,
        description: str,
        billing_cycle: str,
        order_type: str,
    ) -> PaymentOrder:
        order = PaymentOrder(
            order_id=uuid.uuid4().hex,
            user_id=user_id,
            amount=amount_cents,
            description=description,
            duration=billing_cycle,
            status="PENDING",
            order_type=order_type,
            created_at=int(time.time()),
        )
        self._session.add(order)
        await self._session.flush()
        return order

    async def get_order(
        self,
        order_id: str,
    ) -> Optional[PaymentOrder]:
        stmt = select(PaymentOrder).where(
            PaymentOrder.order_id == order_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_order(
        self,
        order_id: str,
        user_id: int,
    ) -> Optional[PaymentOrder]:
        order = await self.get_order(order_id)
        if order is None or order.user_id != user_id:
            return None
        return order
