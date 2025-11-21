import logging

logging.basicConfig(level=logging.INFO)  # INFO, DEBUG, WARNING, ERROR
logger = logging.getLogger(__name__)

logger.info("I have found my main.py")

from fastapi import Depends, FastAPI, HTTPException, security
import bisaRxApi.schemas as sma
from sqlalchemy import orm
import os
import bisaRxApi.services as sv
import uvicorn

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


@app.post("/api/login")
async def login(form_data: security.OAuth2PasswordRequestForm = Depends(), db: orm.Session = Depends(sv.get_db)):
    db_user = await sv.login(form_data.username, form_data.password, db)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return await sv.create_token(db_user)



@app.post("/api/send-data")
async def query(
    data: sma.UserQuery,
    user: sma.UserResponse = Depends(sv.get_current_user),
    db: orm.Session = Depends(sv.get_db)
):
    user_id = str(user.id)

    # If user is already in a question session, handle conversational logic
    if user_id in sv.user_sessions:
        response = await sv.handle_conversation(user_id, data.message, sv.retriever)
        return {"response": response}

    print("Fetching new response from Groq or retriever...")
    await sv.initialize_services()
    response = await sv.handle_conversation(user_id, data.message, sv.retriever)

    
    queryResponse = sma.UserQueryResponse(message=data.message, response=response)
    await sv.save_queries(queryResponse, db, user.id)

    return {"response": response}


@app.get("/")
def root():
    return {"message": "Hello Render!"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Use Render's port
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)