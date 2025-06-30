import os
import logging
import csv
import io
import tempfile

from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import motor.motor_asyncio


from shared.models import (
    APIKeyCreate,
    APIKeyInDB,
    APIKeyUpdate,
    BookChangeLog,
    BookInDB,
    BookSearchQuery,
    DailyChangeReport
)
from shared.config import config
from .deps import get_db, limiter, validate_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API_HOST = os.getenv("API_HOST", "0.0.0.0")
# API_PORT = int(os.getenv("API_PORT", 8000))
# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
API_HOST = config.API_HOST
API_PORT = config.API_PORT
MONGO_URI = config.MONGO_URI

app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: JSONResponse(
    {"detail": "Rate limit exceeded"}, status_code=429
))

# MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.book_db

@app.get("/books", response_model=List[BookInDB])
@limiter.limit("100/hour")
async def list_books(
    request: Request,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    rating: Optional[int] = None,
    sort_by: str = "rating",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    api_key: str = Depends(validate_api_key)
):
    query = {}
    
    if category:
        query["category"] = category
    if min_price is not None or max_price is not None:
        query["price_incl_tax"] = {}
        if min_price is not None:
            query["price_incl_tax"]["$gte"] = min_price
        if max_price is not None:
            query["price_incl_tax"]["$lte"] = max_price
    if rating:
        query["rating"] = rating
    
    sort_field = {
        "rating": "rating",
        "price": "price_incl_tax",
        "reviews": "review_count",
        "newest": "last_updated"
    }.get(sort_by, "rating")
    
    skip = (page - 1) * per_page
    books = await db.books.find(query).sort(sort_field, -1).skip(skip).limit(per_page).to_list(per_page)
    return books

@app.get("/books/{book_id}", response_model=BookInDB)
@limiter.limit("100/hour")
async def get_book(
    request: Request,
    book_id: str,
    api_key: str = Depends(validate_api_key)
):
    book = await db.books.find_one({"_id": book_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book = BookInDB(**book)
    return book

@app.get("/changes", response_model=List[BookChangeLog])
@limiter.limit("50/hour")
async def get_changes(
    request: Request,
    days: int = Query(1, ge=1, le=30),
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(validate_api_key)
):
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    changes = await db.change_log.find({
        "timestamp": {"$gte": since}
    }).sort("timestamp", -1).limit(limit).to_list(limit)

    changes = [
        BookChangeLog(**change).model_dump() for change in changes
    ]
    return changes

@app.get("/reports/daily", response_model=DailyChangeReport)
@limiter.limit("10/hour")
async def get_daily_report(
    request: Request,
    date: Optional[str] = None,
    api_key: str = Depends(validate_api_key)
):
    query = {}
    if date:
        query["date"] = {"$regex": f"^{date}"}
    
    report = await db.reports.find_one(query, sort=[("date", -1)])
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@app.get("/reports/daily/csv")
@limiter.limit("10/hour")
async def get_daily_report_csv(
    request: Request,
    date: Optional[str] = None,
    api_key: str = Depends(validate_api_key)
):
    report = await get_daily_report(request, date, api_key)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["Date", "New Books", "Updated Books", "Change Type", "Book ID", "Changed Fields"])
    
    # Write data
    for change in report["changes"]:
        writer.writerow([
            report["date"],
            report["new_books"],
            report["updated_books"],
            change["change_type"],
            change["book_id"],
            str(change.get("changed_fields", {}))
        ])
    
    output.seek(0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        temp_file.write(output.getvalue().encode())
        return FileResponse(
            path=temp_file.name,
            media_type="text/csv",
            filename=f"book_changes_{report['date'][:10]}.csv"
        )


@app.post("/keys", response_model=APIKeyInDB)
@limiter.limit("5/hour")
async def create_api_key(
    request: Request,
    key_data: APIKeyCreate,
    db=Depends(get_db),
    admin_key: APIKeyInDB = Depends(validate_api_key)
):
    """Create a new API key (admin only)"""
    # Verify admin privileges
    if "admin" not in admin_key.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Check if key already exists
    existing_key = await db.api_keys.find_one({"key": key_data.key})
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key already exists"
        )
    
    # Insert new key
    result = await db.api_keys.insert_one(key_data.model_dump())
    new_key = await db.api_keys.find_one({"_id": result.inserted_id})
    return APIKeyInDB(**new_key)

@app.get("/keys", response_model=List[APIKeyInDB])
@limiter.limit("10/hour")
async def list_api_keys(
    request: Request,
    db=Depends(get_db),
    admin_key: APIKeyInDB = Depends(validate_api_key)
):
    """List all API keys (admin only)"""
    if "admin" not in admin_key.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    keys = await db.api_keys.find().to_list(100)
    return [APIKeyInDB(**key) for key in keys]

@app.patch("/keys/{key_id}", response_model=APIKeyInDB)
@limiter.limit("10/hour")
async def update_api_key(
    request: Request,
    key_id: str,
    updates: APIKeyUpdate,
    db=Depends(get_db),
    admin_key: APIKeyInDB = Depends(validate_api_key)
):
    """Update an API key (admin only)"""
    if "admin" not in admin_key.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided"
        )
    
    await db.api_keys.update_one(
        {"_id": key_id},
        {"$set": update_data}
    )
    updated_key = await db.api_keys.find_one({"_id": key_id})
    if not updated_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return APIKeyInDB(**updated_key)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)