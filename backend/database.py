import os
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean, Date,
    Text, Numeric, DateTime, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
import uuid

# URL dari Environment Variable. Do NOT default to a local SQLite file here;
# tests set `DATABASE_URL` themselves (see `backend/tests/conftest.py`).
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise EnvironmentError(
        "DATABASE_URL is not set. For runtime set DATABASE_URL to your Postgres 'open_trip_db'. "
        "For tests, `backend/tests/conftest.py` sets DATABASE_URL to 'sqlite:///./local_open_trip.db'."
    )

# string koneksi Postgres dari Railway
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Engine database dengan konfigurasi yang tepat
if DATABASE_URL.startswith("sqlite"):
    # Untuk SQLite, gunakan sync driver dan check_same_thread=False
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    # Untuk PostgreSQL atau database lainnya
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# Allowed destination types for trips (used by frontend and validation)
DESTINATION_TYPES = (
    'Island Exploration',
    'Mount Hiking',
    'Camping Ground',
    'City Tour',
    'Wildlife Exploration',
    'Other',
)

# ============================================================================
# ORM MODELS
# ============================================================================

# NOTE: UserModel removed - authentication is delegated to the central Django
# service. This microservice only stores user_id strings on related tables.

# NOTE: Trip-related models (TripModel, ScheduleModel, GuideModel, ItineraryModel)
# have been MOVED to Travel Planner microservice as they are more relevant to
# the travel planning domain. Trip data is now managed by the Travel Planner service.

class ParticipantModel(Base):
    __tablename__ = "participants"

    participant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    trip_pickup_id = Column(UUID(as_uuid=True), nullable=True)
    gender = Column(String, nullable=True)
    nationality = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)


class BookingModel(Base):
    __tablename__ = "bookings"

    booking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # user_id stores user identification as UUID string
    user_id = Column(Text, nullable=False)
    # Reference to Travel Planner's RencanaPerjalanan id (UUID)
    id_rencana = Column(UUID(as_uuid=True), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.participant_id"), nullable=False)
    booking_status = Column(String, nullable=False, default="PENDING")
    # Link to transaction (nullable until transaction created)
    transaction_id = Column(UUID(as_uuid=True), nullable=True)
    participant = relationship("ParticipantModel")


class TransactionModel(Base):
    __tablename__ = "transactions"

    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total_price = Column(Numeric(precision=12, scale=2), nullable=False, default=0)
    trip_price = Column(Numeric(precision=12, scale=2), nullable=False, default=0)
    pickup_fee = Column(Numeric(precision=12, scale=2), nullable=False, default=0)
    payment_status = Column(String, nullable=False, default="PENDING")
    payment_method = Column(String, nullable=True)


# ============================================================================
# HELPERS
# ============================================================================

# membuat semua tabel yang didefinisikan di metadata
def init_db():
    """
    Creates all tables defined in SQLAlchemy metadata.
    Now includes only: bookings, participants, transactions
    
    NOTE: Trip-related tables (trips, schedules, guides, itineraries) are now
    managed by the Travel Planner microservice and will be created in the
    travel_planner_db database.
    """
    Base.metadata.create_all(bind=engine)

# Alias untuk backward compatibility
create_tables = init_db


def drop_tables():
    """Drop all tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)


# Dependency injection untuk session database
def get_session():
    """Get a new database session."""
    with Session(bind=engine) as session:
        yield session

# Alias untuk konsistensi dengan router
get_db = get_session
