from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from uuid import uuid4

from .aggregate_root import Transaction
from .value_objects import PaymentMethod, PaymentType
from storage import TransactionStorage
from auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Request/Response Models
class InitiatePaymentRequest(BaseModel):
    booking_id: str
    amount: float
    payment_type: str  # CREDIT_CARD, DEBIT_CARD, BANK_TRANSFER, E_WALLET, CASH
    provider: str

class TransactionResponse(BaseModel):
    transaction_id: str
    booking_id: Optional[str]
    total_amount: float
    payment_status: str
    payment_type: Optional[str]
    payment_provider: Optional[str]

# Endpoints
@router.post("/", response_model=TransactionResponse)
def initiate_payment(request: InitiatePaymentRequest, current_user: dict = Depends(get_current_user)):
    transaction_id = str(uuid4())
    transaction = Transaction(transaction_id)
    
    try:
        # Create payment method
        payment_type = PaymentType[request.payment_type]
        payment_method = PaymentMethod(payment_type, request.provider)
        
        # Initiate payment
        amount = Decimal(str(request.amount))
        transaction.initiate_payment(request.booking_id, amount, payment_method)
        TransactionStorage.save(transaction)
        
        return TransactionResponse(
            transaction_id=transaction.transaction_id,
            booking_id=transaction.booking_id,
            total_amount=float(transaction.total_amount),
            payment_status=transaction.status.status.value,
            payment_type=transaction.payment_method.type.value,
            payment_provider=transaction.payment_method.provider
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str):
    transaction = TransactionStorage.find_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return TransactionResponse(
        transaction_id=transaction.transaction_id,
        booking_id=transaction.booking_id,
        total_amount=float(transaction.total_amount),
        payment_status=transaction.status.status.value,
        payment_type=transaction.payment_method.type.value if transaction.payment_method else None,
        payment_provider=transaction.payment_method.provider if transaction.payment_method else None
    )

@router.get("/", response_model=List[TransactionResponse])
def get_all_transactions():
    transactions = TransactionStorage.get_all()
    return [
        TransactionResponse(
            transaction_id=t.transaction_id,
            booking_id=t.booking_id,
            total_amount=float(t.total_amount),
            payment_status=t.status.status.value,
            payment_type=t.payment_method.type.value if t.payment_method else None,
            payment_provider=t.payment_method.provider if t.payment_method else None
        )
        for t in transactions
    ]

@router.post("/{transaction_id}/validate")
def validate_payment(transaction_id: str):
    transaction = TransactionStorage.find_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    try:
        transaction.validate_payment(transaction_id)
        TransactionStorage.save(transaction)
        return {"message": "Payment validated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{transaction_id}/confirm")
def confirm_payment(transaction_id: str):
    transaction = TransactionStorage.find_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    try:
        transaction.confirm_payment(transaction_id)
        TransactionStorage.save(transaction)
        return {"message": "Payment confirmed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{transaction_id}/refund")
def refund_payment(transaction_id: str):
    transaction = TransactionStorage.find_by_id(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    try:
        transaction.mark_as_refunded()
        TransactionStorage.save(transaction)
        return {"message": "Transaction refunded successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
