import os
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean, Date,
    Text, Numeric, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

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

class TripModel(Base):
    __tablename__ = "trips"

    # Use INTEGER primary key for trip_id (autoincrement)
    trip_id = Column(Integer, primary_key=True, autoincrement=True)
    trip_name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    current_bookings = Column(Integer, default=0)
    user_id = Column(String, nullable=True)
    # Additional fields used by frontend mapping
    departure_date = Column(Date, nullable=True)
    price = Column(Numeric(precision=12, scale=2), nullable=True)
    status = Column(String(50), nullable=True)
    # `tag` removed in favor of deriving `location` from related schedules
    # Destination type for the trip; should be one of DESTINATION_TYPES
    destination_type = Column(String(50), nullable=True)

    schedules = relationship("ScheduleModel", back_populates="trip", cascade="all, delete-orphan")
    guide = relationship("GuideModel", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    itinerary = relationship("ItineraryModel", back_populates="trip", uselist=False, cascade="all, delete-orphan")

    @property
    def location(self):
        """Return a concatenated location string derived from related schedules.

        This mirrors the frontend expectation where `location` is built
        from schedule entries (e.g. start/end/location). If multiple
        schedules exist, locations are joined with a comma.
        """
        try:
            locs = [s.location for s in self.schedules if getattr(s, 'location', None)]
            # keep order and unique
            seen = set()
            ordered = []
            for l in locs:
                if l not in seen:
                    seen.add(l)
                    ordered.append(l)
            return ", ".join(ordered) if ordered else None
        except Exception:
            return None


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    location = Column(String, nullable=False)

    trip = relationship("TripModel", back_populates="schedules")


class GuideModel(Base):
    __tablename__ = "guides"

    guide_id = Column(String, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    language = Column(String, nullable=False)

    trip = relationship("TripModel", back_populates="guide")


class ItineraryModel(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), unique=True, nullable=False)
    destinations = Column(JSON, nullable=False)
    description = Column(Text, nullable=False)

    trip = relationship("TripModel", back_populates="itinerary")


class ParticipantModel(Base):
    __tablename__ = "participants"

    participant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    gender = Column(String, nullable=True)
    nationality = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    pick_up_point = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class BookingModel(Base):
    __tablename__ = "bookings"

    booking_id = Column(String, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(String, ForeignKey("participants.participant_id"), nullable=False)
    status_code = Column(String, nullable=False, default="PENDING")
    status_description = Column(String, nullable=False, default="Booking is pending confirmation")
    transaction_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

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
