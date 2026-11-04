import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

DEFAULT_DB_PATH = os.environ.get("DB_PATH", "gallery.db")

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH):
    """SQLite photos 테이블 초기화"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            photo_category TEXT,        -- SCREENSHOT, MEMO_OBJECT, PERSON, FOOD, SCENERY, OTHER
            captured_date TEXT,          -- YYYY-MM-DD (EXIF 기반, 결측 시 NULL)
            gps_latitude REAL,           -- 위도 (결측 시 NULL)
            gps_longitude REAL,          -- 경도 (결측 시 NULL)
            location_name TEXT,          -- 역지오코딩된 장소명 (결측 시 NULL)
            people_traits TEXT,          -- 비실명 인물 외형, 의상(패딩, 코트 등), 표정, 자세
            atmosphere TEXT,             -- 시각적 분위기, 시간대, 날씨
            background_details TEXT,     -- 주황색 벽, 흰 벽, 바닷가 등 미시적 배경 특징
            main_objects TEXT            -- JSON 형식의 주요 사물/음식 목록
        );
        """)
        try:
            cursor.execute("ALTER TABLE photos ADD COLUMN photo_category TEXT;")
        except sqlite3.OperationalError:
            pass
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_captured_date ON photos(captured_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_photo_category ON photos(photo_category);")
        conn.commit()

def upsert_photo(
    photo_id: str,
    file_path: str,
    captured_date: Optional[str],
    gps_latitude: Optional[float],
    gps_longitude: Optional[float],
    location_name: Optional[str],
    people_traits: Optional[str],
    atmosphere: Optional[str],
    background_details: Optional[str],
    main_objects: List[str],
    photo_category: Optional[str] = "OTHER",
    db_path: str = DEFAULT_DB_PATH
):
    """사진 메타데이터 삽입 또는 갱신"""
    objects_json = json.dumps(main_objects, ensure_ascii=False) if main_objects else "[]"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO photos (
            id, file_path, photo_category, captured_date, gps_latitude, gps_longitude,
            location_name, people_traits, atmosphere, background_details, main_objects
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            file_path=excluded.file_path,
            photo_category=excluded.photo_category,
            captured_date=excluded.captured_date,
            gps_latitude=excluded.gps_latitude,
            gps_longitude=excluded.gps_longitude,
            location_name=excluded.location_name,
            people_traits=excluded.people_traits,
            atmosphere=excluded.atmosphere,
            background_details=excluded.background_details,
            main_objects=excluded.main_objects;
        """, (
            photo_id, file_path, photo_category, captured_date, gps_latitude, gps_longitude,
            location_name, people_traits, atmosphere, background_details, objects_json
        ))
        conn.commit()

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("main_objects"):
        try:
            d["main_objects"] = json.loads(d["main_objects"])
        except Exception:
            d["main_objects"] = []
    else:
        d["main_objects"] = []
    return d

def get_all_photos(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM photos ORDER BY captured_date DESC, id ASC")
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]

def get_photo_by_id(photo_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
        row = cursor.fetchone()
        return row_to_dict(row) if row else None

def filter_photos_hard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    location_candidates: Optional[List[str]] = None,
    target_category: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> List[str]:
    """
    1차 정형 하드 필터링:
    사진 유형(대분류), 날짜 범위 및 장소 키워드로 매칭되는 사진 ID 목록 반환.
    만약 조건이 없으면 모든 사진 ID를 반환.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = "SELECT id FROM photos WHERE 1=1"
        params: List[Any] = []

        # 카테고리 필터
        if target_category:
            query += " AND photo_category = ?"
            params.append(target_category)

        # 날짜 필터 (captured_date가 있는 경우만 비교 가능)
        if start_date and end_date:
            query += " AND captured_date IS NOT NULL AND captured_date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        elif start_date:
            query += " AND captured_date IS NOT NULL AND captured_date >= ?"
            params.append(start_date)
        elif end_date:
            query += " AND captured_date IS NOT NULL AND captured_date <= ?"
            params.append(end_date)

        # 장소 필터 (location_name에 포함되어 있는지)
        if location_candidates:
            loc_clauses = []
            for loc in location_candidates:
                loc_clauses.append("location_name LIKE ?")
                params.append(f"%{loc}%")
            if loc_clauses:
                query += " AND (" + " OR ".join(loc_clauses) + ")"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [r["id"] for r in rows]

def get_day_context_photos(
    target_date: Optional[str],
    exclude_photo_id: Optional[str] = None,
    window_days: int = 1,
    limit: int = 20,
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """
    당일 맥락 확장 (Day-Context Expansion):
    기준 사진의 captured_date 기준 ±1일 범위 내 사진들을 조회.
    만약 target_date가 결측(NULL)인 경우, 빈 리스트 반환.
    """
    if not target_date:
        return []

    try:
        dt = datetime.strptime(target_date[:10], "%Y-%m-%d")
        start_dt = (dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
        end_dt = (dt + timedelta(days=window_days)).strftime("%Y-%m-%d")
    except Exception:
        # 날짜 파싱 실패 시 단순 일치 시도
        start_dt = target_date
        end_dt = target_date

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
        SELECT * FROM photos
        WHERE captured_date BETWEEN ? AND ?
        """
        params: List[Any] = [start_dt, end_dt]
        if exclude_photo_id:
            query += " AND id != ?"
            params.append(exclude_photo_id)
        
        query += " ORDER BY captured_date ASC, id ASC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]

