import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


if __name__ == "__main__":
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version()")).scalar()
        print(version)
