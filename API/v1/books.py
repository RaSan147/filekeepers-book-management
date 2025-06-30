from datetime import datetime, timedelta, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional

from shared.models import BookInDB, BookChangeLog
from shared.api_deps import get_db, api_ip_rate_limit, validate_api_key

router = APIRouter()

@router.get("", response_model=List[BookInDB])
@api_ip_rate_limit()
async def list_books(
	request: Request,
	category: Optional[str] = Query(None, min_length=1, max_length=50, description="Filter by book category"),
	min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
	max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
	rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating filter (1-5 stars)"),
	sort_by: str = Query("rating",
		description="Field to sort by (default is 'rating'). Options: 'rating', 'price', 'reviews', 'newest'",
		examples="rating"),
	page: int = Query(1, ge=1, description="Page number for pagination"),
	per_page: int = Query(20, ge=1, le=100, description="Number of books per page"),
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: str = Depends(validate_api_key)
):
	"""
	List books with optional filters and sorting.

	Parameters:
	- `category`: Filter by book category (optional).
	- `min_price`: Minimum price filter (optional).
	- `max_price`: Maximum price filter (optional).	
	- `rating`: Minimum rating filter (optional).
	- `sort_by`: Field to sort by. Options: "rating", "price", "reviews", "newest".
	- `page`: Page number for pagination.
	- `per_page`: Number of books per page.

	Response Example:
	```json
	[
		{
			"_id": "60c72b2f9b1e8d001c8e4f3a",
			"url": "https://example.com/book/123",
			"title": "Example Book",
			"category": "Fiction",
			"description": "This is an example book description.",
			"price_incl_tax": 19.99,
			"price_excl_tax": 17.99,
			"availability": 10,
			"review_count": 5,
			"image_url": "https://example.com/image.jpg",
			"rating": 4,
			"content_hash": "abc123hash",
			"raw_html": "<html>...</html>",
			"first_seen": "2023-01-01T00:00:00Z",
			"last_updated": "2023-01-02T00:00:00Z"
		},
		...
	]
	```
	"""
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

@router.get("/changes", response_model=List[BookChangeLog])
@api_ip_rate_limit()
async def get_changes(
	request: Request,
	days: int = Query(1, ge=1, le=30, description="Number of days to look back for changes"),
	limit: int = Query(20, ge=1, le=100, description="Maximum number of changes to return"),
	db: AsyncIOMotorDatabase = Depends(get_db, use_cache=False),
	api_key: str = Depends(validate_api_key)
):
	"""
	Get recent changes to books.

	Parameters:
	- `days`: Number of days to look back for changes (default is 1, max is 30).
	- `limit`: Maximum number of changes to return (default is 20, max is 100).
	"""
	since = datetime.now(tz=timezone.utc) - timedelta(days=days)
	changes_cursor = db.change_log.find({
		"timestamp": {"$gte": since}
	}).sort("timestamp", -1).limit(limit)
	
	changes = await changes_cursor.to_list(limit)
	return [BookChangeLog(**change) for change in changes]

@router.get("/{book_id}", response_model=BookInDB)
@api_ip_rate_limit()
async def get_book(
	request: Request,
	book_id: str = Path(..., pattern="^[0-9a-fA-F]{24}$", description="The ID of the book to retrieve (24-character hex string)"),
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: str = Depends(validate_api_key)
):
	"""
	Get details of a specific book by its ID.

	Parameters:
	- `book_id`: The ID of the book to retrieve (24-character hex string).

	Returns:
	```json
	{
		"_id": "60c72b2f9b1e8d001c8e4f3a",
		"url": "https://example.com/book/123",
		"title": "Example Book",
		"category": "Fiction",
		"description": "This is an example book description.",
		"price_incl_tax": 19.99,
		"price_excl_tax": 17.99,
		"availability": 10,
		"review_count": 5,
		"image_url": "https://example.com/image.jpg",
		"rating": 4,
		"content_hash": "abc123hash",
		"raw_html": "<html>...</html>",
		"first_seen": "2023-01-01T00:00:00Z",
		"last_updated": "2023-01-02T00:00:00Z"
	}
	```
	"""
	if not ObjectId.is_valid(book_id):
		raise HTTPException(status_code=400, detail="Invalid book ID")

	book = await db.books.find_one({"_id": ObjectId(book_id)})
	if not book:
		raise HTTPException(status_code=404, detail="Book not found")
	return BookInDB(**book)
