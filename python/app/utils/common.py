from datetime import datetime


def now_iso() -> str:
    return datetime.now().isoformat()


def make_dm_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))