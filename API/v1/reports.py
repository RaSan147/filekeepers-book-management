from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
import csv
import io
import tempfile
from typing import Optional

from shared.models import DailyChangeReport
from shared.api_deps import get_db, api_ip_rate_limit, validate_api_key

router = APIRouter()

@router.get("/daily", response_model=DailyChangeReport)
@api_ip_rate_limit()
async def get_daily_report(
    request: Request,
    date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", example="2025-06-30"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: str = Depends(validate_api_key)
):
    query = {}
    if date:
        query["date"] = {"$regex": f"^{date}"}
    
    report = await db.reports.find_one(query, sort=[("date", -1)])
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return DailyChangeReport(**report) 

@router.get("/daily/csv")
@api_ip_rate_limit()
async def get_daily_report_csv(
    request: Request,
    date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$", example="2025-06-30"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    api_key: str = Depends(validate_api_key)
):
    report = await get_daily_report(request, date, db, api_key)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["Date", "Book Title", "Change Type", "Book ID", "Changed Fields"])

    async def get_book_title(book_id: str) -> str:
        book = await db.books.find_one({"_id": book_id})
        if book:
            return book.get("title", "Unknown Title")
        return "Unknown Title"
    
    # Write data
    for change in report.changes:
        writer.writerow([
            report.date,
            get_book_title(change["book_id"]),
            change["change_type"],
            change["book_id"],
            str(change.get("changed_fields", {}))
        ])
    
    output.seek(0)
    
    # Use StreamingResponse instead of temporary file
    headers = {
        "Content-Disposition": f"attachment; filename=book_changes_{report.date[:10]}.csv"
    }
    return StreamingResponse(
        iter([output.getvalue().encode()]),
        media_type="text/csv",
        headers=headers
    )