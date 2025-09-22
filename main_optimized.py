# Performance-optimized version of main routes
import asyncio
import time
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

# Add these optimized routes to your main.py

@app.post("/user/create-buckets-fast")
async def create_buckets_optimized(
    request: Request,
    region: str = Form(...),
    num_buckets: int = Form(...),
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Optimized bucket creation with parallel processing"""
    start_time = time.time()
    
    if current_user.is_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    # Optimized database query with eager loading
    from sqlalchemy.orm import joinedload
    user_with_keys = db.query(User).options(
        joinedload(User.aws_keys)
    ).filter(User.id == current_user.id).first()
    
    user_keys = user_with_keys.aws_keys if user_with_keys else []
    valid_keys = [k for k in user_keys if k.status != 'invalid']
    
    if not valid_keys:
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": [],
            "invalid_keys": user_keys,
            "error": "No valid AWS keys available"
        })
    
    # Validate and optimize image
    if not image or not image.content_type.startswith("image/"):
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": valid_keys,
            "error": "Please upload a valid image file"
        })
    
    try:
        # Read and optimize image
        image_content = await image.read()
        print(f"Original image size: {len(image_content)} bytes")
        
        # Use optimized AWS service
        from performance_optimizations import PerformanceOptimizedAWSService
        aws_service = PerformanceOptimizedAWSService()
        
        # Process buckets in parallel
        results = await aws_service.create_buckets_parallel(
            valid_keys, region, num_buckets, image_content
        )
        
        processing_time = time.time() - start_time
        print(f"Total processing time: {processing_time:.2f} seconds")
        
        return templates.TemplateResponse("bucket_results.html", {
            "request": request,
            "current_user": current_user,
            "results": results,
            "region": region
        })
        
    except Exception as e:
        return templates.TemplateResponse("create_buckets.html", {
            "request": request,
            "current_user": current_user,
            "keys": valid_keys,
            "error": f"Error processing request: {str(e)}"
        })

@app.get("/admin/keys-fast", response_class=HTMLResponse)
async def admin_keys_optimized(
    request: Request, 
    current_user: User = Depends(get_admin_user), 
    db: Session = Depends(get_db)
):
    """Optimized admin keys page with caching"""
    from sqlalchemy.orm import joinedload
    
    # Optimized query with eager loading
    keys = db.query(AWSKey).options(
        joinedload(AWSKey.users)
    ).all()
    
    users = db.query(User).filter(User.is_admin == False).all()
    
    # Get stats in parallel for better performance
    aws_service = AWSService()
    
    # Use thread pool for parallel stats gathering
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        stats_futures = {
            executor.submit(aws_service.get_comprehensive_key_stats, key): key 
            for key in keys
        }
        
        keys_with_stats = []
        for future in concurrent.futures.as_completed(stats_futures):
            try:
                stats = future.result(timeout=10)  # 10 second timeout per key
                keys_with_stats.append(stats)
            except Exception as e:
                # Fallback stats for failed keys
                key = stats_futures[future]
                keys_with_stats.append({
                    'bucket_count': None,
                    'bucket_limit': 100,
                    'buckets_remaining': None,
                    'can_create_buckets': None,
                    'connection_error': f"Timeout: {str(e)}"
                })
    
    return templates.TemplateResponse("admin_keys.html", {
        "request": request,
        "current_user": current_user,
        "keys": keys,
        "keys_with_stats": keys_with_stats,
        "users": users
    })

@app.post("/api/validate-key-async/{key_id}")
async def validate_key_async(
    key_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Async key validation that returns immediately"""
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    # Add validation to background tasks
    background_tasks.add_task(validate_key_background, key_id, db)
    
    return JSONResponse({
        "status": "validation_started",
        "message": "Key validation started in background",
        "key_id": key_id
    })

async def validate_key_background(key_id: int, db: Session):
    """Background task for key validation"""
    key = db.query(AWSKey).filter(AWSKey.id == key_id).first()
    if not key:
        return
    
    aws_service = AWSService()
    try:
        status, message = aws_service.validate_aws_key(key.access_key, key.secret_key)
        key.status = status
        key.last_checked = func.now()
        db.commit()
        print(f"Background validation completed for key {key_id}: {status}")
    except Exception as e:
        print(f"Background validation failed for key {key_id}: {str(e)}")

# WebSocket for real-time updates (optional)
@app.websocket("/ws/progress/{user_id}")
async def websocket_progress(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time progress updates"""
    await websocket.accept()
    
    try:
        while True:
            # Send progress updates during bucket creation
            progress_data = {
                "type": "progress",
                "message": "Creating buckets...",
                "progress": 50,
                "timestamp": time.time()
            }
            await websocket.send_json(progress_data)
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# Add caching middleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Add to your app
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response caching for static content
@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Cache static files for 1 hour
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    
    return response
