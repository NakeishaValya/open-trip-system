from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from booking.booking_api import router as booking_router
from transaction.transaction_api import router as transaction_router
from trip.trip_api import router as trip_router

app = FastAPI(
    title="Open Trip System",
    description="DDD-based Open Trip Management System",
    version="1.0.0"
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
app.include_router(booking_router)
app.include_router(transaction_router)
app.include_router(trip_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to Open Trip System API",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
