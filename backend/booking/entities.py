from typing import List

class Participant:
    def __init__(self, participant_id: str, name: str, contact: str, address: str):
        self.participant_id = participant_id
        self.name = name
        self.contact = contact
        self.address = address
        self._active_bookings: List[str] = []
        self._completed_trips: List[str] = []
    
    def register_for_trip(self, trip_id: str) -> None:
        if trip_id not in self._active_bookings:
            self._active_bookings.append(trip_id)
    
    def cancel_registration(self, booking_id: str, reason: str) -> None:
        if booking_id in self._active_bookings:
            self._active_bookings.remove(booking_id)
    
    def update_contact_info(self, new_contact: str) -> None:
        self.contact = new_contact
    
    def get_active_bookings(self) -> List[str]:
        return self._active_bookings.copy()
    
    def has_completed_trip(self, trip_id: str) -> bool:
        return trip_id in self._completed_trips
    
    def mark_trip_completed(self, trip_id: str) -> None:
        if trip_id in self._active_bookings:
            self._active_bookings.remove(trip_id)
        if trip_id not in self._completed_trips:
            self._completed_trips.append(trip_id)
