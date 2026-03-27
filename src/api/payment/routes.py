"""支付回调接口。"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import config
from src.database import get_db
from src.services.payment import PaymentService

router = APIRouter(prefix="/api/payment", tags=["Payment"])
CALLBACK_TOKEN_HEADER = "x-payment-callback-token"
CALLBACK_SIGNATURE_HEADER = "x-payment-callback-signature"


class PaymentCallbackPayload(BaseModel):
    callback_key: str = Field(..., min_length=1, max_length=128)
    order_no: str | None = Field(default=None, max_length=64)
    gateway_order_id: str | None = Field(default=None, max_length=128)
    amount_usd: float = Field(..., gt=0, allow_inf_nan=False)
    pay_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    pay_currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    payload: dict[str, Any] | None = None


def _verify_callback_request_auth(request: Request) -> None:
    expected_token = config.payment_callback_secret
    if not expected_token:
        raise HTTPException(status_code=503, detail="payment callback is disabled")

    provided_token = (request.headers.get(CALLBACK_TOKEN_HEADER) or "").strip()
    if not provided_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=401, detail="invalid payment callback token")


async def _process_callback(
    *,
    payment_method: str,
    request: Request,
    payload: PaymentCallbackPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not payment_method:
        raise HTTPException(status_code=400, detail="payment_method is required")
    _verify_callback_request_auth(request)
    callback_signature = (request.headers.get(CALLBACK_SIGNATURE_HEADER) or "").strip()
    if not callback_signature:
        raise HTTPException(status_code=401, detail="missing payment callback signature")

    try:
        callback_payload = payload.payload if payload.payload is not None else payload.model_dump()
        result = PaymentService.handle_callback(
            db,
            payment_method=payment_method,
            callback_key=payload.callback_key,
            payload=callback_payload,
            callback_signature=callback_signature,
            callback_secret=config.payment_callback_secret,
            order_no=payload.order_no,
            gateway_order_id=payload.gateway_order_id,
            amount_usd=payload.amount_usd,
            pay_amount=payload.pay_amount,
            pay_currency=payload.pay_currency,
            exchange_rate=payload.exchange_rate,
        )
        db.commit()
        return {
            **result,
            "payment_method": payment_method,
            "request_path": request.url.path,
        }
    except Exception as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/callback/alipay/webhook")
async def handle_alipay_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    from fastapi.responses import PlainTextResponse
    import logging
    
    try:
        # Extract x-www-form-urlencoded data provided by Alipay
        form_data = await request.form()
        payload = dict(form_data)
        
        from src.services.payment.gateway.alipay import AlipayGateway
        gateway = AlipayGateway()
        is_valid = gateway.verify_callback_payload(
            payload=payload,
            callback_signature=None,
            callback_secret=None
        )
        
        if not is_valid:
            logging.warning("Alipay webhook signature validation failed.")
            return PlainTextResponse("failure")
        
        trade_status = payload.get("trade_status")
        if trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
            # Need to fetch the order to supply `amount_usd` as expected by internal handle_callback
            order_no = payload.get("out_trade_no")
            order = PaymentService.get_order(db, order_no=order_no, gateway_order_id=None)
            
            if order:
                # Use raw amount 1:1 for CNY
                expected_cny = float(order.amount_usd)
                actual_cny = float(payload.get("total_amount", 0))
                
                # Verify amount within sensible precision
                if abs(expected_cny - actual_cny) > 0.05:
                    logging.error(f"Alipay amount mismatch: Expected {expected_cny}, got {actual_cny}")
                    return PlainTextResponse("failure")

                PaymentService.handle_callback(
                    db,
                    payment_method="alipay",
                    callback_key=f"alipay_{payload.get('notify_id', secrets.token_hex(8))}",
                    payload=payload,
                    callback_signature=payload.get("sign"),
                    callback_secret=None, # Already verified via SDK
                    order_no=order.order_no,
                    gateway_order_id=payload.get("trade_no"),
                    amount_usd=order.amount_usd,
                    pay_amount=actual_cny,
                    pay_currency="CNY",
                    exchange_rate=1.0,
                )
                db.commit()
            else:
                logging.error(f"Alipay webhook: Order {order_no} not found")
                return PlainTextResponse("failure")
            
        return PlainTextResponse("success")
        
    except Exception as e:
        db.rollback()
        logging.error(f"Alipay webhook error: {e}")
        return PlainTextResponse("failure")


@router.post("/callback/wechat")
async def handle_wechat_callback(
    request: Request,
    payload: PaymentCallbackPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await _process_callback(
        payment_method="wechat",
        request=request,
        payload=payload,
        db=db,
    )


@router.post("/callback/{payment_method}")
async def handle_payment_callback(
    payment_method: str,
    request: Request,
    payload: PaymentCallbackPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await _process_callback(
        payment_method=payment_method,
        request=request,
        payload=payload,
        db=db,
    )