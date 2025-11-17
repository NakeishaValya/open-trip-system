from typing import List
from datetime import date

class Guide:
    def __init__(self, guide_id: str, name: str, contact: str, language: str):
        self.guide_id = guide_id
        self.name = name
        self.contact = contact
        self.language = language
        self._assigned_trips: List[str] = []
        self._trip_schedules: dict = {}  # {trip_id: (start_date, end_date)}
    
    def assign_to_trip(self, trip_id: str) -> None:
        if trip_id not in self._assigned_trips:
            self._assigned_trips.append(trip_id)
    
    def unassign_from_trip(self, trip_id: str) -> None:
        if trip_id in self._assigned_trips:
            self._assigned_trips.remove(trip_id)
            if trip_id in self._trip_schedules:
                del self._trip_schedules[trip_id]
    
    def update_contact_info(self, new_contact: str) -> None:
        self.contact = new_contact
    
    def get_assigned_trips(self) -> List[str]:
        return self._assigned_trips.copy()
    
    def is_available(self, start_date: date, end_date: date) -> bool:
        for trip_id, (trip_start, trip_end) in self._trip_schedules.items():
            # Check for date overlap
            if not (end_date < trip_start or start_date > trip_end):
                return False
        return True
    
    def set_trip_schedule(self, trip_id: str, start_date: date, end_date: date) -> None:
        self._trip_schedules[trip_id] = (start_date, end_date)
