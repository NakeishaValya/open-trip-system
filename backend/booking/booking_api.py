from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from uuid import uuid4, UUID
from sqlalchemy.orm import Session
import os

import httpx

from .aggregate_root import Booking
from .entities import Participant
from backend.storage import BookingStorage
from backend.auth import get_current_user, get_current_user_flexible, AuthenticatedUser
from backend.storage import TripStorage
from .value_objects import BookingStatus, StatusCode
from backend.trip.aggregate_root import Trip
from backend.database import get_db, BookingModel, ParticipantModel

router = APIRouter(prefix="/bookings", tags=["Bookings"])
TRAVEL_PLANNER_URL = os.getenv("TRAVEL_PLANNER_URL", "http://localhost:8005")

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


def _build_planner_slot_urls(id_rencana: str, action: str) -> List[str]:
    """Build candidate URLs for direct travel_planner and django gateway modes."""
    base = (TRAVEL_PLANNER_URL or "").rstrip("/")
    if not base:
        return []

    # If pointing to django gateway `/api/planner`, call relative path without `/api/perencanaan`.
    if base.endswith("/api/planner"):
        return [f"{base}/trips/{id_rencana}/{action}"]

    # If already includes `/api/perencanaan`, append relative path.
    if base.endswith("/api/perencanaan"):
        return [f"{base}/trips/{id_rencana}/{action}"]

    # Default: direct call to travel planner FastAPI service.
    return [
        f"{base}/api/perencanaan/trips/{id_rencana}/{action}",
        f"{base}/api/planner/trips/{id_rencana}/{action}",
    ]


def _post_to_planner_slot_endpoint(id_rencana: str, action: str, participant_count: int) -> httpx.Response:
    last_response = None
    attempted_urls = _build_planner_slot_urls(id_rencana, action)
    for url in attempted_urls:
        try:
            response = httpx.post(url, json={"participant_count": participant_count}, timeout=10.0)
            # Try next candidate only when endpoint not found.
            if response.status_code == 404:
                last_response = response
                continue
            return response
        except Exception:
            continue

    if last_response is not None:
        return last_response
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Gagal menghubungi service travel planner. Cek TRAVEL_PLANNER_URL. attempted={attempted_urls}"
    )


def _reserve_slots_in_planner(id_rencana: str, participant_count: int) -> None:
    try:
        response = _post_to_planner_slot_endpoint(id_rencana, "reserve-slots", participant_count)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal menghubungi service travel planner: {str(exc)}"
        )

    if response.status_code >= 400:
        detail = "Slot tidak tersedia"
        try:
            body = response.json()
            detail = body.get("detail") or detail
        except Exception:
            pass

        if response.status_code == 409:
            mapped_status = status.HTTP_409_CONFLICT
        elif response.status_code == 404:
            mapped_status = status.HTTP_502_BAD_GATEWAY
            detail = "Endpoint slot travel planner tidak ditemukan. Periksa TRAVEL_PLANNER_URL dan prefix API service planner"
        else:
            mapped_status = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=mapped_status, detail=detail)


def _release_slots_in_planner(id_rencana: str, participant_count: int) -> None:
    try:
        _post_to_planner_slot_endpoint(id_rencana, "release-slots", participant_count)
    except Exception:
        # Best effort compensation only.
        pass


def _sync_slots_in_planner(id_rencana: str, participant_count: int) -> dict:
    response = _post_to_planner_slot_endpoint(id_rencana, "sync-slots", participant_count)

    if response.status_code >= 400:
        detail = f"Failed syncing trip {id_rencana}"
        try:
            body = response.json()
            detail = body.get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    try:
        return response.json() if isinstance(response.json(), dict) else {"trip_id": id_rencana}
    except Exception:
        return {"trip_id": id_rencana}

# Request/Response Models
class ParticipantRequest(BaseModel):
    name: str
    phone_number: str
    gender: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    pick_up_point: Optional[str] = None
    notes: Optional[str] = None

class ParticipantDetailRequest(BaseModel):
    """Detailed participant info with separate first/last names"""
    first_name: str
    last_name: str
    phone_number: str
    gender: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    pickup_location: Optional[str] = None
    trip_pickup_id: Optional[str] = None  # UUID from travel_planner trip_pickup_point table
    notes: Optional[str] = None

class CreateBookingRequest(BaseModel):
    trip_id: str
    participant: ParticipantRequest

class CreateMultiPassengerBookingRequest(BaseModel):
    """Request model for creating a booking with multiple passengers"""
    id_rencana: str  # Travel plan ID from travel_planner
    participants: List[ParticipantDetailRequest]
    payment_method: Optional[str] = None

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

class MultiPassengerBookingResponse(BaseModel):
    """Response model for multi-passenger booking"""
    booking_id: str
    id_rencana: str
    participant_ids: List[str]
    booking_status: str
    transaction_id: Optional[str] = None
    message: str

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

@router.post("/multi-passenger", status_code=status.HTTP_201_CREATED, response_model=MultiPassengerBookingResponse)
def create_multi_passenger_booking(
    request: CreateMultiPassengerBookingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """
    Create a booking with multiple passengers.
    
    This endpoint creates:
    - Multiple ParticipantModel records (one per passenger)
    - One BookingModel record with all participant_ids stored as an array
    
    All participants are linked to the same booking_id and id_rencana.
    """
    reserved_slots = False
    participant_count = len(request.participants or [])

    try:
        # Validate request
        if not request.participants or len(request.participants) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one participant is required"
            )
        
        _reserve_slots_in_planner(request.id_rencana, participant_count)
        reserved_slots = True

        # Generate IDs
        booking_id = uuid4()
        participant_ids = []
        
        # Create participant records
        for participant_data in request.participants:
            participant_id = uuid4()
            participant_ids.append(str(participant_id))
            
            # Parse trip_pickup_id if provided
            trip_pickup_uuid = None
            if participant_data.trip_pickup_id:
                try:
                    from uuid import UUID
                    trip_pickup_uuid = UUID(participant_data.trip_pickup_id)
                except (ValueError, AttributeError):
                    # If invalid UUID, log and continue with None
                    print(f"Invalid trip_pickup_id: {participant_data.trip_pickup_id}")
            
            # Create ParticipantModel
            participant = ParticipantModel(
                participant_id=participant_id,
                first_name=participant_data.first_name,
                last_name=participant_data.last_name,
                phone_number=participant_data.phone_number,
                gender=participant_data.gender,
                nationality=participant_data.nationality,
                date_of_birth=participant_data.date_of_birth,
                trip_pickup_id=trip_pickup_uuid,  # Store UUID from travel_planner
                notes=participant_data.notes
            )
            db.add(participant)
        
        # Create booking record with all participant IDs
        booking = BookingModel(
            booking_id=booking_id,
            user_id=current_user.id if hasattr(current_user, 'id') else str(current_user.user_id),
            id_rencana=request.id_rencana,
            participant_ids=participant_ids,  # Store as JSON array
            booking_status="PENDING",
            transaction_id=None
        )
        db.add(booking)
        
        # Commit all changes
        db.commit()
        db.refresh(booking)
        
        return MultiPassengerBookingResponse(
            booking_id=str(booking.booking_id),
            id_rencana=str(booking.id_rencana),
            participant_ids=booking.participant_ids,
            booking_status=booking.booking_status,
            transaction_id=str(booking.transaction_id) if booking.transaction_id else None,
            message=f"Booking created successfully with {len(participant_ids)} passenger(s)"
        )
        
    except HTTPException:
        if reserved_slots:
            _release_slots_in_planner(request.id_rencana, participant_count)
        raise
    except Exception as e:
        db.rollback()
        if reserved_slots:
            _release_slots_in_planner(request.id_rencana, participant_count)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create booking: {str(e)}"
        )

@router.get("/user/me")
def get_my_bookings(
    current_user: AuthenticatedUser = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """
    Get all bookings for the currently logged-in user.
    Returns bookings created via the multi-passenger endpoint.
    """
    try:
        # Query bookings for current user
        bookings = db.query(BookingModel).filter(
            BookingModel.user_id == current_user.id
        ).all()
        
        result = []
        for booking in bookings:
            # Get all participants for this booking
            participants = []
            if booking.participant_ids:
                for participant_id in booking.participant_ids:
                    participant = db.query(ParticipantModel).filter(
                        ParticipantModel.participant_id == participant_id
                    ).first()
                    if participant:
                        participants.append({
                            "participant_id": str(participant.participant_id),
                            "first_name": participant.first_name,
                            "last_name": participant.last_name,
                            "phone_number": participant.phone_number,
                            "gender": participant.gender,
                            "nationality": participant.nationality,
                            "date_of_birth": str(participant.date_of_birth) if participant.date_of_birth else None,
                            "trip_pickup_id": str(participant.trip_pickup_id) if participant.trip_pickup_id else None,
                            "notes": participant.notes
                        })
            
            result.append({
                "booking_id": str(booking.booking_id),
                "id_rencana": str(booking.id_rencana),
                "trip_id": str(booking.id_rencana),  # For compatibility
                "booking_status": booking.booking_status,
                "status": booking.booking_status,  # For compatibility
                "transaction_id": str(booking.transaction_id) if booking.transaction_id else None,
                "participants": participants,
                "participant_count": len(participants)
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bookings: {str(e)}"
        )


@router.post("/sync-slot-availability")
def sync_slot_availability(
    current_user: AuthenticatedUser = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """
    Recalculate slot_tersedia in travel_planner_db from existing open_trip bookings.

    Participant count per trip is derived from bookings.participant_ids array length.
    """
    try:
        bookings = db.query(BookingModel).all()
        participant_counts = {}

        for booking in bookings:
            trip_id = str(booking.id_rencana)
            participant_ids = booking.participant_ids or []
            participant_count = len(participant_ids) if isinstance(participant_ids, list) else 0
            participant_counts[trip_id] = participant_counts.get(trip_id, 0) + participant_count

        synced = []
        for trip_id, count in participant_counts.items():
            sync_result = _sync_slots_in_planner(trip_id, count)
            synced.append({
                "trip_id": trip_id,
                "participant_count": count,
                "slot_tersedia": sync_result.get("slot_tersedia")
            })

        return {
            "success": True,
            "synced_count": len(synced),
            "synced": synced
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synchronize slot availability: {str(e)}"
        )

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
def get_bookings_by_trip(
    trip_id: str,
    db: Session = Depends(get_db)
):
    """Return participant rows for a trip from open_trip_db.

    Data source:
    - bookings table (booking_id, booking_status, participant_ids, id_rencana)
    - participants table (participant profile fields)
    """
    try:
        try:
            trip_uuid = UUID(str(trip_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trip_id harus UUID valid"
            )

        bookings = db.query(BookingModel).filter(
            BookingModel.id_rencana == trip_uuid
        ).all()

        if not bookings:
            return []

        participant_ids = []
        booking_status_by_participant = {}
        booking_id_by_participant = {}

        for booking in bookings:
            ids = booking.participant_ids or []
            if not isinstance(ids, list):
                continue
            for pid in ids:
                participant_ids.append(str(pid))
                booking_status_by_participant[str(pid)] = booking.booking_status or "PENDING"
                booking_id_by_participant[str(pid)] = str(booking.booking_id)

        unique_participant_ids = list({pid for pid in participant_ids if pid})
        if not unique_participant_ids:
            return []

        participants = db.query(ParticipantModel).filter(
            ParticipantModel.participant_id.in_(unique_participant_ids)
        ).all()

        rows = []
        for p in participants:
            pid = str(p.participant_id)
            rows.append({
                "booking_id": booking_id_by_participant.get(pid),
                "booking_status": booking_status_by_participant.get(pid, "PENDING"),
                "participant_id": pid,
                "id_rencana": str(trip_uuid),
                "trip_id": str(trip_uuid),
                "first_name": p.first_name,
                "last_name": p.last_name,
                "phone_number": p.phone_number,
                "gender": p.gender,
                "date_of_birth": str(p.date_of_birth) if p.date_of_birth else None,
                "is_confirmed": bool(p.is_confirmed),
                "pick_up_point": None,
                "trip_pickup_id": str(p.trip_pickup_id) if p.trip_pickup_id else None,
                "nationality": p.nationality,
                "notes": p.notes,
            })

        return rows
    except HTTPException:
        raise
    except Exception as e:
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


@router.post("/participants/{participant_id}/confirm")
def confirm_participant(
    participant_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user_flexible),
    db: Session = Depends(get_db)
):
    """Update participant confirmation flag in participants table."""
    try:
        _ = current_user

        try:
            pid_uuid = UUID(str(participant_id))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="participant_id harus UUID valid"
            )

        updated_rows = db.query(ParticipantModel).filter(
            ParticipantModel.participant_id == pid_uuid
        ).update({ParticipantModel.is_confirmed: True}, synchronize_session=False)

        if updated_rows == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant tidak ditemukan"
            )

        db.commit()

        participant = db.query(ParticipantModel).filter(
            ParticipantModel.participant_id == pid_uuid
        ).first()

        if not participant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Participant berhasil diupdate tetapi gagal dibaca ulang"
            )

        db.refresh(participant)

        return {
            "participant_id": str(participant.participant_id),
            "first_name": participant.first_name,
            "last_name": participant.last_name,
            "is_confirmed": bool(participant.is_confirmed),
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengkonfirmasi participant: {str(e)}"
        )

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
