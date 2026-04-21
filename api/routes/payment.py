import asyncio
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id
from database import get_db
from db.config import is_registration_open
from db.plans import get_plan_by_code, get_plan_price
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


def _is_wechat_response_signature_error(exc: Exception) -> bool:
    if wechat_pay_v3_api_module is None:
        return False
    error_cls = getattr(wechat_pay_v3_api_module, "WechatResponseSignatureError", None)
    return bool(error_cls) and isinstance(exc, error_cls)


async def _reconcile_order_after_signature_failure(
    order_id: str,
    svc: PaymentService,
) -> None:
    if wechat_pay_v3 is None:
        return
    logger.error("微信下单响应验签失败，开始对账: %s", order_id)
    query_result = await asyncio.to_thread(wechat_pay_v3.query_order, order_id)
    if query_result.get("success") and query_result.get("trade_state") == "SUCCESS":
        try:
            await svc.handle_payment_success(order_id)
        except Exception:
            logger.error("验签失败后的对账补账失败: %s", order_id, exc_info=True)


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
            await _reconcile_order_after_signature_failure(order.order_id, svc)
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
    svc: PaymentService = Depends(get_payment_service),
):
    body = await request.body()
    if not _wechat_available or wechat_pay_v3 is None:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "签名验证失败"},
        )

    result = await asyncio.to_thread(wechat_pay_v3.process_notify, dict(request.headers), body)
    if not result.get("success"):
        message = result.get("message", "通知处理失败")
        logger.warning("微信支付通知处理失败: %s", message)
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": message},
        )

    data = result.get("data")
    if not isinstance(data, dict):
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "通知数据缺失"},
        )

    try:
        out_trade_no = data["out_trade_no"]
        transaction_id = data["transaction_id"]
        amount = data["amount"]
        amount_total = amount["total"]
        currency = amount["currency"]
    except (KeyError, TypeError) as exc:
        logger.warning("微信支付通知缺少必要字段: %s", exc)
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "通知字段缺失"},
        )

    appid = data.get("appid")
    mchid = data.get("mchid")

    try:
        await svc.apply_wechat_payment_success(
            out_trade_no=out_trade_no,
            transaction_id=transaction_id,
            amount_total=amount_total,
            currency=currency,
            appid=appid,
            mchid=mchid,
            raw_notify=data,
        )
        return NotifyResponse(code="SUCCESS", message="成功")
    except SuspiciousWechatNotifyError as exc:
        logger.error("wechat notify rejected as suspicious: %s", exc)
        return NotifyResponse(code="SUCCESS", message="成功")
    except Exception:
        logger.error("wechat notify processing failed unexpectedly", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": "系统错误"},
        )


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
    if trade_state == "SUCCESS":
        try:
            await svc.handle_payment_success(order_id)
        except Exception:
            logger.error("查询时处理支付成功失败: %s", order_id, exc_info=True)

    return PaymentStatusResponse(
        order_id=order_id,
        status=order.status or "PENDING",
        trade_state=trade_state,
    )
