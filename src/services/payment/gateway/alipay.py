from __future__ import annotations

import logging
from typing import Any

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.util.SignatureUtils import verify_with_rsa

from src.config.settings import config
from src.services.payment.gateway.base import PaymentGateway


class AlipayGateway(PaymentGateway):
    payment_method = "alipay"
    display_name = "支付宝"

    def _get_alipay_client(self) -> DefaultAlipayClient:
        if not config.alipay_app_id or not config.alipay_private_key or not config.alipay_public_key:
            raise ValueError("Alipay configuration is missing in environment variables.")
        
        # Ensure newlines are restored if they were parsed as literal \n from env
        private_key = config.alipay_private_key.replace("\\n", "\n")
        public_key = config.alipay_public_key.replace("\\n", "\n")

        client_config = AlipayClientConfig()
        client_config.server_url = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
        #  if config.alipay_debug else "https://openapi.alipay.com/gateway.do"
        client_config.app_id = config.alipay_app_id
        client_config.app_private_key = private_key
        client_config.alipay_public_key = public_key
        client_config.charset = "utf-8"
        client_config.sign_type = "RSA2"
        #定义DefaultAlipayClient对象后，alipay_client_config不得修改
        return DefaultAlipayClient(alipay_client_config=client_config)

    def create_checkout_payload(self, *, order: Any) -> dict[str, Any]:
        gateway_order_id = getattr(order, "gateway_order_id", None) or getattr(order, "order_no")
        client = self._get_alipay_client()
        
        # Use raw order amount 1:1 for CNY
        cny_amount = float(getattr(order, "amount_usd", 0))
        amount_str = f"{cny_amount:.2f}"
        
        # domain = f"http://{config.host}:{config.port}"
        # notify_url = f"{domain}/api/payment/callback/alipay/webhook"

        domain = 'https://pay.leeda.top'
        notify_url = f"{domain}/api/payment/callback/alipay/webhook"

        # alipay.trade.pay
        model = AlipayTradePagePayModel()
        # 商户订单号，64个字符以内，由商家自主生成
        model.out_trade_no = getattr(order, "order_no")
        # 订单总金额，单位：元（精确到小数点后两位）
        model.total_amount = amount_str
        # 订单标题，用于在支付界面显示
        model.subject = f"Gravity TOKEN充值- {getattr(order, 'order_no')}"
        # 销售产品码，与支付宝签约的产品码名称。注：目前电脑支付场景下仅支持FAST_INSTANT_TRADE_PAY
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        # 支持前置模式和跳转模式。
        # 前置模式是将二维码前置到商户的订单确认页的模式。需要商户在自己的页面中以 iframe 方式请求支付宝页面。具体支持的枚举值有以下几种：
        # 0：订单码-简约前置模式，对应 iframe 宽度不能小于600px，高度不能小于300px；
        # 1：订单码-前置模式，对应iframe 宽度不能小于 300px，高度不能小于600px；
        # 3：订单码-迷你前置模式，对应 iframe 宽度不能小于 75px，高度不能小于75px；
        # 4：订单码-可定义宽度的嵌入式二维码，商户可根据需要设定二维码的大小。
        # 跳转模式下，用户的扫码界面是由支付宝生成的，不在商户的域名下。支持传入的枚举值有：
        # 2：订单码-跳转模式
        # model.qr_pay_mode = "0"

        request = AlipayTradePagePayRequest(biz_model=model)
        # 异步通知地址
        request.notify_url = notify_url
        # 同步跳转地址
        request.return_url = domain

        # Retrieve the page pay URL parameters formatted appropriately
        payment_url = client.page_execute(request, http_method="GET")

        print(payment_url)

        return {
            "gateway": self.payment_method,
            "display_name": self.display_name,
            "gateway_order_id": gateway_order_id,
            "payment_url": payment_url,
            "qr_code": None,
            "expires_at": getattr(order, "expires_at").isoformat() if getattr(order, "expires_at", None) else None,
        }

    def verify_callback_payload(
        self,
        *,
        payload: dict[str, Any] | None,
        callback_signature: str | None,
        callback_secret: str | None,
    ) -> bool:
        if not payload:
            return False
            
        data = dict(payload)
        signature = data.pop("sign", None)
        data.pop("sign_type", None) # Excluded from string to sign
        
        if not signature:
            return False
            
        try:
            public_key = config.alipay_public_key.replace("\\n", "\n")
            # Build string to sign: sort keys, filter empty/None, join with & and =
            sorted_keys = sorted([(str(k), str(v)) for k, v in data.items() if v is not None and v != ""])
            message = "&".join(f"{k}={v}" for k, v in sorted_keys)
            
            return verify_with_rsa(public_key.encode("utf-8"), message.encode("utf-8"), signature)
        except Exception as e:
            logging.error(f"Alipay signature verification failed: {e}")
            return False

