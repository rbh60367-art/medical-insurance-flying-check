from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "database" / "sample_claims.db"


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE settlement_main (
              setl_id TEXT PRIMARY KEY,
              mdtrt_id TEXT,
              fixmedins_code TEXT,
              psn_no TEXT,
              gend TEXT,
              age INTEGER,
              fund_pay_sumamt REAL,
              setl_time TEXT
            );

            CREATE TABLE fee_detail (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              setl_id TEXT,
              mdtrt_id TEXT,
              hilist_code TEXT,
              hilist_name TEXT,
              cnt REAL,
              pric REAL,
              det_item_fee_sumamt REAL,
              fee_ocur_time TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO settlement_main VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("S001", "M001", "H1001", "P001", "1", 45, 180.0, "2025-03-10"),
                ("S002", "M002", "H1002", "P002", "2", 63, 90.0, "2025-04-11"),
                ("S003", "M003", "H1001", "P003", "1", 51, 50.0, "2025-05-12"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO fee_detail (setl_id, mdtrt_id, hilist_code, hilist_name, cnt, pric, det_item_fee_sumamt, fee_ocur_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("S001", "M001", "001103000010000", "急诊监护费", 1, 120.0, 120.0, "2025-03-10"),
                ("S001", "M001", "001102000030000", "急诊诊查费", 1, 30.0, 30.0, "2025-03-10"),
                ("S002", "M002", "001103000010000", "急诊监护费", 1, 120.0, 120.0, "2025-04-11"),
                ("S003", "M003", "001102000030000", "急诊诊查费", 1, 30.0, 30.0, "2025-05-12"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    print(DB_PATH)


if __name__ == "__main__":
    main()
