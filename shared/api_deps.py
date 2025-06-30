from datetime import datetime, timezone
from fastapi.security import APIKeyHeader
from fastapi import Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional
from shared.models import APIKeyInDB
from shared.utils import get_mongo_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

class RateLimitConfig(BaseModel):
    limit: str
    scope: str

async def get_db():
    async for db in get_mongo_client():
        yield db

async def get_api_key(db, api_key: str) -> Optional[APIKeyInDB]:
    """Retrieve API key details from database"""
    key_data = await db.api_keys.find_one({"key": api_key})
    key_data["_id"] = str(key_data["_id"]) if key_data else ''  # Convert ObjectId to str+
    if key_data:
        return APIKeyInDB(**key_data)
    return None

async def validate_api_key(
    api_key: str = Depends(api_key_header),
    db = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing",
        )
    
    key_info = await get_api_key(db, api_key)
    if not key_info or not key_info.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )
    
    # Update last used timestamp
    await db.api_keys.update_one(
        {"_id": key_info.id},
        {"$set": {"last_used": datetime.now(tz=timezone.utc)}}
    )
    
    return key_info

def get_rate_limit(key_info: APIKeyInDB = Depends(validate_api_key)) -> str:
    """Get rate limit configuration from API key info"""
    return key_info.rate_limit

# Initialize limiter with dynamic rate limits
limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])