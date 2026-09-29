import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app.main import db, hash_password, token_for
from datetime import datetime, timezone
name=os.getenv('ADMIN_NAME','Platform Administrator');email=os.getenv('ADMIN_EMAIL','admin@kisanbazaar.local').lower();password=os.getenv('ADMIN_PASSWORD','change_this_password');phone=os.getenv('ADMIN_PHONE','+910000000000');location=os.getenv('ADMIN_LOCATION','India')
u=db.users.find_one({'email':email});now=datetime.now(timezone.utc)
if u: db.users.update_one({'_id':u['_id']},{'$set':{'name':name,'password':hash_password(password),'phone':phone,'role':'admin','location':location,'updatedAt':now}});u=db.users.find_one({'_id':u['_id']})
else:
 u={'name':name,'email':email,'password':hash_password(password),'phone':phone,'role':'admin','location':location,'createdAt':now,'updatedAt':now};u['_id']=db.users.insert_one(u).inserted_id
print('Admin ready:',email);print('Use the ADMIN_PASSWORD from your .env to log in.')
