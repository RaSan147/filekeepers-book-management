import pytest
from fastapi import status
from .conftest import API_ADMIN, LIMITED_API_KEY, NULL_API_KEY, MALFORMED_API_KEY, MALFORMED_API_KEY2

@pytest.mark.asyncio
async def test_get_daily_report(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	response = test_client.get("/api/v1/reports/daily", headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	assert response.headers["content-type"] == "application/json"
	# If data exists, we would expect a 200 OK
	report = response.json()
	assert "new_books" in report
	assert "updated_books" in report
	assert "changes" in report

@pytest.mark.asyncio
async def test_get_daily_report_csv(test_client):
	headers = {"X-API-KEY": API_ADMIN}
	response = test_client.get("/api/v1/reports/daily/csv", headers=headers)
	
	assert response.status_code == status.HTTP_200_OK
	assert response.headers["content-type"] == "text/csv; charset=utf-8"
	assert "attachment" in response.headers["content-disposition"]