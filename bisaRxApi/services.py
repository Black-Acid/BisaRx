from database import engine, SessionLocal, Base
import models


def create_db():
    Base.metadata.create_all(bind=engine)
    
    
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        
create_db()
import os
print(os.path.abspath("BisaRxDB.db"))
