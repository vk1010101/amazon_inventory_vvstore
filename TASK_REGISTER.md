# Task Register

- **2025-11-11 08:40 UTC** — Refined the admin console visuals: introduced a shared layout, refreshed dashboard/upload/bulk upload templates, modernized styling, and added a downloadable CSV template to standardize catalog imports.
- **2025-11-11 09:05 UTC** — Implemented transactional shopping workflows: established orders/order-item tables, added cart, checkout, and buy-now flows with inventory validation, refreshed storefront/product detail UI, and introduced a customer-facing cart experience.
- **2025-11-11 09:19 UTC** — Authored an initial requirements.txt enumerating core dependencies (Flask, pyodbc, SQLAlchemy, pandas) to simplify environment setup across systems.
- **2025-11-11 10:40 UTC** — Delivered supplier login base tied to the existing Admins table, introduced dedicated customer auth flows, enforced login guards across modules, launched advanced inventory analytics with 40% low-stock alerts, and overhauled the storefront with a pro search-first experience and account dropdowns for both roles.
