from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# 4.2 Vision API 인덱싱용 스키마
class PhotoVisionAnalysis(BaseModel):
    photo_category: str = Field(
        default="OTHER",
        description="사진 대분류: 'SCREENSHOT'(모바일/PC 순수 화면캡처), 'MEMO_OBJECT'(모니터화면/포스터/문서/영수증 등 스크린샷 대용 기록 촬영), 'PERSON'(인물/셀피/단체사진), 'FOOD'(음식/카페/디저트/음료), 'SCENERY'(풍경/자연/건물/거리/야경), 'OTHER'(기타 사물)"
    )
    location_name_inference: Optional[str] = Field(default=None, description="간판/랜드마크 기반 유추 장소명")
    people_traits: str = Field(default="", description="인물 수, 옷차림(패딩, 코트 등), 표정, 자세 (실명 언급 금지)")
    background_details: str = Field(default="", description="배경의 구체적 시각 특징 및 색상 (예: 주황색 벽, 흰 벽, 파란 타일)")
    atmosphere: str = Field(default="", description="전체 분위기, 계절감, 시간대 (예: 흐린 겨울 낮, 아늑한 실내)")
    main_objects: List[str] = Field(default_factory=list, description="주요 객체, 음식, 소품 목록")

# 4.3 쿼리 번역기 스키마
class ParsedUserQuery(BaseModel):
    # 정형 필터링 조건 (SQLite WHERE 매핑)
    target_category: Optional[str] = Field(default=None, description="추정 사진 유형 (SCREENSHOT, MEMO_OBJECT, PERSON, FOOD, SCENERY)")
    location_candidates: List[str] = Field(default_factory=list, description="추정 장소 후보 리스트 (예: ['강릉', '여수'])")
    start_date: Optional[str] = Field(default=None, description="추정 시작일 YYYY-MM-DD (현재 날짜 기준 역산)")
    end_date: Optional[str] = Field(default=None, description="추정 종료일 YYYY-MM-DD")
    
    # 비정형 임베딩 쿼리 (ChromaDB 코사인 유사도 검색용)
    semantic_query: str = Field(description="미시적 시각 단서, 의상, 배경 색상, 분위기를 조합한 문장")
    
    # 에이전트 인터랙션 제어
    confidence_score: float = Field(default=0.8, description="사용자 입력으로 사진군을 특정할 수 있는 확신도 (0.0 ~ 1.0)")
    clarification_question: Optional[str] = Field(default=None, description="확신도가 낮을 때 사용자에게 던질 역질문")

# API 통신 모델들
class PhotoItem(BaseModel):
    id: str
    file_path: str
    image_url: str
    photo_category: Optional[str] = None
    captured_date: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    location_name: Optional[str] = None
    people_traits: Optional[str] = None
    atmosphere: Optional[str] = None
    background_details: Optional[str] = None
    main_objects: List[str] = Field(default_factory=list)

class SearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: List[ChatMessage] = Field(default_factory=list)

class SearchResponse(BaseModel):
    status: str  # "success" | "need_clarification"
    confidence_score: float
    clarification_question: Optional[str] = None
    target_photo: Optional[PhotoItem] = None
    xai_tags: List[str] = Field(default_factory=list)
    day_story_photos: List[PhotoItem] = Field(default_factory=list)
    day_story_date: Optional[str] = None
    similar_photos: List[PhotoItem] = Field(default_factory=list)
    parsed_query: Optional[ParsedUserQuery] = None
    fallback_used: bool = False

