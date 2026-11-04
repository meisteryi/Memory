import os
import sys
import glob
import time
import uuid
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from backend.db import init_db, upsert_photo, get_photo_by_id
from backend.vector_store import get_vector_store
from backend.gemini_service import analyze_photo_with_vision

# 역지오코더 (네트워크 실패 대비 타임아웃 3초)
geolocator = Nominatim(user_agent="memory_tracing_smart_gallery_indexer")

def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None

def _convert_to_degrees(value) -> float:
    """EXIF GPS 좌표 (도, 분, 초)를 십진수 실수로 변환"""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return 0.0

def extract_exif(image_path: str) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    EXIF 결측치 방어 정책:
    Pillow로 촬영 일자 및 GPS 좌표를 안전하게 파싱.
    카톡 사진, 캡처본 등 EXIF가 없거나 파싱 오류가 나도 절대로 중단되지 않고 (None, None, None) 반환.
    """
    try:
        with Image.open(image_path) as img:
            exif_raw = img._getexif()
            if not exif_raw:
                return None, None, None

            # EXIF 태그 맵 생성
            exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}

            # 1. 촬영 날짜 추출 (YYYY-MM-DD 포맷 변환)
            captured_date = None
            date_str = exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized") or exif.get("DateTime")
            if date_str and isinstance(date_str, str):
                try:
                    # 보통 EXIF는 "YYYY:MM:DD HH:MM:SS" 형식
                    parts = date_str.split(" ")[0].replace(":", "-")
                    if len(parts) == 10:
                        captured_date = parts
                except Exception:
                    captured_date = None

            # 2. GPS 정보 추출
            gps_lat = None
            gps_lon = None
            gps_info = exif.get("GPSInfo")
            if gps_info and isinstance(gps_info, dict):
                gps_tags = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
                lat = _get_if_exist(gps_tags, "GPSLatitude")
                lat_ref = _get_if_exist(gps_tags, "GPSLatitudeRef")
                lon = _get_if_exist(gps_tags, "GPSLongitude")
                lon_ref = _get_if_exist(gps_tags, "GPSLongitudeRef")

                if lat and lat_ref and lon and lon_ref:
                    gps_lat = _convert_to_degrees(lat)
                    if lat_ref != "N":
                        gps_lat = -gps_lat
                    gps_lon = _convert_to_degrees(lon)
                    if lon_ref != "E":
                        gps_lon = -gps_lon

            return captured_date, gps_lat, gps_lon
    except Exception as e:
        print(f"[{image_path}] EXIF 파싱 방어 처리: {e}")
        return None, None, None

def reverse_geocode(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    """위도/경도 기반 행정구역 장소명 조회 (실패 시 None)"""
    if lat is None or lon is None:
        return None
    try:
        location = geolocator.reverse(f"{lat}, {lon}", timeout=3, language="ko")
        if location and location.address:
            # 주소 축약 (예: 대한민국 서울특별시 마포구)
            addr_parts = location.address.split(",")
            return addr_parts[0].strip() if addr_parts else location.address
    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
        print(f"[Reverse Geocode Warn]: {e}")
    return None

def index_single_photo(
    img_path: str,
    client_date: Optional[str] = None,
    force_reindex: bool = False
) -> Optional[Dict[str, Any]]:
    """
    단일 사진 인덱싱 (EXIF 추출 -> 역지오코딩 -> Vision 분석 -> SQLite/ChromaDB 적재)
    API 업로드 및 일괄 배치에서 공통으로 사용
    """
    filename = os.path.basename(img_path)
    photo_id = filename

    existing = get_photo_by_id(photo_id)
    if existing and not force_reindex:
        return existing

    # 1. EXIF 메타데이터 안전 추출
    captured_date, lat, lon = extract_exif(img_path)
    if not captured_date and client_date:
        captured_date = client_date[:10]

    # 2. 역지오코딩
    location_name = reverse_geocode(lat, lon)

    # 3. Vision 분석
    try:
        with open(img_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        print(f"  - 파일 읽기 실패 ({img_path}): {e}")
        return None

    mime_type = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
    vision_analysis = analyze_photo_with_vision(img_bytes, mime_type=mime_type, hint_filename=filename)
    final_location = location_name or vision_analysis.location_name_inference

    # 4. SQLite photos 테이블 적재
    upsert_photo(
        photo_id=photo_id,
        file_path=img_path,
        photo_category=vision_analysis.photo_category,
        captured_date=captured_date,
        gps_latitude=lat,
        gps_longitude=lon,
        location_name=final_location,
        people_traits=vision_analysis.people_traits,
        atmosphere=vision_analysis.atmosphere,
        background_details=vision_analysis.background_details,
        main_objects=vision_analysis.main_objects
    )

    # 5. ChromaDB 비정형 벡터 임베딩 적재
    category_label_map = {
        "SCREENSHOT": "디지털 화면 스크린샷 캡처",
        "MEMO_OBJECT": "모니터 화면 또는 문서/시간표/영수증 기록 촬영",
        "PERSON": "인물 및 셀카/단체 사진",
        "FOOD": "음식 및 카페 디저트/음료",
        "SCENERY": "풍경 및 야외/건물 배경",
        "OTHER": "일반 사물"
    }
    cat_desc = category_label_map.get(vision_analysis.photo_category, vision_analysis.photo_category)
    objects_desc = ", ".join(vision_analysis.main_objects) if vision_analysis.main_objects else ""

    embedding_text = (
        f"분류: {cat_desc}. "
        f"배경: {vision_analysis.background_details}. "
        f"인물: {vision_analysis.people_traits}. "
        f"분위기: {vision_analysis.atmosphere}. "
        f"사물: {objects_desc}. "
        f"장소: {final_location or ''}."
    ).strip()

    vector_store = get_vector_store()
    vector_store.add_or_update_photo(
        photo_id=photo_id,
        text_content=embedding_text,
        metadata={
            "photo_id": photo_id,
            "photo_category": vision_analysis.photo_category or "OTHER",
            "captured_date": captured_date or "",
            "location_name": final_location or ""
        }
    )

    return get_photo_by_id(photo_id)

def run_indexing(photos_dir: str = "assets/sample_photos", force_reindex: bool = False):
    """
    인덱스 타임 배치 파이프라인:
    1. 사진 스캔 (무작위 100장 지원)
    2. EXIF 추출 (결측 시 NULL 방어)
    3. 역지오코딩
    4. Gemini Flash Vision API 호출 (무료 티어 쿼터 방어: 4.5초 슬립 + 429 재시도)
    5. SQLite 적재 & ChromaDB 벡터 인덱싱
    """
    print(f"=== [Memory Gallery] 인덱싱 파이프라인 시작: {photos_dir} ===")
    init_db()
    vector_store = get_vector_store()

    # 이미지 파일 수집
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.heic", "*.JPG", "*.PNG")
    image_paths = []
    for ext in extensions:
        image_paths.extend(glob.glob(os.path.join(photos_dir, ext)))

    image_paths = sorted(list(set(image_paths)))
    total_count = len(image_paths)
    print(f"발견된 사진 총 {total_count}장")

    if total_count == 0:
        print(f"[알림] {photos_dir} 디렉토리에 사진이 없습니다.")
        return

    processed = 0
    skipped = 0

    for idx, img_path in enumerate(image_paths, start=1):
        filename = os.path.basename(img_path)
        existing = get_photo_by_id(filename)
        if existing and not force_reindex:
            skipped += 1
            continue

        print(f"\n[{idx}/{total_count}] 처리 중: {filename}")
        try:
            res = index_single_photo(img_path, force_reindex=force_reindex)
            if res:
                processed += 1
                print(f"  ✓ 인덱싱 완료: [{res.get('photo_category')}] 날짜={res.get('captured_date')}, 장소={res.get('location_name')}")
        except Exception as e:
            print(f"  ❌ 인덱싱 중 오류 발생 ({filename}): {e}")

        # 6. Gemini 무료 티어 보호를 위한 4.5초 슬립 간격 (15 RPM 준수)
        from backend.gemini_service import get_client
        if idx < total_count:
            if get_client():
                print("  ⏳ 무료 티어 쿼터 방어: 4.5초 대기 중...")
                time.sleep(4.5)
            else:
                time.sleep(0.02)

    print(f"\n=== 인덱싱 완료! 신규 처리: {processed}장, 스킵: {skipped}장, 총 {total_count}장 ===")

if __name__ == "__main__":
    photos_directory = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PHOTOS_DIR", "assets/sample_photos")
    force = "--force" in sys.argv
    run_indexing(photos_directory, force_reindex=force)
