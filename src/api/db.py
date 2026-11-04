"""Supabase connection helper."""

import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

CLIENT_ID = "a1b2c3d4-0001-4000-8000-000000000001"

_sb: Client | None = None

def get_supabase() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL dan SUPABASE_KEY harus diset di .env")
        _sb = create_client(url, key)
    return _sb
