import streamlit as st
import os
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from models import Video, MEDIA_DIR, SessionLocal, engine
from contextlib import contextmanager
import time

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Video Manager")


# --- Database Session ---
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


# --- Data Functions (Cached) ---


@st.cache_data(ttl=600)
def search_topic_folders(query: str):
    """
    Runs the "UI-Aware" query to find folders matching a topic.
    This powers the "Netflix-style" home page.

    Returns:
        List of plain dictionaries, suitable for caching.
    """
    with get_session() as session:
        if not query:
            # If no query, show all top-level folders by video count
            stmt = (
                session.query(
                    Video.container_folder,
                    func.count(Video.id).label("video_count"),
                )
                .group_by(Video.container_folder)
                .order_by(desc("video_count"))
                .limit(50)
            )
        else:
            # If query, search title, tags, and path
            search_term = f"%{query}%"
            stmt = (
                session.query(
                    Video.container_folder,
                    func.count(Video.id).label("video_count"),
                )
                .filter(
                    (Video.title.ilike(search_term))
                    | (Video.tags.ilike(search_term))
                    | (Video.path.ilike(search_term))
                )
                .group_by(Video.container_folder)
                .order_by(desc("video_count"))
            )

        # Convert SQLAlchemy results to plain dicts before session closes
        results = stmt.all()
        return [
            {"container_folder": r.container_folder, "video_count": r.video_count}
            for r in results
        ]


@st.cache_data(ttl=600)
def get_videos_in_folder(folder_path: str, search_query: str = ""):
    """
    Gets all individual videos for the "drill-down" view.

    Returns:
        List of plain dictionaries, suitable for caching.
    """
    with get_session() as session:
        stmt = session.query(Video).filter(Video.container_folder == folder_path)

        if search_query:
            search_term = f"%{search_query}%"
            stmt = stmt.filter(
                (Video.title.ilike(search_term)) | (Video.tags.ilike(search_term))
            )

        results = stmt.order_by(Video.title).all()

        # Convert Video objects to plain dicts before session closes
        return [
            {"id": v.id, "title": v.title, "path": v.path, "tags": v.tags}
            for v in results
        ]


# --- State Management ---
if "view" not in st.session_state:
    st.session_state.view = "home"
if "current_folder" not in st.session_state:
    st.session_state.current_folder = None
if "video_to_play" not in st.session_state:
    st.session_state.video_to_play = None

# --- UI Rendering: View 1 (Home) ---


def render_home_view():
    st.title("🎬 Video Manager")

    search_query = st.text_input(
        "Search for a topic (e.g., Python, Go, Bash...)",
        placeholder="Search all videos...",
        key="home_search",
    )

    st.header("Topics" if search_query else "All Folders")

    folders = search_topic_folders(search_query)

    if not folders:
        st.info(
            f"No results found for '{search_query}'. Try scanning your media library."
        )
        return

    # Create a responsive grid
    cols = st.columns(4)
    col_idx = 0

    for folder_data in folders:
        col = cols[col_idx % 4]
        with col.container(border=True):
            folder = folder_data["container_folder"]
            count = folder_data["video_count"]

            # --- MODIFIED: Use markdown for a smaller, bolded title ---
            st.markdown(f"**{folder}**")
            st.caption(f"{count} video{'s' if count > 1 else ''}")

            if st.button("Open", key=f"open_{folder}", use_container_width=True):
                st.session_state.view = "folder"
                st.session_state.current_folder = folder
                st.session_state.video_to_play = None  # Clear player
                st.cache_data.clear()  # Clear cache to ensure fresh data
                st.rerun()
        col_idx += 1


# --- UI Rendering: View 2 (Folder Drill-down) ---


def render_folder_view():
    folder_path = st.session_state.current_folder

    # --- Header and Navigation ---
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Back to Home"):
            st.session_state.view = "home"
            st.session_state.current_folder = None
            st.session_state.video_to_play = None
            st.cache_data.clear()
            st.rerun()
    with col2:
        st.header(folder_path)

    # --- Video Player ---
    player_placeholder = st.empty()
    if st.session_state.video_to_play:
        video_full_path = os.path.join(MEDIA_DIR, st.session_state.video_to_play)
        if os.path.exists(video_full_path):
            player_placeholder.video(video_full_path)
        else:
            player_placeholder.error(f"Video file not found: {video_full_path}")
            st.warning("The media file seems to be missing. Run the indexer to sync.")

    st.subheader("Videos in this folder")

    # --- Per-folder search ---
    folder_search = st.text_input(
        "Search within this folder", key=f"search_{folder_path}"
    )

    videos = get_videos_in_folder(folder_path, folder_search)

    if not videos:
        st.info(
            "No videos found in this topic."
            if not folder_search
            else "No search results."
        )
        return

    # --- Video Card Grid ---
    cols = st.columns(3)
    col_idx = 0

    for video_data in videos:
        col = cols[col_idx % 3]
        with col.container(border=True):

            # --- MODIFIED: Use markdown for a smaller, bolded title ---
            st.markdown(f"**{video_data['title']}**")

            # --- Play Button ---
            if st.button(
                "▶️ Play", key=f"play_{video_data['id']}", use_container_width=True
            ):
                st.session_state.video_to_play = video_data["path"]
                st.rerun()

            # --- Edit & Delete ---
            with st.expander("Edit Info"):
                with st.form(key=f"form_edit_{video_data['id']}"):
                    new_title = st.text_input("Title", value=video_data["title"])
                    new_tags = st.text_input(
                        "Tags (comma-separated)", value=video_data["tags"] or ""
                    )

                    form_cols = st.columns(2)
                    if form_cols[0].form_submit_button(
                        "Save", use_container_width=True
                    ):
                        try:
                            with get_session() as session:
                                session.query(Video).filter(
                                    Video.id == video_data["id"]
                                ).update({"title": new_title, "tags": new_tags})
                            st.toast(f"Updated '{new_title}'")
                            st.cache_data.clear()
                            time.sleep(0.5)  # Give toast time to show
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating: {e}")

                    if form_cols[1].form_submit_button(
                        "Delete", type="primary", use_container_width=True
                    ):
                        try:
                            with get_session() as session:
                                session.query(Video).filter(
                                    Video.id == video_data["id"]
                                ).delete()
                            st.toast(f"Deleted '{video_data['title']}'")
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting: {e}")

            st.caption(f"Path: {video_data['path']}")
            if video_data["tags"]:
                st.caption(f"Tags: {video_data['tags']}")

        col_idx += 1


# --- Main View Router ---
if st.session_state.view == "home":
    render_home_view()
elif st.session_state.view == "folder":
    render_folder_view()
