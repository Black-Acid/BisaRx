from bisaRxApi.database import engine, SessionLocal, Base
import bisaRxApi.models as models
from passlib.context import CryptContext
from fastapi import HTTPException, security, Depends
import bisaRxApi.schemas as sma
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import orm
import jwt
from typing import Dict, List, Optional
import re
import asyncio
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

user_sessions: Dict[str, Dict[str, List[str]]] = {}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = "nsand329324nrlksndlak;asjdoiqw2"
oauth2schema = security.OAuth2PasswordBearer("/api/login")


MAX_BCRYPT_LENGTH = 72

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:MAX_BCRYPT_LENGTH])

def create_db():
    Base.metadata.create_all(bind=engine)
    
    
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        
        
async def create_user(user: sma.UserRequest, db: orm.Session):
    hashed_pw = hash_password(user.password)
    try:
        new_user = models.UserModel(
            username=user.username,
            hashed_password=hashed_pw
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

async def login(identifier: str, password: str, db: orm.Session):
    user = db.query(models.UserModel).filter_by(username=identifier).first()
    
    if not user:
        return False
    
    
    if not user.password_verification(password):
        return False
    
    return user


async def get_current_user(db: orm.Session = Depends(get_db), token: str = Depends(oauth2schema)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user = db.query(models.UserModel).get(payload["id"])
    except SQLAlchemyError as e:
        raise HTTPException(status_code=401, detail=f"Invalid credentials{e._message}")
    
    return sma.UserResponse.model_validate(user)


async def save_queries(
    conversation: sma.UserQueryResponse, 
    db: orm.Session,
    current_user : int
):
    try: 
        collected_data = models.UserMessages(
            user_id = current_user,
            enquiry = conversation.message,
            response = conversation.response
        )
        db.add(collected_data)
        db.commit()
        db.refresh(collected_data)
    except SQLAlchemyError as exception:
        db.rollback()
        raise HTTPException(status_code=401, detail=f"Data could not saved due to {exception._message}")


# keywords that strongly indicate non-answer intents
REQUEST_HELP_KEYWORDS = [
    "pharmacist", "connect me", "connect to", "prescription", "get medicine",
    "i want medicine", "i need medicine", "talk to a pharmacist", "talk to a doctor",
    "send to pharmacist", "call a pharmacist"
]
CHANGE_TOPIC_KEYWORDS = ["stop", "enough", "i'm tired", "im tired", "i am tired", "pause", "quit", "change topic", "new topic"]
NEW_SYMPTOM_KEYWORDS = ["also", "another", "new", "besides", "i also have", "i have also"]

YES_NO_SHORT = {"yes","no","y","n","yeah","yep","nah","nope","true","false"}

def _contains_any(text: str, keywords):
    t = text.lower()
    return any(k in t for k in keywords)

SYMPTOM_TRIGGERS = [
    "i have", "i'm having", "i am having", "i am", "i'm", "i've been", "i have been",
    "experiencing", "suffering from", "been having"
]

COMMON_SYMPTOM_WORDS = [
    "headache", "cough", "fever", "pain", "nausea", "vomit", "vomiting", "dizzy",
    "dizziness", "chest pain", "sore throat", "rash", "diarrhea", "shortness of breath",
    "breath", "bleeding", "swelling"
]

QUESTION_WORDS = {"what", "when", "where", "why", "who", "how", "which", "whom"}

def _contains_any_phrase(text: str, phrases):
    t = text.lower()
    return any(p in t for p in phrases)



def detect_intent(message: str, last_assistant_question: Optional[str] = None, history: str = "") -> str:
    """
    Returns one of:
    - "answer"
    - "new_symptom"
    - "request_help"
    - "change_topic"
    - "chat"
    """
    msg = (message or "").strip()
    if not msg:
        return "chat"

    lower = msg.lower()
    tokens = lower.split()

    # 0) If user asks something about the bot or uses "you", treat as chat/change_topic
    if any(word in lower for word in ["your name", "who are you", "what are you", "you?" ,"you are"]) or "your" in tokens[:3]:
        return "chat"

    # NEW: Detect explicit symptom patterns early
    if _contains_any_phrase(lower, SYMPTOM_TRIGGERS) and not _contains_any(lower, CHANGE_TOPIC_KEYWORDS):
        return "new_symptom"
    if _contains_any_phrase(lower, COMMON_SYMPTOM_WORDS) and len(tokens) > 1:
        return "new_symptom"

    # Strong keyword checks (non-answer)
    if _contains_any(lower, REQUEST_HELP_KEYWORDS):
        return "request_help"
    if _contains_any(lower, CHANGE_TOPIC_KEYWORDS):
        return "change_topic"
    if _contains_any(lower, NEW_SYMPTOM_KEYWORDS):
        return "new_symptom"

    # If the user directly asks a question (ends with ? or starts with question word)
    is_question_mark = msg.endswith("?")
    starts_with_qword = tokens and tokens[0] in QUESTION_WORDS

    if is_question_mark or starts_with_qword:
        # If the question *exactly* repeats the assistant's last question -> it's likely an answer rephrase
        if last_assistant_question and msg.lower().strip() == last_assistant_question.strip().lower():
            return "answer"
        # Otherwise treat as chat (user changed topic or asked about bot or clarified)
        return "chat"

    # Very short single-word or short phrases -> likely quick answers (yes/no, short counts)
    if len(tokens) <= 4:
        token0 = tokens[0].strip(".,!?")
        if token0 in YES_NO_SHORT:
            return "answer"
        if re.match(r"^\d+$", token0) or re.match(r"^\d+(?:\.\d+)?(days|day|hrs|hours|weeks)?$", lower) or re.match(r"^(one|two|three|four|five|six|seven|eight|nine|ten)$", token0):
            return "answer"
        if _contains_any(lower, CHANGE_TOPIC_KEYWORDS):
            return "change_topic"
        # short messages that clearly reference symptoms like "headache" alone -> treat as new_symptom
        if tokens[0] in COMMON_SYMPTOM_WORDS:
            return "new_symptom"

    # If last assistant question exists, check semantic fit: does the message answer that question (heuristic)
    if last_assistant_question:
        la = last_assistant_question.lower()
        # duration question -> numeric answer
        if re.search(r"(how long|when did|duration|since when)", la) and re.search(r"\b(days?|hours?|weeks?|months?)\b", lower):
            return "answer"
        # yes/no style question -> short message -> answer
        if re.match(r'^(do|did|is|are|have|has|can|could|should|was|were)\b', la.strip()):
            if len(tokens) <= 6:
                return "answer"
        # if last question asks about location/time and user replies with a full sentence starting with 'i' -> answer
        if re.search(r"(where|when|which)", la) and tokens and tokens[0] in {"i","i've","i'm","i am"}:
            return "answer"

    # Heuristic: long messages -> chat/new_symptom
    if len(tokens) > 8:
        if _contains_any(lower, ["i also have", "also have", "and also", "also experiencing", "another symptom", "besides that"]):
            return "new_symptom"
        return "chat"

    # FINAL fallback: be more conservative — prefer chat unless there's a clear last question context
    if last_assistant_question and len(tokens) <= 6:
        # short replies when assistant asked something recently -> probably an answer
        return "answer"

    return "chat"




# Globals to hold services
embeddings = None
vectorstore = None
retriever = None
services_initialized = False

async def initialize_services():
    """
    Lazy-load embeddings, FAISS index, and retriever in a memory-efficient way.
    Only loads saved FAISS index; no need to reprocess the book.
    """
    global embeddings, vectorstore, retriever, services_initialized

    if services_initialized:
        return

    print("⏳ Loading FAISS index and embeddings (lightweight)...")

    # Load embeddings (can be lightweight)
    embeddings = await asyncio.to_thread(
        lambda: HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )

    # Load FAISS index from saved local folder
    vectorstore = await asyncio.to_thread(
        lambda: FAISS.load_local("theBook_faiss_index", embeddings)
    )

    # Set up retriever
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    services_initialized = True
    print("✅ Services initialized: embeddings + FAISS retriever ready")

async def handle_intent_with_ai(intent: str, message: str, history: str, session) -> str:
    """
    Generates dynamic responses for detected intents using a small AI model.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    prompt_text = """
    You are a friendly, intelligent pharmacy assistant chatbot.
    You already know the user's intent: {intent}.
    Here is the recent conversation history:
    {history}

    User message:
    {message}

    Your job:
    - If intent = "chat": respond casually but gently guide them back to describing their symptoms.
    - If intent = "request_help": acknowledge their request and assure them you'll connect them to a pharmacist.
    - If intent = "change_topic": ask what new topic or issue they’d like to discuss.
    - If intent = "new_symptom": acknowledge it and ask one initial clarifying question.
    - If intent = "answer": confirm their response and ask the next diagnostic question if available.
    Be natural and human-like, not robotic.
    Respond in 2–3 sentences only.
    """

    prompt = PromptTemplate.from_template(prompt_text)
    result = await llm.ainvoke(prompt.format(intent=intent, message=message, history=history))
    return result.content.strip()




async def handle_conversation(user_id: str, message: str, retriever):
    session = user_sessions.get(user_id)

    # Determine intent (new_symptom or answer)
    intent = "new_symptom" if session is None else detect_intent(message)
    print(f"[Intent: {intent}]")

    # --- New conversation or symptom ---
    if intent == "new_symptom":
        # Lazy load retriever
        await initialize_services()
        docs = await asyncio.to_thread(retriever.invoke, message) if not hasattr(retriever, "ainvoke") else await retriever.ainvoke(message)
        context = "\n".join(getattr(d, "page_content", "") for d in docs if isinstance(getattr(d, "page_content", ""), str))

        prompt = f"""
        You are a pharmacy assistant AI.
        Ask relevant diagnostic questions only.

        Context:
        {context}

        Patient symptom:
        {message}
        """
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)
        result = await llm.ainvoke(prompt) if hasattr(llm, "ainvoke") else await asyncio.to_thread(llm.invoke, prompt)
        questions = [q.strip() for q in result.content.split("\n") if q.strip().endswith("?")] if hasattr(result, "content") else []

        if not questions:
            return "Couldn't generate diagnostic questions."

        user_sessions[user_id] = {"current": 0, "questions": questions, "answers": []}
        return f"Let's start:\n{questions[0]}"

    # --- User answering questions ---
    elif intent == "answer" and session:
        session["answers"].append(message)
        session["current"] += 1

        if session["current"] < len(session["questions"]):
            return session["questions"][session["current"]]
        else:
            summary = "\n".join(f"Q{i+1}: {q}\nA: {a}" for i, (q, a) in enumerate(zip(session["questions"], session["answers"])))
            del user_sessions[user_id]
            return f"Thanks! Summary:\n{summary}\nForwarding to pharmacist."

    # --- Fallback AI response for casual chat ---
    else:
        return await handle_intent_with_ai(intent, message, session)
