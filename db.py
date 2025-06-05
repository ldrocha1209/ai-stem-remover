# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1) Read DATABASE_URL from environment (Render will set this automatically).
DATABASE_URL = os.getenv("DATABASE_URL")

# 2) Create the engine pointed at Postgres.
engine = create_engine(DATABASE_URL)

# 3) Configure SessionLocal to use that engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
