# Kisan Bazaar — SIH26132

## Current architecture
- **Frontend:** React + Vite + Tailwind CSS + Leaflet
- **Backend:** **Python + FastAPI** (Node/Express removed)
- **Database:** MongoDB
- **Realtime:** Socket.IO-compatible Python ASGI server
- **Cache:** Redis (optional but recommended)
- **Forecasting:** Python regression integrated into FastAPI
- **Payments:** Razorpay (optional configuration)
- **Notifications:** Twilio SMS/WhatsApp (optional; notification failures never block bids/orders)
- **Market data:** Government of India OGD / AGMARKNET resource, with last-successful Redis fallback

## Run backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Check: http://localhost:5000/api/health
Swagger: http://localhost:5000/docs

## Run frontend
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend: http://localhost:5173

## Important
1. Add a valid `MONGO_URI` and `JWT_SECRET`.
2. Add `DATA_GOV_IN_API_KEY` for live government market prices.
3. Redis is optional. If configured, the app caches successful market data and can continue showing the last successful government dataset during temporary upstream failures.
4. Set `NOTIFICATION_CHANNEL=realtime` during development. Twilio Trial restrictions should never make a bid fail.
5. Run `python backend/create_admin.py` after configuring admin environment variables if you need an admin account.

## Functional fixes included
- Buyer bid button validates input, shows loading state and confirms success.
- Farmer bid accept/reject flow is resilient to notification failures.
- Farmer and buyer refresh buttons now show state and recover from API failures.
- Orders refresh/payment/status actions have visible error handling.
- Market-price refresh and filter actions have loading/error states.
- Old service-worker cache is cleared in development; it no longer intercepts POST requests.
- Vite development HMR is disabled to avoid the previous stale `ws://localhost:5173` problem.
- Forecasting no longer needs a second Node service.

## Update: Profile & Profit Dashboard

- `GET /api/dashboard/stats` provides role-based dashboard statistics.
- `PUT /api/profile` updates name, phone, address, location and organization.
- React routes: `/profile` and `/profit-dashboard`.
- Farmer listings now include an owner-protected delete action with confirmation.

Run FastAPI backend:
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```
Run React frontend:
```powershell
cd frontend
npm install
npm run dev
```

## Scalable partner roles (added)
- Registration now supports `warehouse_owner` and `transporter` roles.
- Partner accounts start with `partnerApprovalStatus=pending`.
- Admin can review accounts through `GET /api/admin/partner-accounts` and update status using `PUT /api/admin/partner-accounts/{user_id}/status`.
- Approved warehouse owners can submit warehouses through `POST /api/partner/warehouses`.
- Approved transporters can submit services through `POST /api/partner/transporters`.
- Partner listings remain inactive until a separate admin listing approval process activates them.
- New frontend route: `/partner`.

This keeps the existing admin-managed workflow intact while adding a scalable, approval-based partner onboarding path.
