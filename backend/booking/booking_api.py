from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4

from .aggregate_root import Booking
from .entities import Participant
from backend.storage import BookingStorage
from backend.auth import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/bookings", tags=["Bookings"])

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _get_booking(booking_id: str) -> Booking:
    """
    Mengambil booking berdasarkan ID
    Jika tidak ditemukan, raise 404
    """
    booking = BookingStorage.find_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking dengan ID {booking_id} tidak ditemukan"
        )
    return booking

def _ensure_ownership(booking: Booking, user: AuthenticatedUser):
    """
    Memastikan user yang request adalah pemilik booking
    Jika bukan, raise 403 Forbidden
    """
    if not hasattr(booking, 'user_id'):
        # Jika booking belum punya user_id, skip check (backward compatibility)
        return
    if booking.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki izin untuk mengakses booking ini"
        )

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

# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingResponse)
def create_booking(
    request: CreateBookingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Membuat booking baru untuk trip"""
    booking_id = str(uuid4())
    participant_id = str(uuid4())
    
    participant = Participant(
        participant_id=participant_id,
        name=request.participant.name,
        contact=request.participant.contact,
        address=request.participant.address
    )
    
    booking = Booking.create_booking(booking_id, request.trip_id, participant)
    # Simpan user_id untuk ownership tracking
    booking.user_id = current_user.id
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
def get_booking(
    booking_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Mengambil detail booking berdasarkan ID"""
    booking = _get_booking(booking_id)
    _ensure_ownership(booking, current_user)
    
    return BookingResponse(
        booking_id=booking.booking_id,
        trip_id=booking.trip_id,
        transaction_id=booking.transaction_id,
        participant_name=booking.participant.name,
        status_code=booking.status.status_code.value,
        status_description=booking.status.description
    )

@router.get("/", response_model=List[BookingResponse])
def get_all_bookings(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Mengambil daftar semua booking milik user"""
    # Filter hanya booking milik user yang login
    all_bookings = BookingStorage.get_all()
    bookings = [
        b for b in all_bookings 
        if not hasattr(b, 'user_id') or b.user_id == current_user.id
    ]
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
def confirm_booking(
    booking_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Konfirmasi booking"""
    booking = _get_booking(booking_id)
    _ensure_ownership(booking, current_user)
    
    try:
        booking.confirm_booking()
        BookingStorage.save(booking)
        return {"message": "Booking confirmed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{booking_id}/cancel")
def cancel_booking(
    booking_id: str,
    request: CancelBookingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Membatalkan booking"""
    booking = _get_booking(booking_id)
    _ensure_ownership(booking, current_user)
    
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
