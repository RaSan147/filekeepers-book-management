import pytest
from fastapi import status

from .conftest import API_ADMIN, LIMITED_API_KEY, NULL_API_KEY, MALFORMED_API_KEY, MALFORMED_API_KEY2, MONGO_TEST_ID

@pytest.mark.asyncio
async def test_create_api_key(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	key_data = {
		"name": "New Test Key",
		"owner": "tester",
		"is_admin": False
	}
	response = test_client.post("/api/v1/keys", json=key_data, headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	key = response.json()
	assert key["name"] == "New Test Key"
	assert "key" in key

@pytest.mark.asyncio
async def test_list_api_keys(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	response = test_client.get("/api/v1/keys", headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	keys = response.json()
	assert len(keys) >= 1  # At least our test key

@pytest.mark.asyncio
async def test_update_api_key(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	# First get existing key
	list_response = test_client.get("/api/v1/keys", headers=headers)
	target_api = list_response.json()[0]["key"]
	
	update_data = {"name": "Updated Name"}
	response = test_client.patch(f"/api/v1/keys/{target_api}", json=update_data, headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	updated_key = response.json()
	assert updated_key["name"] == "Updated Name"

@pytest.mark.asyncio
async def test_delete_api_key(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	# First create a key to delete
	create_response = test_client.post("/api/v1/keys", json={
		"name": "To Delete",
		"owner": "tester"
	}, headers=headers)
	target_api = create_response.json()["key"]  # Get the ID of the created key
	
	# Now delete it
	delete_response = test_client.delete(f"/api/v1/keys/{target_api}", headers=headers)

	print(f"Delete response: {delete_response.status_code}, {delete_response.text}")
	assert delete_response.status_code == status.HTTP_200_OK
	
	# Verify it's gone
	print(f"Checking if the key was deleted.../api/v1/keys/{target_api}")
	get_response = test_client.get(f"/api/v1/keys/{target_api}", headers=headers)
	print(f"Get response: {get_response.status_code}, {get_response.text}")
	assert get_response.status_code == status.HTTP_404_NOT_FOUND