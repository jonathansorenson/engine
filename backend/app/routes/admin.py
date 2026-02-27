"""Admin routes for user management."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBaseModel, EmailStr
import bcrypt

from app.database import get_db
from app.models.user import User


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── Schemas ──

class UserCreate(PydanticBaseModel):
    email: str
    password: str
    name: Optional[str] = None
    role: str = "analyst"


class UserUpdate(PydanticBaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(PydanticBaseModel):
    id: str
    email: str
    name: Optional[str]
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ── Helpers ──

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── Routes ──

@router.get("/users", response_model=List[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """List all users (admin only)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user (admin only)."""
    # Check for duplicate email
    existing = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_data.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be: admin, analyst, or viewer")

    user = User(
        email=user_data.email.lower().strip(),
        hashed_password=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role,
        fund_id=user_data.email.lower().strip(),  # Use email as fund_id for isolation
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_data: UserUpdate, db: Session = Depends(get_db)):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.name is not None:
        user.name = user_data.name
    if user_data.role is not None:
        if user_data.role not in ("admin", "analyst", "viewer"):
            raise HTTPException(status_code=400, detail="Role must be: admin, analyst, or viewer")
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.password is not None:
        user.hashed_password = hash_password(user_data.password)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(get_db)):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} deleted"}
