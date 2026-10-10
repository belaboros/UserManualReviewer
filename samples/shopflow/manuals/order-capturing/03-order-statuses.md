# 3. Order statuses

| Status     | Meaning                                                        |
|------------|----------------------------------------------------------------|
| Draft      | The order is being captured and has not been submitted.        |
| Submitted  | The order was submitted; payment is pending.                   |
| Confirmed  | Payment was received; the order is ready for the warehouse.    |
| Shipped    | The order has left the warehouse.                              |
| Delivered  | The customer received the order.                               |
| Cancelled  | The order was cancelled.                                       |

The order number format is `ORD-12345678`.

Status changes after **Confirmed** are made by the delivery team. See the [Delivery manual, section "Order statuses"](../delivery/statuses.html#order-statuses).
