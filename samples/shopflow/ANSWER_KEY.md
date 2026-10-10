# Answer key: planted mistakes in the ShopFlow sample manuals

Keep this file out of the reviewer's input. Manuals are in `manuals/`:
`order-capturing/` (Markdown), `delivery/` (HTML), `notification/` (Markdown).
Together they form one journey: capture order → pick, pack, ship, deliver → notify the customer.

## 1. Duplicate sections

| # | Where | Mistake |
|---|-------|---------|
| D1 | order-capturing/01-getting-started.md §1.3 and 02-creating-an-order.md §2.2 | "Adding products to the cart" appears twice, almost word for word. |
| D2 | delivery/picking.html §1.3 and delivery/statuses.html | "Maximum parcel weight is 30 kg" repeated (and contradicted, see I4). |

## 2. Missing references

| # | Where | Mistake |
|---|-------|---------|
| R1 | order-capturing/index.md, 02 §2.4 | Links to `payment-methods.md`, which does not exist. |
| R2 | order-capturing/02 §2.2 | Anchor `#discount-codes` does not exist. |
| R3 | order-capturing/03 | Links to `delivery/statuses.html#order-statuses`; the anchor is `#delivery-statuses`. |
| R4 | delivery/index.html | Links to `returns.html`, which does not exist. |
| R5 | delivery/picking.html §1.4 | Points to Order Capturing section "Delivery Address Validation", which does not exist. |
| R6 | delivery/picking.html, dispatch.html | Images `images/picking-queue.png` and `images/route-assignment.png` do not exist; the first also has no alt text. |
| R7 | notification/events.md §2.3 | Links to `template-preview.md`, which does not exist. |
| R8 | order-capturing/05-bulk-import.md | Orphan page: nothing links to it. |

## 3. Inconsistencies within one manual

| # | Where | Mistake |
|---|-------|---------|
| I1 | order-capturing 01/02 vs 04 | Max line items: 50 vs 100. |
| I2 | order-capturing 02 vs 04 | Button called **Submit Order** vs **Place Order**. |
| I3 | order-capturing 02 vs 03 | Order number format `ORD-123456` (6 digits) vs `ORD-12345678` (8 digits). |
| I4 | delivery picking.html / statuses.html vs dispatch.html | Max parcel weight 30 kg vs 25 kg. |
| I5 | order-capturing index.md vs 02 | Version ShopFlow 3.4 vs 3.2. |
| I6 | order-capturing 02 §2.5 | Step numbering skips 4 (1, 2, 3, 5). |
| I7 | delivery index.html vs picking.html | Role called **Warehouse Operator** vs **Warehouse role**. |
| I8 | notification channels.md §1.2 vs §1.4 | SMTP port 587 vs 465. |
| I9 | notification index.md vs channels.md §1.4 | Test command `shopflow-notify test --channel=email` vs `shopflow notify test -c email`. |
| I10 | notification events.md §2.2 | Template uses `{{customerName}}` / `{{orderId}}`, but the documented variables are `{{customer_name}}` / `{{order_id}}`. |
| I11 | order-capturing 05 | Bulk-imported orders skip payment and go straight to Confirmed, unlike the normal flow (02, 03). |

## 4. Contradictions across manuals

| # | Where | Mistake |
|---|-------|---------|
| C1 | order-capturing 02/03 vs delivery picking/statuses | Paid order status is **Confirmed** vs **Paid**. |
| C2 | order-capturing 02 §2.6 vs delivery dispatch §2.4 | Cancellation allowed only while Submitted vs until Shipped. |
| C3 | order-capturing 02 §2.3 vs delivery dispatch §2.1 | Postal code optional vs orders without postal code cannot be dispatched. |
| C4 | order-capturing 02/04 vs notification channels §1.3 | Confirmation e-mail within 5 minutes vs batched every 15 minutes. |
| C5 | order-capturing 02 §2.7 vs notification index "Opt-out rules" | Customers can opt out of all e-mails vs transactional e-mails can't be disabled. |
| C6 | delivery dispatch §2.2 vs notification channels §1.1 | "Out for delivery" SMS vs SMS not supported in 3.4. |
| C7 | order-capturing 02 §2.5 vs delivery picking §1.1 | Order "automatically sent to the warehouse" vs supervisor must release it manually. |
| C8 | order-capturing 03 vs delivery statuses | Status lists differ (delivery adds Picking, Ready for dispatch, Out for delivery, Delivery failed, Returned; order manual has none of them). |

## 5. Gaps in the end-to-end journey

| # | Gap |
|---|-----|
| G1 | No manual explains how a supervisor **releases** orders to the picking queue, or who that supervisor is. |
| G2 | No notification event exists for **Out for delivery** or **Delivery failed**, though delivery says the customer is notified. |
| G3 | The **reschedule link** for failed deliveries is not documented anywhere: no template, no variable, no customer-facing steps. |
| G4 | Nobody owns orders on the **Address hold** shelf: no steps to fix the address or contact the customer. |
| G5 | What happens after a parcel is **Returned** (refund, re-delivery, customer notice) is undocumented; `returns.html` is missing. |
| G6 | How a customer's payment moves an order from Submitted to Confirmed/Paid is undocumented (payment manual missing). |
| G7 | Delivery prerequisite "handheld scanner paired with your account" has no pairing instructions. |

## 6. Extra checks

Entries marked "same as" repeat a mistake from the sections above under its extra-check category. In total there are 68 distinct mistakes.

`reference/ui-strings.json` is a reference file with the real UI labels. Feed it to the UI label check; it is not a manual.

| # | Check | Where | Mistake |
|---|-------|-------|---------|
| X1 | Broken link | delivery/index.html | Contents links to `dispatch.htm` (file is `dispatch.html`). |
| X2 | Broken anchor | order-capturing/04 "wrong language" | `01-getting-started.md#logging-in-to-shopflow`; the heading is "1.2 Logging in". |
| X3 | Broken anchor | notification/events.md §2.3 | `../delivery/dispatch.html#failed-delivery`; that heading has no id. |
| X4 | Terminology drift | order-capturing 02 vs 04 | "customer" vs "buyer". |
| X5 | Terminology drift | order-capturing 01 §1.4 vs 04 | **Preferences › Language** vs **Settings › Language**. |
| X6 | Terminology drift | notification channels/events | **Admin › Notifications** vs **Settings › Notifications**. |
| X7 | Terminology drift | delivery (all pages) | "consignee" vs "customer" in the other manuals, and never defined. |
| X8 | UI label mismatch | order-capturing 02 §2.5 | **Submit Order**; ui-strings says `Place Order`. |
| X9 | UI label mismatch | delivery dispatch §2.1 | **Load**; ui-strings says `Load parcel`. |
| X10 | UI label mismatch | delivery dispatch §2.2 | **Delivered**; ui-strings says `Mark as delivered`. |
| X11 | UI label mismatch | order-capturing 04, notification events | **Settings › Language** and **Settings › Notifications › Templates** don't exist in ui-strings. |
| X12 | Prerequisite gap | order-capturing 02 §2.4 | **Payment Terminal** add-on is never explained or set up. |
| X13 | Prerequisite gap | notification channels §1.2 | **Notification Admin** role required, but no one says how to get it. |
| X14 | Prerequisite gap | delivery index | Pairing the handheld scanner is never explained (same as G7). |
| X15 | Step order | order-capturing 02 §2.1 | Step 3 picks the customer's saved address before step 4 creates a new customer. |
| X16 | Step order | delivery dispatch §2.1 vs §2.4 | Parcels are assigned to routes, but routes are only created at the end of the day. |
| X17 | Step order | notification events §2.3 | Step 3 is repeated, and "Preview before saving" comes after **Save**. |
| X18 | Step numbering | order-capturing 02 §2.5 | Step 4 is missing (same as I6). |
| X19 | Undefined term | delivery picking §1.1 | "SLA" not defined. |
| X20 | Undefined term | delivery dispatch §2.1 | "ASN" not defined, and no steps say how to send it. |
| X21 | Undefined term | delivery picking §1.1 | "wms" in the URL is never explained (OMS is defined in order-capturing). |
| X22 | Orphan page | order-capturing/05-bulk-import.md | Nothing links to it (same as R8). |
| X23 | Orphan page | notification/legacy-sms.md | Nothing links to it. |
| X24 | Stale version | order-capturing 02 | Mentions ShopFlow 3.2 in a 3.4 manual (same as I5). |
| X25 | Stale version | delivery index | "Last updated: March 2022" in a 3.4 manual. |
| X26 | Removed feature | delivery dispatch §2.1 | Uses the **Classic Dispatch** screen; delivery index says Classic screens were removed in 3.0. |
| X27 | Removed feature | notification/legacy-sms.md | Describes enabling SMS for 2.x; channels.md says SMS isn't supported in 3.4. Also contradicts batching (sent immediately vs every 15 minutes). |
| X28 | Value conflict | order-capturing 01 §1.4 vs 04 | Session timeout 15 vs 30 minutes. |
| X29 | Value conflict | notification index vs channels §1.2 | Log path `/opt/shopflow/logs/notification.log` vs `/var/log/shopflow/notify.log`. |
| X30 | Value conflict | notification channels §1.2 vs §1.4 | SMTP port 587 vs 465 (same as I8). |
| X31 | Missing error path | order-capturing 02 §2.5 | No guidance if submission or payment fails. |
| X32 | Missing error path | delivery picking §1.2 | No guidance if a barcode won't scan or a product isn't on the shelf. |
| X33 | Missing error path | notification events §2.3 | "If Save fails, the template is not changed" but no recovery steps. |
| X34 | Malformed code | notification channels §1.2 | `notify.json` has a trailing comma after `587` and a missing comma after `}`. |
| X35 | Malformed code | order-capturing 05 | CSV rows 2 and 3 have 3 and 5 columns; the header has 4. |
| X36 | Command conflict | notification index vs channels §1.4 | `shopflow-notify test --channel=email` vs `shopflow notify test -c email` (same as I9). |
| X37 | Image missing | order-capturing 02 §2.5 | `images/order-summary.png` doesn't exist and has no alt text. |
| X38 | Image missing | notification events §2.3 | `images/template-editor.png` doesn't exist. |
| X39 | Image missing | delivery picking, dispatch | Same as R6: missing files, first one has no alt text. |

