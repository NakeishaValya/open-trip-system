from typing import Optional, List
from decimal import Decimal

import backend.database as _db
from backend.database import (
    BookingModel, ParticipantModel,
    TransactionModel,
    TripModel, ScheduleModel, GuideModel, ItineraryModel,
)
from backend.booking.aggregate_root import Booking
from backend.booking.entities import Participant
from backend.booking.value_objects import BookingStatus, StatusCode
from backend.transaction.aggregate_root import Transaction
from backend.transaction.value_objects import PaymentStatus, PaymentStatusEnum, PaymentMethod, PaymentType
from backend.trip.aggregate_root import Trip
from backend.trip.entities import Guide
from backend.trip.value_objects import Schedule, Itinerary


# ============================================================================
# MAPPERS  â€“  ORM â†” Domain
# ============================================================================

def _participant_to_domain(row: ParticipantModel) -> Participant:
    return Participant(
        participant_id=row.participant_id,
        name=row.name,
        contact=row.contact,
        address=row.address,
    )


def _booking_to_domain(row: BookingModel) -> Booking:
    participant = _participant_to_domain(row.participant)
    booking = Booking.__new__(Booking)
    booking.booking_id = row.booking_id
    booking.trip_id = row.trip_id
    booking.participant = participant
    booking.status = BookingStatus(StatusCode(row.status_code), row.status_description)
    booking.transaction_id = row.transaction_id
    if row.user_id is not None:
        booking.user_id = row.user_id
    return booking


def _transaction_to_domain(row: TransactionModel) -> Transaction:
    tx = Transaction.__new__(Transaction)
    tx.transaction_id = row.transaction_id
    tx.booking_id = row.booking_id
    tx.total_amount = Decimal(str(row.total_amount)) if row.total_amount is not None else Decimal("0.00")

    status_enum = PaymentStatusEnum(row.payment_status)
    tx.status = PaymentStatus(status_enum, row.payment_status_timestamp)

    if row.payment_type:
        tx.payment_method = PaymentMethod(PaymentType(row.payment_type), row.payment_provider or "")
    else:
        tx.payment_method = None

    if row.user_id is not None:
        tx.user_id = row.user_id
    return tx


def _trip_to_domain(row: TripModel) -> Trip:
    trip = Trip.__new__(Trip)
    trip.trip_id = row.trip_id
    trip.trip_name = row.trip_name
    trip.capacity = row.capacity
    trip._current_bookings = row.current_bookings or 0

    # Schedules
    trip._schedules = []
    for s in (row.schedules or []):
        trip._schedules.append(Schedule(s.start_date, s.end_date, s.location))

    # Guide
    if row.guide:
        g = row.guide
        guide = Guide(g.guide_id, g.name, g.contact, g.language)
        guide.assign_to_trip(trip.trip_id)
        for sched in trip._schedules:
            guide.set_trip_schedule(trip.trip_id, sched.start_date, sched.end_date)
        trip._guide = guide
    else:
        trip._guide = None

    # Itinerary
    if row.itinerary:
        trip._itinerary = Itinerary(row.itinerary.destinations, row.itinerary.description)
    else:
        trip._itinerary = None

    if row.user_id is not None:
        trip.user_id = row.user_id
    return trip


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
            existing_p = session.get(ParticipantModel, p.participant_id)
            if existing_p:
                existing_p.name = p.name
                existing_p.contact = p.contact
                existing_p.address = p.address
            else:
                session.add(ParticipantModel(
                    participant_id=p.participant_id,
                    name=p.name,
                    contact=p.contact,
                    address=p.address,
                ))

            # Upsert booking
            existing = session.get(BookingModel, booking.booking_id)
            if existing:
                existing.trip_id = booking.trip_id
                existing.participant_id = p.participant_id
                existing.status_code = booking.status.status_code.value
                existing.status_description = booking.status.description
                existing.transaction_id = booking.transaction_id
                existing.user_id = getattr(booking, "user_id", None)
            else:
                session.add(BookingModel(
                    booking_id=booking.booking_id,
                    trip_id=booking.trip_id,
                    participant_id=p.participant_id,
                    status_code=booking.status.status_code.value,
                    status_description=booking.status.description,
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
            rows = session.query(BookingModel).filter(BookingModel.trip_id == trip_id).all()
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
                booking_id=transaction.booking_id,
                total_amount=transaction.total_amount,
                payment_status=transaction.status.status.value,
                payment_status_timestamp=transaction.status.timestamp,
                payment_type=transaction.payment_method.type.value if transaction.payment_method else None,
                payment_provider=transaction.payment_method.provider if transaction.payment_method else None,
                user_id=getattr(transaction, "user_id", None),
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
        session = _db.SessionLocal()
        try:
            row = session.query(TransactionModel).filter(
                TransactionModel.booking_id == booking_id
            ).first()
            return _transaction_to_domain(row) if row else None
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


# ============================================================================
# TRIP STORAGE
# ============================================================================

class TripStorage:
    @staticmethod
    def save(trip: Trip) -> None:
        session = _db.SessionLocal()
        try:
            existing = session.get(TripModel, trip.trip_id)

            if existing:
                existing.trip_name = trip.trip_name
                existing.capacity = trip.capacity
                existing.current_bookings = trip._current_bookings
                existing.user_id = getattr(trip, "user_id", None)

                # Sync schedules â€“ replace all
                session.query(ScheduleModel).filter(ScheduleModel.trip_id == trip.trip_id).delete()
                for s in trip.get_schedules():
                    session.add(ScheduleModel(
                        trip_id=trip.trip_id,
                        start_date=s.start_date,
                        end_date=s.end_date,
                        location=s.location,
                    ))

                # Sync guide
                session.query(GuideModel).filter(GuideModel.trip_id == trip.trip_id).delete()
                guide = trip.get_guide()
                if guide:
                    session.add(GuideModel(
                        guide_id=guide.guide_id,
                        trip_id=trip.trip_id,
                        name=guide.name,
                        contact=guide.contact,
                        language=guide.language,
                    ))

                # Sync itinerary
                session.query(ItineraryModel).filter(ItineraryModel.trip_id == trip.trip_id).delete()
                itin = trip.get_itinerary()
                if itin:
                    session.add(ItineraryModel(
                        trip_id=trip.trip_id,
                        destinations=list(itin.destination_list),
                        description=itin.description,
                    ))
            else:
                trip_model = TripModel(
                    trip_id=trip.trip_id,
                    trip_name=trip.trip_name,
                    capacity=trip.capacity,
                    current_bookings=trip._current_bookings,
                    user_id=getattr(trip, "user_id", None),
                )
                session.add(trip_model)

                for s in trip.get_schedules():
                    session.add(ScheduleModel(
                        trip_id=trip.trip_id,
                        start_date=s.start_date,
                        end_date=s.end_date,
                        location=s.location,
                    ))

                guide = trip.get_guide()
                if guide:
                    session.add(GuideModel(
                        guide_id=guide.guide_id,
                        trip_id=trip.trip_id,
                        name=guide.name,
                        contact=guide.contact,
                        language=guide.language,
                    ))

                itin = trip.get_itinerary()
                if itin:
                    session.add(ItineraryModel(
                        trip_id=trip.trip_id,
                        destinations=list(itin.destination_list),
                        description=itin.description,
                    ))

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def find_by_id(trip_id: str) -> Optional[Trip]:
        session = _db.SessionLocal()
        try:
            row = session.get(TripModel, trip_id)
            return _trip_to_domain(row) if row else None
        finally:
            session.close()

    @staticmethod
    def find_available_trips() -> List[Trip]:
        session = _db.SessionLocal()
        try:
            rows = session.query(TripModel).filter(
                TripModel.current_bookings < TripModel.capacity
            ).all()
            return [_trip_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def get_all() -> List[Trip]:
        session = _db.SessionLocal()
        try:
            rows = session.query(TripModel).all()
            return [_trip_to_domain(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def delete(trip_id: str) -> bool:
        session = _db.SessionLocal()
        try:
            row = session.get(TripModel, trip_id)
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
