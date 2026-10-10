# 5. Bulk order import

You can import up to 500 orders from a CSV file.

The CSV file must have the columns `customer_id;sku;quantity;postal_code`. Example:

```csv
customer_id;sku;quantity;postal_code
C-1001;SKU-778;2;1051
C-1002;SKU-312;1
C-1003;SKU-778;5;1132;express
```

1. Go to **Orders › Import**.
2. Upload the CSV file.
3. Click **Start import**.

Imported orders get the status **Confirmed** immediately and skip payment.
