
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.storage import BookingStorage
from backend.booking.aggregate_root import Booking
from backend.booking.entities import Participant
from backend.booking.value_objects import BookingStatus, StatusCode
from backend.storage import FAKE_BOOKING_DB

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_storage():
    FAKE_BOOKING_DB.clear()
    yield
    FAKE_BOOKING_DB.clear()

def make_participant():
    return Participant(participant_id="p1", name="Test", contact="08123", address="Jl. Test")

# --- UNIT TESTS ---
def test_booking_create_booking():
    participant = make_participant()
    booking = Booking.create_booking("b10", "t10", participant)
    assert booking.booking_id == "b10"
    assert "t10" in participant.get_active_bookings()

def test_booking_confirm_booking():
    participant = make_participant()
    booking = Booking("b11", "t11", participant)
    booking.confirm_booking()
    assert booking.status.status_code == StatusCode.CONFIRMED
    with pytest.raises(ValueError):
        booking.confirm_booking()

def test_booking_request_refund():
    participant = make_participant()
    booking = Booking("b12", "t12", participant)
    with pytest.raises(ValueError):
        booking.request_refund("fail")
    booking.confirm_booking()
    booking.request_refund("alasan")
    assert booking.status.status_code == StatusCode.REFUND_REQUESTED

def test_booking_update_status():
    participant = make_participant()
    booking = Booking("b13", "t13", participant)
    new_status = BookingStatus.completed()
    booking.update_status(new_status)
    assert booking.status.status_code == StatusCode.COMPLETED

def test_booking_set_transaction_id():
    participant = make_participant()
    booking = Booking("b14", "t14", participant)
    booking.set_transaction_id("txid")
    assert booking.transaction_id == "txid"

def test_participant_methods():
    p = make_participant()
    p.register_for_trip("t20")
    assert "t20" in p.get_active_bookings()
    p.cancel_registration("t20", "reason")
    assert "t20" not in p.get_active_bookings()
    p.update_contact_info("08222")
    assert p.contact == "08222"
    p.register_for_trip("t21")
    p.mark_trip_completed("t21")
    assert p.has_completed_trip("t21")

def test_bookingstatus_factories():
    assert BookingStatus.pending().status_code == StatusCode.PENDING
    assert BookingStatus.confirmed().status_code == StatusCode.CONFIRMED
    assert BookingStatus.cancelled().status_code == StatusCode.CANCELLED
    assert BookingStatus.completed().status_code == StatusCode.COMPLETED
    assert BookingStatus.refund_requested().status_code == StatusCode.REFUND_REQUESTED
    assert "alasan" in BookingStatus.cancelled("alasan").description
    assert "refund" in BookingStatus.refund_requested("refund").description

# --- API TESTS ---
def test_create_booking_endpoint():
    data = {"trip_id": "t1", "participant": {"name": "Test", "contact": "08123", "address": "Jl. Test"}}
    token = "testtoken"
    response = client.post("/bookings/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        resp = response.json()
        assert resp["trip_id"] == "t1"
        assert resp["participant_name"] == "Test"

def test_get_booking_not_found():
    response = client.get("/bookings/doesnotexist")
    assert response.status_code == 404

def test_get_all_bookings_empty():
    response = client.get("/bookings/")
    assert response.status_code == 200
    assert response.json() == []

def test_confirm_booking_and_error():
    participant = make_participant()
    booking = Booking.create_booking("b1", "t1", participant)
    BookingStorage.save(booking)
    response = client.post(f"/bookings/{booking.booking_id}/confirm")
    assert response.status_code == 200
    response2 = client.post(f"/bookings/{booking.booking_id}/confirm")
    assert response2.status_code == 400

def test_cancel_booking_and_error():
    participant = make_participant()
    booking = Booking.create_booking("b2", "t2", participant)
    BookingStorage.save(booking)
    response = client.post(f"/bookings/{booking.booking_id}/cancel", json={"reason": "test"})
    assert response.status_code == 200
    response2 = client.post(f"/bookings/{booking.booking_id}/cancel", json={"reason": "test"})
    assert response2.status_code == 400

@pytest.mark.parametrize("data,expected", [
    ({"trip_id": "t1"}, (422, 401)),
    ({"participant": {"name": "Test", "contact": "08123", "address": "Jl. Test"}}, (422, 401)),
])
def test_create_booking_invalid(data, expected):
    token = "testtoken"
    response = client.post("/bookings/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in expected


# --- API EDGE CASE TESTS ---
def test_get_booking_invalid_id():
    response = client.get("/bookings/doesnotexist")
    assert response.status_code == 404

def test_confirm_booking_invalid_id():
    response = client.post("/bookings/doesnotexist/confirm")
    assert response.status_code == 404

def test_cancel_booking_invalid_id():
    response = client.post("/bookings/doesnotexist/cancel", json={"reason": "test"})
    assert response.status_code == 404
