from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional

class BookBase(BaseModel):
    url: str = Field(..., description="URL of the book page")
    title: str = Field(..., description="Title of the book")
    category: str = Field(..., description="Category of the book")
    description: str = Field(..., description="Book description")
    price_incl_tax: float = Field(..., description="Price including tax")
    price_excl_tax: float = Field(..., description="Price excluding tax")
    availability: int = Field(..., description="Number of available copies")
    review_count: int = Field(..., description="Number of reviews")
    image_url: str = Field(..., description="URL of the book cover image")
    rating: int = Field(..., description="Book rating (1-5 stars)")

class BookInDB(BookBase):
    id: str = Field(..., alias="_id", description="MongoDB document ID")
    content_hash: str = Field(..., description="SHA256 hash of book content")
    raw_html: str = Field(..., description="Raw HTML snapshot")
    first_seen: datetime = Field(..., description="When first scraped")
    last_updated: datetime = Field(..., description="When last updated")

class BookChangeLog(BaseModel):
    book_id: str = Field(..., description="ID of the changed book")
    change_type: str = Field(..., description="Type of change (created/updated)")
    changed_fields: dict = Field(..., description="Fields that changed")
    timestamp: datetime = Field(..., description="When change occurred")

class BookSearchQuery(BaseModel):
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rating: int = 0
    sort_by: Optional[str] = "rating"
    page: int = 1
    per_page: int = 20

class DailyChangeReport(BaseModel):
    date: str
    new_books: int
    updated_books: int
    changes: list[dict]