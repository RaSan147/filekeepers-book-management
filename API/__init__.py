from fastapi import FastAPI
from .v1 import router as v1_router
from shared.config import config

API_HOST = config.API_HOST
API_PORT = config.API_PORT
MONGO_URI = config.MONGO_URI


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
		app, host=API_HOST, port=API_PORT,
		log_level="info"
	)