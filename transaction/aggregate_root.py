from decimal import Decimal
from typing import Optional
from .value_objects import PaymentStatus, PaymentStatusEnum, PaymentMethod

class Transaction:    
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        self.total_amount: Decimal = Decimal('0.00')
        self.status = PaymentStatus.initiated()
        self.payment_method: Optional[PaymentMethod] = None
        self.booking_id: Optional[str] = None
    
    def initiate_payment(self, booking_id: str, amount: Decimal, method: PaymentMethod) -> None:
        if self.status.status != PaymentStatusEnum.INITIATED:
            raise ValueError("Transaction already initiated")
        
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        
        self.booking_id = booking_id
        self.total_amount = amount
        self.payment_method = method
        self.status = PaymentStatus.pending()
    
    def validate_payment(self, transaction_id: str) -> None:
        if self.transaction_id != transaction_id:
            raise ValueError("Transaction ID mismatch")
        
        if self.status.status != PaymentStatusEnum.PENDING:
            raise ValueError("Only pending transactions can be validated")
        
        self.status = PaymentStatus.validated()
    
    def confirm_payment(self, transaction_id: str) -> None:
        if self.transaction_id != transaction_id:
            raise ValueError("Transaction ID mismatch")
        
        if self.status.status != PaymentStatusEnum.VALIDATED:
            raise ValueError("Only validated transactions can be confirmed")
        
        self.status = PaymentStatus.confirmed()
    
    def update_status(self, new_status: PaymentStatus) -> None:
        self.status = new_status
    
    def mark_as_failed(self) -> None:
        self.status = PaymentStatus.failed()
    
    def mark_as_refunded(self) -> None:
        if self.status.status != PaymentStatusEnum.CONFIRMED:
            raise ValueError("Only confirmed transactions can be refunded")
        
        self.status = PaymentStatus.refunded()
