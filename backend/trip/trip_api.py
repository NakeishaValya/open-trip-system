from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from uuid import uuid4

from .aggregate_root import Trip
from .entities import Guide
from backend.storage import TripStorage
from backend.auth import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/trips", tags=["Trips"])

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _get_trip(trip_id: str) -> Trip:
    """
    Mengambil trip berdasarkan ID
    Jika tidak ditemukan, raise 404
    """
    trip = TripStorage.find_by_id(trip_id)
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip dengan ID {trip_id} tidak ditemukan"
        )
    return trip

def _ensure_ownership(trip: Trip, user: AuthenticatedUser):
    """
    Memastikan user yang request adalah pemilik/creator trip
    Jika bukan, raise 403 Forbidden
    """
    if not hasattr(trip, 'user_id'):
        # Jika trip belum punya user_id, skip check (backward compatibility)
        return
    if trip.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki izin untuk mengakses trip ini"
        )

# Request/Response Models
class CreateTripRequest(BaseModel):
    trip_name: str
    capacity: int

class TripResponse(BaseModel):
    trip_id: str
    trip_name: str
    capacity: int
    is_available: bool
    guide_name: Optional[str] = None
    schedules: List[dict] = []
    itinerary: Optional[dict] = None

class AddScheduleRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    location: str

class AssignGuideRequest(BaseModel):
    guide_name: str
    contact: str
    language: str

class UpdateItineraryRequest(BaseModel):
    destinations: List[str]
    description: str

class UpdateCapacityRequest(BaseModel):
    new_capacity: int

# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TripResponse)
def create_trip(
    request: CreateTripRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Membuat trip baru (untuk planner/admin)"""
    trip_id = str(uuid4())
    
    try:
        trip = Trip(trip_id, request.trip_name, request.capacity)
        # Simpan user_id untuk ownership tracking
        trip.user_id = current_user.id
        TripStorage.save(trip)
        
        return TripResponse(
            trip_id=trip.trip_id,
            trip_name=trip.trip_name,
            capacity=trip.capacity,
            is_available=trip.is_available_for_booking()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: str):
    """Mengambil detail trip (public access)"""
    trip = _get_trip(trip_id)
    
    schedules = [
        {
            "start_date": str(s.start_date),
            "end_date": str(s.end_date),
            "location": s.location
        }
        for s in trip.get_schedules()
    ]
    
    itinerary = None
    if trip.get_itinerary():
        itinerary = {
            "destinations": trip.get_itinerary().get_destinations(),
            "description": trip.get_itinerary().description
        }
    
    return TripResponse(
        trip_id=trip.trip_id,
        trip_name=trip.trip_name,
        capacity=trip.capacity,
        is_available=trip.is_available_for_booking(),
        guide_name=trip.get_guide().name if trip.get_guide() else None,
        schedules=schedules,
        itinerary=itinerary
    )

@router.get("/", response_model=List[TripResponse])
def get_all_trips():
    """Mengambil daftar semua trip yang tersedia (public access)"""
    trips = TripStorage.get_all()
    return [
        TripResponse(
            trip_id=t.trip_id,
            trip_name=t.trip_name,
            capacity=t.capacity,
            is_available=t.is_available_for_booking(),
            guide_name=t.get_guide().name if t.get_guide() else None
        )
        for t in trips
    ]

@router.post("/{trip_id}/schedule")
def add_schedule(
    trip_id: str,
    request: AddScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Menambahkan jadwal ke trip"""
    trip = _get_trip(trip_id)
    _ensure_ownership(trip, current_user)
    
    # Validasi location tidak boleh kosong/null
    if not request.location or not request.location.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location cannot be empty"
        )
    try:
        start = date.fromisoformat(request.start_date)
        end = date.fromisoformat(request.end_date)
        trip.add_schedule(start, end, request.location)
        TripStorage.save(trip)
        return {"message": "Schedule added successfully"}
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{trip_id}/guide")
def assign_guide(
    trip_id: str,
    request: AssignGuideRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Menugaskan guide ke trip"""
    trip = _get_trip(trip_id)
    _ensure_ownership(trip, current_user)

    # Tambahan validasi: guide_name tidak boleh kosong
    if not request.guide_name or not request.guide_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guide name cannot be empty"
        )

    try:
        guide_id = str(uuid4())
        guide = Guide(guide_id, request.guide_name, request.contact, request.language)
        trip.assign_guide(guide)
        TripStorage.save(trip)
        return {"message": "Guide assigned successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{trip_id}/capacity")
def update_capacity(
    trip_id: str,
    request: UpdateCapacityRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Memperbarui kapasitas trip"""
    trip = _get_trip(trip_id)
    _ensure_ownership(trip, current_user)
    
    try:
        trip.update_capacity(request.new_capacity)
        TripStorage.save(trip)
        return {"message": "Capacity updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{trip_id}/itinerary")
def update_itinerary(
    trip_id: str,
    request: UpdateItineraryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Memperbarui itinerary trip"""
    trip = _get_trip(trip_id)
    _ensure_ownership(trip, current_user)
    
    try:
        trip.update_itinerary(request.destinations, request.description)
        TripStorage.save(trip)
        return {"message": "Itinerary updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
