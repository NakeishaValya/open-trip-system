from backend.storage import BookingStorage, TransactionStorage, TripStorage
from backend.booking.aggregate_root import Booking
from backend.transaction.aggregate_root import Transaction
from backend.trip.aggregate_root import Trip
class DummyBooking(Booking):
    def __init__(self, booking_id="b1", trip_id="t1"):
        self.booking_id = booking_id
        self.trip_id = trip_id

class DummyTransaction(Transaction):
    def __init__(self, transaction_id="tx1"):
        self.transaction_id = transaction_id
        self.booking_id = "b1"

class DummyTrip(Trip):
    def __init__(self, trip_id="t1"):
        self.trip_id = trip_id
        self.capacity = 1
        self._current_bookings = 0
    def is_available_for_booking(self):
        return self._current_bookings < self.capacity

def test_bookingstorage_all():
    b = DummyBooking("b2", "t2")
    BookingStorage.save(b)
    assert BookingStorage.find_by_id("b2") == b
    assert BookingStorage.find_by_trip_id("t2")[0] == b
    assert b in BookingStorage.get_all()
    assert BookingStorage.delete("b2") is True
    assert BookingStorage.find_by_id("b2") is None
    assert BookingStorage.delete("notfound") is False

def test_transactionstorage_all():
    t = DummyTransaction("tx2")
    TransactionStorage.save(t)
    assert TransactionStorage.find_by_id("tx2") == t
    assert TransactionStorage.find_by_booking_id("b1") == t
    assert t in TransactionStorage.get_all()
    assert TransactionStorage.delete("tx2") is True
    assert TransactionStorage.find_by_id("tx2") is None
    assert TransactionStorage.delete("notfound") is False

def test_tripstorage_all():
    tr = DummyTrip("t2")
    TripStorage.save(tr)
    assert TripStorage.find_by_id("t2") == tr
    assert tr in TripStorage.get_all()
    assert TripStorage.delete("t2") is True
    assert TripStorage.find_by_id("t2") is None
    assert TripStorage.delete("notfound") is False
    # find_available_trips
    tr2 = DummyTrip("t3")
    TripStorage.save(tr2)
    assert tr2 in TripStorage.find_available_trips()
    TripStorage.delete("t3")
