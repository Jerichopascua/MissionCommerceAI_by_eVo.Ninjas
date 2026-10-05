"""PesoWebDriver: virtual users calling the REAL PesoWeb API (contract in Docs/onboarding-contract.md).

Rules: every call carries X-Sim-Run; tokens are never logged or put in error text; only connection errors are
retried; tier-limit refusals raise DriverRefusal so the runner records them as decisions instead of crashing."""
import base64
import json
import time
from dataclasses import dataclass

import requests


class DriverError(Exception):
    pass


class DriverRefusal(DriverError):
    """PesoWeb refused a valid request by policy (tier limit, guardrail, ...)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


@dataclass
class Account:
    email: str
    password: str
    token: str
    tenant_id: int
    warehouse_id: int
    user_id: int

    def __repr__(self) -> str:           # never show the token
        return f"Account(email={self.email!r}, tenant_id={self.tenant_id}, warehouse_id={self.warehouse_id})"


def _jwt_claims(token: str) -> dict:
    try:
        body = token.split(".")[1]
        body += "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(body))
    except Exception:
        return {}


def _form(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if v is None:
            continue
        out[k] = (None, "true" if v is True else "false" if v is False else str(v))
    return out


class PesoWebDriver:
    def __init__(self, base_url: str, run_id: str, timeout: float = 60, session=None):
        self.base = base_url.rstrip("/")
        self.run_id = run_id[:64]
        self.timeout = timeout
        self.http = session or requests.Session()
        self.calls = 0
        self.refusals = []

    # ---- plumbing -------------------------------------------------------------------------------------------
    def _call(self, method: str, path: str, token: str = None, json_body=None, form: dict = None, expect_json=True, raw=False):
        headers = {"X-Sim-Run": self.run_id}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        kwargs = {"headers": headers, "timeout": self.timeout}
        if form is not None:
            kwargs["files"] = _form(form)
        elif json_body is not None:
            kwargs["json"] = json_body
        last = None
        for attempt in range(3):
            try:
                self.calls += 1
                resp = self.http.request(method, self.base + path, **kwargs)
                break
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                time.sleep(0.5 * (attempt + 1))
        else:
            raise DriverError(f"{method} {path} unreachable after 3 tries: {type(last).__name__}")
        if raw:
            try:
                return resp.status_code, resp.json()
            except ValueError:
                return resp.status_code, {"message": resp.text[:300]}
        if resp.status_code >= 400:
            text = resp.text[:300]
            try:
                text = resp.json().get("message", text)
            except Exception:
                pass
            if resp.status_code == 400 and "limit reached" in text.lower():
                self.refusals.append({"path": path, "message": text})
                raise DriverRefusal(resp.status_code, text)
            raise DriverError(f"{method} {path} -> {resp.status_code}: {text}")
        if not expect_json or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # ---- accounts -------------------------------------------------------------------------------------------
    def _account(self, email: str, password: str, payload: dict) -> Account:
        token = payload["token"]
        claims = _jwt_claims(token)
        uid = next((int(v) for k, v in claims.items() if k.lower().endswith("/sid") or k.lower() == "sid"), 0)
        return Account(email, password, token, int(payload.get("tenantID") or payload.get("tenantId") or 0),
                       int(payload.get("defaultWarehouseId") or 0), uid)

    def register(self, company: str, first: str, last: str, email: str, password: str, phone: str = "+639000000000") -> Account:
        body = {"CompanyName": company, "FirstName": first, "LastName": last, "Email": email, "Phone": phone,
                "Password": password, "ConfirmPassword": password}
        return self._account(email, password, self._call("POST", "/api/Auth/Register", json_body=body))

    def login(self, email: str, password: str) -> Account:
        body = {"Email": email, "Password": password, "IsRemember": False}
        return self._account(email, password, self._call("POST", "/api/Auth/Login", json_body=body))

    def _update_user(self, actor_token: str, user_id: int, password: str, warehouse_ids=None, subscription=None) -> None:
        d = self._call("GET", f"/api/People/UserDetail/{user_id}", actor_token)
        ids = list(warehouse_ids) if warehouse_ids is not None else [uw["warehouseId"] for uw in d.get("userWarehouses") or []]
        form = {"RoleId": d["roleId"], "FullName": d["fullName"], "UserName": d["userName"], "Email": d["email"],
                "Password": password, "Phone": d.get("phone") or "", "IsActive": True, "IsTwoFactorEnabled": False,
                "Subscription": subscription, "DefaultWarehouseId": d.get("defaultWarehouseId")}
        for i, wid in enumerate(ids):
            form[f"UserWarehouses[{i}].WarehouseId"] = wid
        self._call("PUT", f"/api/People/UpdateUser/{user_id}", actor_token, form=form)

    def root_set_tier(self, root: Account, owner: Account, subscription: int = 3) -> None:
        """The central company (root SuperAdmin) raises a subsidiary's plan tier."""
        self._update_user(root.token, owner.user_id, owner.password, subscription=subscription)

    def grant_branch(self, owner: Account, warehouse_id: int) -> None:
        """AddWarehouse does not assign the owner to the new branch; do it so the owner can stock and monitor it."""
        d = self._call("GET", f"/api/People/UserDetail/{owner.user_id}", owner.token)
        ids = [uw["warehouseId"] for uw in d.get("userWarehouses") or []]
        if warehouse_id not in ids:
            self._update_user(owner.token, owner.user_id, owner.password, ids + [warehouse_id])

    # ---- tenant setup ---------------------------------------------------------------------------------------
    def add_branch(self, acct: Account, name: str, city: str, n: int) -> int:
        body = {"WarehouseName": name, "Email": f"branch{n}.{acct.tenant_id}@simworld.test", "Phone": "+639000000001",
                "Address": f"{n} Sim Street", "City": city, "State": "NCR", "PostalCode": "1000", "Country": "PH"}
        return int(self._call("POST", "/api/Settings/AddWarehouse", acct.token, json_body=body)["id"])

    def role_id(self, acct: Account) -> int:
        d = self._call("GET", "/api/People/UserFormData", acct.token)
        roles = d.get("roles") or d.get("Roles") or []
        if not roles:
            raise DriverError("no role available to assign to staff")
        return int(roles[0].get("id") or roles[0].get("Id"))

    def add_staff(self, owner: Account, role_id: int, name: str, username: str, email: str, password: str, warehouse_id: int) -> int:
        form = {"RoleId": role_id, "FullName": name, "UserName": username, "Email": email, "Password": password,
                "Phone": "+639000000003", "IsActive": True, "IsTwoFactorEnabled": False,
                "DefaultWarehouseId": warehouse_id, "UserWarehouses[0].WarehouseId": warehouse_id}
        return int(self._call("POST", "/api/People/AddUser", owner.token, form=form)["id"])

    def setup_basics(self, acct: Account) -> dict:
        unit = self._call("POST", "/api/Inventory/AddUnit", acct.token,
                          json_body={"unitName": "Piece", "shortName": "pc", "operator": "*", "operationValue": 1})
        tax = self._call("POST", "/api/Settings/AddTaxRate", acct.token, json_body={"taxName": "No Tax", "taxPercentage": 0})
        brand = self._call("POST", "/api/Inventory/AddBrand", acct.token, form={"BrandName": "Generic"})
        return {"unit": int(unit["id"]), "tax": int(tax["id"]), "brand": int(brand["id"])}

    def add_category(self, acct: Account, name: str) -> int:
        return int(self._call("POST", "/api/Inventory/AddCategory", acct.token, form={"CategoryName": name})["id"])

    def add_supplier(self, acct: Account, name: str, n: int) -> int:
        body = {"supplierName": name, "email": f"supplier{n}.{acct.tenant_id}@simworld.test", "phone": "+639000000002",
                "address": "1 Supply St", "city": "Manila", "state": "NCR", "postalCode": "1000", "country": "PH"}
        return int(self._call("POST", "/api/People/AddSupplier", acct.token, json_body=body)["id"])

    def _product_form(self, spec, category_id: int, basics: dict, price=None) -> dict:
        form = {"CategoryId": category_id, "BrandId": basics["brand"], "UnitId": basics["unit"], "SaleUnitId": basics["unit"],
                "PurchaseUnitId": basics["unit"], "TaxId": basics["tax"], "TaxMethod": 1, "ProductCode": spec.code,
                "BarcodeType": "CODE128", "ProductName": spec.name, "Cost": spec.cost, "Price": spec.price if price is None else price, "Discount": 0,
                "StockAlert": 5, "HasVariants": False}
        if spec.expiry:
            form.update({"MonitorExpiry": True, "BatchTracking": True, "ExpiryAlertDays": spec.alert_days})
        return form

    def add_product(self, acct: Account, spec, category_id: int, basics: dict) -> int:
        return int(self._call("POST", "/api/Inventory/AddProduct", acct.token, form=self._product_form(spec, category_id, basics))["id"])

    def set_product_price(self, acct: Account, product_id: int, spec, category_id: int, basics: dict, new_price: float) -> None:
        """The owner changes a product's list price through PesoWeb's own update endpoint (a tenant-wide price)."""
        self._call("PUT", f"/api/Inventory/UpdateProduct/{product_id}", acct.token, form=self._product_form(spec, category_id, basics, new_price), expect_json=False)

    def receive_stock(self, acct: Account, warehouse_id: int, supplier_id: int, lines: list, date: str) -> int:
        """lines: dicts with product_id, unit_cost, quantity and optional batch_no, expiry_date, manufacturing_date."""
        total = sum(l["unit_cost"] * l["quantity"] for l in lines)
        form = {"WarehouseId": warehouse_id, "SupplierId": supplier_id, "PurchaseDate": date, "DiscountPercentage": 0,
                "TaxPercentage": 0, "ShippingCharges": 0, "PaidAmount": total, "OrderStatus": 1}
        for i, l in enumerate(lines):
            form[f"purchaseDetails[{i}].productId"] = l["product_id"]
            form[f"purchaseDetails[{i}].unitCost"] = l["unit_cost"]
            form[f"purchaseDetails[{i}].quantity"] = l["quantity"]
            form[f"purchaseDetails[{i}].amount"] = l["unit_cost"] * l["quantity"]
            if l.get("batch_no"):
                form[f"purchaseDetails[{i}].batchNo"] = l["batch_no"]
                form[f"purchaseDetails[{i}].expiryDate"] = l["expiry_date"]
                form[f"purchaseDetails[{i}].manufacturingDate"] = l["manufacturing_date"]
        return int(self._call("POST", "/api/Purchases/AddPurchase", acct.token, form=form)["id"])

    def customers(self, acct: Account) -> list:
        return self._call("GET", "/api/People/Customers?page=1&pageSize=50", acct.token).get("data", [])

    # ---- operations -----------------------------------------------------------------------------------------
    def open_shift(self, acct: Account, warehouse_id: int, terminal: str, opening_cash: float) -> int:
        body = {"warehouseId": warehouse_id, "posTerminal": terminal, "openingCash": opening_cash}
        return int(self._call("POST", "/api/CashShifts/Open", acct.token, json_body=body)["id"])

    def current_shift(self, acct: Account, warehouse_id: int) -> dict:
        return self._call("GET", f"/api/CashShifts/Current?warehouseId={warehouse_id}", acct.token)

    def close_shift(self, acct: Account, shift_id: int, actual_cash: float, note: str = "") -> dict:
        return self._call("POST", "/api/CashShifts/Close", acct.token,
                          json_body={"shiftId": shift_id, "actualCash": actual_cash, "note": note})

    def sell(self, acct: Account, warehouse_id: int, customer_id: int, lines: list, payment: str = "Cash", paid: float = None) -> dict:
        """lines: (product_id, quantity). Returns the sale (totalAmount, saleDetails[].salePrice)."""
        form = {"warehouseId": warehouse_id, "customerId": customer_id, "discountPercentage": 0, "taxPercentage": 0,
                "shippingCharges": 0, "paidAmount": paid if paid is not None else 0, "paymentMethod": payment, "orderStatus": 1}
        for i, (pid, qty) in enumerate(lines):
            form[f"saleDetails[{i}].productId"] = pid
            form[f"saleDetails[{i}].quantity"] = qty
        return self._call("POST", "/api/Sales/AddSale", acct.token, form=form)

    def return_sale(self, acct: Account, sale_id: int, warehouse_id: int, customer_id: int, lines: list, date: str) -> dict:
        form = {"SaleId": sale_id, "WarehouseId": warehouse_id, "CustomerId": customer_id, "SaleReturnDate": date, "TaxPercentage": 0}
        for i, (pid, qty) in enumerate(lines):
            form[f"saleReturnDetails[{i}].productId"] = pid
            form[f"saleReturnDetails[{i}].quantity"] = qty
        return self._call("POST", "/api/Sales/AddReturn", acct.token, form=form)

    def receiving_report(self, acct: Account, warehouse_id: int, purchase_id: int, product_id: int, expected: float, received: float, note: str = "") -> dict:
        return self._call("POST", "/api/Receiving/Report", acct.token,
                          json_body={"warehouseId": warehouse_id, "sourceType": "Purchase", "sourceId": purchase_id,
                                     "productId": product_id, "expectedQty": expected, "receivedQty": received, "note": note})

    # ---- reads ----------------------------------------------------------------------------------------------
    def detect_exceptions(self, acct: Account, warehouse_id: int) -> dict:
        return self._call("POST", f"/api/Exceptions/Detect?warehouseId={warehouse_id}", acct.token)

    def exceptions(self, acct: Account, warehouse_id: int = None) -> list:
        q = f"?warehouseId={warehouse_id}" if warehouse_id else ""
        out = self._call("GET", f"/api/Exceptions/List{q}", acct.token)
        return out if isinstance(out, list) else (out or {}).get("data", [])

    def active_markdowns(self, acct: Account, warehouse_id: int = None) -> list:
        q = f"?warehouseId={warehouse_id}" if warehouse_id else ""
        return self._call("GET", f"/api/ai/active-markdowns{q}", acct.token) or []

    def near_expiry(self, acct: Account, warehouse_id: int) -> list:
        return self._call("GET", f"/api/Inventory/NearExpiryBatches?warehouse={warehouse_id}&pageSize=200", acct.token).get("data", [])

    # ---- pricing, expiry and AI feeds ---------------------------------------------------------------------
    def pricing_policy(self, acct: Account) -> dict:
        return self._call("GET", "/api/Pricing/Policy", acct.token)

    def set_pricing_policy(self, acct: Account, mode: str, hard_floor: float, soft_floor: float, max_discount: float, max_changes_per_hour: int,
                           list_price_auto_approve: bool = None, **approval_settings) -> dict:
        body = {"AutonomyMode": mode, "HardMarginFloorPct": hard_floor, "SoftMarginFloorPct": soft_floor,
                "MaxDiscountPct": max_discount, "MaxChangesPerSkuPerHour": max_changes_per_hour}
        if list_price_auto_approve is not None:
            body["ListPriceAutoApprove"] = list_price_auto_approve
        body.update(approval_settings)               # e.g. StoreLaneMaxPct, OwnerLaneMinPct, ProposalExpiryHours
        return self._call("PUT", "/api/Pricing/Policy", acct.token, json_body=body)

    def markdown(self, acct: Account, warehouse_id: int, product_id: int, batch_id: int, new_price: float,
                 reason: str = "", prediction_ref: str = None, source: str = "Ai"):
        """Returns (http status, outcome body). 200 applied, 202 needs approval, 422 refused by a guardrail."""
        body = {"WarehouseId": warehouse_id, "ProductId": product_id, "BatchId": batch_id, "NewPrice": new_price,
                "Reason": reason[:300], "Source": source}
        if prediction_ref:
            body["PredictionRef"] = prediction_ref
        return self._call("POST", "/api/Pricing/Markdown", acct.token, json_body=body, raw=True)

    def end_markdown(self, acct: Account, active_markdown_id: int, reason: str = "") -> None:
        self._call("POST", "/api/Pricing/End", acct.token, json_body={"ActiveMarkdownId": active_markdown_id, "Reason": reason}, expect_json=False)

    def active_markdown_rows(self, acct: Account, warehouse_id: int = None) -> list:
        q = f"?warehouseId={warehouse_id}" if warehouse_id else ""
        return self._call("GET", f"/api/Pricing/Active{q}", acct.token) or []

    def expiry_batches(self, acct: Account, warehouse_id: int) -> list:
        return (self._call("GET", f"/api/Expiry/Risk?warehouseId={warehouse_id}", acct.token) or {}).get("batches", [])

    def all_batches(self, acct: Account, warehouse_id: int) -> list:
        """Every batch with stock on hand (the at-risk list from expiry_batches is only the alert window)."""
        return self._call("GET", f"/api/ai/batches?warehouseId={warehouse_id}", acct.token) or []

    def write_off_expired(self, acct: Account, warehouse_id: int) -> dict:
        return self._call("POST", f"/api/Expiry/WriteOffExpired?warehouseId={warehouse_id}", acct.token)

    def receipts(self, acct: Account, warehouse_id: int = None, after_id: int = 0) -> list:
        q = f"?afterId={after_id}&take=1000" + (f"&warehouseId={warehouse_id}" if warehouse_id else "")
        return (self._call("GET", f"/api/ai/receipts{q}", acct.token) or {}).get("receipts", [])

    def movements(self, acct: Account, warehouse_id: int = None, kind: str = "SALE_OUT", after_id: int = 0) -> list:
        q = f"?type={kind}&afterId={after_id}&take=5000" + (f"&warehouseId={warehouse_id}" if warehouse_id else "")
        return (self._call("GET", f"/api/ai/movements{q}", acct.token) or {}).get("movements", [])

    # ---- stock counts -------------------------------------------------------------------------------------
    def create_count(self, acct: Account, warehouse_id: int, product_ids: list, note: str = "") -> dict:
        return self._call("POST", "/api/StockCounts/Create", acct.token,
                          json_body={"warehouseId": warehouse_id, "productIds": product_ids, "note": note})

    def submit_count(self, acct: Account, count_id: int, counts: list) -> dict:
        """counts: dicts {productId, countedQty, reason}."""
        return self._call("POST", "/api/StockCounts/Submit", acct.token, json_body={"stockCountId": count_id, "counts": counts})

    def approve_count(self, acct: Account, count_id: int) -> dict:
        return self._call("POST", "/api/StockCounts/Approve", acct.token, json_body={"stockCountId": count_id})

    # ---- list price changes (guarded, approved by a human) -----------------------------------------------
    def propose_list_price(self, acct: Account, warehouse_id: int, product_id: int, new_price: float, reason: str = "",
                           prediction_ref: str = None, source: str = "Ai"):
        """Returns (http status, outcome). 202 waits for approval, 422 is refused by a rule."""
        body = {"WarehouseId": warehouse_id, "ProductId": product_id, "NewPrice": new_price, "Reason": reason[:300], "Source": source}
        if prediction_ref:
            body["PredictionRef"] = prediction_ref
        return self._call("POST", "/api/Pricing/ListPrice", acct.token, json_body=body, raw=True)

    def approve_list_price(self, acct: Account, price_change_id: int):
        return self._call("POST", "/api/Pricing/ApproveListPrice", acct.token, json_body={"PriceChangeId": price_change_id}, raw=True)

    def reject_list_price(self, acct: Account, price_change_id: int, reason: str = ""):
        return self._call("POST", "/api/Pricing/RejectListPrice", acct.token, json_body={"PriceChangeId": price_change_id, "Reason": reason}, raw=True)

    def list_price_changes(self, acct: Account, status: str = None, product_id: int = None) -> list:
        parts = [x for x in (f"status={status}" if status else "", f"productId={product_id}" if product_id else "") if x]
        return self._call("GET", "/api/Pricing/ListPriceChanges" + ("?" + "&".join(parts) if parts else ""), acct.token) or []

