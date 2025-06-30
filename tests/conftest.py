from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
from pymongo import IndexModel
import pytest
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient
import pytest_asyncio
from shared.config import config
from API import app
import os

from shared.models import BookChangeLog


API_ADMIN = "11111111-1111-1111-1111-111111111111"
LIMITED_API_KEY = "22222222-2222-2222-2222-222222222222"
NULL_API_KEY = "00000000-0000-0000-0000-000000000000"
MALFORMED_API_KEY = "111-111-111"
MALFORMED_API_KEY2 = "00000000-0000-0000-00000000-00000000"
MONGO_TEST_ID = "123456789012345678901234"  # Example ObjectId for testing

@pytest.fixture
def test_client():
	return TestClient(app)

@pytest.fixture(autouse=True)
# @pytest.fixture(autouse=True)
async def setup_and_teardown():
	# Setup - connect to test database
	test_db_name = "book_db"
	test_mongo_uri = config.MONGO_URI
	print(f"Connecting to test MongoDB at {test_mongo_uri}")
	
	client = AsyncIOMotorClient(test_mongo_uri)
	db = client[test_db_name]
	# drop the database if it exists
	await client.drop_database(test_db_name)
	db = client[test_db_name]


	
	# Create test collections and indexes
	await db.books.create_indexes([
		IndexModel([("url", 1)], unique=True),
		IndexModel([("category", 1)]),
		IndexModel([("price_incl_tax", 1)]),
		IndexModel([("rating", 1)]),
		IndexModel([("last_updated", -1)]),
	])
	
	await db.change_log.create_index([("timestamp", -1)])

	# await db.api_keys.create_index("key")
	# await db.api_keys.create_index("owner")
	# await db.api_keys.create_index("is_active")
	# await db.api_keys.create_indexes([
	# 	IndexModel([("key", 1)], unique=True),
	# 	IndexModel([("owner", 1)]),
	# 	IndexModel([("is_active", 1)]),
	# ])

	# Insert test data
	test_book = {
		"url": "http://test.com/book1",
		"title": "Test Book",
		"category": "Test",
		"description": "Test description",
		"price_incl_tax": 10.99,
		"price_excl_tax": 9.99,
		"availability": 5,
		"review_count": 3,
		"image_url": "http://test.com/image.jpg",
		"rating": 4,
		"content_hash": "testhash",
		"raw_html": "<html>test</html>",
		"first_seen": "2023-01-01T00:00:00Z",
		"last_updated": "2023-01-01T00:00:00Z",
		"_id": ObjectId(MONGO_TEST_ID)
	}
	res = await db.books.insert_one(test_book)
	print(f"Inserted test book with ID: {res}")
	
	demo_key = {
		"key": NULL_API_KEY,
		"name": "Test Key",
		"owner": "tester",
		"rate_limit": "100/hour",
		"scopes": ["admin", "read", "write"],
		"is_active": True,
		"created_at": "2023-01-01T00:00:00Z"
	}

	test_key = demo_key.copy()
	test_key.update(
		{
			"key": API_ADMIN,
			"name": "Admin Test Key",
			"owner": "admin",
			"scopes": ["admin", "read", "write"],
			"rate_limit": "1000/hour"
		}
	)
	print(f"Inserting test key: {test_key}")
	res = await db.api_keys.insert_one(test_key)

	print(f"Test key ID: {res}")

	limited_test_key = demo_key.copy()
	limited_test_key.update(
		{
			"key": LIMITED_API_KEY,
			"name": "Limited Test Key",
			"scopes": ["read"],
			"rate_limit": "10/hour"
		}
	)

	print(f"Inserting limited test key: {limited_test_key}")
	res = await db.api_keys.insert_one(limited_test_key)
	print(f"Limited test key ID: {res}")

	# Create a change log entry
	changes = [{
		"book_id": ObjectId(MONGO_TEST_ID),
		"change_type": "created",
		"changed_fields": {
			"title": "Test Book",
			"price_incl_tax": 10.99,
			"price_excl_tax": 9.99,
			"availability": 5,
			"review_count": 3,
			"image_url": "http://test.com/image.jpg",
			"rating": 4,
			"description": "Test description",
			"category": "Test",
			"url": "http://test.com/book1"
		},
		"timestamp": datetime.now(timezone.utc)
	}]

	report = {
		"date": datetime.now(timezone.utc).isoformat(),
		"new_books": 1,
		"updated_books": 1,
		"changes": [BookChangeLog(**change).model_dump() for change in changes]
	}
	
	# Store report
	await db.reports.insert_one(report)
	
	yield db  # Test runs here
	
	# Teardown - clean up test database
	await client.drop_database(test_db_name)
	client.close()