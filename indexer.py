import os
import sys
from sqlalchemy.orm import sessionmaker, Session
from models import Video, MEDIA_DIR, engine, SessionLocal
from tqdm import tqdm
from contextlib import contextmanager

# --- Configuration ---

# 1. Allowed video file extensions (using a set for fast lookup)
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".mpeg",
    ".mpg",
}

# 2. Folders to completely skip (system folders, recycle bins, etc.)
# We check if a folder *name* (not the full path) is in this set.
SKIP_FOLDERS = {
    "@eaDir",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".DS_Store",
    ".thumbnails",
    ".recycle",
}


@contextmanager
def get_session():
    """Provides a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def scan_disk_paths() -> set:
    """
    Scans the MEDIA_DIR for all valid video files.

    Applies the VIDEO_EXTENSIONS and SKIP_FOLDERS filters.

    Returns:
        A set of relative file paths (e.g., "Tutorials/Go/video1.mp4")
    """
    print(f"Starting scan of '{MEDIA_DIR}'...")
    disk_paths = set()

    # We wrap os.walk in tqdm for a progress bar
    # Note: This progress bar updates per-directory, not per-file
    file_count = 0
    for root, dirs, files in tqdm(
        os.walk(MEDIA_DIR, topdown=True), desc="Scanning directories"
    ):

        # --- Filter 1: Skip Folders ---
        # Modify 'dirs' in-place to prevent os.walk from descending into them
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDERS]

        for file in files:

            # --- NEW: Filter 3: Junk Files ---
            # Skip macOS metadata files or other common junk files
            if file.startswith("._") or file == ".DS_Store":
                continue

            # --- Filter 2: Video Extensions ---
            if os.path.splitext(file)[1].lower() in VIDEO_EXTENSIONS:
                try:
                    full_path = os.path.join(root, file)
                    # Get the relative path from the media_dir base
                    relative_path = os.path.relpath(full_path, MEDIA_DIR)
                    disk_paths.add(relative_path)
                    file_count += 1
                except Exception as e:
                    print(f"Warning: Could not process file {full_path}. Error: {e}")

    print(f"Scan complete. Found {file_count} video files on disk.")
    return disk_paths


def get_db_paths(session: Session) -> set:
    """
    Gets the relative paths of all videos currently in the database.

    Returns:
        A set of relative file paths.
    """
    print("Fetching existing video paths from database...")
    paths = session.query(Video.path).all()
    db_paths = set(row[0] for row in paths)
    print(f"Found {len(db_paths)} videos in database.")
    return db_paths


def sync_database():
    """
    Main synchronization function.
    Implements the "Add New, Remove Old" logic.
    """
    with get_session() as session:
        # Step 1: Get all paths from the DB
        db_paths = get_db_paths(session)

        # Step 2: Scan all valid paths from the Disk
        disk_paths = scan_disk_paths()

        # Step 3: Calculate differences
        paths_to_add = disk_paths - db_paths
        paths_to_remove = db_paths - disk_paths

        # --- Step 4: Add New Videos ---
        if paths_to_add:
            print(f"Adding {len(paths_to_add)} new videos to the database...")
            new_videos = []
            for path in tqdm(paths_to_add, desc="Adding videos"):
                container = os.path.dirname(path)
                title = os.path.splitext(os.path.basename(path))[0]

                new_videos.append(
                    Video(
                        title=title,
                        path=path,
                        container_folder=container,
                        tags="",  # Default to empty tags
                    )
                )
            session.add_all(new_videos)

        # --- Step 5: Remove Old Videos ---
        if paths_to_remove:
            print(f"Removing {len(paths_to_remove)} old video entries...")
            # This is more efficient for large deletes
            session.query(Video).filter(Video.path.in_(paths_to_remove)).delete(
                synchronize_session=False
            )

        # Commit is handled by the 'get_session' context manager
        print("\n--- Sync Summary ---")
        print(f"Added:   {len(paths_to_add)} new videos")
        print(f"Removed: {len(paths_to_remove)} old entries")
        print(f"Total:   {len(disk_paths)} videos in catalog.")
        print("Database synchronization complete.")


if __name__ == "__main__":
    print("Starting Video Library Indexer...")

    # Check if MEDIA_DIR exists
    if not os.path.isdir(MEDIA_DIR):
        print(f"Error: Media directory not found: {MEDIA_DIR}")
        print("Please check the 'MEDIA_DIR' constant in 'models.py'")
        sys.exit(1)

    # Check if database file exists, if not, create it
    db_file = engine.url.database
    if not os.path.exists(db_file):
        print(f"Database file not found. Creating new database at: {db_file}")
        from models import create_db_and_tables

        create_db_and_tables()

    sync_database()
