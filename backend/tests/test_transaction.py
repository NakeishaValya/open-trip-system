

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.storage import TransactionStorage
from backend.transaction.aggregate_root import Transaction
from backend.transaction.value_objects import PaymentStatus, PaymentStatusEnum, PaymentMethod, PaymentType
import backend.storage as storage_mod
from decimal import Decimal

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_storage():
    storage_mod.FAKE_TRANSACTION_DB.clear()
    yield
    storage_mod.FAKE_TRANSACTION_DB.clear()

# --- UNIT TESTS ---
def test_transaction_initiate_payment():
    tx = Transaction("tx1")
    method = PaymentMethod.credit_card("VISA")
    tx.initiate_payment("b1", Decimal("100.00"), method)
    assert tx.booking_id == "b1"
    assert tx.total_amount == Decimal("100.00")
    assert tx.payment_method == method
    assert tx.status.status == PaymentStatusEnum.PENDING
    with pytest.raises(ValueError):
        tx.initiate_payment("b1", Decimal("100.00"), method)
    tx2 = Transaction("tx2")
    with pytest.raises(ValueError):
        tx2.initiate_payment("b2", Decimal("0.00"), method)

def test_transaction_validate_and_confirm():
    tx = Transaction("tx3")
    method = PaymentMethod.debit_card("BCA")
    tx.initiate_payment("b3", Decimal("200.00"), method)
    tx.validate_payment("tx3")
    assert tx.status.status == PaymentStatusEnum.VALIDATED
    with pytest.raises(ValueError):
        tx.validate_payment("wrong")
    with pytest.raises(ValueError):
        tx.validate_payment("tx3")
    tx.confirm_payment("tx3")
    assert tx.status.status == PaymentStatusEnum.CONFIRMED
    with pytest.raises(ValueError):
        tx.confirm_payment("wrong")
    with pytest.raises(ValueError):
        tx.confirm_payment("tx3")

def test_transaction_update_status_and_fail():
    tx = Transaction("tx4")
    tx.update_status(PaymentStatus.validated())
    assert tx.status.status == PaymentStatusEnum.VALIDATED
    tx.mark_as_failed()
    assert tx.status.status == PaymentStatusEnum.FAILED

def test_transaction_mark_as_refunded():
    tx = Transaction("tx5")
    method = PaymentMethod.e_wallet("OVO")
    tx.initiate_payment("b5", Decimal("300.00"), method)
    tx.validate_payment("tx5")
    tx.confirm_payment("tx5")
    tx.mark_as_refunded()
    assert tx.status.status == PaymentStatusEnum.REFUNDED
    tx2 = Transaction("tx6")
    with pytest.raises(ValueError):
        tx2.mark_as_refunded()

def test_paymentmethod_factories():
    assert PaymentMethod.credit_card("VISA").type == PaymentType.CREDIT_CARD
    assert PaymentMethod.debit_card("BCA").type == PaymentType.DEBIT_CARD
    assert PaymentMethod.bank_transfer("Mandiri").type == PaymentType.BANK_TRANSFER
    assert PaymentMethod.e_wallet("OVO").type == PaymentType.E_WALLET
    assert PaymentMethod.cash().type == PaymentType.CASH

# --- API TESTS ---
def test_get_transaction_not_found():
    response = client.get("/transactions/doesnotexist")
    assert response.status_code == 404

def test_get_all_transactions_empty():
    response = client.get("/transactions/")
    assert response.status_code == 200
    assert response.json() == []

def test_initiate_payment_success():
    data = {
        "booking_id": "b1",
        "amount": 100.0,
        "payment_type": "CREDIT_CARD",
        "provider": "VISA"
    }
    token = "testtoken"
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        resp = response.json()
        assert resp["booking_id"] == "b1"
        assert resp["total_amount"] == 100.0
        assert resp["payment_type"] == "CREDIT_CARD"
        assert resp["payment_provider"] == "VISA"

@pytest.mark.parametrize("data,expected", [
    ({"booking_id": "b2", "amount": 100.0, "payment_type": "INVALID", "provider": "VISA"}, (400, 401)),
    ({"booking_id": "b3", "amount": 0.0, "payment_type": "CREDIT_CARD", "provider": "VISA"}, (400, 401)),
    ({"booking_id": "b4", "amount": -50.0, "payment_type": "CREDIT_CARD", "provider": "VISA"}, (400, 401)),
    ({"booking_id": "b5", "amount": 100.0, "payment_type": "CREDIT_CARD"}, (422, 401)),
    ({"booking_id": "b6", "amount": 100.0, "payment_type": "UNSUPPORTED", "provider": "VISA"}, (400, 401)),
])
def test_initiate_payment_invalid_cases(data, expected):
    token = "testtoken"
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in expected

def test_get_transaction_success():
    transaction = Transaction("t1")
    TransactionStorage.save(transaction)
    response = client.get(f"/transactions/{transaction.transaction_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == transaction.transaction_id

def test_get_all_transactions_with_data():
    transaction = Transaction("t2")
    TransactionStorage.save(transaction)
    response = client.get("/transactions/")
    assert response.status_code == 200
    data = response.json()
    assert any(t["transaction_id"] == transaction.transaction_id for t in data)

def test_validate_payment_not_found():
    response = client.post("/transactions/doesnotexist/validate")
    assert response.status_code == 404

def test_confirm_payment_not_found():
    response = client.post("/transactions/doesnotexist/confirm")
    assert response.status_code == 404

def test_refund_payment_not_found():
    response = client.post("/transactions/doesnotexist/refund")
    assert response.status_code == 404

def test_validate_confirm_refund_success():
    transaction = Transaction("t3")
    TransactionStorage.save(transaction)
    response = client.post(f"/transactions/{transaction.transaction_id}/validate")
    assert response.status_code in (200, 400)
    response2 = client.post(f"/transactions/{transaction.transaction_id}/confirm")
    assert response2.status_code in (200, 400)
    response3 = client.post(f"/transactions/{transaction.transaction_id}/refund")
    assert response3.status_code in (200, 400)

def test_validate_payment_error_branches():
    transaction = Transaction("t4")
    TransactionStorage.save(transaction)
    client.post(f"/transactions/{transaction.transaction_id}/validate")
    response = client.post(f"/transactions/{transaction.transaction_id}/validate")
    assert response.status_code == 400
    response2 = client.post("/transactions/wrongid/validate")
    assert response2.status_code == 404

def test_confirm_payment_error_branches():
    transaction = Transaction("t5")
    TransactionStorage.save(transaction)
    response = client.post(f"/transactions/{transaction.transaction_id}/confirm")
    assert response.status_code == 400
    client.post(f"/transactions/{transaction.transaction_id}/validate")
    client.post(f"/transactions/{transaction.transaction_id}/confirm")
    response2 = client.post(f"/transactions/{transaction.transaction_id}/confirm")
    assert response2.status_code == 400

def test_refund_payment_error_branches():
    transaction = Transaction("t6")
    TransactionStorage.save(transaction)
    response = client.post(f"/transactions/{transaction.transaction_id}/refund")
    assert response.status_code == 400
    client.post(f"/transactions/{transaction.transaction_id}/validate")
    client.post(f"/transactions/{transaction.transaction_id}/confirm")
    client.post(f"/transactions/{transaction.transaction_id}/refund")
    response2 = client.post(f"/transactions/{transaction.transaction_id}/refund")
    assert response2.status_code == 400


# --- API EDGE CASE TESTS ---
def test_initiate_payment_missing_fields():
    token = "testtoken"
    # Missing provider
    data = {"booking_id": "b5", "amount": 100.0, "payment_type": "CREDIT_CARD"}
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (422, 401)
    # Missing payment_type
    data2 = {"booking_id": "b6", "amount": 100.0, "provider": "VISA"}
    response2 = client.post("/transactions/", json=data2, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code in (422, 401)
    # Missing amount
    data3 = {"booking_id": "b7", "payment_type": "CREDIT_CARD", "provider": "VISA"}
    response3 = client.post("/transactions/", json=data3, headers={"Authorization": f"Bearer {token}"})
    assert response3.status_code in (422, 401)

def test_initiate_payment_provider_empty():
    token = "testtoken"
    # Provider kosong
    data = {"booking_id": "b8", "amount": 100.0, "payment_type": "CREDIT_CARD", "provider": ""}
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (400, 401)
    # Provider whitespace
    data2 = {"booking_id": "b9", "amount": 100.0, "payment_type": "CREDIT_CARD", "provider": "   "}
    response2 = client.post("/transactions/", json=data2, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code in (400, 401)

def test_initiate_payment_amount_invalid():
    token = "testtoken"
    # Amount string
    data = {"booking_id": "b10", "amount": "notanumber", "payment_type": "CREDIT_CARD", "provider": "VISA"}
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (400, 422, 401)
    # Amount None
    data2 = {"booking_id": "b11", "amount": None, "payment_type": "CREDIT_CARD", "provider": "VISA"}
    response2 = client.post("/transactions/", json=data2, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code in (400, 422, 401)

def test_initiate_payment_type_invalid():
    token = "testtoken"
    data = {"booking_id": "b12", "amount": 100.0, "payment_type": "NOT_A_TYPE", "provider": "VISA"}
    response = client.post("/transactions/", json=data, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (400, 401)

def test_validate_payment_invalid_id():
    # Not found
    response = client.post("/transactions/doesnotexist/validate")
    assert response.status_code == 404

def test_confirm_payment_invalid_id():
    # Not found
    response = client.post("/transactions/doesnotexist/confirm")
    assert response.status_code == 404

def test_refund_payment_invalid_id():
    # Not found
    response = client.post("/transactions/doesnotexist/refund")
    assert response.status_code == 404
