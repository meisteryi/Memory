import os
import json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.models import (
    PhotoVisionAnalysis,
    ParsedUserQuery,
    PhotoItem,
    SearchRequest,
    ChatRequest,
    SearchResponse,
    ChatMessage
)
from backend.db import (
    init_db,
    get_all_photos,
    get_photo_by_id,
    filter_photos_hard,
    get_day_context_photos,
    DEFAULT_DB_PATH
)
from backend.vector_store import get_vector_store
from backend.gemini_service import parse_user_query_with_llm
from backend.indexer import index_single_photo

app = FastAPI(
    title="Memory-Tracing Smart Gallery Backend",
    description="인지 모방형 스마트 갤러리: 기억 복원 및 맥락 확장 에이전트 백엔드 API",
    version="1.0.0"
)

# CORS 허용 (플러터 웹 및 모바일 클라이언트 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PHOTOS_DIR = os.environ.get("PHOTOS_DIR", "assets/sample_photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# 정적 사진 서빙 마운트
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")

@app.get("/viewer", response_class=FileResponse)
def get_metadata_viewer():
    """웹 브라우저에서 인덱싱된 108장 사진 메타데이터를 직접 열람하는 대시보드"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "reports", "metadata_viewer.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    raise HTTPException(status_code=404, detail="Viewer not found. Run scripts/generate_viewer.py first.")

# 세션별 대화 기록 메모리 저장소 (간단한 인메모리 관리)
session_histories: Dict[str, List[ChatMessage]] = {}

@app.on_event("startup")
def startup_event():
    init_db()
    get_vector_store()
    print("[Server] SQLite 및 ChromaDB 초기화 완료")

def _to_photo_item(row: Dict[str, Any]) -> PhotoItem:
    filename = os.path.basename(row["file_path"])
    return PhotoItem(
        id=row["id"],
        file_path=row["file_path"],
        image_url=f"/photos/{filename}",
        photo_category=row.get("photo_category"),
        captured_date=row.get("captured_date"),
        gps_latitude=row.get("gps_latitude"),
        gps_longitude=row.get("gps_longitude"),
        location_name=row.get("location_name"),
        people_traits=row.get("people_traits"),
        atmosphere=row.get("atmosphere"),
        background_details=row.get("background_details"),
        main_objects=row.get("main_objects", [])
    )

def _find_similar_mood_photos(
    target_dict: Dict[str, Any],
    exclude_ids: List[str],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """비슷한 분위기 확장: 타겟 사진의 분위기/배경 묘사로 벡터 검색 (타겟·당일 사진 제외)"""
    mood_text = " ".join(
        str(target_dict.get(k) or "")
        for k in ("atmosphere", "background_details", "photo_category")
    ).strip()
    if not mood_text:
        return []
    exclude = set(exclude_ids)
    matches = get_vector_store().query_similar(query_text=mood_text, n_results=limit + len(exclude))
    results: List[Dict[str, Any]] = []
    for m in matches:
        if m["id"] in exclude:
            continue
        row = get_photo_by_id(m["id"])
        if row:
            results.append(row)
        if len(results) >= limit:
            break
    return results

def _extract_query_keywords(text: str) -> List[str]:
    """검색어에서 주요 시각 단서 키워드 추출 (불용어 제외)"""
    stop_words = {"사진", "찾아줘", "보여줘", "찍은", "에서", "앞에서", "으로", "이랑", "하고", "있는", "있었던", "했던", "그때", "거", "것", "쯤", "날"}
    # 공백 및 특수문자 기준 분리
    words = [w.strip() for w in text.replace(",", " ").replace(".", " ").split() if len(w.strip()) >= 2]
    return [w for w in words if w not in stop_words]

def _rank_candidates_hybrid(
    matches: List[Dict[str, Any]],
    allowed_ids: Optional[List[str]],
    query: str,
    parsed: ParsedUserQuery
) -> Optional[Dict[str, Any]]:
    """
    하이브리드 랭킹 (Dense Vector Cosine + Sparse Keyword Re-ranking):
    미시적 시각 단서(주황색, 벽, 패딩, 흰 벽, 카페 등)의 정확한 타격을 위해 가중치 결합
    """
    keywords = _extract_query_keywords(f"{query} {parsed.semantic_query}")
    
    # 평가 대상 사진 목록 선정
    pool_ids = set()
    vector_scores = {}
    for m in matches:
        pool_ids.add(m["id"])
        vector_scores[m["id"]] = m.get("similarity", 0.5)

    if allowed_ids:
        # 1차 필터링된 후보군 추가
        for aid in allowed_ids[:20]:
            pool_ids.add(aid)
            if aid not in vector_scores:
                vector_scores[aid] = 0.4

    if not pool_ids:
        all_photos = get_all_photos()
        return all_photos[0] if all_photos else None

    scored_photos = []
    for pid in pool_ids:
        photo = get_photo_by_id(pid)
        if not photo:
            continue

        v_score = vector_scores.get(pid, 0.4)
        
        # Sparse 키워드 매칭 점수
        kw_score = 0.0
        searchable_text = f"{photo.get('background_details', '')} {photo.get('people_traits', '')} {photo.get('atmosphere', '')} {photo.get('location_name', '')}"
        
        # 카테고리 일치 가중치 보너스
        cat_bonus = 0.0
        if parsed.target_category and photo.get("photo_category") == parsed.target_category:
            cat_bonus = 0.4

        for kw in keywords:
            if kw in searchable_text:
                kw_score += 0.35
            # 부분 음절 매칭 (예: "주황" in "주황색")
            elif any(sub in searchable_text for sub in [kw[:2], kw[-2:]] if len(sub) >= 2):
                kw_score += 0.15

        total_score = v_score + kw_score + cat_bonus
        scored_photos.append((total_score, photo))

    scored_photos.sort(key=lambda x: x[0], reverse=True)
    return scored_photos[0][1] if scored_photos else None

def _generate_xai_tags(photo: Dict[str, Any], parsed: ParsedUserQuery, original_query: str) -> List[str]:
    """설명 가능한 AI (XAI) 매칭 태그 생성"""
    tags = []

    # 0. 카테고리 태그
    cat = photo.get("photo_category")
    if cat:
        cat_labels = {
            "SCREENSHOT": "📱 화면 스크린샷",
            "MEMO_OBJECT": "📝 모니터/문서 기록용 촬영",
            "PERSON": "👤 인물 사진",
            "FOOD": "☕/🍽️ 음식·카페",
            "SCENERY": "🏞️ 풍경·배경",
            "OTHER": "📷 사물 사진"
        }
        tags.append(cat_labels.get(cat, f"📁 {cat}"))
    
    # 1. 날짜 일치
    if photo.get("captured_date") and (parsed.start_date or parsed.end_date):
        tags.append(f"🎯 날짜 일치 ({photo['captured_date']})")
    elif photo.get("captured_date") and any(w in original_query for w in ["작년", "재작년", "겨울", "여름", "가을", "봄", "이맘때"]):
        tags.append(f"🎯 시점 유사 ({photo['captured_date']})")

    # 2. 의상 일치
    traits = photo.get("people_traits") or ""
    clothing_keywords = ["패딩", "코트", "자켓", "니트", "반팔", "모자", "셔츠", "청바지", "원피스", "후드"]
    matched_cloth = [k for k in clothing_keywords if k in traits and (k in original_query or k in parsed.semantic_query)]
    if matched_cloth:
        tags.append(f"🧥 의상 일치 ({', '.join(matched_cloth)})")
    elif traits and any(w in original_query for w in ["사람", "친구", "우리", "나"]):
        tags.append(f"👥 인물 매칭 ({traits[:18]}...)")

    # 3. 배경 일치
    bg = photo.get("background_details") or ""
    bg_keywords = ["주황", "흰 벽", "하얀", "벽", "바다", "카페", "타일", "나무", "숲", "창가", "테이블", "하늘"]
    matched_bg = [k for k in bg_keywords if k in bg and (k in original_query or k in parsed.semantic_query)]
    if matched_bg:
        tags.append(f"🎨 배경 일치 ({', '.join(matched_bg)})")

    # 4. 장소 일치
    loc = photo.get("location_name") or ""
    if loc and parsed.location_candidates:
        tags.append(f"📍 장소 일치 ({loc})")

    # 기본 매칭 보장
    if not tags:
        tags.append("✨ 미시적 시각 단서 및 분위기 매칭")
        if photo.get("atmosphere"):
            tags.append(f"🌤️ 분위기 ({photo['atmosphere'][:15]}...)")

    return tags

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Memory-Tracing Smart Gallery"}

@app.get("/api/photos", response_model=List[PhotoItem])
def list_photos():
    """갤러리 메인 뷰 (3열 그리드) 초기 로딩용 전체 사진 목록"""
    rows = get_all_photos()
    return [_to_photo_item(r) for r in rows]

@app.post("/api/upload_and_index", response_model=PhotoItem)
async def upload_and_index(
    file: UploadFile = File(...),
    client_date: Optional[str] = Form(None)
):
    """
    모바일 갤러리에서 실제 사진을 업로드받아 실시간 인덱싱 (EXIF, Gemini Vision, SQLite, ChromaDB)
    """
    filename = file.filename or f"upload_{os.urandom(4).hex()}.jpg"
    dest_path = os.path.join(PHOTOS_DIR, filename)
    with open(dest_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    indexed = index_single_photo(dest_path, client_date=client_date, force_reindex=True)
    if not indexed:
        raise HTTPException(status_code=500, detail="사진 인덱싱에 실패했습니다.")
    return _to_photo_item(indexed)

@app.post("/api/search", response_model=SearchResponse)
def search_photos(req: SearchRequest):
    """
    단일 샷 자연어 검색:
    Query Translator -> Hard/Soft 하이브리드 검색 -> 타겟 사진 P & Day-Context 타임라인 반환
    """
    parsed = parse_user_query_with_llm(req.query, chat_history=None)

    # 1. 모호성 판정 (Clarification Loop)
    if parsed.confidence_score < 0.6 and parsed.clarification_question:
        return SearchResponse(
            status="need_clarification",
            confidence_score=parsed.confidence_score,
            clarification_question=parsed.clarification_question,
            parsed_query=parsed
        )

    # 2. 하이브리드 필터링 & 랭킹
    # 2.1 SQLite 1차 하드 필터링 (카테고리, 날짜, 장소)
    hard_candidate_ids = filter_photos_hard(
        start_date=parsed.start_date,
        end_date=parsed.end_date,
        location_candidates=parsed.location_candidates,
        target_category=parsed.target_category
    )

    fallback_used = False
    # 하드 필터 결과가 0건일 경우: 카테고리/날짜 불일치 방어를 위해 조건 완화 후 소프트 벡터 검색으로 우회 (Fallback)
    if not hard_candidate_ids and parsed.target_category:
        # 카테고리 없이 날짜/장소만 재시도
        hard_candidate_ids = filter_photos_hard(
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            location_candidates=parsed.location_candidates
        )
    if not hard_candidate_ids:
        fallback_used = True
        hard_candidate_ids = None

    # 2.2 ChromaDB 시맨틱 쿼리 검색
    vector_store = get_vector_store()
    matches = vector_store.query_similar(
        query_text=parsed.semantic_query,
        n_results=10,
        allowed_ids=hard_candidate_ids
    )

    target_dict = _rank_candidates_hybrid(matches, hard_candidate_ids, req.query, parsed)
    if not target_dict:
        all_photos = get_all_photos()
        if not all_photos:
            raise HTTPException(status_code=404, detail="갤러리에 등록된 사진이 없습니다. 먼저 인덱싱을 진행해주세요.")
        target_dict = all_photos[0]

    # 3. 당일 맥락 확장 (Day-Context Expansion)
    target_date = target_dict.get("captured_date")
    day_story_photos_dict = get_day_context_photos(
        target_date=target_date,
        exclude_photo_id=target_dict["id"],
        window_days=1,
        limit=10
    )
    similar_photos_dict = _find_similar_mood_photos(
        target_dict,
        exclude_ids=[target_dict["id"]] + [r["id"] for r in day_story_photos_dict],
    )

    xai_tags = _generate_xai_tags(target_dict, parsed, req.query)

    return SearchResponse(
        status="success",
        confidence_score=parsed.confidence_score,
        target_photo=_to_photo_item(target_dict),
        xai_tags=xai_tags,
        day_story_photos=[_to_photo_item(r) for r in day_story_photos_dict],
        day_story_date=target_date,
        similar_photos=[_to_photo_item(r) for r in similar_photos_dict],
        parsed_query=parsed,
        fallback_used=fallback_used
    )

@app.post("/api/chat", response_model=SearchResponse)
def chat_and_clarify(req: ChatRequest):
    """
    스무고개 대화형 역질문 및 탐색 (Multi-turn Clarification):
    세션 히스토리를 바탕으로 사용자 답변을 점진적으로 축소
    """
    session_id = req.session_id
    history = session_histories.get(session_id, [])

    # 요청에 포함된 히스토리가 있으면 동기화
    if req.history:
        history = req.history

    # 사용자 새 메시지 추가
    history.append(ChatMessage(role="user", content=req.message))

    # LLM 질의 분석
    parsed = parse_user_query_with_llm(req.message, chat_history=history)

    # 확신도가 여전히 낮고 역질문이 생성되었으며 대화가 3턴 미만일 때 역질문 전송
    user_turns = sum(1 for m in history if m.role == "user")
    if parsed.confidence_score < 0.6 and parsed.clarification_question and user_turns < 4:
        # 어시스턴트 역질문 기록 저장
        history.append(ChatMessage(role="assistant", content=parsed.clarification_question))
        session_histories[session_id] = history
        return SearchResponse(
            status="need_clarification",
            confidence_score=parsed.confidence_score,
            clarification_question=parsed.clarification_question,
            parsed_query=parsed
        )

    # 충분히 좁혀졌거나 최대 턴 도달 시 최종 하이브리드 검색 수행
    hard_candidate_ids = filter_photos_hard(
        start_date=parsed.start_date,
        end_date=parsed.end_date,
        location_candidates=parsed.location_candidates,
        target_category=parsed.target_category
    )

    fallback_used = False
    if not hard_candidate_ids and parsed.target_category:
        hard_candidate_ids = filter_photos_hard(
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            location_candidates=parsed.location_candidates
        )
    if not hard_candidate_ids:
        fallback_used = True
        hard_candidate_ids = None

    vector_store = get_vector_store()
    matches = vector_store.query_similar(
        query_text=parsed.semantic_query,
        n_results=10,
        allowed_ids=hard_candidate_ids
    )

    combined_query_context = " ".join([m.content for m in history if m.role == "user"])
    target_dict = _rank_candidates_hybrid(matches, hard_candidate_ids, combined_query_context, parsed)
    if not target_dict:
        all_photos = get_all_photos()
        if not all_photos:
            raise HTTPException(status_code=404, detail="갤러리에 사진이 없습니다.")
        target_dict = all_photos[0]

    target_date = target_dict.get("captured_date")
    day_story_photos_dict = get_day_context_photos(
        target_date=target_date,
        exclude_photo_id=target_dict["id"],
        window_days=1,
        limit=10
    )
    similar_photos_dict = _find_similar_mood_photos(
        target_dict,
        exclude_ids=[target_dict["id"]] + [r["id"] for r in day_story_photos_dict],
    )

    # 복합 컨텍스트를 반영한 태그
    combined_query_context = " ".join([m.content for m in history if m.role == "user"])
    xai_tags = _generate_xai_tags(target_dict, parsed, combined_query_context)

    # 성공 메시지를 히스토리에 기록
    history.append(ChatMessage(role="assistant", content="원하시는 가장 일치하는 기억의 사진을 찾았습니다!"))
    session_histories[session_id] = history

    return SearchResponse(
        status="success",
        confidence_score=max(parsed.confidence_score, 0.75),
        target_photo=_to_photo_item(target_dict),
        xai_tags=xai_tags,
        day_story_photos=[_to_photo_item(r) for r in day_story_photos_dict],
        day_story_date=target_date,
        similar_photos=[_to_photo_item(r) for r in similar_photos_dict],
        parsed_query=parsed,
        fallback_used=fallback_used
    )
