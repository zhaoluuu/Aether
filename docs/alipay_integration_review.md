# Alipay Integration Review

This document contains all the raw code changes made for the Alipay integration.

```diff
diff --git a/.env.example b/.env.example
index 46340fd4..f6e618c0 100644
--- a/.env.example
+++ b/.env.example
@@ -25,6 +25,17 @@ ENCRYPTION_KEY=change-this-to-another-secure-random-string
 # 建议使用 32+ 位随机字符串
 PAYMENT_CALLBACK_SECRET=change-this-to-a-secure-callback-secret
 
+# ==================== 支付宝支付配置 ====================
+# 应用ID
+ALIPAY_APP_ID=
+# 支付宝公钥（建议使用字符串，注意保留头尾BEGIN/END标识及换行）
+ALIPAY_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
+# 应用私钥
+ALIPAY_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
+# 是否使用沙箱环境（true为沙箱，false为生产）
+ALIPAY_DEBUG=true
+
+
 # 管理员账号（仅首次初始化时使用, 创建完成后可在系统内修改密码）
 ADMIN_EMAIL=admin@example.com
 ADMIN_USERNAME=admin
diff --git a/frontend/src/utils/walletDisplay.ts b/frontend/src/utils/walletDisplay.ts
index ece2eb0f..b9d2a2f9 100644
--- a/frontend/src/utils/walletDisplay.ts
+++ b/frontend/src/utils/walletDisplay.ts
@@ -16,8 +16,9 @@ export function formatWalletCurrency(
   const amount = Number(value ?? 0)
   return `$${amount.toFixed(decimals)}`
 }
+export type BadgeVariant = 'success' | 'warning' | 'default' | 'secondary' | 'destructive' | 'outline' | 'dark' | undefined;
 
-export function walletStatusBadge(status: string | null | undefined): string {
+export function walletStatusBadge(status: string | null | undefined): BadgeVariant {
   if (status === 'active') return 'success'
   if (status === 'suspended') return 'warning'
   if (status === 'closed') return 'destructive'
@@ -109,7 +110,7 @@ export function walletLinkTypeLabel(type: string | null | undefined): string {
   return labels[type] || '其他'
 }
 
-export function paymentStatusBadge(status: string | null | undefined): string {
+export function paymentStatusBadge(status: string | null | undefined): BadgeVariant {
   if (status === 'credited' || status === 'refunded') return 'success'
   if (status === 'paid' || status === 'refunding') return 'outline'
   if (status === 'pending') return 'secondary'
@@ -140,7 +141,7 @@ export function refundStatusLabel(status: string | null | undefined): string {
   return labels[status] || status
 }
 
-export function refundStatusBadge(status: string | null | undefined): string {
+export function refundStatusBadge(status: string | null | undefined): BadgeVariant {
   if (status === 'succeeded') return 'success'
   if (status === 'processing') return 'outline'
   if (status === 'pending_approval' || status === 'approved') return 'secondary'
@@ -160,7 +161,7 @@ export function callbackStatusLabel(status: string | null | undefined): string {
   return labels[status] || status
 }
 
-export function callbackStatusBadge(status: string | null | undefined): string {
+export function callbackStatusBadge(status: string | null | undefined): BadgeVariant {
   if (status === 'processed') return 'success'
   if (status === 'duplicate' || status === 'ignored') return 'secondary'
   if (status === 'invalid_signature' || status === 'error') return 'destructive'
diff --git a/frontend/src/views/user/WalletCenter.vue b/frontend/src/views/user/WalletCenter.vue
index 3fbf0050..0e0b0cfa 100644
--- a/frontend/src/views/user/WalletCenter.vue
+++ b/frontend/src/views/user/WalletCenter.vue
@@ -56,10 +56,9 @@
         </Card>
       </div>
 
-      <!-- TODO(wallet): 充值/退款用户主动操作入口暂未启用，待支付链路联调完成后再开放 -->
       <div
         v-if="ENABLE_WALLET_ACTION_FORMS"
-        class="grid grid-cols-1 xl:grid-cols-2 gap-4"
+        class="grid grid-cols-1 gap-4"
       >
         <Card class="p-5 space-y-4">
           <div class="flex items-center justify-between">
@@ -144,7 +143,8 @@
           </div>
         </Card>
 
-        <Card class="p-5 space-y-4">
+        <!-- TODO: 暂时屏蔽退款入口 -->
+        <Card v-if="false" class="p-5 space-y-4">
           <div class="flex items-center justify-between">
             <h3 class="text-base font-semibold">
               申请退款
@@ -594,8 +594,7 @@ import {
 
 const { success, error: showError } = useToast()
 
-// TODO(wallet): 充值和退款前台入口尚未正式启用；联调完成后改为 true 即可恢复显示。
-const ENABLE_WALLET_ACTION_FORMS = false
+const ENABLE_WALLET_ACTION_FORMS = true
 
 const loadingInitial = ref(true)
 const loadingTransactions = ref(false)
@@ -813,7 +812,7 @@ async function submitRefund() {
 
 function buildRefundIdempotencyKey(): string {
   if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
-    return crypto.randomUUID().replaceAll('-', '')
+    return crypto.randomUUID().replace(/-/g, '')
   }
   return `${Date.now()}_${Math.random().toString(16).slice(2, 10)}`
 }
diff --git a/src/api/payment/routes.py b/src/api/payment/routes.py
index d9569bc1..0305c3b0 100644
--- a/src/api/payment/routes.py
+++ b/src/api/payment/routes.py
@@ -82,18 +82,71 @@ async def _process_callback(
         raise HTTPException(status_code=400, detail=str(exc)) from exc
 
 
-@router.post("/callback/alipay")
-async def handle_alipay_callback(
+@router.post("/callback/alipay/webhook")
+async def handle_alipay_webhook(
     request: Request,
-    payload: PaymentCallbackPayload,
     db: Session = Depends(get_db),
-) -> dict[str, Any]:
-    return await _process_callback(
-        payment_method="alipay",
-        request=request,
-        payload=payload,
-        db=db,
-    )
+) -> Any:
+    from fastapi.responses import PlainTextResponse
+    import logging
+    
+    try:
+        # Extract x-www-form-urlencoded data provided by Alipay
+        form_data = await request.form()
+        payload = dict(form_data)
+        
+        from src.services.payment.gateway.alipay import AlipayGateway
+        gateway = AlipayGateway()
+        is_valid = gateway.verify_callback_payload(
+            payload=payload,
+            callback_signature=None,
+            callback_secret=None
+        )
+        
+        if not is_valid:
+            logging.warning("Alipay webhook signature validation failed.")
+            return PlainTextResponse("failure")
+        
+        trade_status = payload.get("trade_status")
+        if trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
+            # Need to fetch the order to supply `amount_usd` as expected by internal handle_callback
+            order_no = payload.get("out_trade_no")
+            order = PaymentService.get_order(db, order_no=order_no, gateway_order_id=None)
+            
+            if order:
+                expected_cny = float(order.amount_usd) * 7.2
+                actual_cny = float(payload.get("total_amount", 0))
+                
+                # Verify amount within sensible precision
+                if abs(expected_cny - actual_cny) > 0.05:
+                    logging.error(f"Alipay amount mismatch: Expected {expected_cny}, got {actual_cny}")
+                    return PlainTextResponse("failure")
+
+                PaymentService.handle_callback(
+                    db,
+                    payment_method="alipay",
+                    callback_key=f"alipay_{payload.get('notify_id', secrets.token_hex(8))}",
+                    payload=payload,
+                    callback_signature=payload.get("sign"),
+                    callback_secret=None, # Already verified via SDK
+                    order_no=order.order_no,
+                    gateway_order_id=payload.get("trade_no"),
+                    amount_usd=order.amount_usd,
+                    pay_amount=actual_cny,
+                    pay_currency="CNY",
+                    exchange_rate=7.2,
+                )
+                db.commit()
+            else:
+                logging.error(f"Alipay webhook: Order {order_no} not found")
+                return PlainTextResponse("failure")
+            
+        return PlainTextResponse("success")
+        
+    except Exception as e:
+        db.rollback()
+        logging.error(f"Alipay webhook error: {e}")
+        return PlainTextResponse("failure")
 
 
 @router.post("/callback/wechat")
diff --git a/src/config/settings.py b/src/config/settings.py
index 8e273098..ce3c4e69 100644
--- a/src/config/settings.py
+++ b/src/config/settings.py
@@ -138,6 +138,12 @@ class Config:
         # 支付回调安全配置（公开回调入口必须携带该共享密钥）
         self.payment_callback_secret = os.getenv("PAYMENT_CALLBACK_SECRET", "").strip()
 
+        # Alipay 配置
+        self.alipay_app_id = os.getenv("ALIPAY_APP_ID", "").strip()
+        self.alipay_private_key = os.getenv("ALIPAY_PRIVATE_KEY", "").strip()
+        self.alipay_public_key = os.getenv("ALIPAY_PUBLIC_KEY", "").strip()
+        self.alipay_debug = os.getenv("ALIPAY_DEBUG", "true").lower() == "true"
+
         self.public_api_rate_limit = int(os.getenv("PUBLIC_API_RATE_LIMIT", "60"))
 
         # 异常处理配置
diff --git a/src/services/payment/gateway/alipay.py b/src/services/payment/gateway/alipay.py
index 0cde8d64..7fe6535b 100644
--- a/src/services/payment/gateway/alipay.py
+++ b/src/services/payment/gateway/alipay.py
@@ -1,7 +1,15 @@
 from __future__ import annotations
 
+import logging
 from typing import Any
 
+from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
+from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
+from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
+from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
+from alipay.aop.api.util.SignatureUtils import verify_with_rsa
+
+from src.config.settings import config
 from src.services.payment.gateway.base import PaymentGateway
 
 
@@ -9,13 +17,81 @@ class AlipayGateway(PaymentGateway):
     payment_method = "alipay"
     display_name = "支付宝"
 
+    def _get_alipay_client(self) -> DefaultAlipayClient:
+        if not config.alipay_app_id or not config.alipay_private_key or not config.alipay_public_key:
+            raise ValueError("Alipay configuration is missing in environment variables.")
+        
+        # Ensure newlines are restored if they were parsed as literal \n from env
+        private_key = config.alipay_private_key.replace("\\n", "\n")
+        public_key = config.alipay_public_key.replace("\\n", "\n")
+
+        client_config = AlipayClientConfig()
+        client_config.server_url = "https://openapi-sandbox.dl.alipaydev.com/gateway.do" if config.alipay_debug else "https://openapi.alipay.com/gateway.do"
+        client_config.app_id = config.alipay_app_id
+        client_config.app_private_key = private_key
+        client_config.alipay_public_key = public_key
+        client_config.charset = "utf-8"
+        client_config.sign_type = "RSA2"
+        return DefaultAlipayClient(client_config=client_config)
+
     def create_checkout_payload(self, *, order: Any) -> dict[str, Any]:
-        gateway_order_id = getattr(order, "gateway_order_id", None) or f"ali_{order.order_no}"
+        gateway_order_id = getattr(order, "gateway_order_id", None) or getattr(order, "order_no")
+        client = self._get_alipay_client()
+        
+        # Convert USD to CNY for Alipay (Fixed rate 7.2)
+        cny_amount = float(getattr(order, "amount_usd", 0)) * 7.2
+        amount_str = f"{cny_amount:.2f}"
+        
+        domain = f"http://{config.host}:{config.port}"
+        notify_url = f"{domain}/api/payment/callback/alipay/webhook"
+
+        model = AlipayTradePagePayModel()
+        model.out_trade_no = getattr(order, "order_no")
+        model.total_amount = amount_str
+        model.subject = f"Aether Recharge - {getattr(order, 'order_no')}"
+        model.product_code = "FAST_INSTANT_TRADE_PAY"
+
+        request = AlipayTradePagePayRequest(biz_model=model)
+        request.notify_url = notify_url
+        request.return_url = domain
+
+        # Retrieve the page pay URL parameters formatted appropriately
+        payment_url = client.page_execute(request, http_method="GET")
+
         return {
             "gateway": self.payment_method,
             "display_name": self.display_name,
             "gateway_order_id": gateway_order_id,
-            "payment_url": f"/pay/mock/alipay/{order.order_no}",
-            "qr_code": f"mock://alipay/{order.order_no}",
+            "payment_url": payment_url,
+            "qr_code": None,
             "expires_at": getattr(order, "expires_at", None),
         }
+
+    def verify_callback_payload(
+        self,
+        *,
+        payload: dict[str, Any] | None,
+        callback_signature: str | None,
+        callback_secret: str | None,
+    ) -> bool:
+        if not payload:
+            return False
+            
+        data = dict(payload)
+        signature = data.pop("sign", None)
+        data.pop("sign_type", None) # Excluded from string to sign
+        
+        if not signature:
+            return False
+            
+        try:
+            public_key = config.alipay_public_key.replace("\\n", "\n")
+            # Build string to sign: sort keys, filter empty/None, join with & and =
+            sorted_keys = sorted([(str(k), str(v)) for k, v in data.items() if v is not None and v != ""])
+            message = "&".join(f"{k}={v}" for k, v in sorted_keys)
+            
+            return verify_with_rsa(public_key.encode("utf-8"), message.encode("utf-8"), signature)
+        except Exception as e:
+            logging.error(f"Alipay signature verification failed: {e}")
+            return False
+
diff --git a/tests/api/test_payment_routes.py b/tests/api/test_payment_routes.py
index 80f06216..97c21e13 100644
--- a/tests/api/test_payment_routes.py
+++ b/tests/api/test_payment_routes.py
@@ -230,3 +230,69 @@ async def test_admin_payment_credit_adapter_marks_manual_credit(
     assert gateway_response["manual_credit"] is True
     assert gateway_response["credited_by"] == "admin-1"
     db.commit.assert_called_once()
+
+def test_alipay_webhook_success(monkeypatch: pytest.MonkeyPatch) -> None:
+    db = MagicMock()
+    client = _build_payment_app(db)
+    
+    monkeypatch.setattr("src.services.payment.gateway.alipay.AlipayGateway.verify_callback_payload", lambda *args, **kwargs: True)
+    
+    order = PaymentOrder(
+        id="po-123",
+        order_no="out_123",
+        amount_usd=Decimal("10.00"),
+    )
+    monkeypatch.setattr("src.services.payment.service.PaymentService.get_order", lambda *args, **kwargs: order)
+    
+    captured_kwargs = {}
+    def _fake_handle_callback(*args, **kwargs):
+        captured_kwargs.update(kwargs)
+    monkeypatch.setattr("src.services.payment.service.PaymentService.handle_callback", _fake_handle_callback)
+    
+    form_data = {
+        "trade_status": "TRADE_SUCCESS",
+        "out_trade_no": "out_123",
+        "trade_no": "ali_trade_888",
+        "total_amount": "72.00",
+        "sign": "mock-sign",
+    }
+    
+    response = client.post(
+        "/api/payment/callback/alipay/webhook",
+        data=form_data,
+    )
+    
+    assert response.status_code == 200
+    assert response.text == "success"
+    assert captured_kwargs["pay_amount"] == 72.0
+    assert captured_kwargs["amount_usd"] == Decimal("10.00")
+    db.commit.assert_called_once()
+
+
+def test_alipay_webhook_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
+    db = MagicMock()
+    client = _build_payment_app(db)
+    monkeypatch.setattr("src.services.payment.gateway.alipay.AlipayGateway.verify_callback_payload", lambda *args, **kwargs: False)
+    
+    response = client.post(
+        "/api/payment/callback/alipay/webhook",
+        data={"trade_status": "TRADE_SUCCESS", "out_trade_no": "out_123"},
+    )
+    assert response.status_code == 200
+    assert response.text == "failure"
+    db.commit.assert_not_called()
+
+
+def test_alipay_webhook_amount_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
+    db = MagicMock()
+    client = _build_payment_app(db)
+    monkeypatch.setattr("src.services.payment.gateway.alipay.AlipayGateway.verify_callback_payload", lambda *args, **kwargs: True)
+    
+    order = PaymentOrder(id="po-123", order_no="out_123", amount_usd=Decimal("10.00"))
+    monkeypatch.setattr("src.services.payment.service.PaymentService.get_order", lambda *args, **kwargs: order)
+    
+    response = client.post("/api/payment/callback/alipay/webhook", data={"trade_status": "TRADE_SUCCESS", "out_trade_no": "out_123", "total_amount": "70.00"})
+    
+    assert response.status_code == 200
+    assert response.text == "failure"
+    db.commit.assert_not_called()

```
