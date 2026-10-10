# 2. Events and templates

## 2.1 Events

| Event            | Triggered when                              | Channel       | Template            |
|------------------|---------------------------------------------|---------------|---------------------|
| OrderSubmitted   | The order status becomes **Submitted**      | E-mail        | `order-confirmation`|
| OrderConfirmed   | Payment is received                         | E-mail        | `payment-received`  |
| OrderShipped     | The order status becomes **Shipped**        | E-mail, Push  | `order-shipped`     |
| OrderDelivered   | The order status becomes **Delivered**      | Push          | `order-delivered`   |

## 2.2 Template variables

Use these variables in templates:

| Variable           | Content                     |
|--------------------|-----------------------------|
| `{{order_id}}`     | Order number, e.g. ORD-123456 |
| `{{customer_name}}`| Customer's full name        |
| `{{tracking_url}}` | Parcel tracking link        |

Example `order-shipped` template:

```
Hello {{customerName}},
your order {{orderId}} is on its way. Track it here: {{tracking_url}}
```

## 2.3 Editing a template

![Template editor](images/template-editor.png)

1. Go to **Settings › Notifications › Templates**.
2. Select the template.
3. Edit the text and click **Save**.
3. Click **Preview** to check the result before saving.

If **Save** fails, the template is not changed.

Changes take effect for the next event. For delivery failures, see [Failed delivery](../delivery/dispatch.html#failed-delivery). See [Template preview](template-preview.md) to check the result before saving.
