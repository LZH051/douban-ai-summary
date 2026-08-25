from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_DIR = PROJECT_ROOT / "database"
OUTPUT_DIR = PROJECT_ROOT / "output"

RAW_DATA_FILE = DATA_DIR / "douban_movies_raw.csv"
CLEAN_DATA_FILE = DATA_DIR / "douban_movies_cleaned.csv"
CLEANING_REPORT_FILE = OUTPUT_DIR / "cleaning_report.json"
SCRAPING_ERROR_FILE = OUTPUT_DIR / "scraping_errors.csv"
AI_SUMMARY_FILE = OUTPUT_DIR / "ai_summaries.csv"
AI_USAGE_FILE = OUTPUT_DIR / "ai_usage.jsonl"
DATABASE_FILE = DATABASE_DIR / "douban_ai.db"
SCHEMA_FILE = DATABASE_DIR / "schema.sql"


def ensure_directories() -> None:
    for directory in (DATA_DIR, DATABASE_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
