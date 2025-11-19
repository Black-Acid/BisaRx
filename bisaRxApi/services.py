from database import engine, SessionLocal, Base
import models
from passlib.context import CryptContext
from fastapi import HTTPException, security, Depends
import bisaRxApi.schemas as sma
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import orm
import jwt



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = "nsand329324nrlksndlak;asjdoiqw2"
oauth2schema = security.OAuth2PasswordBearer("/api/login")

def create_db():
    Base.metadata.create_all(bind=engine)
    
    
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        
        
async def create_user(user: sma.UserRequest, db: orm.Session):
    hash_password = pwd_context.hash(user.password)
    try:
        new_user = models.UserModel(
            username=user.username,
            hashed_password=hash_password
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Couldn't save the data due to {e._message}")
        
    return new_user


async def create_token(user: models.UserModel):
    user_schema = sma.UserResponse.model_validate(user)
    user_dict = user_schema.model_dump()
    
    
    token = jwt.encode(user_dict, JWT_SECRET)
    
    return dict(access_token=token, token_type="bearer")


async def get_user(user: sma.UserRequest, db: orm.Session):
    return db.query(models.UserModel).filter_by(username=user.username).first()