import sqlalchemy as sql
from sqlalchemy import orm
from sqlalchemy.orm import DeclarativeBase

# from sqlalchemy.orm import DeclarativeBase as Base



# DB_URL = "sqlite:///C:/Users/LENOVO/Desktop/bisaRx/bisaRxApi/BisaRxDB.db"

DB_URL = "postgresql://neondb_owner:npg_aIOdp1xz8ZwL@ep-crimson-glade-abzvwvo4-pooler.eu-west-2.aws.neon.tech/bisarxdb?sslmode=require&channel_binding=require"


engine = sql.create_engine(DB_URL)

SessionLocal = orm.sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass