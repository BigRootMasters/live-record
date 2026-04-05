import os
import sys
import shutil

from sqlalchemy import inspect, text

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.models import Recording, db


LEGACY_RECORDING_STATUSES = {
    "transcribed",
    "notified",
    "transcription_failed",
}


def normalize_recording_statuses():
    updated = 0
    rows = Recording.query.filter(Recording.status.in_(LEGACY_RECORDING_STATUSES)).all()
    for row in rows:
        row.status = "completed"
        updated += 1

    if updated:
        db.session.commit()

    return updated


def drop_summaries_table():
    inspector = inspect(db.engine)
    if "summaries" not in inspector.get_table_names():
        return False

    db.session.execute(text("DROP TABLE summaries"))
    db.session.commit()
    return True


def remove_legacy_summary_directory():
    summary_storage_path = os.path.abspath(
        os.getenv("SUMMARY_STORAGE_PATH", "./data/summaries")
    )
    if not os.path.exists(summary_storage_path):
        return None

    shutil.rmtree(summary_storage_path, ignore_errors=True)
    return summary_storage_path


def main():
    app = create_app()
    with app.app_context():
        normalized = normalize_recording_statuses()
        dropped = drop_summaries_table()
        removed_dir = remove_legacy_summary_directory()

    print(f"normalized_recordings={normalized}")
    print(f"dropped_summaries_table={dropped}")
    print(f"removed_summary_dir={removed_dir or 'none'}")


if __name__ == "__main__":
    main()
