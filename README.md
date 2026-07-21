# TravelKart

TravelKart is a premium, modern e-commerce web application designed for browsing and purchasing travel gear and merchandise (luggage, bags, accessories, etc.).

---

## ✍️ Author
- **Ajay Sunil**

---

## 🛠️ Tech Stack

- **Frontend:** React (Vite), Redux Toolkit (state management), Vanilla CSS.
- **Backend:** Django, Django REST Framework (API).
- **Database:** PostgreSQL  

---

## 🚀 Getting Started

Follow these steps to run the application locally:

### 1. Backend Setup
1. Open a terminal and navigate to the `backend` directory.
2. Activate the Python virtual environment:
   - On Windows: `env\Scripts\activate`
   - On Mac/Linux: `source env/bin/activate`
3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the database migrations:
   ```bash
   python manage.py migrate
   ```
5. Run the development server:
   ```bash
   python manage.py runserver
   ```
   The backend API will run on `http://localhost:8000`.

### 2. Frontend Setup
1. Open a new terminal and navigate to the `frontend` directory.
2. Install the node modules:
   ```bash
   npm install
   ```
3. Run the frontend development server:
   ```bash
   npm run dev
   ```
   The user interface will be accessible on `http://localhost:5173`.

---

## ✨ Features

- **Product Catalog:** Categories, subcategories, brand filtering, sorting options (newest, price, name), and price filtering (incorporating discount offers).
- **Authentication:** Secure logins via JWT token rotation, Google OAuth integration, email verification with OTP, and forgot/reset password flows.
- **Wishlist:** Save favorite items, view them on a personal wishlist, and sort by price.
- **Shopping Cart & Checkout:** Manage items in a cart, apply coupons, and checkout with wallet/payment methods.
- **Admin Dashboard:** Control panel to manage users, products, categories, coupons, and view sales reports.
