from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, Cookie, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import os
import sys
from typing import Optional, List
import uvicorn

# Force immediate output flushing for debugging
# sys.stdout.reconfigure(line_buffering=True)

from database import get_db, engine
from models import Base, User, AWSKey, Team
from schemas import UserCreate, UserResponse, AWSKeyCreate, AWSKeyResponse, Token, TeamCreate, TeamResponse
from aws_service import AWSService
from maintenance import maintenance_middleware, maintenance

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AWS S3 Bucket Manager", version="1.0.0")

# Add maintenance mode middleware
@app.middleware("http")
async def maintenance_check(request: Request, call_next):
    return await maintenance_middleware(request, call_next)

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
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
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

def get_team_leader_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_team_leader:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team leader permissions required"
        )
    # Ensure the user has a team assigned
    if not current_user.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No team assigned"
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
    elif user.is_team_leader:
        response = RedirectResponse(url="/team-leader/dashboard", status_code=302)
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
    user_role: str = Form("user"),
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
    
    # Set user roles based on selection
    is_admin = user_role == "admin"
    is_team_leader = user_role == "team_leader"
    
    db_user = User(
        username=username, 
        hashed_password=hashed_password, 
        is_admin=is_admin,
        is_team_leader=is_team_leader
    )
    db.add(db_user)
    db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=302)

# Admin Team Management Routes
@app.get("/admin/teams", response_class=HTMLResponse)
async def admin_teams(request: Request, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    users = db.query(User).filter(User.is_admin == False).all()
    keys = db.query(AWSKey).all()
    return templates.TemplateResponse("admin_teams.html", {
        "request": request,
        "current_user": current_user,
        "teams": teams,
        "users": users,
        "keys": keys
    })

@app.post("/admin/teams/create")
async def create_team(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    leader_id: str = Form(""),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Check if team name exists
    if db.query(Team).filter(Team.name == name).first():
        teams = db.query(Team).all()
        users = db.query(User).filter(User.is_admin == False).all()
        keys = db.query(AWSKey).all()
        return templates.TemplateResponse("admin_teams.html", {
            "request": request,
            "current_user": current_user,
            "teams": teams,
            "users": users,
            "keys": keys,
            "error": "Team name already exists"
        })
    
    # Parse leader_id
    parsed_leader_id = None
    if leader_id and leader_id.strip() and leader_id != "0":
        try:
            parsed_leader_id = int(leader_id)
        except ValueError:
            parsed_leader_id = None
    
    # Create team
    db_team = Team(
        name=name.strip(),
        description=description.strip() if description else None,
        leader_id=parsed_leader_id
    )
    db.add(db_team)
    db.commit()
    
    # If a leader was assigned, update their is_team_leader status and team_id
    if parsed_leader_id:
        leader = db.query(User).filter(User.id == parsed_leader_id).first()
        if leader:
            leader.is_team_leader = True
            leader.team_id = db_team.id
            db.commit()
    
    return RedirectResponse(url="/admin/teams", status_code=302)

@app.post("/admin/teams/{team_id}/assign-leader")
async def assign_team_leader(
    team_id: int,
    user_id: int = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove previous leader if exists
    if team.leader_id:
        old_leader = db.query(User).filter(User.id == team.leader_id).first()
        if old_leader:
            old_leader.is_team_leader = False
            old_leader.team_id = None
    
    # Assign new leader
    team.leader_id = user_id
    user.is_team_leader = True
    user.team_id = team_id
    db.commit()
    
    return RedirectResponse(url="/admin/teams", status_code=302)

@app.post("/admin/teams/{team_id}/assign-user")
async def assign_user_to_team(
    team_id: int,
    user_id: int = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Assign user to team
    user.team_id = team_id
    db.commit()
    
    return RedirectResponse(url="/admin/teams", status_code=302)

@app.post("/admin/teams/{team_id}/assign-key")
async def assign_key_to_team(
    team_id: int,
    key_id: int = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    # Check if already assigned
    if key not in team.aws_keys:
        team.aws_keys.append(key)
        db.commit()
    
    return RedirectResponse(url="/admin/teams", status_code=302)

@app.post("/admin/teams/{team_id}/delete")
async def delete_team(
    team_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Remove team leader status from leader
    if team.leader_id:
        leader = db.query(User).filter(User.id == team.leader_id).first()
        if leader:
            leader.is_team_leader = False
            leader.team_id = None
    
    # Remove team_id from all members
    for member in team.members:
        member.team_id = None
    
    db.delete(team)
    db.commit()
    return RedirectResponse(url="/admin/teams", status_code=302)

@app.get("/admin/keys", response_class=HTMLResponse)
async def admin_keys(request: Request, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    # Optimized database queries with eager loading
    from sqlalchemy.orm import joinedload
    import concurrent.futures
    import time
    
    start_time = time.time()
    
    # Use eager loading to avoid N+1 queries
    keys = db.query(AWSKey).options(joinedload(AWSKey.users)).all()
    users = db.query(User).filter(User.is_admin == False).all()
    
    print(f"Database queries completed in {time.time() - start_time:.2f} seconds")
    
    # Get comprehensive stats in parallel for better performance
    aws_service = AWSService()
    
    # Use thread pool for parallel stats gathering (max 5 concurrent to avoid rate limits)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        stats_futures = {
            executor.submit(aws_service.get_comprehensive_key_stats, key): key 
            for key in keys
        }
        
        keys_with_stats = []
        for future in concurrent.futures.as_completed(stats_futures, timeout=30):
            try:
                stats = future.result(timeout=10)  # 10 second timeout per key
                keys_with_stats.append(stats)
            except Exception as e:
                # Fallback stats for failed keys
                key = stats_futures[future]
                keys_with_stats.append({
                    'key_id': key.id,
                    'key_name': key.name,
                    'bucket_count': None,
                    'bucket_limit': 100,
                    'buckets_remaining': None,
                    'can_create_buckets': None,
                    'connection_error': f"Timeout or error: {str(e)[:50]}..."
                })
                print(f"Stats gathering failed for key {key.name}: {e}")
    
    # Sort stats to match original key order
    stats_dict = {stat['key_id']: stat for stat in keys_with_stats}
    keys_with_stats = [stats_dict.get(key.id, {}) for key in keys]
    
    total_time = time.time() - start_time
    print(f"Admin keys page loaded in {total_time:.2f} seconds")
    
    return templates.TemplateResponse("admin_keys.html", {
        "request": request,
        "current_user": current_user,
        "keys": keys,
        "keys_with_stats": keys_with_stats,
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
    
    # Sanitize inputs: trim whitespace; normalize access key to uppercase
    sanitized_name = name.strip() if name else name
    sanitized_access = access_key.strip().upper() if access_key else access_key
    sanitized_secret = secret_key.strip() if secret_key else secret_key

    db_key = AWSKey(
        name=sanitized_name,
        access_key=sanitized_access,
        secret_key=sanitized_secret,
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
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already assigned
    if user not in key.users:
        key.users.append(user)
        db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

# User Routes
@app.get("/user/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    # Optimized query with eager loading to avoid N+1 queries
    from sqlalchemy.orm import joinedload
    user_with_keys = db.query(User).options(
        joinedload(User.aws_keys)
    ).filter(User.id == current_user.id).first()
    
    user_keys = user_with_keys.aws_keys if user_with_keys else []

    # Just-in-time re-validation to avoid stale statuses
    aws_service = AWSService()
    for k in user_keys:
        try:
            status, _ = aws_service.validate_aws_key(k.access_key, k.secret_key)
            k.status = status
            k.last_checked = func.now()
        except Exception:
            # keep previous status if validation failed unexpectedly
            pass
    db.commit()

    valid_keys = [k for k in user_keys if k.status != 'invalid']
    invalid_keys = [k for k in user_keys if k.status == 'invalid']
    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "keys": valid_keys,
        "invalid_keys": invalid_keys
    })

@app.get("/user/create-buckets", response_class=HTMLResponse)
async def create_buckets_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    user_keys = current_user.aws_keys
    valid_keys = [k for k in user_keys if k.status != 'invalid']
    invalid_keys = [k for k in user_keys if k.status == 'invalid']
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
        "keys": valid_keys,
        "invalid_keys": invalid_keys,
        "regions": regions
    })

@app.post("/user/create-buckets")
async def create_buckets(
    request: Request,
    region: str = Form(...),
    num_buckets: int = Form(...),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print(f"DEBUG MAIN: Starting bucket creation for user {current_user.username}")
    print(f"DEBUG MAIN: Region: {region}, Num buckets: {num_buckets}")
    print(f"DEBUG MAIN: Image filename: {image.filename if image else 'None'}")
    print(f"DEBUG MAIN: Image content type: {image.content_type if image else 'None'}")
    
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    user_keys = current_user.aws_keys
    valid_keys = [k for k in user_keys if k.status != 'invalid']
    invalid_keys = [k for k in user_keys if k.status == 'invalid']
    
    print(f"DEBUG MAIN: Found {len(user_keys)} total keys, {len(valid_keys)} valid keys")
    
    if not valid_keys:
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": valid_keys,
            "invalid_keys": invalid_keys,
            "error": "No valid AWS keys available (invalid keys are excluded)"
        })
    
    # Basic validation for uploaded image content type
    if image is None or (image.content_type is not None and not image.content_type.startswith("image/")):
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": valid_keys,
            "invalid_keys": invalid_keys,
            "error": "Please upload a valid image file (png, jpg, jpeg, etc.)"
        })

    # Read the image file properly in the async context
    try:
        image_content = await image.read()
        print(f"DEBUG MAIN: Read {len(image_content)} bytes from uploaded image in main.py")
    except Exception as e:
        print(f"ERROR MAIN: Error reading image in main.py: {str(e)}")
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": valid_keys,
            "invalid_keys": invalid_keys,
            "error": f"Error processing uploaded image: {str(e)}"
        })

    print(f"DEBUG MAIN: About to call optimized AWS service with {len(valid_keys)} keys")
    
    # Use optimized AWS service for parallel processing
    from aws_service_optimized import OptimizedAWSService
    aws_service = OptimizedAWSService()
    
    # Use async parallel processing
    import asyncio
    results = await aws_service.create_buckets_for_user_parallel(valid_keys, region, num_buckets, image_file=image, image_content=image_content)
    
    print(f"DEBUG MAIN: Optimized AWS service returned: {results}")
    print(f"DEBUG MAIN: Total buckets created: {results.get('total_buckets_created', 0)}")
    print(f"DEBUG MAIN: Total URLs generated: {results.get('total_urls_generated', 0)}")
    print(f"DEBUG MAIN: Processing time: {results.get('processing_time', 'N/A')}")
    
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

@app.post("/admin/keys/{key_id}/unassign/{user_id}")
async def unassign_key_from_user(
    key_id: int,
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove user from key's users
    if user in key.users:
        key.users.remove(user)
        db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

@app.post("/admin/keys/{key_id}/unassign-all")
async def unassign_key_from_all(
    key_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    # Remove all users from this key
    key.users.clear()
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
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key or key not in current_user.aws_keys:
        raise HTTPException(status_code=404, detail="Key not found or not assigned to you")
    
    aws_service = AWSService()
    status, message = aws_service.validate_aws_key(key.access_key, key.secret_key)
    
    # Update key status and last_checked timestamp
    key.status = status
    key.last_checked = func.now()
    db.commit()
    
    return RedirectResponse(url="/user/dashboard", status_code=302)

@app.post("/user/keys/{key_id}/unassign")
async def user_unassign_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can unassign themselves from keys
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key or key not in current_user.aws_keys:
        raise HTTPException(status_code=404, detail="Key not found or not assigned to you")
    
    # Remove current user from key's users
    key.users.remove(current_user)
    db.commit()
    
    return RedirectResponse(url="/user/dashboard", status_code=302)

# Team Leader Routes
@app.get("/team-leader/dashboard", response_class=HTMLResponse)
async def team_leader_dashboard(request: Request, current_user: User = Depends(get_team_leader_user), db: Session = Depends(get_db)):
    # Get team with members and keys
    from sqlalchemy.orm import joinedload
    team = db.query(Team).options(
        joinedload(Team.members),
        joinedload(Team.aws_keys)
    ).filter(Team.id == current_user.team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return templates.TemplateResponse("team_leader_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "team": team
    })

@app.get("/team-leader/manage-users", response_class=HTMLResponse)
async def team_leader_manage_users(request: Request, current_user: User = Depends(get_team_leader_user), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get all non-admin users not in any team
    available_users = db.query(User).filter(
        User.is_admin == False,
        User.team_id == None,
        User.is_team_leader == False
    ).all()
    
    return templates.TemplateResponse("team_leader_manage_users.html", {
        "request": request,
        "current_user": current_user,
        "team": team,
        "available_users": available_users
    })

@app.post("/team-leader/users/add")
async def team_leader_add_user(
    user_id: int = Form(...),
    current_user: User = Depends(get_team_leader_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is available (not admin, not team leader, not in another team)
    if user.is_admin or user.is_team_leader or user.team_id:
        raise HTTPException(status_code=400, detail="User is not available")
    
    # Add user to team
    user.team_id = current_user.team_id
    db.commit()
    
    return RedirectResponse(url="/team-leader/manage-users", status_code=302)

@app.post("/team-leader/users/{user_id}/remove")
async def team_leader_remove_user(
    user_id: int,
    current_user: User = Depends(get_team_leader_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is in the team leader's team
    if user.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="User is not in your team")
    
    # Don't allow removing yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from team")
    
    # Remove user from team
    user.team_id = None
    db.commit()
    
    return RedirectResponse(url="/team-leader/manage-users", status_code=302)

@app.get("/team-leader/assign-keys", response_class=HTMLResponse)
async def team_leader_assign_keys(request: Request, current_user: User = Depends(get_team_leader_user), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team members (excluding the leader)
    team_members = db.query(User).filter(
        User.team_id == current_user.team_id,
        User.id != current_user.id
    ).all()
    
    return templates.TemplateResponse("team_leader_assign_keys.html", {
        "request": request,
        "current_user": current_user,
        "team": team,
        "team_members": team_members
    })

@app.post("/team-leader/keys/{key_id}/assign")
async def team_leader_assign_key(
    key_id: int,
    user_id: int = Form(...),
    current_user: User = Depends(get_team_leader_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if key belongs to the team
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key or key not in team.aws_keys:
        raise HTTPException(status_code=404, detail="Key not found or not assigned to your team")
    
    # Check if user is in the team
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.team_id != current_user.team_id:
        raise HTTPException(status_code=404, detail="User not found or not in your team")
    
    # Assign key to user
    if user not in key.users:
        key.users.append(user)
        db.commit()
    
    return RedirectResponse(url="/team-leader/assign-keys", status_code=302)

@app.post("/team-leader/keys/{key_id}/unassign/{user_id}")
async def team_leader_unassign_key(
    key_id: int,
    user_id: int,
    current_user: User = Depends(get_team_leader_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if key belongs to the team
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key or key not in team.aws_keys:
        raise HTTPException(status_code=404, detail="Key not found or not assigned to your team")
    
    # Check if user is in the team
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.team_id != current_user.team_id:
        raise HTTPException(status_code=404, detail="User not found or not in your team")
    
    # Unassign key from user
    if user in key.users:
        key.users.remove(user)
        db.commit()
    
    return RedirectResponse(url="/team-leader/assign-keys", status_code=302)

@app.post("/admin/keys/{key_id}/refresh-stats")
async def refresh_key_stats(
    key_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    # Refresh both validation status and comprehensive stats
    aws_service = AWSService()
    status, message = aws_service.validate_aws_key(key.access_key, key.secret_key)
    
    # Update key status and last_checked timestamp
    key.status = status
    key.last_checked = func.now()
    db.commit()
    
    return RedirectResponse(url="/admin/keys", status_code=302)

# Maintenance Mode Admin Routes
@app.get("/admin/maintenance", response_class=HTMLResponse)
async def admin_maintenance(request: Request, current_user: User = Depends(get_admin_user)):
    """Admin page to control maintenance mode"""
    return templates.TemplateResponse("admin_maintenance.html", {
        "request": request,
        "current_user": current_user,
        "maintenance_enabled": maintenance.is_enabled(),
        "maintenance_config": maintenance.config
    })

@app.post("/admin/maintenance/enable")
async def enable_maintenance(
    message: str = Form("We're currently performing scheduled maintenance to improve your experience."),
    estimated_completion: str = Form(""),
    current_user: User = Depends(get_admin_user)
):
    """Enable maintenance mode"""
    maintenance.enable(message, estimated_completion if estimated_completion else None)
    return RedirectResponse(url="/admin/maintenance", status_code=302)

@app.post("/admin/maintenance/disable")
async def disable_maintenance(current_user: User = Depends(get_admin_user)):
    """Disable maintenance mode"""
    maintenance.disable()
    return RedirectResponse(url="/admin/maintenance", status_code=302)

# Health check endpoint (bypasses maintenance)
@app.get("/health")
async def health_check():
    """Health check endpoint that bypasses maintenance mode"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/status")
async def status_check():
    """Status endpoint that bypasses maintenance mode"""
    return {
        "status": "running",
        "maintenance_mode": maintenance.is_enabled(),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
