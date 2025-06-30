from datetime import datetime, timezone
from functools import wraps
import uuid
from bson import ObjectId
from fastapi.security import APIKeyHeader
from fastapi import Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional
from shared.models import APIKeyInDB
from shared.utils import get_mongo_client
from shared.config import config
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_db():
    async for db in get_mongo_client():
        yield db

async def get_api_key(db, api_key: str) -> Optional[APIKeyInDB]:
    """Retrieve API key details from database"""
    key_data = await db.api_keys.find_one({"key": api_key})
    if not key_data:
        return None

    if key_data:
        return APIKeyInDB(**key_data)
    return None



async def validate_api_key(
    request: Request,
    api_key: str = Depends(api_key_header),
    db = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
        )
    
    # Validate UUID format (optional but recommended)
    try:
        uuid.UUID(api_key, version=4)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key format",
        )
    
    key_info = await get_api_key(db, api_key)
    if not key_info or not key_info.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or inactive API key",
        )
    
    # Update last used timestamp
    await db.api_keys.update_one(
        {"_id": ObjectId(key_info.id)},
        {"$set": {"last_used": datetime.now(tz=timezone.utc)}}
    )
    
    # Store key info in request state
    request.state.api_key = key_info
    request.state.api_key_id = key_info.id  # Store ID for rate limiting
    
    return key_info


# Initialize limiters
user_limiter = Limiter(key_func=lambda request: request.state.api_key_id)
ip_limiter = Limiter(key_func=get_remote_address)

def api_ip_rate_limit():
    """
    Decorator that automatically uses the rate limit from the validated API key
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get the rate limit from the validated API key
            rate_limit = request.state.api_key.rate_limit
            ip_limit = config.DEFAULT_IP_RATE_LIMIT
            
            # Create a decorated version with both limits
            limited_func = ip_limiter.limit(ip_limit)(
                user_limiter.limit(rate_limit)(func)
            )
            
            try:
                return await limited_func(request, *args, **kwargs)
            except RateLimitExceeded as e:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=str(e),
                )
        return wrapper
    return decorator
