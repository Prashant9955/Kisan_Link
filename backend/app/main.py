import os, math, hashlib, hmac, secrets, logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import bcrypt
import httpx
import razorpay
import socketio
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from pydantic import BaseModel, Field, EmailStr, field_validator
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from twilio.rest import Client

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('kisan-bazaar')

MONGO_URI=os.getenv('MONGO_URI','mongodb://127.0.0.1:27017')
DB_NAME=os.getenv('MONGO_DB_NAME','kisan_bazaar')
client=MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db=client[DB_NAME]
JWT_SECRET=os.getenv('JWT_SECRET','change-me-in-production')
JWT_ALG='HS256'
JWT_MIN=int(os.getenv('JWT_EXPIRES_MINUTES','10080'))
FRONTEND_URL=os.getenv('FRONTEND_URL','http://localhost:5173')

# Optional integrations
try:
    redis_client = __import__('redis').Redis.from_url(os.getenv('REDIS_URL'), decode_responses=True) if os.getenv('REDIS_URL') else None
except Exception:
    redis_client=None

sio=socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
fastapi_app=FastAPI(title='Kisan Bazaar API', version='2.0.0')
fastapi_app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in FRONTEND_URL.split(',')] if FRONTEND_URL else ['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app=socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


def oid(value):
    try: return ObjectId(str(value))
    except Exception: raise HTTPException(400,'Invalid id')

def clean(v):
    if isinstance(v,ObjectId): return str(v)
    if isinstance(v,datetime): return v.isoformat()
    if isinstance(v,list): return [clean(x) for x in v]
    if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
    return v

def public_user(u):
    if not u: return None
    return {'_id':str(u['_id']),'name':u['name'],'email':u['email'],'role':u['role'],'phone':u.get('phone',''),'location':u.get('location',''),'address':u.get('address',''),'organization':u.get('organization',''),'verified':bool(u.get('phoneVerified',False))}

def hash_password(p): return bcrypt.hashpw(p.encode(),bcrypt.gensalt()).decode()
def check_password(p,h): return bcrypt.checkpw(p.encode(),h.encode())
def token_for(u):
    return jwt.encode({'id':str(u['_id']),'role':u['role'],'exp':datetime.now(timezone.utc)+timedelta(minutes=JWT_MIN)},JWT_SECRET,algorithm=JWT_ALG)

def auth_user(request:Request):
    raw=request.headers.get('Authorization','')
    if not raw.startswith('Bearer '): raise HTTPException(401,'Not authorized, no token')
    try: payload=jwt.decode(raw.split(' ',1)[1],JWT_SECRET,algorithms=[JWT_ALG]); uid=payload.get('id')
    except JWTError: raise HTTPException(401,'Not authorized, token failed')
    u=db.users.find_one({'_id':oid(uid)})
    if not u: raise HTTPException(401,'User no longer exists')
    return u

def role_required(*roles):
    def dep(request:Request):
        u=auth_user(request)
        if u['role'] not in roles: raise HTTPException(403,f"Role '{u['role']}' is not allowed to access this route")
        return u
    return dep

async def notify(user,title,message):
    if not user:return
    payload={'title':title,'message':message,'at':datetime.now(timezone.utc).isoformat()}
    try: await sio.emit('notification',payload,room=f"user:{user['_id']}")
    except Exception as e: log.warning('Realtime notification failed: %s',e)
    channel=os.getenv('NOTIFICATION_CHANNEL','realtime')
    if channel not in ('sms','whatsapp','both'): return
    sid,auth=os.getenv('TWILIO_ACCOUNT_SID'),os.getenv('TWILIO_AUTH_TOKEN')
    if not sid or not auth or not user.get('phone'): return
    try:
        from twilio.rest import Client
        c=Client(sid,auth); body=f'{title}: {message}'
        if channel in ('sms','both') and os.getenv('TWILIO_SMS_FROM'):
            try: c.messages.create(body=body,from_=os.getenv('TWILIO_SMS_FROM'),to=user['phone'])
            except Exception as e: log.warning('Twilio SMS failed (non-blocking): %s',e)
        if channel in ('whatsapp','both') and os.getenv('TWILIO_WHATSAPP_FROM'):
            try:
                to=user['phone'] if str(user['phone']).startswith('whatsapp:') else f"whatsapp:{user['phone']}"
                c.messages.create(body=body,from_=os.getenv('TWILIO_WHATSAPP_FROM'),to=to)
            except Exception as e: log.warning('Twilio WhatsApp failed (non-blocking): %s',e)
    except Exception as e: log.warning('Twilio setup failed (non-blocking): %s',e)

async def emit_global(event,payload):
    try: await sio.emit(event,payload)
    except Exception as e: log.warning('Realtime global emit failed: %s',e)

# ---- Pydantic request models ----
class RegisterIn(BaseModel):
    name:str; email:EmailStr; password:str=Field(min_length=6); phone:str; role:str='farmer'; location:Optional[str]=None; organization:Optional[str]=None
class LoginIn(BaseModel): email:EmailStr; password:str
class ProfileUpdateIn(BaseModel):
    name:Optional[str]=None
    phone:Optional[str]=None
    address:Optional[str]=None
    location:Optional[str]=None
    organization:Optional[str]=None
class VerifyOTPIn(BaseModel): userId:str; otp:str=Field(min_length=6,max_length=6)
class ResendOTPIn(BaseModel): userId:str
class CropIn(BaseModel):
    name:str; category:str; quantity:float=Field(gt=0); unit:str='kg'; pricePerUnit:float=Field(gt=0); description:Optional[str]=None; mandi:Optional[str]=None; variety:Optional[str]=None; grade:Optional[str]=None; moisture:Optional[float]=Field(default=None, ge=0, le=100); packaging:Optional[str]=None
    @field_validator('unit')
    @classmethod
    def unit_ok(cls,v):
        if v not in ('kg','quintal','ton'): raise ValueError('Invalid unit')
        return v
class CropEdit(BaseModel): quantity:Optional[float]=None; unit:Optional[str]=None; pricePerUnit:Optional[float]=None; description:Optional[str]=None; mandi:Optional[str]=None; status:Optional[str]=None; variety:Optional[str]=None; grade:Optional[str]=None; moisture:Optional[float]=Field(default=None, ge=0, le=100); packaging:Optional[str]=None
class BidIn(BaseModel): cropId:str; amountPerUnit:float=Field(gt=0); quantity:float=Field(gt=0)
class MandiIn(BaseModel): name:str; district:str; state:str; longitude:Optional[float]=None; latitude:Optional[float]=None; coordinates:Optional[list[float]]=None
class TransporterIn(BaseModel): name:str; phone:str; vehicleType:str; baseRatePerKm:float=18; minFare:float=250; serviceArea:Optional[str]=None; active:bool=True
class StatusIn(BaseModel): status:str
class PaymentVerifyIn(BaseModel): razorpay_order_id:str; razorpay_payment_id:str; razorpay_signature:str
class RatingIn(BaseModel): score:int=Field(ge=1,le=5); comment:Optional[str]=''
class DisputeIn(BaseModel): reason:str; details:str
class StorageBookingIn(BaseModel):
    warehouseId:str
    orderId:Optional[str]=None
    quantity:float=Field(gt=0)
    startDate:str
    endDate:Optional[str]=None
    notes:Optional[str]=''
class WarehouseIn(BaseModel):
    name:str; location:str; capacity:float=Field(gt=0); availableCapacity:float=Field(ge=0); unit:str='quintal'; costPerUnit:float=Field(ge=0); contact:str=''; active:bool=True
class PartnerApprovalIn(BaseModel): status:str
class WarehouseOwnerWarehouseIn(WarehouseIn): pass
class TransporterSelfIn(TransporterIn): pass
class LogisticsBookingIn(BaseModel):
    orderId:str; transporterId:Optional[str]=None; pickupAddress:str; deliveryAddress:str; quantity:float=Field(gt=0)
class LogisticsStatusIn(BaseModel): status:str; latitude:Optional[float]=None; longitude:Optional[float]=None; note:Optional[str]=None

# ---- startup ----
@fastapi_app.on_event('startup')
def startup():
    try:
        client.admin.command('ping')
        db.users.create_index([('email',ASCENDING)],unique=True)
        db.mandis.create_index([('location','2dsphere')])
        db.payments.create_index([('order',ASCENDING)],unique=True)
        db.ratings.create_index([('order',ASCENDING),('from',ASCENDING)],unique=True)
        log.info('MongoDB connected: %s',DB_NAME)
    except Exception as e: log.error('MongoDB unavailable: %s',e)

@fastapi_app.get('/api/health')
def health():
    try: client.admin.command('ping'); mongo='ok'
    except Exception: mongo='down'
    redis='ok' if redis_client and _redis_ping() else 'optional/down'
    return {'status':'ok','service':'kisan-bazaar-api','database':mongo,'redis':redis,'backend':'python-fastapi'}
def _redis_ping():
    try: redis_client.ping(); return True
    except Exception:return False
@fastapi_app.get('/api/config/public')
def public_config(): return {'razorpayKeyId':os.getenv('RAZORPAY_KEY_ID') or None}

# ---- Auth / Twilio OTP ----
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))
OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '5'))


def twilio_is_configured():
    return all([
        os.getenv('TWILIO_ACCOUNT_SID'),
        os.getenv('TWILIO_AUTH_TOKEN'),
        os.getenv('TWILIO_SMS_FROM')
    ])


def send_twilio_otp(phone: str, otp: str):
    # Twilio is used only when all required environment variables are present.
    if not twilio_is_configured():
        return False

    try:
        twilio_client = Client(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        twilio_client.messages.create(
            body=f'Your Kisan Bazaar verification OTP is {otp}. It is valid for {OTP_EXPIRY_MINUTES} minutes.',
            from_=os.getenv('TWILIO_SMS_FROM'),
            to=phone
        )
        return True
    except Exception as exc:
        log.error('Twilio OTP sending failed: %s', exc)
        raise HTTPException(502, 'OTP could not be sent. Check Twilio configuration and phone number.')


def issue_otp(user):
    otp=f'{secrets.randbelow(1000000):06d}'
    now=datetime.now(timezone.utc)

    db.users.update_one(
        {'_id':user['_id']},
        {'$set':{
            'phoneVerified':False,
            'otpHash':hashlib.sha256(otp.encode()).hexdigest(),
            'otpExpiresAt':now+timedelta(minutes=OTP_EXPIRY_MINUTES),
            'otpAttempts':0,
            'updatedAt':now
        }}
    )

    sent = send_twilio_otp(user.get('phone', '').strip(), otp)

    # SHOW_DEV_OTP should be false in production.
    if sent:
        return None
    return otp

@fastapi_app.post('/api/auth/register',status_code=201)
def register(x:RegisterIn):
    email=str(x.email).lower()
    if db.users.find_one({'email':email}): raise HTTPException(400,'User already exists with this email')
    role=x.role if x.role in ('farmer','buyer','warehouse_owner','transporter') else 'farmer'
    u={'name':x.name.strip(),'email':email,'password':hash_password(x.password),'phone':x.phone.strip(),'role':role,'location':x.location,'organization':x.organization,'phoneVerified':False,'partnerApprovalStatus':'pending' if role in ('warehouse_owner','transporter') else 'not_required','documentVerificationStatus':'not_submitted','createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)}
    u['_id']=db.users.insert_one(u).inserted_id
    otp=issue_otp(u)
    response={'userId':str(u['_id']),'name':u['name'],'email':u['email'],'role':u['role'],'requiresPhoneVerification':True}
    if otp and os.getenv('SHOW_DEV_OTP','false').lower()=='true': response['devOtp']=otp
    return response

@fastapi_app.post('/api/auth/verify-phone')
def verify_phone(x:VerifyOTPIn):
    u=db.users.find_one({'_id':oid(x.userId)})
    if not u: raise HTTPException(404,'User not found')
    if u.get('phoneVerified'): return {'message':'Phone already verified','token':token_for(u),'user':public_user(u)}
    if u.get('otpAttempts',0)>=OTP_MAX_ATTEMPTS: raise HTTPException(429,'Too many incorrect attempts. Request a new OTP.')
    expires=u.get('otpExpiresAt')
    if not expires or expires < datetime.now(timezone.utc): raise HTTPException(400,'OTP expired. Request a new OTP.')
    if not hmac.compare_digest(u.get('otpHash',''),hashlib.sha256(x.otp.encode()).hexdigest()):
        db.users.update_one({'_id':u['_id']},{'$inc':{'otpAttempts':1}})
        raise HTTPException(400,'Invalid OTP')
    db.users.update_one({'_id':u['_id']},{'$set':{'phoneVerified':True,'updatedAt':datetime.now(timezone.utc)},'$unset':{'otpHash':'','otpExpiresAt':'','otpAttempts':''}})
    u['phoneVerified']=True
    return {'message':'Phone verified successfully','token':token_for(u),'user':public_user(u)}

@fastapi_app.post('/api/auth/resend-otp')
def resend_otp(x:ResendOTPIn):
    u=db.users.find_one({'_id':oid(x.userId)})
    if not u: raise HTTPException(404,'User not found')
    if u.get('phoneVerified'):
        return {'message':'Phone is already verified'}

    otp=issue_otp(u)
    response={'message':'OTP sent successfully' if otp is None else 'A new development OTP was generated'}
    if otp and os.getenv('SHOW_DEV_OTP','false').lower()=='true':
        response['devOtp']=otp
    return response

@fastapi_app.post('/api/auth/login')
def login(x: LoginIn):
    u = db.users.find_one({
        'email': str(x.email).lower()
    })

    if not u or not check_password(x.password, u['password']):
        raise HTTPException(
            status_code=401,
            detail='Invalid email or password'
        )

    # Phone verification only when enabled in .env
    require_verification = os.getenv(
        'REQUIRE_PHONE_VERIFICATION',
        'true'
    ).lower() == 'true'

    if require_verification and not u.get('phoneVerified', False):
        raise HTTPException(
            status_code=403,
            detail={
                'code': 'PHONE_NOT_VERIFIED',
                'userId': str(u['_id']),
                'message': 'Please verify your phone number before login.'
            }
        )

    return {
        '_id': str(u['_id']),
        'name': u['name'],
        'email': u['email'],
        'role': u['role'],
        'token': token_for(u)
    }

@fastapi_app.post('/api/auth/verification-document')
async def upload_verification_document(document:UploadFile=File(...), documentType:str=Form(...), u=Depends(auth_user)):
    allowed_types={'aadhaar','pan','gst','other'}
    allowed_ext={'.pdf','.jpg','.jpeg','.png'}
    filename=(document.filename or '').lower()
    ext=os.path.splitext(filename)[1]
    if documentType.lower() not in allowed_types: raise HTTPException(400,'Invalid document type')
    if ext not in allowed_ext: raise HTTPException(400,'Only PDF, JPG, JPEG and PNG files are allowed')
    content=await document.read()
    if len(content)>5*1024*1024: raise HTTPException(413,'Document must be smaller than 5 MB')
    record={'userId':u['_id'],'documentType':documentType.lower(),'filename':document.filename,'contentType':document.content_type,'content':content,'status':'pending','createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)}
    db.verification_documents.delete_many({'userId':u['_id'],'documentType':documentType.lower(),'status':'pending'})
    db.verification_documents.insert_one(record)
    db.users.update_one({'_id':u['_id']},{'$set':{'documentVerificationStatus':'pending','updatedAt':datetime.now(timezone.utc)}})
    return {'message':'Document submitted for review','status':'pending','documentType':documentType.lower()}

@fastapi_app.get('/api/auth/verification-status')
def verification_status(u=Depends(auth_user)):
    docs=[]
    for d in db.verification_documents.find({'userId':u['_id']},{'content':0}): docs.append(clean(d))
    return {'phoneVerified':bool(u.get('phoneVerified',False)),'documentVerificationStatus':u.get('documentVerificationStatus','not_submitted'),'documents':docs}

@fastapi_app.get('/api/admin/verification-documents')
def admin_verification_documents(u=Depends(role_required('admin'))):
    out=[]
    for d in db.verification_documents.find({}, {'content':0}).sort('createdAt', DESCENDING):
        item=clean(d)
        item['user']=public_user(db.users.find_one({'_id':d['userId']}))
        out.append(item)
    return out

@fastapi_app.patch('/api/admin/verification-documents/{document_id}')
def review_verification_document(document_id:str, x:StatusIn, u=Depends(role_required('admin'))):
    if x.status not in ('verified','rejected','pending'):
        raise HTTPException(400,'Status must be pending, verified or rejected')
    d=db.verification_documents.find_one({'_id':oid(document_id)})
    if not d: raise HTTPException(404,'Verification document not found')
    now=datetime.now(timezone.utc)
    db.verification_documents.update_one({'_id':d['_id']},{'$set':{'status':x.status,'reviewedBy':u['_id'],'updatedAt':now}})
    db.users.update_one({'_id':d['userId']},{'$set':{'documentVerificationStatus':x.status,'updatedAt':now}})
    return {'message':'Verification status updated','status':x.status}
@fastapi_app.get('/api/auth/me')
def me(u=Depends(auth_user)): return public_user(u)

# ---- profile and dashboard ----
@fastapi_app.put('/api/profile')
def update_profile(x:ProfileUpdateIn,u=Depends(auth_user)):
    patch={k:v.strip() if isinstance(v,str) else v for k,v in x.model_dump().items() if v is not None}
    if not patch: return public_user(u)
    patch['updatedAt']=datetime.now(timezone.utc)
    db.users.update_one({'_id':u['_id']},{'$set':patch})
    u.update(patch)
    return public_user(u)

@fastapi_app.get('/api/dashboard/stats')
def dashboard_stats(u=Depends(auth_user)):
    role=u['role']
    if role=='farmer':
        crops=list(db.crops.find({'farmer':u['_id']}))
        bids=list(db.bids.find({'farmer':u['_id']}))
        orders=list(db.orders.find({'farmer':u['_id']}))
        revenue=sum(float(o.get('totalPrice',0)) for o in orders if o.get('status')!='cancelled')
        return {'role':role,'revenue':round(revenue,2),'totalOrders':len(orders),'totalCrops':len(crops),'totalBids':len(bids),'acceptedBids':sum(1 for b in bids if b.get('status')=='accepted'),'activeCrops':sum(1 for c in crops if c.get('status')=='available'),'priceSignals':[]}
    if role=='buyer':
        bids=list(db.bids.find({'buyer':u['_id']}))
        orders=list(db.orders.find({'buyer':u['_id']}))
        spending=sum(float(o.get('totalPrice',0)) for o in orders if o.get('status')!='cancelled')
        return {'role':role,'spending':round(spending,2),'totalOrders':len(orders),'totalCrops':0,'totalBids':len(bids),'acceptedBids':sum(1 for b in bids if b.get('status')=='accepted'),'activeCrops':0,'priceSignals':[]}
    return {'role':role,'revenue':0,'spending':0,'totalOrders':db.orders.count_documents({}),'totalCrops':db.crops.count_documents({}),'totalBids':db.bids.count_documents({}),'acceptedBids':db.bids.count_documents({'status':'accepted'}),'activeCrops':db.crops.count_documents({'status':'available'}),'priceSignals':[]}

# ---- crops ----
def crop_out(c,full=False):
    x=clean(c)
    if full:
        x['farmer']=public_user(db.users.find_one({'_id':c['farmer']}))
        if c.get('mandi'):
            x['mandi']=clean(db.mandis.find_one({'_id':c['mandi']}))
    return x
@fastapi_app.get('/api/crops')
def crops(category:Optional[str]=None,search:Optional[str]=None,minPrice:Optional[float]=None,maxPrice:Optional[float]=None):
    f={'status':'available'}
    if category:f['category']=category
    if search:f['name']={'$regex':search,'$options':'i'}
    if minPrice is not None or maxPrice is not None:
        f['pricePerUnit']={}
        if minPrice is not None:f['pricePerUnit']['$gte']=minPrice
        if maxPrice is not None:f['pricePerUnit']['$lte']=maxPrice
    return [crop_out(c,True) for c in db.crops.find(f).sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/crops/mine')
def my_crops(u=Depends(role_required('farmer'))): return [crop_out(c) for c in db.crops.find({'farmer':u['_id']}).sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/crops/{cid}')
def crop(cid:str):
    c=db.crops.find_one({'_id':oid(cid)})
    if not c: raise HTTPException(404,'Crop not found')
    return crop_out(c,True)
@fastapi_app.post('/api/crops',status_code=201)
def create_crop(x:CropIn,u=Depends(role_required('farmer'))):
    c=x.model_dump(); c['farmer']=u['_id']; c['mandi']=oid(c['mandi']) if c.get('mandi') else None; c.update(createdAt=datetime.now(timezone.utc),updatedAt=datetime.now(timezone.utc),status='available')
    c['_id']=db.crops.insert_one(c).inserted_id; return crop_out(c)
@fastapi_app.put('/api/crops/{cid}')
def update_crop(cid:str,x:CropEdit,u=Depends(role_required('farmer'))):
    c=db.crops.find_one({'_id':oid(cid)})
    if not c:raise HTTPException(404,'Crop not found')
    if c['farmer']!=u['_id']:raise HTTPException(403,'Not authorized to update this crop')
    patch={k:v for k,v in x.model_dump().items() if v is not None}
    if 'mandi' in patch:patch['mandi']=oid(patch['mandi']) if patch['mandi'] else None
    patch['updatedAt']=datetime.now(timezone.utc);db.crops.update_one({'_id':c['_id']},{'$set':patch});c.update(patch);return crop_out(c)
@fastapi_app.delete('/api/crops/{cid}')
def delete_crop(cid:str,u=Depends(role_required('farmer','admin'))):
    c=db.crops.find_one({'_id':oid(cid)})
    if not c:raise HTTPException(404,'Crop not found')
    if u['role']!='admin' and c['farmer']!=u['_id']:raise HTTPException(403,'Not authorized to delete this crop')
    db.crops.delete_one({'_id':c['_id']});return {'message':'Crop removed'}

# ---- mandis ----
def mandi_out(m):return clean(m)
@fastapi_app.get('/api/mandis')
def mandis():return [mandi_out(x) for x in db.mandis.find().sort('name',ASCENDING)]
@fastapi_app.get('/api/mandis/nearby')
def nearby(lng:float,lat:float,maxDistanceKm:float=50):
    rows=db.mandis.find({'location':{'$near':{'$geometry':{'type':'Point','coordinates':[lng,lat]},'$maxDistance':maxDistanceKm*1000}}})
    return [mandi_out(x) for x in rows]
@fastapi_app.post('/api/mandis',status_code=201)
def create_mandi(x:MandiIn,u=Depends(role_required('admin'))):
    coords=x.coordinates if x.coordinates else ([x.longitude,x.latitude] if x.longitude is not None and x.latitude is not None else None)
    if not coords or len(coords)!=2:raise HTTPException(400,'Coordinates are required')
    m={'name':x.name,'district':x.district,'state':x.state,'location':{'type':'Point','coordinates':coords},'createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)};m['_id']=db.mandis.insert_one(m).inserted_id;return clean(m)

# ---- market data / redis fallback ----
DATASET=os.getenv('DATA_GOV_RESOURCE_ID','9ef84268-d588-465a-a308-a864a43d0070')
def norm_record(r):
    def num(*keys):
        for key in keys:
            value = r.get(key)

            if value is None:
                continue

            try:
                # Handles values like "1,250" and "1250"
                value = str(value).replace(',', '').strip()
                return float(value)
            except (ValueError, TypeError):
                continue

        return None

    modal = num(
        'modal_price',
        'Modal_Price',
        'modalPrice',
        'Modal Price'
    )

    if modal is None:
        return None

    return {
        'state': r.get('state') or r.get('State'),
        'district': r.get('district') or r.get('District'),
        'market': r.get('market') or r.get('Market'),
        'commodity': r.get('commodity') or r.get('Commodity'),
        'variety': r.get('variety') or r.get('Variety'),
        'grade': r.get('grade') or r.get('Grade'),
        'arrival_date': (
            r.get('arrival_date')
            or r.get('Arrival_Date')
            or r.get('Arrival Date')
            or r.get('date')
        ),
        'min_price': num(
            'min_price',
            'Min_Price',
            'minPrice',
            'Min Price'
        ),
        'max_price': num(
            'max_price',
            'Max_Price',
            'maxPrice',
            'Max Price'
        ),
        'modal_price': modal
    }
def cache_get(key):
    if not redis_client or not _redis_ping():return None
    try:
        import json; v=redis_client.get(key); return json.loads(v) if v else None
    except:return None
def cache_set(key,val,ttl):
    if not redis_client:return
    try:
        import json;redis_client.setex(key,ttl,json.dumps(val,default=str))
    except Exception as e:log.warning('Redis cache write failed: %s',e)
async def live_market(params):
    import urllib.parse
    import json

    api_key = os.getenv('DATA_GOV_IN_API_KEY')

    # Cache key filters ke basis par banegi
    filter_params = {
        key: params.get(key)
        for key in ('commodity', 'state', 'district', 'market')
    }

    limit = min(int(params.get('limit', 100)), 10000)

    q = {
        'api-key': api_key,
        'format': 'json',
        'limit': str(limit)
    }

    for key in ('commodity', 'state', 'district', 'market'):
        if params.get(key):
            q[f'filters[{key}]'] = params[key]

    cache_key = (
        'market:' +
        hashlib.sha256(
            urllib.parse.urlencode(q).encode()
        ).hexdigest()
    )

    last_success_key = (
        'market:last-success:' +
        hashlib.sha256(
            str(sorted(filter_params.items())).encode()
        ).hexdigest()
    )

    # --------------------------------------------------
    # 1. GOVERNMENT API FIRST
    # --------------------------------------------------

    try:
        if not api_key:
            raise RuntimeError(
                'DATA_GOV_IN_API_KEY is missing'
            )

        headers = {
            'User-Agent': 'KisanBazaar/1.0',
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=15.0,
                read=45.0,
                write=15.0,
                pool=15.0
            ),
            headers=headers,
            follow_redirects=True,
            trust_env=False
        ) as hc:

            response = await hc.get(
                f'https://api.data.gov.in/resource/{DATASET}',
                params=q
            )

            response.raise_for_status()
            data = response.json()

        records = []

        for raw_record in data.get('records', []):
            record = norm_record(raw_record)

            if record is not None:
                records.append(record)

        result = {
            'title': data.get('title'),
            'total': data.get('total', len(records)),
            'records': records
        }

        # --------------------------------------------------
        # 2. SAVE SUCCESSFUL LIVE DATA TO REDIS
        # --------------------------------------------------

        cache_set(
            cache_key,
            result,
            int(os.getenv(
                'MARKET_CACHE_TTL_SECONDS',
                '300'
            ))
        )

        cache_set(
            last_success_key,
            result,
            int(os.getenv(
                'MARKET_LAST_SUCCESS_TTL_SECONDS',
                '86400'
            ))
        )

        log.info(
            'Government market API successful: %s records',
            len(records)
        )

        return {
            **result,
            'cache': 'live'
        }

    # --------------------------------------------------
    # 3. GOVERNMENT API FAILS → REDIS FALLBACK
    # --------------------------------------------------

    except Exception as error:

        log.warning(
            'Government market API failed: %s',
            error
        )

        fallback = cache_get(last_success_key)

        if fallback:
            return {
                **fallback,
                'cache': 'last-success',
                'warning': (
                    'Government market API temporarily unavailable; '
                    'showing the last successful government dataset.'
                )
            }

        if isinstance(error, httpx.HTTPStatusError):
            raise HTTPException(
                status_code=error.response.status_code,
                detail=(
                    'Government market-price API failed: '
                    f'{error.response.status_code} '
                    f'{error.response.text[:300]}'
                )
            )

        raise HTTPException(
            status_code=502,
            detail=(
                'Government market API unavailable: '
                f'{str(error)[:200]}'
            )
        )
@fastapi_app.get('/api/market-prices')
async def market_prices(
    commodity: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None,
    limit: int = 100
):
    return {
        'source': 'Government of India OGD / AGMARKNET',
        **(
            await live_market({
                'commodity': commodity,
                'state': state,
                'district': district,
                'market': market,
                'limit': limit
            })
        )
    }

# ---- forecasting ----

def parse_market_date(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    text = str(value).strip()

    formats = [
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%d/%m/%Y %H:%M:%S'
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return datetime.min.replace(tzinfo=timezone.utc)


def regression_forecast(prices):
    if len(prices) < 3:
        raise ValueError(
            'At least 3 prices are required for forecasting'
        )

    n = len(prices)

    xs = list(range(n))

    mean_x = sum(xs) / n
    mean_y = sum(prices) / n

    denominator = sum(
        (x - mean_x) ** 2
        for x in xs
    ) or 1

    slope = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(xs, prices)
    ) / denominator

    intercept = mean_y - slope * mean_x

    predicted_price = intercept + slope * n

    predictions = [
        intercept + slope * x
        for x in xs
    ]

    squared_error = sum(
        (actual - predicted) ** 2
        for actual, predicted in zip(prices, predictions)
    )

    total_variance = sum(
        (price - mean_y) ** 2
        for price in prices
    )

    r2 = 1 - (
        squared_error / (total_variance or 1)
    )

    if slope > 0.5:
        trend = 'rising'
    elif slope < -0.5:
        trend = 'falling'
    else:
        trend = 'stable'

    return {
        'available': True,
        'predicted_price': round(
            max(0, predicted_price),
            2
        ),
        'last_price': round(prices[-1], 2),
        'trend': trend,
        'slope': round(slope, 4),
        'observations': n,
        'r2': round(r2, 3)
    }


@fastapi_app.get('/api/forecast/{crop_name}')
async def forecast(
    crop_name: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None
):
    data = await live_market({
        'commodity': crop_name,
        'state': state,
        'district': district,
        'market': market,
        'limit': 100
    })

    # Date-wise sorting: oldest → newest
    records = sorted(
        data.get('records', []),
        key=lambda record: parse_market_date(
            record.get('arrival_date')
        )
    )

    valid_records = [
        record
        for record in records
        if isinstance(
            record.get('modal_price'),
            (int, float)
        )
        and record.get('modal_price') > 0
    ]

    prices = [
        record['modal_price']
        for record in valid_records
    ]

    if len(prices) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f'At least 3 valid market observations '
                f'are required to forecast {crop_name}. '
                f'Found: {len(prices)}'
            )
        )

    forecast_result = regression_forecast(prices)

    response = {
        **forecast_result,
        'source': (
            data.get('title')
            or 'Government of India OGD / AGMARKNET'
        ),
        'history': [
            {
                'date': record.get('arrival_date'),
                'price': record.get('modal_price')
            }
            for record in valid_records
        ],
        'dataCache': data.get('cache')
    }

    if data.get('warning'):
        response['warning'] = data['warning']

    return response

# ---- bids ----
def bid_out(b):
    x=clean(b); buyer=db.users.find_one({'_id':b['buyer']}); x['buyer']=public_user(buyer);return x
@fastapi_app.post('/api/bids',status_code=201)
async def place_bid(x:BidIn,u=Depends(role_required('buyer'))):
    c=db.crops.find_one({'_id':oid(x.cropId)})
    if not c or c.get('status')!='available':raise HTTPException(404,'Crop not available for bidding')
    if c['farmer']==u['_id']:raise HTTPException(400,'You cannot bid on your own crop')
    if x.quantity>c['quantity']:raise HTTPException(400,f"Bid quantity cannot exceed available crop quantity ({c['quantity']} {c['unit']})")
    b={'crop':c['_id'],'buyer':u['_id'],'farmer':c['farmer'],'amountPerUnit':x.amountPerUnit,'quantity':x.quantity,'status':'pending','createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)};b['_id']=db.bids.insert_one(b).inserted_id
    farmer=db.users.find_one({'_id':c['farmer']});await notify(farmer,'New bid received',f"A buyer placed a bid of ₹{x.amountPerUnit:g} per {c['unit']} for {x.quantity:g} {c['unit']} of {c['name']}.");await emit_global('market:update',{'type':'bid-created','cropId':str(c['_id'])})
    return {'success':True,'message':'Bid placed successfully','bid':bid_out(b)}
@fastapi_app.get('/api/bids/crop/{cid}')
def bids_crop(cid:str,u=Depends(role_required('farmer'))):return [bid_out(b) for b in db.bids.find({'crop':oid(cid)}).sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/bids/mine')
def bids_mine(u=Depends(role_required('buyer'))):
    rows=[]
    for b in db.bids.find({'buyer':u['_id']}).sort('createdAt',DESCENDING):
        x=clean(b);c=db.crops.find_one({'_id':b['crop']});x['crop']=clean({k:c[k] for k in ('_id','name','pricePerUnit','unit')}) if c else None;rows.append(x)
    return rows
@fastapi_app.put('/api/bids/{bid_id}/accept')
async def accept_bid(bid_id:str,u=Depends(role_required('farmer'))):
    b=db.bids.find_one({'_id':oid(bid_id)})
    if not b:raise HTTPException(404,'Bid not found')
    if b['farmer']!=u['_id']:raise HTTPException(403,'Not authorized to accept this bid')
    if b['status']!='pending':raise HTTPException(400,'Only pending bids can be accepted')
    c=db.crops.find_one({'_id':b['crop']})
    if not c or c.get('status')!='available':raise HTTPException(400,'Crop is no longer available')
    db.bids.update_one({'_id':b['_id']},{'$set':{'status':'accepted','updatedAt':datetime.now(timezone.utc)}})
    db.bids.update_many({'crop':b['crop'],'_id':{'$ne':b['_id']},'status':'pending'},{'$set':{'status':'rejected','updatedAt':datetime.now(timezone.utc)}})
    db.crops.update_one({'_id':c['_id']},{'$set':{'status':'reserved','updatedAt':datetime.now(timezone.utc)}})
    total=b['amountPerUnit']*b['quantity']; earning=round(total*float(os.getenv('MIDDLEMAN_MARGIN_RATE','0.20')),2)
    o={'bid':b['_id'],'crop':b['crop'],'buyer':b['buyer'],'farmer':b['farmer'],'quantity':b['quantity'],'totalPrice':total,'estimatedMiddlemanEarning':earning,'savings':earning,'status':'confirmed','createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)};o['_id']=db.orders.insert_one(o).inserted_id
    buyer=db.users.find_one({'_id':b['buyer']});await notify(buyer,'Bid accepted',f'Your bid for ₹{total:g} has been accepted. Order {o["_id"]} is ready.');await notify(u,'Order created',f'Order {o["_id"]} was created from the accepted bid.');await emit_global('market:update',{'type':'order-created','orderId':str(o['_id'])})
    b['status']='accepted';return {'bid':bid_out(b),'order':clean(o)}
@fastapi_app.put('/api/bids/{bid_id}/reject')
async def reject_bid(bid_id:str,u=Depends(role_required('farmer'))):
    b=db.bids.find_one({'_id':oid(bid_id)})
    if not b:raise HTTPException(404,'Bid not found')
    if b['farmer']!=u['_id']:raise HTTPException(403,'Not authorized to reject this bid')
    db.bids.update_one({'_id':b['_id']},{'$set':{'status':'rejected','updatedAt':datetime.now(timezone.utc)}});b['status']='rejected';await notify(db.users.find_one({'_id':b['buyer']}),'Bid rejected','Your bid was rejected by the farmer.');return bid_out(b)

# ---- orders ----
def order_out(o,role):
    x=clean(o);x['crop']=clean(db.crops.find_one({'_id':o['crop']})) if db.crops.find_one({'_id':o['crop']}) else None
    other='buyer' if role=='farmer' else 'farmer';u=db.users.find_one({'_id':o[other]});x[other]=public_user(u);return x
@fastapi_app.get('/api/orders/buyer')
def orders_buyer(u=Depends(role_required('buyer'))):return [order_out(o,'buyer') for o in db.orders.find({'buyer':u['_id']}).sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/orders/farmer')
def orders_farmer(u=Depends(role_required('farmer'))):return [order_out(o,'farmer') for o in db.orders.find({'farmer':u['_id']}).sort('createdAt',DESCENDING)]
@fastapi_app.put('/api/orders/{order_id}/status')
async def update_order(order_id:str,x:StatusIn,u=Depends(role_required('farmer'))):
    allowed={'confirmed','in-transit','delivered','cancelled'}
    if x.status not in allowed:raise HTTPException(400,'Invalid order status')
    o=db.orders.find_one({'_id':oid(order_id)})
    if not o:raise HTTPException(404,'Order not found')
    if o['farmer']!=u['_id']:raise HTTPException(403,'Not authorized to update this order')
    db.orders.update_one({'_id':o['_id']},{'$set':{'status':x.status,'updatedAt':datetime.now(timezone.utc)}});o['status']=x.status
    if x.status=='delivered':db.crops.update_one({'_id':o['crop']},{'$set':{'status':'sold','updatedAt':datetime.now(timezone.utc)}})
    return order_out(o,'farmer')

# ---- payments ----
def rp_client():
    if not os.getenv('RAZORPAY_KEY_ID') or not os.getenv('RAZORPAY_KEY_SECRET'):raise HTTPException(503,'Razorpay is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.')
    return razorpay.Client(auth=(os.getenv('RAZORPAY_KEY_ID'),os.getenv('RAZORPAY_KEY_SECRET')))
@fastapi_app.post('/api/payments/order/{order_id}',status_code=201)
def create_payment(order_id:str,u=Depends(role_required('buyer'))):
    o=db.orders.find_one({'_id':oid(order_id)})
    if not o:raise HTTPException(404,'Order not found')
    if o['buyer']!=u['_id']:raise HTTPException(403,'Only the buyer can pay')
    p=db.payments.find_one({'order':o['_id']})
    if p and p.get('status')=='success':return clean(p)
    provider=rp_client().order.create({'amount':round(o['totalPrice']*100),'currency':'INR','receipt':f"order_{o['_id']}",'payment_capture':1})
    pdata={'order':o['_id'],'payer':u['_id'],'amount':o['totalPrice'],'method':'RAZORPAY_UPI','status':'created','providerOrderId':provider['id'],'createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)}
    if p:db.payments.update_one({'_id':p['_id']},{'$set':pdata});pdata['_id']=p['_id']
    else:pdata['_id']=db.payments.insert_one(pdata).inserted_id
    return {'payment':clean(pdata),'razorpay':{'orderId':provider['id'],'amount':provider['amount'],'currency':provider['currency'],'keyId':os.getenv('RAZORPAY_KEY_ID')}}
@fastapi_app.post('/api/payments/verify')
def verify_payment(x:PaymentVerifyIn,u=Depends(role_required('buyer'))):
    p=db.payments.find_one({'providerOrderId':x.razorpay_order_id})
    if not p:raise HTTPException(404,'Payment not found')
    if p['payer']!=u['_id']:raise HTTPException(403,'Not authorized')
    secret=os.getenv('RAZORPAY_KEY_SECRET','');expected=hmac.new(secret.encode(),f'{x.razorpay_order_id}|{x.razorpay_payment_id}'.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,x.razorpay_signature):raise HTTPException(400,'Invalid payment signature')
    db.payments.update_one({'_id':p['_id']},{'$set':{'status':'success','providerPaymentId':x.razorpay_payment_id,'transactionId':x.razorpay_payment_id,'updatedAt':datetime.now(timezone.utc)}});p.update(status='success',providerPaymentId=x.razorpay_payment_id,transactionId=x.razorpay_payment_id);return clean(p)
@fastapi_app.get('/api/payments/order/{order_id}')
def get_payment(order_id:str,u=Depends(auth_user)):return clean(db.payments.find_one({'order':oid(order_id)})) if db.payments.find_one({'order':oid(order_id)}) else None

# ---- ratings/disputes ----
@fastapi_app.post('/api/ratings/order/{order_id}',status_code=201)
def create_rating(order_id:str,x:RatingIn,u=Depends(auth_user)):
    o=db.orders.find_one({'_id':oid(order_id)})
    if not o:raise HTTPException(404,'Order not found')
    if o['status']!='delivered':raise HTTPException(400,'Rating is available after delivery')
    to=o['farmer'] if o['buyer']==u['_id'] else o['buyer'] if o['farmer']==u['_id'] else None
    if not to:raise HTTPException(403,'Not part of this order')
    if db.ratings.find_one({'order':o['_id'],'from':u['_id']}):raise HTTPException(409,'You already rated this order')
    r={'order':o['_id'],'from':u['_id'],'to':to,'score':x.score,'comment':x.comment,'createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)};r['_id']=db.ratings.insert_one(r).inserted_id;return clean(r)
@fastapi_app.get('/api/ratings/mine')
def ratings_mine(u=Depends(auth_user)):return [clean(r) for r in db.ratings.find({'from':u['_id']}).sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/ratings/user/{user_id}')
def ratings_user(user_id:str):
    rows=list(db.ratings.find({'to':oid(user_id)}));avg=sum(r['score'] for r in rows)/len(rows) if rows else 0;return {'count':len(rows),'average':round(avg,1),'ratings':[clean(r) for r in rows]}
@fastapi_app.post('/api/disputes/order/{order_id}',status_code=201)
def create_dispute(order_id:str,x:DisputeIn,u=Depends(auth_user)):
    o=db.orders.find_one({'_id':oid(order_id)})
    if not o:raise HTTPException(404,'Order not found')
    if u['_id'] not in (o['buyer'],o['farmer']):raise HTTPException(403,'Not part of this order')
    d={'order':o['_id'],'openedBy':u['_id'],'reason':x.reason,'details':x.details,'status':'open','createdAt':datetime.now(timezone.utc),'updatedAt':datetime.now(timezone.utc)};d['_id']=db.disputes.insert_one(d).inserted_id;return clean(d)
@fastapi_app.get('/api/disputes/mine')
def disputes_mine(u=Depends(auth_user)):return [clean(d) for d in db.disputes.find({'openedBy':u['_id']}).sort('createdAt',DESCENDING)]

# ---- Scalable partner onboarding ----
@fastapi_app.get('/api/partners/me')
def partner_profile(u=Depends(role_required('warehouse_owner','transporter'))):
    return public_user(u) | {'partnerApprovalStatus':u.get('partnerApprovalStatus','pending')}

@fastapi_app.post('/api/partner/warehouses', status_code=201)
def partner_create_warehouse(x:WarehouseOwnerWarehouseIn, u=Depends(role_required('warehouse_owner'))):
    if u.get('partnerApprovalStatus') != 'approved': raise HTTPException(403,'Partner account is awaiting admin approval')
    d=x.model_dump(); d.update(owner=u['_id'], active=False, approvalStatus='pending', createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
    d['_id']=db.warehouses.insert_one(d).inserted_id
    return clean(d)

@fastapi_app.post('/api/partner/transporters', status_code=201)
def partner_create_transporter(x:TransporterSelfIn, u=Depends(role_required('transporter'))):
    if u.get('partnerApprovalStatus') != 'approved': raise HTTPException(403,'Partner account is awaiting admin approval')
    d=x.model_dump(); d.update(owner=u['_id'], active=False, approvalStatus='pending', createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
    d['_id']=db.transporters.insert_one(d).inserted_id
    return clean(d)

@fastapi_app.get('/api/admin/partner-accounts')
def admin_partner_accounts(u=Depends(role_required('admin'))):
    return [public_user(x) | {'partnerApprovalStatus':x.get('partnerApprovalStatus','pending')} for x in db.users.find({'role':{'$in':['warehouse_owner','transporter']}})]

@fastapi_app.put('/api/admin/partner-accounts/{user_id}/status')
def admin_partner_status(user_id:str, x:PartnerApprovalIn, u=Depends(role_required('admin'))):
    if x.status not in ('approved','rejected','pending'): raise HTTPException(400,'Invalid approval status')
    r=db.users.update_one({'_id':oid(user_id),'role':{'$in':['warehouse_owner','transporter']}},{'$set':{'partnerApprovalStatus':x.status,'updatedAt':datetime.now(timezone.utc)}})
    if not r.matched_count: raise HTTPException(404,'Partner account not found')
    return {'message':'Partner status updated','status':x.status}

# ---- Step 6: warehouse / storage booking ----
@fastapi_app.get('/api/storage/warehouses')
def storage_warehouses(location:Optional[str]=None, u=Depends(auth_user)):
    query={'active':True}
    rows=[]
    for w in db.warehouses.find(query).sort('name',ASCENDING):
        if location and location.lower() not in str(w.get('location','')).lower():
            continue
        rows.append(clean(w))
    return rows

@fastapi_app.post('/api/storage/warehouses', status_code=201)
def create_storage_warehouse(x:WarehouseIn, u=Depends(role_required('admin'))):
    d=x.model_dump(); d.update(approvalStatus='approved', createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
    d['_id']=db.warehouses.insert_one(d).inserted_id
    return clean(d)

@fastapi_app.post('/api/storage/bookings', status_code=201)
def create_storage_booking(x:StorageBookingIn, u=Depends(auth_user)):
    w=db.warehouses.find_one({'_id':oid(x.warehouseId),'active':True})
    if not w: raise HTTPException(404,'Warehouse not found')
    if float(w.get('availableCapacity',0)) < x.quantity: raise HTTPException(400,'Insufficient warehouse capacity')
    order=None
    if x.orderId:
        order=db.orders.find_one({'_id':oid(x.orderId)})
        if not order or u['_id'] not in (order.get('buyer'),order.get('farmer')): raise HTTPException(403,'Not part of this order')
    now=datetime.now(timezone.utc)
    d={'warehouse':w['_id'],'bookedBy':u['_id'],'order':order['_id'] if order else None,'quantity':x.quantity,'startDate':x.startDate,'endDate':x.endDate,'notes':x.notes,'status':'requested','createdAt':now,'updatedAt':now}
    d['_id']=db.storage_bookings.insert_one(d).inserted_id
    db.warehouses.update_one({'_id':w['_id']},{'$inc':{'availableCapacity':-x.quantity},'$set':{'updatedAt':now}})
    return clean(d)

@fastapi_app.get('/api/storage/bookings/mine')
def storage_bookings_mine(u=Depends(auth_user)):
    rows=[]
    for b in db.storage_bookings.find({'bookedBy':u['_id']}).sort('createdAt',DESCENDING):
        x=clean(b); w=db.warehouses.find_one({'_id':b['warehouse']}); x['warehouseDetails']=clean(w); rows.append(x)
    return rows

@fastapi_app.put('/api/storage/bookings/{booking_id}/status')
def update_storage_booking(booking_id:str, x:StatusIn, u=Depends(auth_user)):
    b=db.storage_bookings.find_one({'_id':oid(booking_id)})
    if not b: raise HTTPException(404,'Storage booking not found')
    if b['bookedBy']!=u['_id'] and u['role']!='admin': raise HTTPException(403,'Not authorized')
    allowed={'requested','confirmed','stored','released','cancelled'}
    if x.status not in allowed: raise HTTPException(400,'Invalid storage status')
    db.storage_bookings.update_one({'_id':b['_id']},{'$set':{'status':x.status,'updatedAt':datetime.now(timezone.utc)}})
    b['status']=x.status; return clean(b)

# ---- logistics ----
def hav(lat1,lon1,lat2,lon2):
    R=6371; p=math.pi/180; a=math.sin((lat2-lat1)*p/2)**2+math.cos(lat1*p)*math.cos(lat2*p)*math.sin((lon2-lon1)*p/2)**2;return R*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
@fastapi_app.get('/api/logistics/transporters')
def transporter_list():return [clean(x) for x in db.transporters.find({'active':True}).sort('baseRatePerKm',ASCENDING)]
@fastapi_app.get('/api/logistics/estimate')
def logistics_estimate(mandiId:str,fromLat:float,fromLng:float,quantity:float=1,u=Depends(auth_user)):
    m=db.mandis.find_one({'_id':oid(mandiId)});
    if not m:raise HTTPException(404,'Mandi not found')
    lng,lat=m['location']['coordinates'];straight=hav(fromLat,fromLng,lat,lng);road_distance=straight*1.2;ts=list(db.transporters.find({'active':True}).sort('baseRatePerKm',ASCENDING).limit(5));rate=(ts[0]['baseRatePerKm'] if ts else 18);minimum=(ts[0]['minFare'] if ts else 250);base_cost=max(minimum,road_distance*rate);handling=round(max(0,quantity)*2,2);cost=base_cost+handling;return {'origin':{'latitude':fromLat,'longitude':fromLng},'destination':{'latitude':lat,'longitude':lng,'name':m.get('name')},'straightDistanceKm':round(straight,2),'distanceKm':round(road_distance,1),'routeFactor':1.2,'quantity':quantity,'ratePerKm':rate,'minimumFare':minimum,'handlingCost':handling,'estimatedCost':round(cost,2),'currency':'INR','transporters':[clean(t) for t in ts]}

# ---- logistics booking and tracking ----
@fastapi_app.post('/api/logistics/bookings', status_code=201)
async def create_logistics_booking(x:LogisticsBookingIn,u=Depends(auth_user)):
    o=db.orders.find_one({'_id':oid(x.orderId)})
    if not o: raise HTTPException(404,'Order not found')
    if u['_id'] not in (o['buyer'],o['farmer']): raise HTTPException(403,'Not part of this order')
    transporter=None
    if x.transporterId:
        transporter=db.transporters.find_one({'_id':oid(x.transporterId),'active':True})
        if not transporter: raise HTTPException(404,'Transporter not found')
    existing=db.logistics_bookings.find_one({'order':o['_id'],'status':{'$nin':['cancelled','delivered']}})
    if existing: return clean(existing)
    now=datetime.now(timezone.utc)
    b={'order':o['_id'],'bookedBy':u['_id'],'transporter':transporter['_id'] if transporter else None,'pickupAddress':x.pickupAddress,'deliveryAddress':x.deliveryAddress,'quantity':x.quantity,'status':'requested','tracking':{'latitude':None,'longitude':None,'note':'Booking requested'},'createdAt':now,'updatedAt':now}
    b['_id']=db.logistics_bookings.insert_one(b).inserted_id
    await notify(db.users.find_one({'_id':o['buyer']}),'Logistics booking created',f'Booking {b["_id"]} has been requested.')
    await notify(db.users.find_one({'_id':o['farmer']}),'Logistics booking created',f'Booking {b["_id"]} has been requested.')
    return clean(b)

@fastapi_app.get('/api/logistics/bookings/mine')
def logistics_bookings_mine(u=Depends(auth_user)):
    orders=list(db.orders.find({'$or':[{'buyer':u['_id']},{'farmer':u['_id']}]} ,{'_id':1}))
    ids=[o['_id'] for o in orders]
    return [clean(x) for x in db.logistics_bookings.find({'order':{'$in':ids}}).sort('createdAt',DESCENDING)]

@fastapi_app.get('/api/logistics/bookings/{booking_id}/track')
def track_logistics_booking(booking_id:str,u=Depends(auth_user)):
    b=db.logistics_bookings.find_one({'_id':oid(booking_id)})
    if not b: raise HTTPException(404,'Booking not found')
    o=db.orders.find_one({'_id':b['order']})
    if not o or u['_id'] not in (o['buyer'],o['farmer']): raise HTTPException(403,'Not authorized')
    return clean(b)

@fastapi_app.put('/api/logistics/bookings/{booking_id}/status')
async def update_logistics_booking(booking_id:str,x:LogisticsStatusIn,u=Depends(auth_user)):
    b=db.logistics_bookings.find_one({'_id':oid(booking_id)})
    if not b: raise HTTPException(404,'Booking not found')
    o=db.orders.find_one({'_id':b['order']})
    if not o or u['_id'] not in (o['buyer'],o['farmer']): raise HTTPException(403,'Not authorized')
    allowed={'requested','confirmed','picked-up','in-transit','delivered','cancelled'}
    if x.status not in allowed: raise HTTPException(400,'Invalid logistics status')
    tracking=b.get('tracking',{})
    if x.latitude is not None: tracking['latitude']=x.latitude
    if x.longitude is not None: tracking['longitude']=x.longitude
    if x.note is not None: tracking['note']=x.note
    db.logistics_bookings.update_one({'_id':b['_id']},{'$set':{'status':x.status,'tracking':tracking,'updatedAt':datetime.now(timezone.utc)}})
    b['status']=x.status;b['tracking']=tracking
    await emit_global('logistics:update',{'bookingId':str(b['_id']),'status':x.status,'tracking':clean(tracking)})
    return clean(b)


# ---- Admin warehouse management ----

@fastapi_app.get('/api/admin/warehouses')
def admin_warehouses(
    u=Depends(role_required('admin'))
):
    return [
        clean(w)
        for w in db.warehouses.find().sort(
            'name',
            ASCENDING
        )
    ]


@fastapi_app.post('/api/admin/warehouses', status_code=201)
def admin_create_warehouse(
    x: WarehouseIn,
    u=Depends(role_required('admin'))
):
    data = x.model_dump()

    data.update({
        'approvalStatus': 'approved',
        'createdAt': datetime.now(timezone.utc),
        'updatedAt': datetime.now(timezone.utc)
    })

    data['_id'] = db.warehouses.insert_one(data).inserted_id

    return clean(data)


@fastapi_app.delete('/api/admin/warehouses/{warehouse_id}')
def admin_delete_warehouse(
    warehouse_id: str,
    u=Depends(role_required('admin'))
):
    result = db.warehouses.delete_one({
        '_id': oid(warehouse_id)
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail='Warehouse not found'
        )

    return {
        'message': 'Warehouse deleted successfully'
    }


# ---- admin ----
@fastapi_app.get('/api/admin/dashboard')
def admin_dashboard(u=Depends(role_required('admin'))):
    successful=db.payments.count_documents({'status':'success'});gross=sum(x.get('totalPrice',0) for x in db.orders.find({'status':{'$ne':'cancelled'}}, {'totalPrice':1}));return {'users':db.users.count_documents({}),'crops':db.crops.count_documents({}),'orders':db.orders.count_documents({}),'bids':db.bids.count_documents({}),'mandis':db.mandis.count_documents({}),'openDisputes':db.disputes.count_documents({'status':{'$in':['open','under-review']}}),'successfulPayments':successful,'grossOrderValue':gross}
@fastapi_app.get('/api/admin/users')
def admin_users(u=Depends(role_required('admin'))):return [public_user(x) for x in db.users.find().sort('createdAt',DESCENDING)]
@fastapi_app.get('/api/admin/mandis')
def admin_mandis(u=Depends(role_required('admin'))):return mandis()
@fastapi_app.post('/api/admin/mandis',status_code=201)
def admin_create_mandi(x:MandiIn,u=Depends(role_required('admin'))):return create_mandi(x,u)
@fastapi_app.put('/api/admin/mandis/{mid}')
def admin_update_mandi(mid:str,x:MandiIn,u=Depends(role_required('admin'))):
    m=db.mandis.find_one({'_id':oid(mid)});
    if not m:raise HTTPException(404,'Mandi not found')
    coords=x.coordinates if x.coordinates else ([x.longitude,x.latitude] if x.longitude is not None and x.latitude is not None else m['location']['coordinates']);patch={'name':x.name,'district':x.district,'state':x.state,'location':{'type':'Point','coordinates':coords},'updatedAt':datetime.now(timezone.utc)};db.mandis.update_one({'_id':m['_id']},{'$set':patch});m.update(patch);return clean(m)
@fastapi_app.delete('/api/admin/mandis/{mid}')
def admin_delete_mandi(mid:str,u=Depends(role_required('admin'))):db.mandis.delete_one({'_id':oid(mid)});return {'message':'Mandi deleted'}
@fastapi_app.get('/api/admin/transporters')
def admin_transporters(u=Depends(role_required('admin'))):return [clean(x) for x in db.transporters.find().sort('name',ASCENDING)]
@fastapi_app.post('/api/admin/transporters',status_code=201)
def admin_create_transporter(x:TransporterIn,u=Depends(role_required('admin'))):d=x.model_dump();d.update(createdAt=datetime.now(timezone.utc),updatedAt=datetime.now(timezone.utc));d['_id']=db.transporters.insert_one(d).inserted_id;return clean(d)
@fastapi_app.delete('/api/admin/transporters/{tid}')
def admin_delete_transporter(tid:str,u=Depends(role_required('admin'))):db.transporters.delete_one({'_id':oid(tid)});return {'message':'Transporter deleted'}
@fastapi_app.get('/api/admin/disputes')
def admin_disputes(u=Depends(role_required('admin'))):
    out=[]
    for d in db.disputes.find().sort('createdAt',DESCENDING):
        x=clean(d);x['openedBy']=public_user(db.users.find_one({'_id':d['openedBy']}));x['order']=clean(db.orders.find_one({'_id':d['order']}));out.append(x)
    return out
# Re-register two generic admin endpoints with request parsing (FastAPI keeps the latest route first-match only if unique; these are unique paths).
@fastapi_app.api_route('/api/admin/transporters/{tid}',methods=['PUT'])
async def admin_update_transporter_route(tid:str,request:Request,u=Depends(role_required('admin'))):
    body=await request.json();d=db.transporters.find_one({'_id':oid(tid)})
    if not d:raise HTTPException(404,'Transporter not found')
    allowed=['name','phone','vehicleType','baseRatePerKm','minFare','serviceArea','active'];patch={k:body[k] for k in allowed if k in body};patch['updatedAt']=datetime.now(timezone.utc);db.transporters.update_one({'_id':d['_id']},{'$set':patch});d.update(patch);return clean(d)
@fastapi_app.api_route('/api/admin/disputes/{did}',methods=['PUT'])
async def admin_update_dispute_route(did:str,request:Request,u=Depends(role_required('admin'))):
    body=await request.json();d=db.disputes.find_one({'_id':oid(did)})
    if not d:raise HTTPException(404,'Dispute not found')
    patch={};
    if body.get('status'):patch['status']=body['status']
    if body.get('resolution') is not None:patch['resolution']=body['resolution']
    patch['updatedAt']=datetime.now(timezone.utc);db.disputes.update_one({'_id':d['_id']},{'$set':patch});d.update(patch);return clean(d)


# ---- Step 2: FPO lot discovery ----
@fastapi_app.get('/api/lots/search')
def search_fpo_lots(search: Optional[str] = None, location: Optional[str] = None, verifiedOnly: bool = False, u=Depends(auth_user)):
    query = {'status': 'available'}
    if search:
        query['name'] = {'$regex': search.strip(), '$options': 'i'}
    rows = []
    for c in db.crops.find(query).sort('createdAt', DESCENDING):
        farmer = db.users.find_one({'_id': c.get('farmer')})
        if not farmer:
            continue
        if location and location.lower() not in str(farmer.get('location', '')).lower() and location.lower() not in str(c.get('mandi', '')).lower():
            continue
        is_verified = bool(farmer.get('phoneVerified')) and farmer.get('documentVerificationStatus') == 'verified'
        if verifiedOnly and not is_verified:
            continue
        item = crop_out(c, True)
        item['lotType'] = 'FPO lot' if farmer.get('organization') else 'Farmer lot'
        item['farmerVerification'] = {'phoneVerified': bool(farmer.get('phoneVerified')), 'documentStatus': farmer.get('documentVerificationStatus', 'not_submitted'), 'verified': is_verified}
        rows.append(item)
    return rows

# ---- Step 3: Buyer demand posting and quality requirements ----
class DemandIn(BaseModel):
    cropName: str = Field(min_length=2)
    quantity: float = Field(gt=0)
    unit: str = 'quintal'
    targetPrice: Optional[float] = Field(default=None, gt=0)
    qualityRequirements: Optional[str] = ''
    location: Optional[str] = ''
    neededBy: Optional[str] = ''
    notes: Optional[str] = ''

@fastapi_app.post('/api/demands', status_code=201)
def create_demand(x: DemandIn, u=Depends(role_required('buyer'))):
    demand = x.model_dump()
    demand.update({'buyer': u['_id'], 'status': 'open', 'createdAt': datetime.now(timezone.utc), 'updatedAt': datetime.now(timezone.utc)})
    demand['_id'] = db.demands.insert_one(demand).inserted_id
    return clean(demand)

@fastapi_app.get('/api/demands')
@fastapi_app.get('/api/demands')
def list_demands(
    search: Optional[str] = None,
    u=Depends(auth_user)
):
    # Closed/cancelled demands ko chhodkar baaki demands show hongi
    query = {
        'status': {
            '$nin': ['closed', 'cancelled']
        }
    }

    if search:
        query['cropName'] = {
            '$regex': search.strip(),
            '$options': 'i'
        }

    result = []

    for demand in db.demands.find(query).sort(
        'createdAt',
        DESCENDING
    ):
        item = clean(demand)

        buyer = db.users.find_one({
            '_id': demand.get('buyer')
        })

        item['buyer'] = public_user(buyer) if buyer else None

        result.append(item)

    return result
@fastapi_app.get('/api/demands/mine')
def my_demands(u=Depends(role_required('buyer'))):
    return [clean(d) for d in db.demands.find({'buyer': u['_id']}).sort('createdAt', DESCENDING)]

@fastapi_app.patch('/api/demands/{demand_id}/close')
def close_demand(demand_id: str, u=Depends(role_required('buyer'))):
    d = db.demands.find_one({'_id': oid(demand_id)})
    if not d: raise HTTPException(404, 'Demand not found')
    if d['buyer'] != u['_id']: raise HTTPException(403, 'Not authorized')
    db.demands.update_one({'_id': d['_id']}, {'$set': {'status': 'closed', 'updatedAt': datetime.now(timezone.utc)}})
    d['status'] = 'closed'
    return clean(d)

# socket.io
@sio.event
async def connect(sid,environ,auth): log.info('socket connected %s',sid)
@sio.event
async def disconnect(sid): log.info('socket disconnected %s',sid)
@sio.on('authenticate')
async def socket_auth(sid,data):
    uid=(data or {}).get('userId')
    if uid: await sio.enter_room(sid,f'user:{uid}')

if __name__=='__main__':
    import uvicorn
    uvicorn.run('main:app',host='0.0.0.0',port=int(os.getenv('PORT','5000')),reload=True)
