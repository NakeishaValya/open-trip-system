from typing import Optional, List
from decimal import Decimal
from datetime import date

import backend.database as _db
from backend.database import (
    BookingModel, ParticipantModel,
    TransactionModel,
    # NOTE: Trip-related models (TripModel, ScheduleModel, GuideModel, ItineraryModel)
    # have been MOVED to Travel Planner microservice
)
from backend.booking.aggregate_root import Booking
from backend.booking.entities import Participant
from backend.booking.value_objects import BookingStatus, StatusCode
from backend.transaction.aggregate_root import Transaction
from backend.transaction.value_objects import PaymentStatus, PaymentStatusEnum, PaymentMethod, PaymentType
# NOTE: Trip-related domain models moved to Travel Planner
# from backend.trip.aggregate_root import Trip
# from backend.trip.entities import Guide
# from backend.trip.value_objects import Schedule, Itinerary
from sqlalchemy.orm import Session


# ============================================================================
# MAPPERS  — ORM ↔ Domain
# ============================================================================

def _participant_to_domain(row: ParticipantModel) -> Participant:
    # Combine first_name and last_name from DB to name in domain
    full_name = f"{row.first_name} {row.last_name}".strip()
    return Participant(
        participant_id=str(row.participant_id),  # Convert UUID to string
        name=full_name,
        contact=row.phone_number,  # Map phone_number to contact
        address='',  # pick_up_point removed from new schema
        gender=row.gender,
        nationality=row.nationality,
        date_of_birth=row.date_of_birth,
        notes=row.notes,
    )


def _booking_to_domain(row: BookingModel) -> Booking:
    participant = _participant_to_domain(row.participant)
    booking = Booking.__new__(Booking)
    booking.booking_id = str(row.booking_id)  # Convert UUID to string
    booking.trip_id = str(row.id_rencana)  # Map id_rencana to trip_id
    booking.participant = participant
    # Map booking_status to domain model (status_code and description)
    booking.status = BookingStatus(StatusCode(row.booking_status), row.booking_status)
    booking.transaction_id = str(row.transaction_id) if row.transaction_id else None
    if row.user_id is not None:
        booking.user_id = row.user_id
    return booking


def _transaction_to_domain(row: TransactionModel) -> Transaction:
    tx = Transaction.__new__(Transaction)
    tx.transaction_id = row.transaction_id
    # Note: booking_id removed from new schema, set to None for backward compatibility
    tx.booking_id = None
    tx.total_amount = Decimal(str(row.total_price)) if row.total_price is not None else Decimal("0.00")

    status_enum = PaymentStatusEnum(row.payment_status)
    # payment_status_timestamp removed from new schema, use None
    tx.status = PaymentStatus(status_enum, None)

    # payment_method stored as single field, parse if needed
    if row.payment_method:
        # Assume payment_method is stored as type string (e.g., "CREDIT_CARD")
        try:
            tx.payment_method = PaymentMethod(PaymentType(row.payment_method), "")
        except:
            tx.payment_method = None
    else:
        tx.payment_method = None

    # user_id removed from new schema
    tx.user_id = None
    return tx


# NOTE: _trip_to_domain() removed - Trip domain is now in Travel Planner service


# ============================================================================
# BOOKING STORAGE
# ============================================================================

class BookingStorage:
    @staticmethod
    def save(booking: Booking) -> None:
        session = _db.SessionLocal()
        try:
            # Upsert participant
            p = booking.participant
            # Split name into first_name and last_name
            name_parts = p.name.strip().split(' ', 1)
            first_name = name_parts[0] if len(name_parts) > 0 else 'Unknown'
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            existing_p = session.get(ParticipantModel, p.participant_id)
            if existing_p:
                existing_p.first_name = first_name
                existing_p.last_name = last_name
                existing_p.phone_number = p.contact
            else:
                session.add(ParticipantModel(
                    participant_id=p.participant_id,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=p.contact,
                ))

            # Upsert booking
            existing = session.get(BookingModel, booking.booking_id)
            if existing:
                existing.id_rencana = booking.trip_id
                existing.participant_id = p.participant_id
                existing.booking_status = booking.status.status_code.value
                existing.transaction_id = booking.transaction_id
                existing.user_id = getattr(booking, "user_id", None)
            else:
                session.add(BookingModel(
                    booking_id=booking.booking_id,
                    id_rencana=booking.trip_id,
                    participant_id=p.participant_id,
                    booking_status=booking.status.status_code.value,
                    transaction_id=booking.transaction_id,
                    user_id=getattr(booking, "user_id", None),
                ))

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def find_by_id(booking_id: str) -> Optional[Booking]:
        session = _db.SessionLocal()
        try:
            row = session.get(BookingModel, booking_id)
            return _booking_to_domain(row) if row else None
        finally:
            session.close()

    @staticmethod
    def find_by_trip_id(trip_id: str) -> List[Booking]:
        session = _db.SessionLocal()
        try:
            rows = session.query(BookingModel).filter(BookingModel.id_rencana == trip_id).all()
            return [_booking_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def get_all() -> List[Booking]:
        session = _db.SessionLocal()
        try:
            rows = session.query(BookingModel).all()
            return [_booking_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def find_by_user_id(user_id: str) -> List[Booking]:
        """Find all bookings for a specific user"""
        session = _db.SessionLocal()
        try:
            rows = session.query(BookingModel).filter(BookingModel.user_id == user_id).all()
            return [_booking_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def delete(booking_id: str) -> bool:
        session = _db.SessionLocal()
        try:
            row = session.get(BookingModel, booking_id)
            if row:
                session.delete(row)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# ============================================================================
# TRANSACTION STORAGE
# ============================================================================

class TransactionStorage:
    @staticmethod
    def save(transaction: Transaction) -> None:
        session = _db.SessionLocal()
        try:
            existing = session.get(TransactionModel, transaction.transaction_id)
            data = dict(
                transaction_id=transaction.transaction_id,
                total_price=transaction.total_amount,
                trip_price=Decimal("0.00"),  # Default, should be set from trip API
                pickup_fee=Decimal("0.00"),  # Default, calculate as total_price - trip_price
                payment_status=transaction.status.status.value,
                payment_method=transaction.payment_method.type.value if transaction.payment_method else None,
            )
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
            else:
                session.add(TransactionModel(**data))

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def find_by_id(transaction_id: str) -> Optional[Transaction]:
        session = _db.SessionLocal()
        try:
            row = session.get(TransactionModel, transaction_id)
            return _transaction_to_domain(row) if row else None
        finally:
            session.close()

    @staticmethod
    def find_by_booking_id(booking_id: str) -> Optional[Transaction]:
        """
        Find transaction by booking_id.
        Note: In new schema, booking_id is not directly in transactions table.
        We need to query bookings table first to get transaction_id.
        """
        session = _db.SessionLocal()
        try:
            # Find booking first to get transaction_id
            booking_row = session.get(BookingModel, booking_id)
            if not booking_row or not booking_row.transaction_id:
                return None
            
            # Then find transaction by transaction_id
            tx_row = session.get(TransactionModel, booking_row.transaction_id)
            return _transaction_to_domain(tx_row) if tx_row else None
        finally:
            session.close()

    @staticmethod
    def get_all() -> List[Transaction]:
        session = _db.SessionLocal()
        try:
            rows = session.query(TransactionModel).all()
            return [_transaction_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def delete(transaction_id: str) -> bool:
        session = _db.SessionLocal()
        try:
            row = session.get(TransactionModel, transaction_id)
            if row:
                session.delete(row)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


"""
Temporary TripStorage implementation

The original project moved trip persistence to the Travel Planner service.
To keep this microservice runnable for local development and tests that
expect `TripStorage` to exist, provide a lightweight in-memory store.

This is NOT meant for production — replace with inter-service calls or
shared database integration as needed.
"""

from backend.trip.aggregate_root import Trip

# Simple in-memory store: {trip_id: Trip}
_trip_store = {}

class TripStorage:
    @staticmethod
    def save(trip: Trip) -> None:
        _trip_store[trip.trip_id] = trip

    @staticmethod
    def find_by_id(trip_id: str) -> Optional[Trip]:
        return _trip_store.get(trip_id)

    @staticmethod
    def get_all() -> List[Trip]:
        return list(_trip_store.values())

    @staticmethod
    def delete(trip_id: str) -> bool:
        if trip_id in _trip_store:
            del _trip_store[trip_id]
            return True
        return False



# ============================================================================
# PARTICIPANT STORAGE
# ============================================================================

class ParticipantStorage:
    def __init__(self, session: Session):
        self.session = session

    def save(
        self, 
        participant_id: str, 
        name: str, 
        phone_number: str,
        gender: Optional[str] = None,
        nationality: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        pick_up_point: Optional[str] = None,
        notes: Optional[str] = None
    ):
        participant = ParticipantModel(
            participant_id=participant_id,
            name=name,
            phone_number=phone_number,
            gender=gender,
            nationality=nationality,
            date_of_birth=date_of_birth,
            pick_up_point=pick_up_point,
            notes=notes
        )
        self.session.add(participant)
        self.session.commit()

    def find_by_id(self, participant_id: str) -> Optional[ParticipantModel]:
        return self.session.query(ParticipantModel).filter(
            ParticipantModel.participant_id == participant_id
        ).first()
