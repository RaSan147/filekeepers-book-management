from fastapi import APIRouter
from . import books, reports, keys

router = APIRouter()
router.include_router(books.router, prefix="/books", tags=["books"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(keys.router, prefix="/keys", tags=["keys"])