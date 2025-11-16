from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class PaymentStatusEnum(Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

@dataclass(frozen=True)
class PaymentStatus:
    status: PaymentStatusEnum
    timestamp: datetime
    
    @staticmethod
    def initiated():
        return PaymentStatus(PaymentStatusEnum.INITIATED, datetime.now())
    
    @staticmethod
    def pending():
        return PaymentStatus(PaymentStatusEnum.PENDING, datetime.now())
    
    @staticmethod
    def validated():
        return PaymentStatus(PaymentStatusEnum.VALIDATED, datetime.now())
    
    @staticmethod
    def confirmed():
        return PaymentStatus(PaymentStatusEnum.CONFIRMED, datetime.now())
    
    @staticmethod
    def failed():
        return PaymentStatus(PaymentStatusEnum.FAILED, datetime.now())
    
    @staticmethod
    def refunded():
        return PaymentStatus(PaymentStatusEnum.REFUNDED, datetime.now())

class PaymentType(Enum):
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    E_WALLET = "E_WALLET"
    CASH = "CASH"

@dataclass(frozen=True)
class PaymentMethod:
    type: PaymentType
    provider: str
    
    @staticmethod
    def credit_card(provider: str):
        return PaymentMethod(PaymentType.CREDIT_CARD, provider)
    
    @staticmethod
    def debit_card(provider: str):
        return PaymentMethod(PaymentType.DEBIT_CARD, provider)
    
    @staticmethod
    def bank_transfer(provider: str):
        return PaymentMethod(PaymentType.BANK_TRANSFER, provider)
    
    @staticmethod
    def e_wallet(provider: str):
        return PaymentMethod(PaymentType.E_WALLET, provider)
    
    @staticmethod
    def cash():
        return PaymentMethod(PaymentType.CASH, "Cash")
