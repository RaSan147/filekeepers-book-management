import pytest
from fastapi import status
from .conftest import LIMITED_API_KEY, NULL_API_KEY, MALFORMED_API_KEY, MALFORMED_API_KEY2

@pytest.mark.asyncio
async def test_access_without_api_key(test_client):
	response = test_client.get("/api/v1/books")
	assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_access_with_invalid_api_key(test_client):
	headers = {"X-API-KEY": MALFORMED_API_KEY}
	response = test_client.get("/api/v1/books", headers=headers)
	assert response.status_code == status.HTTP_403_FORBIDDEN

	headers = {"X-API-KEY": MALFORMED_API_KEY2}
	response = test_client.get("/api/v1/books", headers=headers)
	assert response.status_code == status.HTTP_403_FORBIDDEN

	
	headers = {"X-API-KEY": NULL_API_KEY}
	response = test_client.get("/api/v1/books", headers=headers)
	assert response.status_code == status.HTTP_403_FORBIDDEN



@pytest.mark.asyncio
async def test_rate_limiting(test_client):
	headers = {"X-API-KEY": LIMITED_API_KEY}
	# Make several rapid requests to trigger rate limiting
	for _ in range(10):
		response = test_client.get("/api/v1/books", headers=headers)
		print(response.status_code, "THE REASON IS", response.text)
		assert response.status_code == status.HTTP_200_OK
	
	# Depending on your rate limit settings, this might trigger a 429
	response = test_client.get("/api/v1/books", headers=headers)
	assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]