from backend.storage import BookingStorage, TransactionStorage, TripStorage
from backend.booking.aggregate_root import Booking
from backend.booking.entities import Participant
from backend.transaction.aggregate_root import Transaction
from backend.transaction.value_objects import PaymentMethod
from backend.trip.aggregate_root import Trip
from decimal import Decimal


def _make_booking(booking_id="b1", trip_id="t1"):
    participant = Participant(participant_id="p1", name="Test", contact="08123", address="Jl. Test")
    return Booking.create_booking(booking_id, trip_id, participant)


def _make_transaction(transaction_id="tx1", booking_id="b1"):
    tx = Transaction(transaction_id)
    method = PaymentMethod.credit_card("VISA")
    tx.initiate_payment(booking_id, Decimal("100.00"), method)
    return tx


def test_bookingstorage_all():
    b = _make_booking("b2", "t2")
    BookingStorage.save(b)
    found = BookingStorage.find_by_id("b2")
    assert found is not None
    assert found.booking_id == "b2"
    assert found.trip_id == "t2"

    by_trip = BookingStorage.find_by_trip_id("t2")
    assert len(by_trip) == 1
    assert by_trip[0].booking_id == "b2"

    all_bookings = BookingStorage.get_all()
    assert any(bk.booking_id == "b2" for bk in all_bookings)

    assert BookingStorage.delete("b2") is True
    assert BookingStorage.find_by_id("b2") is None
    assert BookingStorage.delete("notfound") is False


def test_transactionstorage_all():
    t = _make_transaction("tx2", "b1")
    TransactionStorage.save(t)
    found = TransactionStorage.find_by_id("tx2")
    assert found is not None
    assert found.transaction_id == "tx2"

    by_booking = TransactionStorage.find_by_booking_id("b1")
    assert by_booking is not None
    assert by_booking.transaction_id == "tx2"

    all_txs = TransactionStorage.get_all()
    assert any(tx.transaction_id == "tx2" for tx in all_txs)

    assert TransactionStorage.delete("tx2") is True
    assert TransactionStorage.find_by_id("tx2") is None
    assert TransactionStorage.delete("notfound") is False


def test_tripstorage_all():
    tr = Trip("t2", "Trip Two", 5)
    TripStorage.save(tr)
    found = TripStorage.find_by_id("t2")
    assert found is not None
    assert found.trip_id == "t2"
    assert found.trip_name == "Trip Two"

    all_trips = TripStorage.get_all()
    assert any(trip.trip_id == "t2" for trip in all_trips)

    assert TripStorage.delete("t2") is True
    assert TripStorage.find_by_id("t2") is None
    assert TripStorage.delete("notfound") is False

    # find_available_trips
    tr2 = Trip("t3", "Trip Three", 5)
    TripStorage.save(tr2)
    available = TripStorage.find_available_trips()
    assert any(trip.trip_id == "t3" for trip in available)
    TripStorage.delete("t3")
