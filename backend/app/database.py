from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./dev.db')

# Configure engine with sensible pooling for production DBs; keep sqlite behavior for local dev
_IS_SQLITE = str(DATABASE_URL).startswith('sqlite')
if _IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.environ.get('DB_POOL_SIZE', '5')),
        max_overflow=int(os.environ.get('DB_MAX_OVERFLOW', '10')),
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    from .models import Base

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
