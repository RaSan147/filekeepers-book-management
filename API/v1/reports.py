from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.models import APIKeyCreate, APIKeyInDB, APIKeyUpdate
from shared.api_deps import get_db, limiter, validate_api_key

router = APIRouter()

@router.post("", response_model=APIKeyInDB)
@limiter.limit("5/hour")
async def create_api_key(
    request: Request,
    key_data: APIKeyCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: APIKeyInDB = Depends(validate_api_key)
):
    """Create a new API key (admin only)"""
    # Verify admin privileges
    if "admin" not in api_key.scopes:
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


@router.get("", response_model=list[APIKeyInDB])
@limiter.limit("10/hour")
async def list_api_keys(
	request: Request,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""List all API keys (admin only)"""
	if "admin" not in api_key.scopes:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	keys = await db.api_keys.find().to_list(100)
	return [APIKeyInDB(**key) for key in keys]

@router.patch("/{key_id}", response_model=APIKeyInDB)
@limiter.limit("10/hour")
async def update_api_key(
	request: Request,
	key_id: str,
	updates: APIKeyUpdate,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""Update an API key (admin only)"""
	if "admin" not in api_key.scopes:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	# Update the key
	result = await db.api_keys.update_one(
		{"_id": key_id},
		{"$set": updates.model_dump(exclude_unset=True)}
	)
	
	if result.modified_count == 0:
		raise HTTPException(status_code=404, detail="API key not found")
	
	updated_key = await db.api_keys.find_one({"_id": key_id})
	return APIKeyInDB(**updated_key)
