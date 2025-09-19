from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from typing import Optional, List
import uvicorn

from database import get_db, engine
from models import Base, User, AWSKey
from schemas import UserCreate, UserResponse, AWSKeyCreate, AWSKeyResponse, Token
from aws_service import AWSService

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AWS S3 Bucket Manager", version="1.0.0")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Security
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    if user.is_admin:
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
    else:
        response = RedirectResponse(url="/user/dashboard", status_code=302)
    
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

# Admin Routes
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    keys = db.query(AWSKey).all()
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "keys": keys
    })

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": current_user,
        "users": users
    })

@app.post("/admin/users/create")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Check if user exists
    if db.query(User).filter(User.username == username).first():
        users = db.query(User).all()
        return templates.TemplateResponse("admin_users.html", {
            "request": request,
            "current_user": current_user,
            "users": users,
            "error": "Username already exists"
        })
    
    hashed_password = get_password_hash(password)
    db_user = User(username=username, hashed_password=hashed_password, is_admin=is_admin)
    db.add(db_user)
    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=302)

@app.get("/admin/keys", response_class=HTMLResponse)
async def admin_keys(request: Request, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    keys = db.query(AWSKey).all()
    users = db.query(User).filter(User.is_admin == False).all()
    return templates.TemplateResponse("admin_keys.html", {
        "request": request,
        "current_user": current_user,
        "keys": keys,
        "users": users
    })

@app.post("/admin/keys/create")
async def create_key(
    request: Request,
    name: str = Form(...),
    access_key: str = Form(...),
    secret_key: str = Form(...),
    user_id: str = Form(""),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Convert empty string or "0" to None, otherwise convert to int
    parsed_user_id = None
    if user_id and user_id.strip() and user_id != "0":
        try:
            parsed_user_id = int(user_id)
        except ValueError:
            parsed_user_id = None
    
    db_key = AWSKey(
        name=name,
        access_key=access_key,
        secret_key=secret_key,
        user_id=parsed_user_id
    )
    db.add(db_key)
    db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

@app.post("/admin/keys/{key_id}/assign")
async def assign_key(
    key_id: int,
    user_id: int = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    key.user_id = user_id
    db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

# User Routes
@app.get("/user/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    user_keys = db.query(AWSKey).filter(AWSKey.user_id == current_user.id).all()
    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "keys": user_keys
    })

@app.get("/user/create-buckets", response_class=HTMLResponse)
async def create_buckets_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    user_keys = db.query(AWSKey).filter(AWSKey.user_id == current_user.id).all()
    regions = [
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'ca-central-1', 'ca-west-1',
        'eu-west-1', 'eu-west-2', 'eu-west-3',
        'eu-central-1', 'eu-central-2',
        'eu-north-1', 'eu-south-1', 'eu-south-2',
        'ap-south-1', 'ap-south-2',
        'ap-southeast-1', 'ap-southeast-2', 'ap-southeast-3', 'ap-southeast-4',
        'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
        'ap-east-1',
        'sa-east-1',
        'me-south-1', 'me-central-1',
        'il-central-1',
        'af-south-1'
    ]
    
    return templates.TemplateResponse("create_buckets.html", {
        "request": request,
        "current_user": current_user,
        "keys": user_keys,
        "regions": regions
    })

@app.post("/user/create-buckets")
async def create_buckets(
    request: Request,
    region: str = Form(...),
    num_buckets: int = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    user_keys = db.query(AWSKey).filter(AWSKey.user_id == current_user.id).all()
    
    if not user_keys:
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": user_keys,
            "error": "No AWS keys assigned to your account"
        })
    
    aws_service = AWSService()
    results = aws_service.create_buckets_for_user(user_keys, region, num_buckets)
    
    return templates.TemplateResponse("bucket_results.html", {
        "request": request,
        "current_user": current_user,
        "results": results,
        "region": region
    })

@app.post("/admin/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)

@app.post("/admin/keys/{key_id}/delete")
async def delete_key(
    key_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    db.delete(key)
    db.commit()
    return RedirectResponse(url="/admin/keys", status_code=302)

@app.post("/admin/keys/{key_id}/unassign")
async def unassign_key(
    key_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    key.user_id = None
    db.commit()
    return RedirectResponse(url="/admin/keys", status_code=302)

@app.post("/admin/keys/{key_id}/validate")
async def validate_key_admin(
    key_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    aws_service = AWSService()
    status, message = aws_service.validate_aws_key(key.access_key, key.secret_key)
    
    # Update key status and last_checked timestamp
    key.status = status
    key.last_checked = func.now()
    db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

@app.post("/user/keys/{key_id}/validate")
async def validate_key_user(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only validate their own assigned keys
    key = db.query(AWSKey).filter(
        AWSKey.id == key_id,
        AWSKey.user_id == current_user.id
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found or not assigned to you")
    
    aws_service = AWSService()
    status, message = aws_service.validate_aws_key(key.access_key, key.secret_key)
    
    # Update key status and last_checked timestamp
    key.status = status
    key.last_checked = func.now()
    db.commit()
    
    return RedirectResponse(url="/user/dashboard", status_code=302)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
