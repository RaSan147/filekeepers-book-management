from fastapi import FastAPI
from .v1 import router as v1_router
from shared.config import config

app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/", tags=["root"])
async def read_root():
	return {"message": "Welcome to the Book Management API. Please refer to the documentation for usage at /docs or /redoc."}

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(
		app, host=config.API_HOST, port=config.API_PORT,
		log_level="info"
	)