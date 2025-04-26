import sqlite3
import json
import pickle
import time
import os
from typing import List, Dict, Any
import numpy as np  # <--- Додано імпорт numpy для _to_native
                          
DB_PATH = "sessions/packing_sessions.db"

def init_db(db_path: str = DB_PATH) -> None:
    """
    Ініціалізує базу даних: створює таблицю sessions з назвою, timestamp,
    даними контейнера, коробок та фігурою, якщо її немає.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        container_json TEXT NOT NULL,
        boxes_json TEXT NOT NULL,
        fig_pickle BLOB NOT NULL,
        packed_items_json TEXT NOT NULL DEFAULT '[]'
    )
    """)
    conn.commit()
    conn.close()

def save_session_to_db(
    name: str,
    container: Dict[str, Any],
    boxes: List[Dict[str, Any]],
    fig,
    packed_items: List[Dict[str, Any]]
) -> int:
    """
    Зберігає сесію пакування у БД з вказаною назвою "name",
    контейнер, коробки, згенеровану фігуру та результати packed_items.
    Повертає id нової сесії.
    """
    def _to_native(obj):
        # рекурсивно конвертує numpy-типи в вбудовані Python-типи
        if isinstance(obj, dict):
            return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_native(v) for v in obj]
        # перевіряємо на всі numpy-скалярні типи
        if isinstance(obj, np.generic):
            return obj.item()
        return obj

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cont_json   = json.dumps(_to_native(container), ensure_ascii=False)
    boxes_json  = json.dumps(_to_native(boxes), ensure_ascii=False)
    packed_json = json.dumps(_to_native(packed_items), ensure_ascii=False)
    fig_bytes   = pickle.dumps(fig)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO sessions
            (name, timestamp, container_json, boxes_json, fig_pickle, packed_items_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, ts, cont_json, boxes_json, fig_bytes, packed_json)
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def list_sessions(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Повертає список сесій із полями 'id', 'name' та 'timestamp'.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name, timestamp FROM sessions ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": row[0], "name": row[1], "timestamp": row[2]} for row in rows]


def load_fig_from_db(session_id: int, db_path: str = DB_PATH):
    """
    Завантажує об'єкт Matplotlib Figure з БД за session_id.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT fig_pickle FROM sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"Session {session_id} not found")
    fig = pickle.loads(row[0])
    return fig
