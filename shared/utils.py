import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, DESCENDING
from shared.config import config

MONGO_URI = config.MONGO_URI

async def get_mongo_client():
    client = AsyncIOMotorClient(MONGO_URI)
    try:
        # Ensure indexes
        db = client.book_db
        await db.books.create_indexes([
            IndexModel([("title", DESCENDING)]),
            IndexModel([("rating", DESCENDING)]),
        ])
        yield db
    finally:
        client.close()