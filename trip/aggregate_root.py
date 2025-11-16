from typing import List, Optional
from datetime import date
from .entities import Guide
from .value_objects import Schedule, Itinerary

class Trip:    
    def __init__(self, trip_id: str, trip_name: str, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be greater than zero")
        
        self.trip_id = trip_id
        self.trip_name = trip_name
        self.capacity = capacity
        self._schedules: List[Schedule] = []
        self._itinerary: Optional[Itinerary] = None
        self._guide: Optional[Guide] = None
        self._current_bookings: int = 0
    
    def add_schedule(self, start_date: date, end_date: date, location: str) -> None:
        new_schedule = Schedule(start_date, end_date, location)
        
        # Check for overlapping schedules
        for existing_schedule in self._schedules:
            if new_schedule.overlaps_with(existing_schedule):
                raise ValueError(f"Schedule overlaps with existing schedule at {existing_schedule.location}")
        
        self._schedules.append(new_schedule)
    
    def assign_guide(self, guide: Guide) -> None:
        if self._guide is not None:
            raise ValueError("Trip already has an assigned guide")
        
        # Check if guide is available for all schedules
        for schedule in self._schedules:
            if not guide.is_available(schedule.start_date, schedule.end_date):
                raise ValueError(f"Guide is not available for schedule at {schedule.location}")
        
        self._guide = guide
        guide.assign_to_trip(self.trip_id)
        
        # Set schedule for guide
        for schedule in self._schedules:
            guide.set_trip_schedule(self.trip_id, schedule.start_date, schedule.end_date)
    
    def update_capacity(self, new_capacity: int) -> None:
        if new_capacity <= 0:
            raise ValueError("Capacity must be greater than zero")
        
        if new_capacity < self._current_bookings:
            raise ValueError(f"Cannot reduce capacity below current bookings ({self._current_bookings})")
        
        self.capacity = new_capacity
    
    def update_itinerary(self, destinations: List[str], description: str) -> None:
        self._itinerary = Itinerary(destinations, description)
    
    def get_schedules(self) -> List[Schedule]:
        return self._schedules.copy()
    
    def get_itinerary(self) -> Optional[Itinerary]:
        return self._itinerary
    
    def get_guide(self) -> Optional[Guide]:
        return self._guide
    
    def is_available_for_booking(self) -> bool:
        return self._current_bookings < self.capacity
    
    def increment_bookings(self) -> None:
        if not self.is_available_for_booking():
            raise ValueError("Trip is at full capacity")
        self._current_bookings += 1
    
    def decrement_bookings(self) -> None:
        if self._current_bookings > 0:
            self._current_bookings -= 1
