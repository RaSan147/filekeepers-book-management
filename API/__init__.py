from typing import Optional
from fastapi import Depends, FastAPI, Path, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.api_deps import api_ip_rate_limit, get_db, validate_api_key
from shared.config import config

from API.v1 import router as v1_router

API_VERSION = "v1"

if API_VERSION == "v1":
	from API.v1.books import list_books as v_list_books
	from API.v1.books import get_changes as v_get_changes
	from API.v1.books import get_book as v_get_book
else:
	raise ValueError(f"Unsupported API version: {API_VERSION}")


API_HOST = config.API_HOST
API_PORT = config.API_PORT
MONGO_URI = config.MONGO_URI

app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/", tags=["root"])
async def read_root():
	return {"message": "Welcome to the Book Management API. Please refer to the documentation for usage at /docs or /redoc."}

@app.get("/health", tags=["health"])
async def health_check():
	return {"status": "ok", "version": config.APP_VERSION}


# Add redirects for GET /books GET /books/{book_id} GET /changes
@app.get("/books", tags=["books"])
@api_ip_rate_limit()
async def list_books(
	request: Request,
	category: Optional[str] = Query(None, min_length=1, max_length=50, description="Filter by book category"),
	min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
	max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
	rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating filter (1-5 stars)"),
	sort_by: str = Query("rating",
		description="Field to sort by (default is 'rating'). Options: 'rating', 'price', 'reviews', 'newest'",
		examples=["rating"]),
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
	return await v_list_books(
		request=request,
		category=category,
		min_price=min_price,
		max_price=max_price,
		rating=rating,
		sort_by=sort_by,
		page=page,
		per_page=per_page,
		db=db,
		api_key=api_key
	)


@app.get("/books/{book_id}", tags=["books"])
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
	return await v_get_book(
		request=request,
		book_id=book_id,
		db=db,
		api_key=api_key
	)

@app.get("/changes", tags=["changes"])
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
	return await v_get_changes(
		request=request,
		days=days,
		limit=limit,
		db=db,
		api_key=api_key
	)



if __name__ == "__main__":
	import uvicorn
	uvicorn.run(
		app, host=API_HOST, port=API_PORT,
		log_level="info"
	)