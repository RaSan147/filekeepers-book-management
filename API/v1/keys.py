from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.config import config
from shared.models import APIKeyCreate, APIKeyInDB, APIKeyUpdate
from shared.api_deps import get_db, api_ip_rate_limit, validate_api_key

router = APIRouter()

@router.post("", response_model=APIKeyInDB)
@api_ip_rate_limit()
async def create_api_key(
    request: Request,
    key_data: APIKeyCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: APIKeyInDB = Depends(validate_api_key)
):
    """
	Create a new API key (admin only)

	This endpoint allows an admin to create a new API key with specified scopes and rate limits.
	
	JSON body:
	```json
	{
		"name": "string", # Name of the API key
		"owner": "string", # Owner of the API key
		"rate_limit": "string", # Rate limit for the API key (e.g, "100/hour")
		"scopes": ["string"], # List of scopes/permissions
		"is_admin": false # Whether the key is for admin use (grants all permissions)
	}
	```

	Response Example:
	```json
	{
		"key": "string", # Auto-generated API key (UUID4)
		"name": "string", # Name of the API key
		"owner": "string", # Owner of the API key
		"rate_limit": "string", # Rate limit configuration (e.g., "100/hour")
		"scopes": ["string"], # List of permissions/scopes
		"is_active": true, # Whether the key is active
		"created_at": "2023-10-01T00:00:00Z", # When the key was created
		"_id": "string" # MongoDB document ID
	}
	```
	"""
    # Verify admin privileges
    if "admin" not in api_key.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Set default scopes and rate limit
    scopes = key_data.scopes or (["admin", "read", "write"] if key_data.is_admin else ["read"])
    rate_limit = key_data.rate_limit or (
        config.DEFAULT_ADMIN_RATE_LIMIT if key_data.is_admin 
        else config.DEFAULT_USER_RATE_LIMIT
    )

    # Generate the key data
    new_key_data = {
        "key": str(uuid4()),  # Generate new UUID4 key
        "name": key_data.name,
        "owner": key_data.owner,
        "rate_limit": rate_limit,
        "scopes": scopes,
        "is_active": True,
        "created_at": datetime.now(tz=timezone.utc)
    }

    # Insert new key
    result = await db.api_keys.insert_one(new_key_data)
    new_key = await db.api_keys.find_one({"_id": result.inserted_id})
        
    return APIKeyInDB(**new_key)

@router.get("", response_model=list[APIKeyInDB])
@api_ip_rate_limit()
async def list_api_keys(
	request: Request,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""
	List all API keys (admin only)

	This endpoint allows an admin to retrieve a list of all API keys in the system.
	Response Example:
	```json
	[
		{
			"key": "string", # Auto-generated API key (UUID4)
			"name": "string", # Name of the API key
			"owner": "string", # Owner of the API key
			"rate_limit": "string", # Rate limit configuration (e.g., "100/hour")
			"scopes": ["string"], # List of permissions/scopes
			"is_active": true, # Whether the key is active
			"created_at": "2023-10-01T00:00:00Z", # When the key was created
			"_id": "string" # MongoDB document ID
		},
		...
	]
	"""
	if "admin" not in api_key.scopes:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	keys = await db.api_keys.find().to_list(100)
	return [APIKeyInDB(**key) for key in keys]

@router.get("/{target_api}", response_model=APIKeyInDB)
@api_ip_rate_limit()
async def get_api_key(
	request: Request,
	target_api: str,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""
	Get details of a specific API key

	This endpoint retrieves the details of a specific API key by its key value.

	Response Example:
	```json
	{
		"key": "string", # Auto-generated API key (UUID4)
		"name": "string", # Name of the API key
		"owner": "string", # Owner of the API key
		"rate_limit": "string", # Rate limit configuration (e.g., "100/hour")
		"scopes": ["string"], # List of permissions/scopes
		"is_active": true, # Whether the key is active
		"created_at": "2023-10-01T00:00:00Z", # When the key was created
		"_id": "string" # MongoDB document ID
	}
	```
	"""
	if not ("admin" in api_key.scopes or api_key.key == target_api):
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	key_data = await db.api_keys.find_one({"key": target_api})
	if not key_data:
		raise HTTPException(status_code=404, detail="API key not found")
	
	return APIKeyInDB(**key_data)

@router.patch("/{target_api}", response_model=APIKeyInDB)
@api_ip_rate_limit()
async def update_api_key(
	request: Request,
	target_api: str,
	updates: APIKeyUpdate,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""
	Update an API key (admin only)

	This endpoint allows an admin to update an existing API key's details.

	JSON body:
	```json
	{
		"name": "string", # New name of the API key
		"rate_limit": "string", # New rate limit for the API key (e.g, "100/hour")
		"is_active": true, # Whether the key is active
		"scopes": ["string"] # List of new scopes/permissions
	}
	```
	Response Example:
	```json
	{
		"key": "string", # Auto-generated API key (UUID4)
		"name": "string", # Name of the API key
		"owner": "string", # Owner of the API key
		"rate_limit": "string", # Rate limit configuration (e.g., "100/hour")
		"scopes": ["string"], # List of permissions/scopes
		"is_active": true, # Whether the key is active
		"created_at": "2023-10-01T00:00:00Z", # When the key was created
		"id": "string" # MongoDB document ID
	}
	```
	"""
	if "admin" not in api_key.scopes:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	# Update the key
	result = await db.api_keys.update_one(
		{"key": target_api},
		{"$set": updates.model_dump(exclude_unset=True)}
	)
	
	if result.modified_count == 0:
		raise HTTPException(status_code=404, detail="API key not found")
	
	updated_key = await db.api_keys.find_one({"key": target_api})
	return APIKeyInDB(**updated_key)

@router.delete("/{target_api}", status_code=status.HTTP_200_OK)
@api_ip_rate_limit()
async def delete_api_key(
	request: Request,
	target_api: str,
	db: AsyncIOMotorDatabase = Depends(get_db),
	api_key: APIKeyInDB = Depends(validate_api_key)
):
	"""
	Delete an API key (admin only)

	This endpoint allows an admin to delete an existing API key.

	Response Example:
	```json
	{		
		"detail": "API key deleted successfully"
		"status": "success"
		"a
	}
	"""
	if "admin" not in api_key.scopes:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Admin privileges required"
		)
	
	result = await db.api_keys.delete_one({"key": target_api})
	if result.deleted_count == 0:
		raise HTTPException(status_code=404, detail="API key not found")
	
	return {
		"detail": "API key deleted successfully",
		"status": "success"
		}
