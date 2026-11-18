"""Resolve project resources independently of the caller's working directory."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYLLABI_FOLDER = PROJECT_ROOT / 'data' / 'syllabi'
WEB_ROOT = PROJECT_ROOT / 'web'
ENV_FILE = PROJECT_ROOT / '.env'
