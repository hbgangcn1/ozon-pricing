import asyncio
import json
import logging
import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id
from database import get_db
from db.config import is_registration_open
from db.plans import get_plan_by_code, get_plan_price
from models.log import WechatNotifyAuditLog
from services.payment_service import (
    PaymentService,
    SuspiciousWechatNotifyError,
)

try:
    import wechat_pay_v3_api as wechat_pay_v3_api_module

    wechat_pay_v3 = wechat_pay_v3_api_module.wechat_pay_v3
    _wechat_available = True
except ImportError:
    wechat_pay_v3_api_module = None
    wechat_pay_v3 = None
    _wechat_available = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payment"])
WECHAT_NOTIFY_ACK = {"code": "SUCCESS", "message": "OK"}
MAX_AUDIT_RAW_BODY_LENGTH = 8192


def _is_production() -> bool:
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT")
    if app_env:
        return app_env.lower() == "production"
    return os.getenv("PRODUCTION_MODE", "").lower() == "true"


def _is_wechat_response_signature_error(exc: Exception) -> bool:
    if wechat_pay_v3_api_module is None:
        return False
    error_cls = getattr(wechat_pay_v3_api_module, "WechatResponseSignatureError", None)
    return bool(error_cls) and isinstance(exc, error_cls)


def _is_wechat_pay_signature_error(exc: Exception) -> bool:
    if wechat_pay_v3_api_module is None:
        return False
    error_cls = getattr(wechat_pay_v3_api_module, "WeChatPayError", None)
    return bool(error_cls) and isinstance(exc, error_cls) and (
        str(exc) == "signature verification failed"
    )


async def _reconcile_order_after_signature_failure(
    order_id: str,
    svc: PaymentService,
) -> bool:
    if wechat_pay_v3 is None:
        return False
    logger.error("微信下单响应验签失败，开始对账: %s", order_id)
    query_result = await asyncio.to_thread(wechat_pay_v3.query_order, order_id)
    if query_result.get("success") and query_result.get("trade_state") == "SUCCESS":
        return await _apply_wechat_query_success(
            order_id,
            query_result,
            svc,
            "验签失败后的对账补账失败",
        )
    return False


async def get_payment_service(
    session: AsyncSession = Depends(get_db),
) -> PaymentService:
    return PaymentService(session)


class CreatePaymentRequest(BaseModel):
    plan_code: str
    billing_cycle: Literal["month", "year"]
    amount: float


class CreatePaymentResponse(BaseModel):
    order_id: str
    code_url: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    order_id: str
    status: str
    trade_state: Optional[str] = None


class NotifyResponse(BaseModel):
    code: str
    message: str


def _success_ack() -> NotifyResponse:
    return NotifyResponse(**WECHAT_NOTIFY_ACK)


def _decode_audit_raw_body(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    return text[:MAX_AUDIT_RAW_BODY_LENGTH]


def _parse_raw_notify_identifiers(body: bytes) -> tuple[str | None, str | None]:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    out_trade_no = data.get("out_trade_no")
    transaction_id = data.get("transaction_id")
    return _safe_identifier(out_trade_no), _safe_identifier(transaction_id)


def _safe_identifier(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:64]


async def _write_notify_audit_log(
    session: AsyncSession,
    *,
    body: bytes,
    verified: bool,
    response_code: str,
    response_message: str,
) -> None:
    out_trade_no, transaction_id = _parse_raw_notify_identifiers(body)
    session.add(
        WechatNotifyAuditLog(
            out_trade_no=out_trade_no,
            transaction_id=transaction_id,
            signature_verified=verified,
            raw_body=_decode_audit_raw_body(body),
            response_code=response_code,
            response_message=response_message[:256],
        )
    )
    await session.flush()


def _extract_wechat_success_fields(data: dict) -> tuple[str, str, int, str]:
    out_trade_no = data["out_trade_no"]
    transaction_id = data["transaction_id"]
    amount = data["amount"]
    amount_total = amount["total"]
    currency = amount["currency"]
    return out_trade_no, transaction_id, amount_total, currency


async def _apply_wechat_query_success(
    order_id: str,
    result: dict,
    svc: PaymentService,
    log_message: str,
) -> bool:
    data = result.get("data")
    if not isinstance(data, dict):
        logger.warning("微信订单查询成功但缺少交易数据: %s", order_id)
        return False
    try:
        out_trade_no, transaction_id, amount_total, currency = (
            _extract_wechat_success_fields(data)
        )
    except (KeyError, TypeError) as exc:
        logger.warning("微信订单查询成功但缺少必要字段: %s", exc)
        return False
    if out_trade_no != order_id:
        logger.error(
            "微信订单查询结果订单号不匹配: expected=%s actual=%s",
            order_id,
            out_trade_no,
        )
        return False

    try:
        await svc.apply_wechat_payment_success(
            out_trade_no=out_trade_no,
            transaction_id=transaction_id,
            amount_total=amount_total,
            currency=currency,
            appid=data.get("appid"),
            mchid=data.get("mchid"),
            raw_notify=data,
        )
        return True
    except SuspiciousWechatNotifyError as exc:
        session = getattr(svc, "_session", None)
        if session is not None:
            await session.rollback()
        logger.error("%s: %s", log_message, exc)
        return False
    except Exception:
        session = getattr(svc, "_session", None)
        if session is not None:
            await session.rollback()
        logger.error("%s: %s", log_message, order_id, exc_info=True)
        return False


def _to_cents(amount: float) -> int:
    return int(round(amount * 100))


@router.post("/create", response_model=CreatePaymentResponse)
async def create_payment(
    req: CreatePaymentRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
    svc: PaymentService = Depends(get_payment_service),
):
    is_open = await is_registration_open(session)
    use_test_price = not is_open
    plan_price = await get_plan_price(
        session, req.plan_code, req.billing_cycle, use_test_price=use_test_price
    )
    if plan_price is None or _to_cents(plan_price) != _to_cents(req.amount):
        return JSONResponse(
            status_code=400,
            content={"error": "amount_mismatch"},
        )

    plan = await get_plan_by_code(session, req.plan_code)
    plan_name = plan.get("plan_name", req.plan_code) if plan else req.plan_code
    description = f"订阅{plan_name}"
    amount_cents = _to_cents(req.amount)

    order = await svc.create_order(
        user_id=user_id,
        amount_cents=amount_cents,
        description=description,
        billing_cycle=req.billing_cycle,
        order_type=req.plan_code,
    )

    if not _wechat_available or wechat_pay_v3 is None:
        order.status = "FAILED"
        return JSONResponse(
            status_code=502,
            content={
                "error": "wechat_error",
                "message": "微信支付模块不可用",
            },
        )

    try:
        result = await asyncio.to_thread(
            wechat_pay_v3.create_native_order,
            order.order_id,
            amount_cents,
            order.description,
        )
    except Exception as exc:
        if _is_wechat_response_signature_error(exc):
            credited = await _reconcile_order_after_signature_failure(
                order.order_id, svc
            )
            if credited:
                await session.commit()
            raise HTTPException(
                status_code=502,
                detail="微信支付订单创建状态未确认，请重试",
            ) from exc
        raise
    if not result.get("success"):
        order.status = "FAILED"
        return JSONResponse(
            status_code=502,
            content={
                "error": "wechat_error",
                "message": result.get("message", "微信下单失败"),
            },
        )

    return CreatePaymentResponse(
        order_id=order.order_id,
        code_url=result.get("code_url"),
    )


@router.post("/notify", response_model=NotifyResponse)
async def payment_notify(
    request: Request,
    session: AsyncSession = Depends(get_db),
    svc: PaymentService = Depends(get_payment_service),
):
    body = await request.body()
    if not _wechat_available or wechat_pay_v3 is None:
        is_prod = _is_production()
        allow_success = not is_prod or os.getenv("E2E_TEST") == "1"
        response_code = "SUCCESS" if allow_success else "FAIL"
        response_message = (
            "OK"
            if allow_success
            else "微信支付模块不可用 (生产环境拒绝 ACK 以触发微信重试)"
        )
        await _write_notify_audit_log(
            session,
            body=body,
            verified=False,
            response_code=response_code,
            response_message=response_message,
        )
        if allow_success:
            logger.warning("微信支付模块不可用，通知仅审计并返回成功确认")
            return _success_ack()
        logger.error("微信支付模块不可用，生产环境返回 503 触发微信重试")
        return JSONResponse(
            status_code=503,
            content={"code": "FAIL", "message": "微信支付模块不可用"},
        )

    payload = None
    verified = True
    try:
        payload = await asyncio.to_thread(
            wechat_pay_v3.process_notify,
            dict(request.headers),
            body,
        )
    except Exception as exc:
        verified = False
        if _is_wechat_pay_signature_error(exc):
            logger.warning("微信支付通知签名验证失败，仅审计并返回成功确认")
        else:
            logger.warning("微信支付通知解析异常，仅审计并返回成功确认", exc_info=True)
    await _write_notify_audit_log(
        session,
        body=body,
        verified=verified,
        response_code="SUCCESS",
        response_message="OK",
    )

    if not isinstance(payload, dict):
        logger.warning("微信支付通知未验签或无有效交易载荷，仅写入审计日志")
        return _success_ack()

    try:
        out_trade_no, transaction_id, amount_total, currency = (
            _extract_wechat_success_fields(payload)
        )
    except (KeyError, TypeError) as exc:
        logger.warning("微信支付通知缺少必要字段: %s", exc)
        return _success_ack()

    appid = payload.get("appid")
    mchid = payload.get("mchid")

    try:
        await svc.apply_wechat_payment_success(
            out_trade_no=out_trade_no,
            transaction_id=transaction_id,
            amount_total=amount_total,
            currency=currency,
            appid=appid,
            mchid=mchid,
            raw_notify=payload,
        )
        return _success_ack()
    except SuspiciousWechatNotifyError as exc:
        # Suspicious 异常时 CAS UPDATE 已写入但校验失败：必须显式 rollback
        # 以撤销脏状态；随后重写审计行，仍返回 SUCCESS 阻止微信重试风暴。
        await session.rollback()
        await _write_notify_audit_log(
            session,
            body=body,
            verified=verified,
            response_code="SUCCESS",
            response_message="OK",
        )
        logger.error("wechat notify rejected as suspicious: %s", exc)
        return _success_ack()
    except Exception:
        await session.rollback()
        await _write_notify_audit_log(
            session,
            body=body,
            verified=verified,
            response_code="FAIL",
            response_message="processing failed",
        )
        logger.error("wechat notify processing failed unexpectedly", exc_info=True)
        return JSONResponse({"code": "FAIL", "message": "处理失败，请重试"}, 503)


@router.get("/{order_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(
    order_id: str,
    user_id: int = Depends(get_current_user_id),
    svc: PaymentService = Depends(get_payment_service),
):
    order = await svc.get_user_order(order_id, user_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.status != "PENDING":
        return PaymentStatusResponse(
            order_id=order_id,
            status=order.status or "PENDING",
            trade_state=order.status if order.status == "SUCCESS" else None,
        )

    if not _wechat_available or wechat_pay_v3 is None:
        return PaymentStatusResponse(
            order_id=order_id,
            status=order.status or "PENDING",
        )

    result = await asyncio.to_thread(wechat_pay_v3.query_order, order_id)
    trade_state = result.get("trade_state") if result.get("success") else None
    credited = False
    original_status = order.status or "PENDING"
    if trade_state == "SUCCESS":
        credited = await _apply_wechat_query_success(
            order_id,
            result,
            svc,
            "查询时处理支付成功失败",
        )
        if credited:
            order.status = "SUCCESS"

    return PaymentStatusResponse(
        order_id=order_id,
        status="SUCCESS" if credited else original_status,
        trade_state=trade_state,
    )
