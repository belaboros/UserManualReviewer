# 2. Creating an order

This chapter describes the full order capturing flow in ShopFlow 3.2.

## 2.1 Selecting the customer

1. Click **New Order**.
2. In the **Customer** field, search by customer name, e-mail or customer number.
3. Select the customer's saved delivery address from the **Address book**.
4. If the customer does not exist, click **Create customer** and fill in the mandatory fields.

## 2.2 Adding products to the cart

1. On the **Orders** dashboard, click **New Order**.
2. In the **Product search** field, type a product name or SKU.
3. Select the product from the result list.
4. Enter the quantity and click **Add to cart**.

Repeat these steps for each product. You can add up to 50 line items to one order. To apply a discount, see [Discount codes](#discount-codes).

## 2.3 Entering the delivery address

Fill in the delivery address fields:

| Field         | Mandatory |
|---------------|-----------|
| Recipient name| Yes       |
| Street        | Yes       |
| City          | Yes       |
| Postal code   | No        |
| Country       | Yes       |
| Phone number  | No        |

ShopFlow validates the address automatically. Orders with an unvalidated address can still be submitted.

## 2.4 Choosing the payment method

Select one of the available payment methods. For card payments taken over the phone, use the **Payment Terminal** add-on. See [Payment methods](payment-methods.md) for details.

## 2.5 Submitting the order

![](images/order-summary.png)

1. Review the order summary on the right side of the screen.
2. Check the delivery address and the total amount.
3. Accept the terms and conditions.
5. Click **Submit Order**.

ShopFlow assigns an order number in the format `ORD-123456` (six digits) and sets the status to **Submitted**.

The customer receives an order confirmation e-mail **within 5 minutes**.

When payment is confirmed, the status changes to **Confirmed** and the order is **automatically sent to the warehouse** for delivery. No further action is needed from the sales agent.

## 2.6 Cancelling an order

An order can be cancelled only while it has the status **Submitted**. Once the order is **Confirmed**, it can no longer be cancelled from the OMS; contact the warehouse instead.

## 2.7 Customer notification preferences

Customers can opt out of **all** e-mail notifications in their account settings. If a customer has opted out, no order confirmation is sent.
