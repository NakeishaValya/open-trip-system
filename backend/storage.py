from typing import Dict, Optional, List
from backend.booking.aggregate_root import Booking
from backend.transaction.aggregate_root import Transaction
from backend.trip.aggregate_root import Trip

# In-Memory Database
FAKE_BOOKING_DB: Dict[str, Booking] = {}
FAKE_TRANSACTION_DB: Dict[str, Transaction] = {}
FAKE_TRIP_DB: Dict[str, Trip] = {}

class BookingStorage:    
    @staticmethod
    def save(booking: Booking) -> None:
        FAKE_BOOKING_DB[booking.booking_id] = booking
    
    @staticmethod
    def find_by_id(booking_id: str) -> Optional[Booking]:
        return FAKE_BOOKING_DB.get(booking_id)
    
    @staticmethod
    def find_by_trip_id(trip_id: str) -> List[Booking]:
        return [b for b in FAKE_BOOKING_DB.values() if b.trip_id == trip_id]
    
    @staticmethod
    def get_all() -> List[Booking]:
        return list(FAKE_BOOKING_DB.values())
    
    @staticmethod
    def delete(booking_id: str) -> bool:
        if booking_id in FAKE_BOOKING_DB:
            del FAKE_BOOKING_DB[booking_id]
            return True
        return False

class TransactionStorage:    
    @staticmethod
    def save(transaction: Transaction) -> None:
        FAKE_TRANSACTION_DB[transaction.transaction_id] = transaction
    
    @staticmethod
    def find_by_id(transaction_id: str) -> Optional[Transaction]:
        return FAKE_TRANSACTION_DB.get(transaction_id)
    
    @staticmethod
    def find_by_booking_id(booking_id: str) -> Optional[Transaction]:
        for transaction in FAKE_TRANSACTION_DB.values():
            if transaction.booking_id == booking_id:
                return transaction
        return None
    
    @staticmethod
    def get_all() -> List[Transaction]:
        return list(FAKE_TRANSACTION_DB.values())
    
    @staticmethod
    def delete(transaction_id: str) -> bool:
        if transaction_id in FAKE_TRANSACTION_DB:
            del FAKE_TRANSACTION_DB[transaction_id]
            return True
        return False

class TripStorage:    
    @staticmethod
    def save(trip: Trip) -> None:
        FAKE_TRIP_DB[trip.trip_id] = trip
    
    @staticmethod
    def find_by_id(trip_id: str) -> Optional[Trip]:
        return FAKE_TRIP_DB.get(trip_id)
    
    @staticmethod
    def find_available_trips() -> List[Trip]:
        return [t for t in FAKE_TRIP_DB.values() if t.is_available_for_booking()]
    
    @staticmethod
    def get_all() -> List[Trip]:
        return list(FAKE_TRIP_DB.values())
    
    @staticmethod
    def delete(trip_id: str) -> bool:
        if trip_id in FAKE_TRIP_DB:
            del FAKE_TRIP_DB[trip_id]
            return True
        return False