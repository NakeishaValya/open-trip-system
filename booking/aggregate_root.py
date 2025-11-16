from typing import Optional
from .entities import Participant
from .value_objects import BookingStatus, StatusCode

class Booking:    
    def __init__(self, booking_id: str, trip_id: str, participant: Participant):
        self.booking_id = booking_id
        self.trip_id = trip_id
        self.participant = participant
        self.status = BookingStatus.pending()
        self.transaction_id: Optional[str] = None
    
    @staticmethod
    def create_booking(booking_id: str, trip_id: str, participant: Participant) -> 'Booking':
        booking = Booking(booking_id, trip_id, participant)
        participant.register_for_trip(trip_id)
        return booking
    
    def cancel_booking(self, reason: str) -> None:
        if self.status.status_code == StatusCode.CANCELLED:
            raise ValueError("Booking is already cancelled")
        
        self.status = BookingStatus.cancelled(reason)
        self.participant.cancel_registration(self.booking_id, reason)
    
    def confirm_booking(self) -> None:
        if self.status.status_code != StatusCode.PENDING:
            raise ValueError("Only pending bookings can be confirmed")
        
        self.status = BookingStatus.confirmed()
    
    def request_refund(self, reason: str) -> None:
        if self.status.status_code not in [StatusCode.CONFIRMED, StatusCode.COMPLETED]:
            raise ValueError("Only confirmed or completed bookings can request refund")
        
        self.status = BookingStatus.refund_requested(reason)
    
    def update_status(self, new_status: BookingStatus) -> None:
        self.status = new_status
    
    def set_transaction_id(self, transaction_id: str) -> None:
        self.transaction_id = transaction_id
