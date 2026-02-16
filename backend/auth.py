import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from uuid import uuid4
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Konfigurasi JWT
# Environment variable untuk production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY tidak ditemukan di environment variable"
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

security = HTTPBearer()

class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str

class User(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    
    def dict_safe(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active
        }

FAKE_USER_DB: Dict[str, User] = {}

class UserStorage:
    @staticmethod
    def save(user: User) -> None:
        FAKE_USER_DB[user.user_id] = user
    
    @staticmethod
    def find_by_id(user_id: str) -> Optional[User]:
        return FAKE_USER_DB.get(user_id)
    
    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        for user in FAKE_USER_DB.values():
            if user.username == username:
                return user
        return None
    
    @staticmethod
    def get_by_email(email: str) -> Optional[User]:
        for user in FAKE_USER_DB.values():
            if user.email == email:
                return user
        return None
    
    @staticmethod
    def get_all() -> list[User]:
        return list(FAKE_USER_DB.values())
    
    @staticmethod
    def delete(user_id: str) -> bool:
        if user_id in FAKE_USER_DB:
            del FAKE_USER_DB[user_id]
            return True
        return False

# ============================================================================
# APAPUN TENTANG JWT
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> AuthenticatedUser:
    """Fungsi untuk mengecek user saat ini berdasarkan token JWT (Stateless)"""
    token = credentials.credentials
    
    # Exception untuk invalid credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify the signature directly (Stateless)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Extract user info from the token
        user_id = payload.get("user_id")
        
        if user_id is None:
            raise credentials_exception
            
        return AuthenticatedUser(
            id=str(user_id),
            email=payload.get("email"),
            role=payload.get("role", "CUSTOMER")
        )
    
    # Handle JWT errors
    except JWTError:
        raise credentials_exception

# ============================================================================
# REQUEST/RESPONSE
# ============================================================================

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password is too long (max 72 bytes)')
        return v

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool

# ============================================================================
# ENDPOINTS
# ============================================================================

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    existing_user = UserStorage.get_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    existing_email = UserStorage.get_by_email(request.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_id = str(uuid4())
    hashed_password = get_password_hash(request.password)
    
    user = User(
        user_id=user_id,
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        full_name=request.full_name
    )
    
    UserStorage.save(user)
    
    return UserResponse(**user.dict_safe())

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    user = UserStorage.get_by_username(request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.user_id,
            "email": user.email,
            "role": "CUSTOMER"
        },
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    user = UserStorage.find_by_id(current_user.id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(**user.dict_safe())
