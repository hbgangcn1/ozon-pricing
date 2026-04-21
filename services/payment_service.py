import logging
import time
import uuid
from typing import Literal, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.order import PaymentOrder
from models.user import User

logger = logging.getLogger(__name__)


class WechatNotifyError(Exception):
    """Base for WeChat notify processing errors."""


class DuplicateWechatNotifyError(WechatNotifyError):
    """Genuine duplicate (same txid)."""


class SuspiciousWechatNotifyError(WechatNotifyError):
    """Validation failure / potential replay / inconsistent state."""


def _extract_plan_code(description: str) -> str:
    if "\u6548\u7387\u7248" in description:
        return "efficiency"
    elif "\u4e13\u4e1a\u7248" in description:
        return "professional"
    elif "\u4f01\u4e1a\u7248" in description:
        return "enterprise"
    return "efficiency"


def _parse_duration(duration: str) -> int:
    text = (duration or "").lower()
    if "\u5e74" in text or "year" in text:
        return 365
    if "\u6708" in text or "month" in text:
        return 30
    return 30


def _redact_txid(transaction_id: Optional[str]) -> str:
    if not transaction_id:
        return "<empty>"
    return f"***{transaction_id[-6:]}"


class PaymentService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def apply_wechat_payment_success(
        self,
        *,
        out_trade_no: str,
        transaction_id: str,
        amount_total: int,
        currency: str,
        appid: str | None,
        mchid: str | None,
        raw_notify: dict,
    ) -> Literal["processed", "duplicate"]:
        """Use CAS update + same-txid classification to stop concurrent
        WeChat retries from double-crediting the same order.
        """
        _ = raw_notify
        self._validate_wechat_notify_identity(currency, appid, mchid)

        stmt = (
            update(PaymentOrder)
            .where(
                PaymentOrder.order_id == out_trade_no,
                PaymentOrder.status.in_(["PENDING", "PAID"]),
                PaymentOrder.wechat_transaction_id.is_(None),
            )
            .values(
                status="SUCCESS",
                wechat_transaction_id=transaction_id,
                updated_at=int(time.time()),
            )
            .returning(
                PaymentOrder.id,
                PaymentOrder.user_id,
                PaymentOrder.amount,
                PaymentOrder.description,
                PaymentOrder.duration,
            )
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return await self._classify_wechat_cas_miss(
                out_trade_no=out_trade_no,
                transaction_id=transaction_id,
            )

        if row.amount != amount_total:
            logger.error(
                "wechat notify amount mismatch: order=%s stored=%s notify=%s",
                out_trade_no,
                row.amount,
                amount_total,
            )
            raise SuspiciousWechatNotifyError(
                f"amount mismatch: order={row.amount} notify={amount_total}"
            )

        user = await self._session.get(User, row.user_id)
        if not user:
            logger.error(
                "wechat notify user missing: order=%s user_id=%s",
                out_trade_no,
                row.user_id,
            )
            raise SuspiciousWechatNotifyError(
                f"user not found: {row.user_id}"
            )

        current_time = int(time.time())
        plan_code = _extract_plan_code(row.description or "")
        duration_days = _parse_duration(row.duration or "\u6708")
        expiry = current_time + duration_days * 86400

        user.subscription_type = plan_code
        user.user_type = plan_code
        user.subscription_expires = expiry
        user.subscription_start = current_time
        user.remaining_calculations = -1
        logger.info(
            "wechat notify processed: order=%s user=%s plan=%s",
            out_trade_no,
            row.user_id,
            plan_code,
        )
        return "processed"

    async def handle_payment_success(self, order_id: str) -> None:
        stmt = select(PaymentOrder).where(
            PaymentOrder.order_id == order_id,
        )
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError(f"\u8ba2\u5355\u4e0d\u5b58\u5728: {order_id}")

        if order.status == "SUCCESS":
            logger.info("订单已处理，跳过: %s", order_id)
            return

        current_time = int(time.time())
        plan_code = _extract_plan_code(order.description or "")
        duration_days = _parse_duration(order.duration or "\u6708")
        expiry = current_time + duration_days * 86400

        user = await self._session.get(User, order.user_id)
        if not user:
            raise ValueError(f"用户不存在: user_id={order.user_id}")

        order.status = "SUCCESS"
        order.updated_at = current_time
        user.subscription_type = plan_code
        user.user_type = plan_code
        user.subscription_expires = expiry
        user.subscription_start = current_time
        user.remaining_calculations = -1
        await self._session.commit()
        logger.info(
            "支付成功: order=%s user=%d plan=%s expires=%d",
            order_id, order.user_id, plan_code, expiry,
        )

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

    async def _classify_wechat_cas_miss(
        self,
        *,
        out_trade_no: str,
        transaction_id: str,
    ) -> Literal["duplicate"]:
        existing = await self.get_order(out_trade_no)
        if existing is None:
            logger.error("wechat notify order missing: order=%s", out_trade_no)
            raise SuspiciousWechatNotifyError(
                f"order not found: {out_trade_no}"
            )
        if (
            existing.status == "SUCCESS"
            and existing.wechat_transaction_id == transaction_id
        ):
            logger.warning(
                "wechat notify duplicate (same txid): order=%s txid=%s",
                out_trade_no,
                _redact_txid(transaction_id),
            )
            return "duplicate"
        if existing.status == "SUCCESS":
            logger.error(
                "wechat notify txid conflict: order=%s stored=%s incoming=%s",
                out_trade_no,
                _redact_txid(existing.wechat_transaction_id),
                _redact_txid(transaction_id),
            )
            raise SuspiciousWechatNotifyError(
                "txid conflict on already-paid order"
            )
        logger.warning(
            "wechat notify on non-pending order: order=%s status=%s",
            out_trade_no,
            existing.status,
        )
        raise SuspiciousWechatNotifyError(
            f"order in non-pending state: {existing.status}"
        )

    @staticmethod
    def _validate_wechat_notify_identity(
        currency: str,
        appid: str | None,
        mchid: str | None,
    ) -> None:
        if currency != "CNY":
            logger.error("wechat notify currency mismatch: %s", currency)
            raise SuspiciousWechatNotifyError(
                f"currency mismatch: {currency}"
            )

        try:
            from wechat_pay_config import wechat_config
        except ImportError:
            logger.warning(
                "wechat_pay_config import failed; skipping appid/mchid checks"
            )
            return

        if wechat_config.app_id and appid != wechat_config.app_id:
            logger.error("wechat notify appid mismatch")
            raise SuspiciousWechatNotifyError("appid mismatch")
        if wechat_config.mch_id and mchid != wechat_config.mch_id:
            logger.error("wechat notify mchid mismatch")
            raise SuspiciousWechatNotifyError("mchid mismatch")
