# PesoWeb onboarding contract (verified live, 2026-10-05)

The chain a simulated owner follows through the **real** PesoWeb API, from signup to a sale with a markdown. Every step below was executed against a running PesoWeb (branch `Retail_MissionCommerceAI`) on a restored copy of the June 30 dev database, using `pesoweb-additions/smoke/seed-expiry-tenant.ps1`, `cash-shift-smoke.ps1` and `pricing-smoke.ps1` (all pass). This is the contract the Sim `PesoWebDriver` implements.

Auth: after Register or Login, send `Authorization: Bearer <token>`. Optional `X-Sim-Run: <run id>` tags the events the call produces (kept to 64 chars).

## What a brand-new tenant starts with
- Plan tier **Lite** (`Subscription = 5`): 1 branch, 1 user, 1,000 products (from `SubscriptionTierLimits`).
- One default branch (warehouse), returned as `defaultWarehouseId`.
- One customer, "Cash Customer", and two payment methods: Cash and Card.
- The owner role has **all** permissions, including `Cash.*`, `AI.Read` and `Pricing.*`.
- **Nothing else**: no categories, brands, units, tax rates or suppliers. The owner's onboarding must create them.

## The chain

| # | Step | Route | Body | Returns |
|---|---|---|---|---|
| 1 | Sign up | `POST /api/Auth/Register` | JSON `{CompanyName, FirstName, LastName, Email, Phone, Password, ConfirmPassword}` (password at least 6 chars) | login payload: `token`, `tenantID`, `defaultWarehouseId`, `permissions` |
| 2 | Category | `POST /api/Inventory/AddCategory` | multipart `CategoryName` | `id` |
| 3 | Brand | `POST /api/Inventory/AddBrand` | multipart `BrandName` | `id` |
| 4 | Unit | `POST /api/Inventory/AddUnit` | JSON `{unitName, shortName, operator:"*", operationValue:1}` | `id` |
| 5 | Tax rate | `POST /api/Settings/AddTaxRate` | JSON `{taxName, taxPercentage}` | `id` |
| 6 | Supplier | `POST /api/People/AddSupplier` | JSON `{supplierName, email, phone, address, city, state, postalCode, country}` | `id` |
| 7 | Expiry product | `POST /api/Inventory/AddProduct` | multipart `CategoryId, BrandId, UnitId, SaleUnitId, PurchaseUnitId, TaxId, TaxMethod(1), ProductCode, BarcodeType, ProductName, Cost, Price, Discount, StockAlert, MonitorExpiry=true, BatchTracking=true, ExpiryAlertDays, HasVariants=false` | `id` |
| 8 | Receive stock with a batch | `POST /api/Purchases/AddPurchase` | multipart `WarehouseId, SupplierId, PurchaseDate, DiscountPercentage, TaxPercentage, ShippingCharges, PaidAmount, OrderStatus=1` plus `purchaseDetails[0].productId / unitCost / quantity / amount / batchNo / expiryDate / manufacturingDate` | `id` |
| 9 | Sell | `POST /api/Sales/AddSale` | multipart `WarehouseId, CustomerId, DiscountPercentage, TaxPercentage, ShippingCharges, PaidAmount, PaymentMethod, OrderStatus` plus `saleDetails[0].productId / quantity` | 201 with `saleDetails[].salePrice` |

Reads used: `GET /api/People/Customers?page=1&pageSize=5` (`data[].id`), `GET /api/Inventory/NearExpiryBatches?warehouse=<id>&pageSize=50` (`data[]` with `id, productId, qtyOnHand, expiryDate`), `GET /api/Inventory/ProductDetail/{id}?warehouse=<id>`.

Rules learned:
- **Stock is received only when the purchase's `OrderStatus` is `1`.** For a batch-tracked product, `batchNo` and `expiryDate` are required on every line.
- `AddSale` prices from the product and consumes stock first-expiry-first-out (FEFO); a sale of 1 unit with no markdown at list price 100 returned `salePrice = 100`.
- The cashier shift, markdown and read endpoints are documented in `pesoweb-additions/README.md`.

## Findings (things the simulator and the plan must work around)

1. **Tier limits are enforced for real.** On a Lite tenant, a second `AddWarehouse` returns `400 {"message":"Branch limit reached for your subscription plan. Maximum allowed branches: 1."}`. A simulated owner who wants more branches than the tier allows must downsize, or the central company must raise the tier. How the tier changes (the owner's `Users.Subscription`, set by the root `SuperAdmin`) has not been exercised through the API yet.
2. **(Fixed in Plan 3: `scripts/20261005_widen_users_subscription_check.sql` and migration `WidenUsersSubscriptionCheck`.) Signup depended on a database constraint that the repo's scripts did not update.** `Register` assigns `Subscription = 5`, but `CK_Users_Subscription_Valid` in databases built from the repo's scripts and the June 30 backup allows only 1, 2 or 3, so signup returns a 500. It works on a database where the constraint was widened to `IN (1,2,3,4,5)`. Your real dev database must have been changed by hand; the repo has no script for it. (The verification database was patched the same way.)
3. **(Fixed in Plan 3: purchase receiving now stores the line's unit cost on the batch.) Batches had no cost.** Purchase receiving hard-codes `UnitCost = null`, so `ProductBatch.Cost` and the `PURCHASE_IN` ledger cost are NULL in every database checked. Expiry money-at-risk, the margin floor and waste in pesos therefore use the product's current `Cost`. Capturing the purchase line's unit cost on the batch is a recommended fix.
4. The owner role of a new tenant cannot read `GET /api/Settings/Roles` (403); not needed by the simulator.
5. The repo's EF migrations cannot build a database from scratch (a foreign-key cycle in an old migration), and the migration history is incomplete (only the first migration is recorded). Real databases come from the backup plus the SQL scripts; see "Live verification environment" in `pesoweb-additions/README.md`.
6. **`AddWarehouse` does not assign the owner to the new branch.** The owner's `UserWarehouses` only contains the default branch, so `AddPurchase` for a new branch returns `400 Invalid purchase data` and `Exceptions/List` hides it. Fix used by the sim: read `GET /api/People/UserDetail/{id}` and `PUT /api/People/UpdateUser/{id}` (multipart) with the extra `UserWarehouses[i].WarehouseId`; an owner may do this for itself as long as `Subscription` is omitted.
7. **Plan tier changes go through root.** The central company reads `UserDetail` for the owner and sends `UpdateUser` with `Subscription=3` (the owner's current plain password keeps the hash unchanged). Owners cannot change their own tier (403).
8. Usernames and emails are unique across all tenants, so a simulated world tags both with its run id. `GET /api/People/UserFormData` returns `roles` for staff creation; staff added with the owner's role get all permissions.
9. `Exceptions/Detect` does not run by itself; the sim triggers it per branch after trading (the nightly job in a real deployment). FEFO sells the nearest-expiry batch first, so stock delivered short-dated in the morning is usually sold before any alert can fire.
