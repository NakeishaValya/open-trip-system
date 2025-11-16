from dataclasses import dataclass
from enum import Enum

class StatusCode(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    REFUND_REQUESTED = "REFUND_REQUESTED"

@dataclass(frozen=True)
class BookingStatus:
    status_code: StatusCode
    description: str
    
    @staticmethod
    def pending():
        return BookingStatus(StatusCode.PENDING, "Booking is pending confirmation")
    
    @staticmethod
    def confirmed():
        return BookingStatus(StatusCode.CONFIRMED, "Booking is confirmed")
    
    @staticmethod
    def cancelled(reason: str = ""):
        description = f"Booking is cancelled: {reason}" if reason else "Booking is cancelled"
        return BookingStatus(StatusCode.CANCELLED, description)
    
    @staticmethod
    def completed():
        return BookingStatus(StatusCode.COMPLETED, "Booking is completed")
    
    @staticmethod
    def refund_requested(reason: str = ""):
        description = f"Refund requested: {reason}" if reason else "Refund requested"
        return BookingStatus(StatusCode.REFUND_REQUESTED, description)
