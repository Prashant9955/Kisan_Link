# Kisan Bazaar Python FastAPI Backend

The previous Node/Express backend has been replaced by Python + FastAPI. MongoDB remains the primary database.

## Run
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# fill MONGO_URI, JWT_SECRET and DATA_GOV_IN_API_KEY as needed
python run.py
```

API: http://localhost:5000/api/health
Docs: http://localhost:5000/docs

Optional: Redis, Razorpay and Twilio are non-blocking integrations. A Twilio failure must never make a successful bid fail.
