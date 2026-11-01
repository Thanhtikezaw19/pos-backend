# POS backend

REST API for a single-shop point-of-sale app. Built with Django 5.2, Django REST Framework, and MySQL.
The web UI is in the separate frontend repository (SvelteKit).

## Requirements

- Python 3.12 (for example, `pyenv install 3.12.12`)
- MySQL 8 or later

## Setup

1. Create the database and user in MySQL:

   ```sql
   CREATE DATABASE pos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'pos_user'@'localhost' IDENTIFIED BY 'your-password';
   GRANT ALL PRIVILEGES ON pos.* TO 'pos_user'@'localhost';
   -- Needed so `manage.py test` can create its test database:
   GRANT ALL PRIVILEGES ON test_pos.* TO 'pos_user'@'localhost';
   ```

2. Install dependencies and configure the environment:

   ```sh
   python3.12 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp .env.example .env
   ```

   In `.env`, set `SECRET_KEY` and `DATABASE_URL`:

   ```
   DATABASE_URL=mysql://pos_user:your-password@127.0.0.1:3306/pos
   ```

   URL-encode special characters in the password, for example `#` as `%23`. If `DATABASE_URL` is
   not set, the app uses a local SQLite file.

3. Create the tables and load demo data:

   ```sh
   .venv/bin/python manage.py migrate
   .venv/bin/python manage.py seed_demo
   ```

   `seed_demo` creates two users, 20 products, and 5 orders. Run it with `--reset` to delete all
   products and orders and load the demo data again.

4. Start the API on http://127.0.0.1:8000:

   ```sh
   .venv/bin/python manage.py runserver
   ```

Run the tests with `.venv/bin/python manage.py test`.

`CORS_ALLOWED_ORIGINS` in `.env` lists the frontend URLs allowed to call the API. The default
allows the SvelteKit dev server at `http://localhost:5173`.

## Demo logins

| Username | Password | Role |
|---|---|---|
| `admin` | `admin12345` | Admin: dashboard, products, categories, users, all orders, refunds |
| `cashier` | `cashier12345` | Cashier: sales and their own orders |

Change these passwords before using the app with real data.

## How it works

- **Sales:** `POST /api/orders/` runs in one database transaction. It locks the product rows,
  rejects the whole sale if any line is short on stock, then saves the order and deducts stock.
  The logic is in `sales/services.py`.
- **Order items** store the product name, SKU, and price at the time of sale, so later product
  edits don't change old receipts.
- **Refunds:** admins can refund a completed order once. Refunding returns the stock.
- **Products and users** can't be deleted once they have sales history. Deactivate them instead.
- **Money** is stored as `DECIMAL(12,2)` and sent as strings in the API.

## API

All endpoints are under `/api/` and need an `Authorization: Token <token>` header, except login.

| Method | Path | Access |
|---|---|---|
| POST | `auth/login/` | Anyone |
| POST | `auth/logout/` | Signed in |
| GET | `auth/me/` | Signed in |
| GET, POST, PATCH | `users/` | Admin |
| GET / POST, PATCH, DELETE | `categories/` | Read: staff. Write: admin |
| GET / POST, PATCH | `products/?search=&category=&active=` | Read: staff. Write: admin |
| GET | `orders/?date_from=&date_to=&status=` | Admin: all. Cashier: own |
| POST | `orders/` | Staff |
| GET | `orders/{id}/` | Admin: all. Cashier: own |
| POST | `orders/{id}/refund/` | Admin |
| GET | `dashboard/` | Admin |

## Not in v1

Barcode scanning, tax and discounts, multiple branches, online payment gateways, offline mode,
and customer loyalty.
