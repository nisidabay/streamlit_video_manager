import os
from sqlalchemy import create_engine, Column, Integer, String, Index
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Configuration Constants ---
# The root directory of your media library
MEDIA_DIR = "/media/wezterm"
# The path to the SQLite database file
DATABASE_URL = "sqlite:///videos.db"

# --- SQLAlchemy Setup ---
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# --- The "UI-Aware" Video Model ---
class Video(Base):
    """
    The Video model, designed for a fast UI.
    """

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)

    # Title extracted from the filename (e.g., "01 - Intro to Go")
    title = Column(String(255), nullable=False)

    # The relative path to the file from MEDIA_DIR
    # This MUST be unique.
    path = Column(String(1024), nullable=False, unique=True)

    # The "container folder" for grouping (e.g., "Tutorials/Go")
    # We add an index for fast grouping and searching.
    container_folder = Column(String(768), nullable=False, index=True)

    # Tags for searching
    tags = Column(String(512), nullable=True, index=True)


# Add indexes for columns we will search frequently
Index("ix_video_title_tags", Video.title, Video.tags)


def create_db_and_tables():
    """
    One-time function to create the database schema.
    """
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("Database tables created successfully.")


if __name__ == "__main__":
    # This allows you to run `python models.py` once
    # from your terminal to create the database.
    create_db_and_tables()
