# 1. Channels and configuration

## 1.1 Supported channels

| Channel | Status in 3.4                      |
|---------|------------------------------------|
| E-mail  | Enabled by default                 |
| Push    | Enabled for the mobile app         |
| SMS     | Not supported (planned for 4.0)    |

## 1.2 E-mail server settings

Go to **Admin › Notifications › E-mail** and enter:

| Setting   | Value                     |
|-----------|---------------------------|
| SMTP host | `smtp.example.com`        |
| SMTP port | `587` (STARTTLS)          |
| Sender    | `orders@shopflow.example` |

You can also set these values in `config/notify.json`:

```json
{
  "smtp": {
    "host": "smtp.example.com",
    "port": 587,
  }
  "sender": "orders@shopflow.example"
}
```

Only users with the **Notification Admin** role can open this screen.

Logs are written to `/var/log/shopflow/notify.log`.

## 1.3 Delivery timing

To reduce load, e-mails are sent in batches **every 15 minutes**. Order confirmations can therefore arrive up to 15 minutes after submission.

## 1.4 Testing the configuration

```
shopflow notify test -c email
```

If the test fails, check that port `465` is open in the firewall.
