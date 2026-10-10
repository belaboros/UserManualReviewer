# ShopFlow Notification Service – User Manual

Version: ShopFlow 3.4 · Audience: Administrators and customer service staff

The Notification Service sends messages to customers when something happens to their order.

## Contents

1. [Channels and configuration](channels.md)
2. [Events and templates](events.md)
3. [Opt-out rules](#opt-out-rules)

## Opt-out rules

Customers can opt out of **marketing** messages only. **Transactional** messages (order confirmation, shipping updates) are always sent and cannot be disabled.

## Logs

Notification logs are written to `/opt/shopflow/logs/notification.log`.

## Testing a notification

Run the following command on the ShopFlow server:

```
shopflow-notify test --channel=email --to=agent@example.com
```
