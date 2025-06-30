import pytest
from fastapi import status
from shared.models import BookInDB
from .conftest import API_ADMIN, LIMITED_API_KEY, NULL_API_KEY, MALFORMED_API_KEY, MALFORMED_API_KEY2, MONGO_TEST_ID


@pytest.mark.asyncio
async def test_list_books(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	response = test_client.get("/api/v1/books", headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	books = response.json()
	assert len(books) == 1
	assert books[0]["title"] == "Test Book"

@pytest.mark.asyncio
async def test_list_books_with_filters(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	params = {
		"category": "Test",
		"min_price": 5,
		"max_price": 15,
		"rating": 4,
		"sort_by": "rating",
		"page": 1,
		"per_page": 10
	}
	response = test_client.get("/api/v1/books", headers=headers, params=params)
	
	assert response.status_code == status.HTTP_200_OK
	books = response.json()
	assert len(books) == 1

@pytest.mark.asyncio
async def test_get_book(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	book_id = MONGO_TEST_ID
	response = test_client.get(f"/api/v1/books/{book_id}", headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	book = response.json()
	assert book["title"] == "Test Book"
	assert book["_id"] == book_id

@pytest.mark.asyncio
async def test_get_nonexistent_book(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	book_id = "000000000000000000000000"
	response = test_client.get(f"/api/v1/books/{book_id}", headers=headers)
	
	assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_get_changes(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	response = test_client.get("/api/v1/books/changes", headers=headers)
	
	print(response.status_code, response.text)
	assert response.status_code == status.HTTP_200_OK
	changes = response.json()
	assert isinstance(changes, list)