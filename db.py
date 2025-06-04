# db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We’ll store users.db in your project folder. 
# In production you might pick a better path, but for now this works.
DATABASE_URL = "sqlite:///./users.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
