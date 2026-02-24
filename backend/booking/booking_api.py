from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from uuid import uuid4

from .aggregate_root import Booking
from .entities import Participant
from backend.storage import BookingStorage
from backend.auth import get_current_user, get_current_user_flexible, AuthenticatedUser
from backend.storage import TripStorage
from .value_objects import BookingStatus, StatusCode
from backend.trip.aggregate_root import Trip

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

# Request/Response Models
class ParticipantRequest(BaseModel):
    name: str
    phone_number: str
    gender: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    pick_up_point: Optional[str] = None
    notes: Optional[str] = None

class CreateBookingRequest(BaseModel):
    trip_id: str
    participant: ParticipantRequest

class PassengerResponse(BaseModel):
    name: str
    phone_number: str
    gender: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    pick_up_point: Optional[str] = None
    notes: Optional[str] = None

class BookingResponse(BaseModel):
    booking_id: str
    trip_id: str
    participant_id: str
    status: str
    message: Optional[str] = None
    passenger: Optional[PassengerResponse] = None

class CancelBookingRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = None

class RefundRequest(BaseModel):
    booking_id: str
    amount: Optional[float] = None
    reason: Optional[str] = None

# ==========================================
# ENDPOINTS
# ==========================================
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BookingResponse)
def create_booking(
    request: CreateBookingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user_flexible)
):
    """Create a booking for a trip using Pydantic request model."""
    try:
        payload = request
        trip = _get_trip(payload.trip_id)

        if not trip.is_available_for_booking():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trip sudah penuh atau tidak tersedia untuk booking"
            )

        participant_data = payload.participant
        participant_id = str(uuid4())
        booking_id = str(uuid4())

        # Map participant fields to domain Participant (contact/address)
        contact = participant_data.phone_number or ''
        address = participant_data.pick_up_point or ''
        participant = Participant(participant_id, participant_data.name, contact, address)

        # Create domain booking and persist
        booking = Booking.create_booking(booking_id, payload.trip_id, participant)
        # attach user id if available
        if hasattr(current_user, 'id'):
            booking.user_id = current_user.id
        elif hasattr(current_user, 'user_id'):
            booking.user_id = current_user.user_id

        BookingStorage.save(booking)

        # increment trip bookings and persist trip
        try:
            trip.increment_bookings()
            TripStorage.save(trip)
        except Exception:
            # best effort: rollback booking if trip update fails
            raise HTTPException(status_code=500, detail="Failed to update trip booking count")

        passenger_resp = PassengerResponse(
            name=participant.name,
            phone_number=participant.contact,
            gender=getattr(participant_data, 'gender', None),
            nationality=getattr(participant_data, 'nationality', None),
            date_of_birth=getattr(participant_data, 'date_of_birth', None),
            pick_up_point=getattr(participant_data, 'pick_up_point', None),
            notes=getattr(participant_data, 'notes', None),
        )

        return BookingResponse(
            booking_id=booking.booking_id,
            trip_id=booking.trip_id,
            participant_id=participant.participant_id,
            status=booking.status.status_code.value,
            message="Booking created",
            passenger=passenger_resp
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user_flexible)
):
    """Mengambil detail booking berdasarkan ID"""
    booking = _get_booking(booking_id)
    _ensure_ownership(booking, current_user)
    
    return BookingResponse(
        booking_id=booking.booking_id,
        trip_id=booking.trip_id,
        participant_id=booking.participant.participant_id,
        status=booking.status.status_code.value,
        message=booking.status.description,
        passenger=PassengerResponse(
            name=booking.participant.name,
            phone_number=booking.participant.phone_number,
            gender=booking.participant.gender,
            nationality=booking.participant.nationality,
            date_of_birth=booking.participant.date_of_birth,
            pick_up_point=booking.participant.pick_up_point,
            notes=booking.participant.notes
        )
    )

@router.get("/", response_model=List[BookingResponse])
def get_all_bookings(
    current_user: AuthenticatedUser = Depends(get_current_user_flexible)
):
    """Mengambil daftar semua booking milik user"""
    # Filter hanya booking milik user yang login
    all_bookings = BookingStorage.get_all()
    bookings = [
        b for b in all_bookings 
        if not hasattr(b, 'user_id') or b.user_id == current_user.id
    ]
    # Sync status based on trip schedule dates
    for b in bookings:
        try:
            # Only consider confirmed bookings for status changes
            if b.status.status_code == StatusCode.CONFIRMED:
                trip = TripStorage.find_by_id(b.trip_id)
                if trip:
                    schedules = trip.get_schedules()
                    if schedules:
                        # determine earliest start and latest end
                        starts = [s.start_date for s in schedules]
                        ends = [s.end_date for s in schedules]
                        earliest = min(starts)
                        latest = max(ends)
                        today = _date.today()
                        # If trip already finished -> completed
                        if latest < today:
                            b.update_status(BookingStatus.completed())
                            BookingStorage.save(b)
                        # If trip hasn't started yet -> upcoming
                        elif earliest >= today:
                            b.update_status(BookingStatus.upcoming())
                            BookingStorage.save(b)
        except Exception:
            # best-effort sync; do not fail the whole request
            continue
    return [
        BookingResponse(
            booking_id=b.booking_id,
            trip_id=b.trip_id,
            participant_id=b.participant.participant_id,
            status=b.status.status_code.value,
            message=b.status.description,
            passenger=PassengerResponse(
                name=b.participant.name,
                phone_number=b.participant.phone_number,
                gender=b.participant.gender,
                nationality=b.participant.nationality,
                date_of_birth=b.participant.date_of_birth,
                pick_up_point=b.participant.pick_up_point,
                notes=b.participant.notes
            )
        )
        for b in bookings
    ]


@router.get("/by_trip/{trip_id}")
def get_bookings_by_trip(trip_id: str):
    """Return bookings for a given trip_id (no ownership check).

    This endpoint is intended for internal UI needs where we want to
    display booking/participant data for a trip without requiring the
    request to originate from the booking owner.
    """
    try:
        all_bookings = BookingStorage.get_all()
        matched = [b for b in all_bookings if getattr(b, 'trip_id', None) == trip_id]

        results = []
        for b in matched:
            try:
                # Fetch the participant from database to get trip_pickup_id
                from backend.database import ParticipantModel, SessionLocal
                db = SessionLocal()
                try:
                    participant_model = db.query(ParticipantModel).filter(
                        ParticipantModel.participant_id == b.participant.participant_id
                    ).first()
                finally:
                    db.close()
                
                result = {
                    "booking_id": b.booking_id,
                    "trip_id": b.trip_id,
                    "participant_id": b.participant.participant_id,
                    "status": b.status.status_code.value,
                    "message": b.status.description,
                    "passenger": {
                        "name": b.participant.name,
                        "phone_number": b.participant.phone_number,
                        "gender": b.participant.gender,
                        "nationality": b.participant.nationality,
                        "date_of_birth": str(b.participant.date_of_birth) if b.participant.date_of_birth else None,
                        "pick_up_point": b.participant.pick_up_point,
                        "notes": b.participant.notes
                    }
                }
                results.append(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise

        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{booking_id}/confirm")
def confirm_booking(
    booking_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user_flexible)
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
    current_user: AuthenticatedUser = Depends(get_current_user_flexible)
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
