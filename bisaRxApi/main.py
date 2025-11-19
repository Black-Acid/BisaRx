import logging

logging.basicConfig(level=logging.INFO)  # INFO, DEBUG, WARNING, ERROR
logger = logging.getLogger(__name__)

logger.info("I have found my main.py")

from fastapi import Depends, FastAPI, HTTPException, security
import bisaRxApi.schemas as sma
from sqlalchemy import orm
import os
from dotenv import load_dotenv
import bisaRxApi.services as sv

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/register-user/")
async def register_user(user: sma.UserRequest, db: orm.Session = Depends(sv.get_db)):
    checked_user = await sv.get_user(user, db)
    if checked_user:
        raise HTTPException(status_code=400, detail="A User already exists with that username")
    try:
        creating_user = await sv.create_user(user, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad request: {e}")

    print(creating_user)
    return await sv.create_token(creating_user)