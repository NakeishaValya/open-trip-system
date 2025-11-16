from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from uuid import uuid4

from .aggregate_root import Trip
from .entities import Guide
from repository import TripRepository

router = APIRouter(prefix="/trips", tags=["Trips"])

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

# Endpoints
@router.post("/", response_model=TripResponse)
def create_trip(request: CreateTripRequest):
    trip_id = str(uuid4())
    
    try:
        trip = Trip(trip_id, request.trip_name, request.capacity)
        TripRepository.save(trip)
        
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
    trip = TripRepository.find_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
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
    trips = TripRepository.get_all()
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
def add_schedule(trip_id: str, request: AddScheduleRequest):
    trip = TripRepository.find_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    try:
        start = date.fromisoformat(request.start_date)
        end = date.fromisoformat(request.end_date)
        trip.add_schedule(start, end, request.location)
        TripRepository.save(trip)
        return {"message": "Schedule added successfully"}
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{trip_id}/guide")
def assign_guide(trip_id: str, request: AssignGuideRequest):
    trip = TripRepository.find_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    try:
        guide_id = str(uuid4())
        guide = Guide(guide_id, request.guide_name, request.contact, request.language)
        trip.assign_guide(guide)
        TripRepository.save(trip)
        return {"message": "Guide assigned successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{trip_id}/capacity")
def update_capacity(trip_id: str, request: UpdateCapacityRequest):
    trip = TripRepository.find_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    try:
        trip.update_capacity(request.new_capacity)
        TripRepository.save(trip)
        return {"message": "Capacity updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{trip_id}/itinerary")
def update_itinerary(trip_id: str, request: UpdateItineraryRequest):
    trip = TripRepository.find_by_id(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    try:
        trip.update_itinerary(request.destinations, request.description)
        TripRepository.save(trip)
        return {"message": "Itinerary updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
