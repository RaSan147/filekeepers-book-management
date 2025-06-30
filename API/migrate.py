import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from shared.models import APIKeyCreate
from shared.config import config

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
	client = AsyncIOMotorClient(config.MONGO_URI)
	db = client.book_db
	
	# Create indexes
	await db.api_keys.create_index("key", unique=True)
	await db.api_keys.create_index("owner")
	await db.api_keys.create_index("is_active")
	
	# Create initial admin key if none exists
	existing_keys = await db.api_keys.count_documents({})
	if existing_keys== 0:
		admin_key = APIKeyCreate(
			_id='',
			key=config.DEFAULT_ADMIN_API_KEY,
			name=config.DEFAULT_ADMIN_TASK_NAME,
			owner="system",
			rate_limit=config.DEFAULT_ADMIN_RATE_LIMIT,
			scopes=["admin", "read", "write", "temporary"],
		)
		await db.api_keys.insert_one(admin_key.model_dump())
		logger.info("Created initial admin key")


if __name__ == "__main__":
	asyncio.run(migrate())