from bson import ObjectId
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from uuid import uuid4, UUID

from shared.config import config


class ObjectIdStr(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_before_validator_function(
            lambda v: str(v) if isinstance(v, ObjectId) else v,
            core_schema.str_schema()
        )


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
    id: ObjectIdStr = Field(..., alias="_id", description="MongoDB document ID")
    content_hash: str = Field(..., description="SHA256 hash of book content")
    raw_html: str = Field(..., description="Raw HTML snapshot")
    first_seen: datetime = Field(..., description="When first scraped")
    last_updated: datetime = Field(..., description="When last updated")

class BookChangeLog(BaseModel):
    book_id: ObjectIdStr = Field(..., description="ID of the changed book")
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


# class APIKeyBase(BaseModel):
#     key: str = Field(..., description="The API key value")
#     name: str = Field(..., description="Name/description of the key")
#     owner: str = Field(..., description="Owner of the key")
#     rate_limit: str = Field("100/hour", description="Rate limit configuration")
#     scopes: Optional[List[str]] = None

# class APIKeyInDB(APIKeyBase):
#     id: ObjectIdStr = Field(..., alias="_id", description="MongoDB document ID")
#     created_at: datetime = Field(default_factory=(lambda _: datetime.now(tz=timezone.utc)), description="When the key was created")
#     is_active: bool = Field(default=True, description="Whether the key is active")
#     last_used: Optional[datetime] = Field(default_factory=(lambda _: datetime.now(tz=timezone.utc)), description="When the key was last used")
#     scopes: List[str] = Field(default_factory=list, description="List of permissions/scopes")
#     # expires_at: Optional[datetime] = None # Not implemented yet

#     # # Alternative solution for ObjectId conversion
#     # @field_validator("id", mode="before")
#     # @classmethod
#     # def convert_object_id(cls, v: Any) -> str:
#     #     if isinstance(v, ObjectId):
#     #         return str(v)
#     #     return v

# class APIKeyCreate(APIKeyInDB):
#     pass

# class APIKeyUpdate(BaseModel):
#     name: Optional[str] = None
#     rate_limit: Optional[str] = None
#     is_active: Optional[bool] = None


class APIKeyBase(BaseModel):
    key: str = Field(
        default_factory=lambda: str(uuid4()), 
        description="Auto-generated API key (UUID4)"
    )
    name: str = Field(..., description="Name/description of the key")
    owner: str = Field(..., description="Owner of the key")
    rate_limit: str = Field(
        "100/hour", 
        description="Rate limit configuration (e.g., '100/hour')"
    )
    scopes: List[str] = Field(
        default_factory=list, 
        description="List of permissions/scopes"
    )
    is_active: bool = Field(
        default=True, 
        description="Whether the key is active"
    )

class APIKeyInDB(APIKeyBase):
    id: ObjectIdStr = Field(..., alias="_id", description="MongoDB document ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the key was created"
    )
    last_used: Optional[datetime] = Field(
        None,
        description="When the key was last used"
    )

class APIKeyCreate(BaseModel):
    name: str = Field(..., description="Name/description of the key")
    owner: str = Field(..., description="Owner of the key")
    rate_limit: Optional[str] = Field(
        default=None, 
        description="Rate limit configuration (e.g., '100/hour')"
    )
    is_admin: bool = Field(
        default=False, 
        description="Whether the key is for admin use (grants all permissions)"
    )
    scopes: Optional[List[str]] = Field(
        default_factory=lambda: ["admin", "read", "write"] if False else ["read"],
        description='List of permissions/scopes for the key (Available ["admin", "read", "write"]), default is ["read"]'
    )

class APIKeyUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None, 
        description="New name/description for the key"
    )
    rate_limit: Optional[str] = Field(
        default=None, 
        description="New rate limit configuration (e.g., '100/hour')"
    )
    is_active: Optional[bool] = Field(
        default=None, 
        description="Whether to activate/deactivate the key"
    )
    scopes: Optional[List[str]] = Field(
        default=None, 
        description="New list of permissions/scopes for the key"
    )