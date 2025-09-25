import os
import sqlite3
from typing import List, Tuple
try:
    # Prefer project settings for table/time column
    from datainsight_agent.config.settings import load_settings  # type: ignore
    _SET = load_settings()
    _TBL = _SET.dw_table
    _TCOL = _SET.dw_time_column
except Exception:  # pragma: no cover
    _SET = None
    _TBL = os.getenv("DW_TABLE", "dws_user_activity_monthly")
    _TCOL = os.getenv("DW_TIME_COLUMN", "month")


TARGET_USER_IDS: Tuple[str, ...] = ("u1", "u2", "u3", "u4", "u5")


def get_db_path() -> str:
    """Resolve SQLite DB path from env or default to datainsight.db."""
    return os.getenv("DB_PATH", "datainsight.db")


def fetch_null_candidates(cur: sqlite3.Cursor, limit: int = 20) -> List[tuple]:
    """Find rows in 2025 with any key dimension being NULL."""
    query = (
        f"SELECT user_id, {_TCOL}, device_model, os_version, country, channel_subtype "
        f"FROM {_TBL} "
        f"WHERE {_TCOL} BETWEEN '2025-01' AND '2025-12' "
        f"AND (device_model IS NULL OR os_version IS NULL OR country IS NULL OR channel_subtype IS NULL) "
        f"LIMIT ?"
    )
    return cur.execute(query, (limit,)).fetchall()


def delete_early_test_rows(cur: sqlite3.Cursor) -> int:
    """Delete rows for the known early test users within 2025."""
    placeholders = ",".join(["?"] * len(TARGET_USER_IDS))
    query = (
        f"DELETE FROM {_TBL} "
        f"WHERE user_id IN ({placeholders}) "
        f"AND {_TCOL} BETWEEN '2025-01' AND '2025-12'"
    )
    cur.execute(query, TARGET_USER_IDS)
    # sqlite3 does not return rowcount reliably; the connection's total_changes will reflect after commit
    return cur.rowcount if cur.rowcount is not None else -1


def check_null_bucket(cur: sqlite3.Cursor, column: str) -> List[tuple]:
    """Return any remaining NULL bucket group rows for the column in 2025."""
    query = (
        f"SELECT {column}, COUNT(DISTINCT user_id) "
        f"FROM {_TBL} "
        f"WHERE active=1 AND {_TCOL} BETWEEN '2025-01' AND '2025-12' "
        f"GROUP BY {column} HAVING {column} IS NULL"
    )
    return cur.execute(query).fetchall()


def main() -> None:
    db_path = get_db_path()
    print(f"DB: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        candidates = fetch_null_candidates(cur)
        print("CANDIDATES_BEFORE(sample):", candidates[:10])

        _rowcount_hint = delete_early_test_rows(cur)
        conn.commit()
        print("DELETE_ROWCOUNT_HINT:", _rowcount_hint)
        print("TOTAL_CHANGES:", conn.total_changes)

        print("NULL_device_model:", check_null_bucket(cur, "device_model"))
        print("NULL_os_version:", check_null_bucket(cur, "os_version"))
        print("NULL_country:", check_null_bucket(cur, "country"))
        print("NULL_channel_subtype:", check_null_bucket(cur, "channel_subtype"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()


