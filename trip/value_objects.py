from dataclasses import dataclass
from datetime import date
from typing import List

@dataclass(frozen=True)
class Schedule:
    start_date: date
    end_date: date
    location: str
    
    def __post_init__(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be after start date")
    
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1
    
    def overlaps_with(self, other: 'Schedule') -> bool:
        return not (self.end_date < other.start_date or self.start_date > other.end_date)

@dataclass(frozen=True)
class Itinerary:
    destination_list: tuple  # Using tuple for immutability
    description: str
    
    def __init__(self, destination_list: List[str], description: str):
        if not destination_list:
            raise ValueError("Destination list cannot be empty")
        
        object.__setattr__(self, 'destination_list', tuple(destination_list))
        object.__setattr__(self, 'description', description)
    
    def get_destinations(self) -> List[str]:
        return list(self.destination_list)
    
    def number_of_destinations(self) -> int:
        return len(self.destination_list)
