import os
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean, Date,
    Text, Numeric, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# URL dari Environment Variable atau default ke SQLite lokal
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local_open_trip.db")

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

# ============================================================================
# ORM MODELS
# ============================================================================

class UserModel(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class TripModel(Base):
    __tablename__ = "trips"

    trip_id = Column(String, primary_key=True)
    trip_name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    current_bookings = Column(Integer, default=0)
    user_id = Column(String, nullable=True)

    schedules = relationship("ScheduleModel", back_populates="trip", cascade="all, delete-orphan")
    guide = relationship("GuideModel", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    itinerary = relationship("ItineraryModel", back_populates="trip", uselist=False, cascade="all, delete-orphan")


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    location = Column(String, nullable=False)

    trip = relationship("TripModel", back_populates="schedules")


class GuideModel(Base):
    __tablename__ = "guides"

    guide_id = Column(String, primary_key=True)
    trip_id = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    language = Column(String, nullable=False)

    trip = relationship("TripModel", back_populates="guide")


class ItineraryModel(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), unique=True, nullable=False)
    destinations = Column(JSON, nullable=False)
    description = Column(Text, nullable=False)

    trip = relationship("TripModel", back_populates="itinerary")


class ParticipantModel(Base):
    __tablename__ = "participants"

    participant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    address = Column(String, nullable=False)


class BookingModel(Base):
    __tablename__ = "bookings"

    booking_id = Column(String, primary_key=True)
    trip_id = Column(String, nullable=False)
    participant_id = Column(String, ForeignKey("participants.participant_id"), nullable=False)
    status_code = Column(String, nullable=False, default="PENDING")
    status_description = Column(String, nullable=False, default="Booking is pending confirmation")
    transaction_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)

    participant = relationship("ParticipantModel")


class TransactionModel(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True)
    booking_id = Column(String, nullable=True)
    total_amount = Column(Numeric(precision=12, scale=2), default=0)
    payment_status = Column(String, nullable=False, default="INITIATED")
    payment_status_timestamp = Column(DateTime, nullable=True)
    payment_type = Column(String, nullable=True)
    payment_provider = Column(String, nullable=True)
    user_id = Column(String, nullable=True)


# ============================================================================
# HELPERS
# ============================================================================

# membuat semua tabel yang didefinisikan di metadata
def init_db():
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
