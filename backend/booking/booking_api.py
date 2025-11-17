from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4

from .aggregate_root import Booking
from .entities import Participant
from backend.storage import BookingStorage

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# Request/Response Models
class ParticipantRequest(BaseModel):
    name: str
    contact: str
    address: str

class CreateBookingRequest(BaseModel):
    trip_id: str
    participant: ParticipantRequest

class BookingResponse(BaseModel):
    booking_id: str
    trip_id: str
    transaction_id: Optional[str]
    participant_name: str
    status_code: str
    status_description: str

class CancelBookingRequest(BaseModel):
    reason: str

class RefundRequest(BaseModel):
    reason: str

# Endpoints
@router.post("/", response_model=BookingResponse)
def create_booking(request: CreateBookingRequest):
    booking_id = str(uuid4())
    participant_id = str(uuid4())
    
    participant = Participant(
        participant_id=participant_id,
        name=request.participant.name,
        contact=request.participant.contact,
        address=request.participant.address
    )
    
    booking = Booking.create_booking(booking_id, request.trip_id, participant)
    BookingStorage.save(booking)
    
    return BookingResponse(
        booking_id=booking.booking_id,
        trip_id=booking.trip_id,
        transaction_id=booking.transaction_id,
        participant_name=booking.participant.name,
        status_code=booking.status.status_code.value,
        status_description=booking.status.description
    )

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: str):
    booking = BookingStorage.find_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return BookingResponse(
        booking_id=booking.booking_id,
        trip_id=booking.trip_id,
        transaction_id=booking.transaction_id,
        participant_name=booking.participant.name,
        status_code=booking.status.status_code.value,
        status_description=booking.status.description
    )

@router.get("/", response_model=List[BookingResponse])
def get_all_bookings():
    bookings = BookingStorage.get_all()
    return [
        BookingResponse(
            booking_id=b.booking_id,
            trip_id=b.trip_id,
            transaction_id=b.transaction_id,
            participant_name=b.participant.name,
            status_code=b.status.status_code.value,
            status_description=b.status.description
        )
        for b in bookings
    ]

@router.post("/{booking_id}/confirm")
def confirm_booking(booking_id: str):
    booking = BookingStorage.find_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    try:
        booking.confirm_booking()
        BookingStorage.save(booking)
        return {"message": "Booking confirmed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, request: CancelBookingRequest):
    booking = BookingStorage.find_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    try:
        booking.cancel_booking(request.reason)
        BookingStorage.save(booking)
        return {"message": "Booking cancelled successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# @router.post("/{booking_id}/refund")
# def request_refund(booking_id: str, request: RefundRequest):
#     booking = BookingRepository.find_by_id(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
    
#     try:
#         booking.request_refund(request.reason)
#         BookingRepository.save(booking)
#         return {"message": "Refund requested successfully"}
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
