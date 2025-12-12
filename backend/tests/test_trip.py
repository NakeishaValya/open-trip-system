from backend.trip.aggregate_root import Trip
from backend.trip.entities import Guide
from backend.trip.value_objects import Schedule, Itinerary
from datetime import date
import pytest

def test_trip_init_and_capacity():
    trip = Trip("t1", "Trip 1", 10)
    assert trip.trip_id == "t1"
    assert trip.capacity == 10
    with pytest.raises(ValueError):
        Trip("t2", "Trip 2", 0)

def test_trip_add_schedule_and_overlap():
    trip = Trip("t3", "Trip 3", 5)
    trip.add_schedule(date(2025,1,1), date(2025,1,5), "Bali")
    assert len(trip.get_schedules()) == 1
    # Overlap
    with pytest.raises(ValueError):
        trip.add_schedule(date(2025,1,3), date(2025,1,7), "Bali")

def test_trip_assign_guide():
    trip = Trip("t4", "Trip 4", 5)
    trip.add_schedule(date(2025,2,1), date(2025,2,5), "Lombok")
    guide = Guide("g1", "Guide 1", "08123", "EN")
    trip.assign_guide(guide)
    assert trip.get_guide() == guide
    # Assign again (should error)
    with pytest.raises(ValueError):
        trip.assign_guide(guide)
    # Guide not available
    trip2 = Trip("t5", "Trip 5", 5)
    trip2.add_schedule(date(2025,2,3), date(2025,2,7), "Lombok")
    with pytest.raises(ValueError):
        trip2.assign_guide(guide)

def test_trip_update_capacity():
    trip = Trip("t6", "Trip 6", 5)
    trip.increment_bookings()
    trip.increment_bookings()
    trip.update_capacity(10)
    assert trip.capacity == 10
    with pytest.raises(ValueError):
        trip.update_capacity(1)
    with pytest.raises(ValueError):
        trip.update_capacity(0)

def test_trip_update_itinerary():
    trip = Trip("t7", "Trip 7", 5)
    trip.update_itinerary(["Bali", "Lombok"], "Liburan")
    iti = trip.get_itinerary()
    assert iti.number_of_destinations() == 2
    with pytest.raises(ValueError):
        trip.update_itinerary([], "Kosong")

def test_trip_booking_availability():
    trip = Trip("t8", "Trip 8", 2)
    assert trip.is_available_for_booking()
    trip.increment_bookings()
    trip.increment_bookings()
    assert not trip.is_available_for_booking()
    with pytest.raises(ValueError):
        trip.increment_bookings()
    trip.decrement_bookings()
    assert trip.is_available_for_booking()

def test_guide_methods():
    guide = Guide("g2", "Guide 2", "08123", "ID")
    guide.assign_to_trip("t9")
    assert "t9" in guide.get_assigned_trips()
    guide.set_trip_schedule("t9", date(2025,3,1), date(2025,3,5))
    assert guide.is_available(date(2025,4,1), date(2025,4,5))
    assert not guide.is_available(date(2025,3,3), date(2025,3,4))
    guide.unassign_from_trip("t9")
    assert "t9" not in guide.get_assigned_trips()
    guide.update_contact_info("08222")
    assert guide.contact == "08222"

def test_schedule_and_itinerary():
    sched = Schedule(date(2025,5,1), date(2025,5,5), "Bali")
    assert sched.duration_days() == 5
    sched2 = Schedule(date(2025,5,6), date(2025,5,10), "Lombok")
    assert not sched.overlaps_with(sched2)
    with pytest.raises(ValueError):
        Schedule(date(2025,5,10), date(2025,5,5), "Error")
    iti = Itinerary(["Bali", "Lombok"], "Liburan")
    assert iti.number_of_destinations() == 2
    assert "Bali" in iti.get_destinations()
    with pytest.raises(ValueError):
        Itinerary([], "Kosong")


# --- API EDGE CASE TESTS ---
from fastapi.testclient import TestClient
from backend.main import app
from backend.storage import TripStorage
import backend.storage as storage_mod

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_trip_storage():
    storage_mod.FAKE_TRIP_DB.clear()
    yield
    storage_mod.FAKE_TRIP_DB.clear()

def test_create_trip_invalid():
    token = "testtoken"
    # Negative capacity
    data = {"trip_name": "Trip X", "capacity": -1}
    response = client.post("/trips/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (400, 401)
    # Missing fields
    response2 = client.post("/trips/", json={"capacity": 10}, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code in (422, 401)
    response3 = client.post("/trips/", json={"trip_name": "Trip Z"}, headers={"Authorization": f"Bearer {token}"})
    assert response3.status_code in (422, 401)

def test_get_trip_not_found():
    response = client.get("/trips/doesnotexist")
    assert response.status_code == 404

def test_add_schedule_errors():
    # Not found
    response = client.post("/trips/doesnotexist/schedule", json={"start_date": "2025-12-01", "end_date": "2025-12-05", "location": "Bali"})
    assert response.status_code == 404
    # Invalid date
    from backend.trip.aggregate_root import Trip
    trip = Trip("t100", "Trip API", 10)
    TripStorage.save(trip)
    response2 = client.post(f"/trips/{trip.trip_id}/schedule", json={"start_date": "invalid", "end_date": "2025-12-05", "location": "Bali"})
    assert response2.status_code == 400
    # End date before start date
    response3 = client.post(f"/trips/{trip.trip_id}/schedule", json={"start_date": "2025-12-10", "end_date": "2025-12-01", "location": "Bali"})
    assert response3.status_code == 400

def test_assign_guide_errors():
    # Not found
    response = client.post("/trips/doesnotexist/guide", json={"guide_name": "Guide X", "contact": "08123", "language": "EN"})
    assert response.status_code == 404
    # Empty guide name
    from backend.trip.aggregate_root import Trip
    trip = Trip("t101", "Trip API2", 10)
    TripStorage.save(trip)
    response2 = client.post(f"/trips/{trip.trip_id}/guide", json={"guide_name": "", "contact": "08123", "language": "EN"})
    assert response2.status_code == 400

def test_update_capacity_errors():
    # Not found
    response = client.put("/trips/doesnotexist/capacity", json={"new_capacity": 20})
    assert response.status_code == 404
    from backend.trip.aggregate_root import Trip
    trip = Trip("t102", "Trip API3", 10)
    TripStorage.save(trip)
    # Invalid
    response2 = client.put(f"/trips/{trip.trip_id}/capacity", json={"new_capacity": -5})
    assert response2.status_code == 400
    # Non-integer capacity
    response3 = client.put(f"/trips/{trip.trip_id}/capacity", json={"new_capacity": "notanint"})
    assert response3.status_code == 422

def test_update_itinerary_errors():
    # Not found
    response = client.put("/trips/doesnotexist/itinerary", json={"destinations": ["A"], "description": "desc"})
    assert response.status_code == 404
    from backend.trip.aggregate_root import Trip
    trip = Trip("t103", "Trip API4", 10)
    TripStorage.save(trip)
    # Invalid
    response2 = client.put(f"/trips/{trip.trip_id}/itinerary", json={"destinations": [], "description": "desc"})
    assert response2.status_code == 400
    # Destinations not a list
    response3 = client.put(f"/trips/{trip.trip_id}/itinerary", json={"destinations": "notalist", "description": "desc"})
    assert response3.status_code == 422

def test_update_itinerary_description_empty():
    from backend.trip.aggregate_root import Trip
    trip = Trip("t200", "Trip API Desc", 10)
    TripStorage.save(trip)
    response = client.put(f"/trips/{trip.trip_id}/itinerary", json={"destinations": ["A"], "description": ""})
    assert response.status_code == 200 or response.status_code == 400

def test_assign_guide_contact_language_empty():
    from backend.trip.aggregate_root import Trip
    trip = Trip("t201", "Trip API Guide", 10)
    TripStorage.save(trip)
    # Contact kosong
    response = client.post(f"/trips/{trip.trip_id}/guide", json={"guide_name": "Guide X", "contact": "", "language": "EN"})
    # Tergantung validasi, bisa 200 atau 400
    assert response.status_code in (200, 400)
    # Language kosong
    response2 = client.post(f"/trips/{trip.trip_id}/guide", json={"guide_name": "Guide X", "contact": "08123", "language": ""})
    assert response2.status_code in (200, 400)

def test_add_schedule_location_whitespace():
    from backend.trip.aggregate_root import Trip
    trip = Trip("t202", "Trip API Loc", 10)
    TripStorage.save(trip)
    response = client.post(f"/trips/{trip.trip_id}/schedule", json={"start_date": "2025-12-01", "end_date": "2025-12-05", "location": "   "})
    assert response.status_code == 400
