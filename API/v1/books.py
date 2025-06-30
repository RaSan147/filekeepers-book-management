from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional

from shared.models import BookInDB, BookChangeLog
from shared.config import config
from shared.api_deps import get_db, limiter, validate_api_key

router = APIRouter()

@router.get("", response_model=List[BookInDB])
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
    db: AsyncIOMotorDatabase = Depends(get_db),
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
    books_cursor = db.books.find(query).sort(sort_field, -1).skip(skip).limit(per_page)
    books = await books_cursor.to_list(per_page)
    return [BookInDB(**book) for book in books]

@router.get("/{book_id}", response_model=BookInDB)
@limiter.limit("100/hour")
async def get_book(
    request: Request,
    book_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: str = Depends(validate_api_key)
):
    book = await db.books.find_one({"_id": book_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return BookInDB(**book)

@router.get("/changes", response_model=List[BookChangeLog])
@limiter.limit("50/hour")
async def get_changes(
    request: Request,
    days: int = Query(1, ge=1, le=30),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: str = Depends(validate_api_key)
):
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    changes_cursor = db.change_log.find({
        "timestamp": {"$gte": since}
    }).sort("timestamp", -1).limit(limit)
    
    changes = await changes_cursor.to_list(limit)
    return [BookChangeLog(**change) for change in changes]