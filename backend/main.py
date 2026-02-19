from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import router as auth_router
from backend.booking.booking_api import router as booking_router
from backend.transaction.transaction_api import router as transaction_router
from backend.trip.trip_api import router as trip_router
from backend.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    create_tables()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Open Trip System",
    description="DDD-based Open Trip Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# app.include_router(auth_router)
app.include_router(booking_router, prefix='/api/opentrip')
app.include_router(transaction_router, prefix='/api/opentrip')
app.include_router(trip_router, prefix='/api/opentrip')

@app.get("/")
def root():
    return {
        "message": "Welcome to Open Trip System API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
