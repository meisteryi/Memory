import os
import io
import json
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import APIError

from backend.models import PhotoVisionAnalysis, ParsedUserQuery, ChatMessage

# .env 로드
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-flash-lite-latest"

def get_client() -> Optional[genai.Client]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key.strip() in ("", "your_gemini_api_key_here"):
        return None
    return genai.Client(api_key=api_key)

def _optimize_image_bytes(image_bytes: bytes, max_dim: int = 1024) -> Tuple[bytes, str]:
    """Gemini Vision 전송 속도 및 대역폭 최적화를 위한 리사이징"""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # 투명 배경(RGBA)인 경우 RGB로 변환
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 긴 변이 max_dim보다 큰 경우만 축소
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                return buf.getvalue(), "image/jpeg"
    except Exception as e:
        pass
    return image_bytes, "image/jpeg"

def analyze_photo_with_vision(image_bytes: bytes, mime_type: str = "image/jpeg", hint_filename: Optional[str] = None, retry_count: int = 3) -> PhotoVisionAnalysis:
    """
    Gemini Flash Vision API를 호출하여 이미지의 미시적 시각 단서 및 분위기 분석
    429 에러 발생 시 지수 백오프 적용
    """
    client = get_client()
    if not client:
        # API 키 부재 시 안전한 휴리스틱 기본값 반환
        fn = (hint_filename or "").lower()
        if "orange_wall" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="성수동 카페거리",
                people_traits="검정 숏패딩을 입고 환하게 웃는 인물 1명",
                background_details="따뜻하고 선명한 주황색 벽 아트월",
                atmosphere="쌀쌀한 늦가을 또는 초겨울의 밝고 활기찬 분위기",
                main_objects=["패딩", "벽"]
            )
        elif "white_wall" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="연남동 포토 스튜디오",
                people_traits="니트와 캐주얼 의상을 입고 브이 포즈를 취한 친구들 3명",
                background_details="모던하고 미니멀한 흰 벽 스튜디오 배경",
                atmosphere="다정하고 따뜻한 실내 분위기",
                main_objects=["친구들", "스튜디오"]
            )
        elif "winter_cafe" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="강릉 안목해변 카페거리",
                people_traits="따뜻한 니트 스웨터를 입은 인물",
                background_details="나무 원목 테이블과 따스한 조명의 실내 인테리어",
                atmosphere="아늑하고 포근한 겨울 오후",
                main_objects=["커피 잔", "원목 테이블"]
            )
        elif "summer_beach" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="제주 협재해수욕장",
                people_traits="반팔 티셔츠와 밀짚모자를 쓴 여행객",
                background_details="푸른 에메랄드빛 바다와 하얀 백사장",
                atmosphere="청량하고 화창한 한여름 낮",
                main_objects=["밀짚모자", "바다", "모래사장"]
            )
        elif "fall_park" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="올림픽공원",
                people_traits="베이지색 롱코트를 입고 걷는 인물",
                background_details="노랗게 물든 은행나무와 낙엽 산책로",
                atmosphere="낭만적이고 선선한 늦가을",
                main_objects=["롱코트", "낙엽"]
            )
        elif "night_han_river" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="반포한강공원",
                people_traits="편안한 회색 후드티를 입은 인물",
                background_details="화려한 한강 다리 조명과 어두운 밤하늘 강변",
                atmosphere="시원한 바람이 부는 운치 있는 도시의 밤",
                main_objects=["한강 다리 조명", "후드티"]
            )
        elif "food" in fn or "kakao" in fn:
            return PhotoVisionAnalysis(
                location_name_inference="도심 분식 맛집",
                people_traits="테이블 너머로 보이는 손과 옷소매",
                background_details="정겨운 분식집 테이블과 벽면 낙서",
                atmosphere="왁자지껄하고 정겨운 점심 식사 분위기",
                main_objects=["떡볶이", "튀김", "접시"]
            )
        return PhotoVisionAnalysis(
            location_name_inference=None,
            people_traits="캐주얼한 일상복 차림의 인물",
            background_details="일상적인 실내외 배경",
            atmosphere="평온한 일상 분위기",
            main_objects=["소품", "배경"]
        )

    prompt = """
    당신은 사진의 대분류, 미시적 시각 단서와 인지적 기억 요소를 정밀 분석하는 최고의 비전 AI 전문가입니다.
    제공된 이미지를 주의 깊게 관찰하고 다음 규칙을 반드시 준수하여 JSON으로 분석 결과를 추출하세요:

    [1. photo_category (사진 핵심 대분류 - 다음 6개 중 반드시 택 1)]
    - 'SCREENSHOT': 모바일 폰이나 PC 화면을 캡처한 순수 디지털 스크린샷, 메신저 대화 캡처, 앱 UI, 웹페이지 캡처.
    - 'MEMO_OBJECT': 정보 기록 또는 스크린샷 대용으로 직접 카메라로 찍은 사진 (예: 모니터/노트북 화면 직접 촬영, TV 화면, 강의 슬라이드, 발표 화면, 포스터, 시간표, 안내문, 영수증, 책/문서 기록 등).
    - 'PERSON': 인물이 주요 피사체인 사진 (셀피/셀카, 독사진, 친구/연인/가족과 함께 찍은 인물/단체 사진, 사람의 상반신/전신).
    - 'FOOD': 음식 접시/그릇, 식사, 고기, 찌개, 베이커리/디저트, 카페 커피/라떼, 주류/음료 등이 메인인 사진.
    - 'SCENERY': 자연 풍경, 바다, 산, 하늘, 도시 거리/야경, 건물 외관, 인물이 없는 실내외 공간/배경이 주가 되는 사진.
    - 'OTHER': 위 5개 카테고리에 명확히 속하지 않는 기타 단독 사물/물체.

    [2. 미시적 시각 단서 및 분위기]
    - people_traits: 인물 수, 구체적 옷차림(예: 검정 숏패딩, 베이지색 코트, 흰색 반팔 티셔츠, 니트), 표정, 포즈. (인물이 없으면 빈 문자열 "")
    - background_details: 배경의 구체적 시각 특징과 색상 (예: 주황색 벽, 흰 벽, 카페 타일, 바닷가 모래사장, 초록 잔디, 원목 테이블, 모니터 화면).
    - atmosphere: 전체적인 시각 분위기, 계절감, 조명, 시간대 (예: 쌀쌀한 늦가을 오후, 따뜻한 실내 조명, 화창한 여름 낮, 어두운 밤).
    - main_objects: 주요 물품, 음식, 기기, 소품 리스트.
    - location_name_inference: 간판, 랜드마크, 특징적 배경을 통해 유추 가능한 장소명 (없으면 null).
    """

    optimized_bytes, opt_mime = _optimize_image_bytes(image_bytes)

    delay = 10.0
    for attempt in range(retry_count):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    types.Part.from_bytes(data=optimized_bytes, mime_type=opt_mime),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PhotoVisionAnalysis,
                    temperature=0.2
                )
            )
            data = json.loads(response.text)
            return PhotoVisionAnalysis(**data)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"[Gemini Vision] 429 Rate limit 도달. {delay}초 대기 후 재시도 (시도 {attempt+1}/{retry_count})...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"[Gemini Vision Error]: {e}")
                if attempt == retry_count - 1:
                    break
                time.sleep(2)

    # 실패 시 폴백 반환
    return PhotoVisionAnalysis(
        location_name_inference=None,
        people_traits="분석 실패 폴백",
        background_details="일반 배경",
        atmosphere="자연스러운 분위기",
        main_objects=[]
    )

def parse_user_query_with_llm(
    query: str,
    chat_history: Optional[List[ChatMessage]] = None,
    current_date: Optional[str] = None
) -> ParsedUserQuery:
    """
    자연어 쿼리를 시간적 앵커(Temporal Anchor)와 함께 주입하여
    정형/비정형 조건으로 분리 파싱하고, 스무고개 역질문 필요 여부를 판정
    """
    if not current_date:
        current_date = datetime.now().strftime("%Y-%m-%d")

    client = get_client()
    if not client:
        # API 키가 없을 때의 정규식 기반 휴리스틱 폴백
        return _fallback_query_parser(query, current_date)

    # 대화 기록 포맷팅
    history_text = ""
    if chat_history:
        for m in chat_history:
            history_text += f"- {m.role}: {m.content}\n"

    system_instruction = f"""
    당신은 인간의 불완전한 기억 표현을 데이터베이스 검색 조건으로 변환하는 '기억 추적 갤러리 에이전트'입니다.
    현재 기준 날짜는 [{current_date}] 입니다.

    [규칙]
    1. target_category (추정 사진 유형):
       - 'SCREENSHOT': 사용자가 스크린샷, 캡처본, 카톡 캡처, 대화 내용 캡처, 결제화면 캡처 등을 찾을 때.
       - 'MEMO_OBJECT': 모니터 화면 찍은 거, 노트북 화면 촬영, 시간표, 포스터, 강의 슬라이드, 발표 화면, 영수증, 안내문, 문서/책 등을 찍은 정보 기록용 사진을 찾을 때.
       - 'PERSON': 사람, 친구들, 셀카/셀피, 단체 사진, 우리들 얼굴 등을 찾을 때.
       - 'FOOD': 음식, 밥, 고기, 떡볶이, 카페 디저트, 커피, 술자리/맥주 등을 찾을 때.
       - 'SCENERY': 풍경, 바다, 산, 하늘, 야경, 거리, 건물, 자연 등을 찾을 때.
       - 위 유형이 명확하지 않으면 null로 둡니다.

    2. 시간적 앵커 (Temporal Anchor):
       - '작년 이맘때': 작년 오늘 기준 앞뒤 1개월 (예: {int(current_date[:4])-1}-10-01 ~ {int(current_date[:4])-1}-11-30)
       - '지난 주', '지난 달', '재작년 겨울', '2년 전 여름' 등을 현재 날짜 기준으로 정확한 start_date, end_date (YYYY-MM-DD) 범위로 계산하십시오.
       - 시점이 명시되지 않으면 start_date와 end_date는 null로 설정합니다.

    3. location_candidates:
       - '제주도', '강릉', '홍대', '부산' 등 언급된 지명 또는 유추 가능한 지명 목록. 없으면 빈 배열.

    4. semantic_query:
       - 미시적 시각 단서(옷차림: 패딩, 코트 등 / 배경: 주황색 벽, 흰 벽 / 분위기: 겨울, 카페 등 / 유형 특징)를 조합한 풍부한 검색 문장 생성.

    5. confidence_score & clarification_question:
       - 사용자의 기억 단서가 1~2개 이상 구체적이면 confidence_score >= 0.7, clarification_question = null.
       - 입력이 너무 막연하거나(예: "사진 찾아줘", "보여줘") 시공간이나 시각 단서가 전혀 없으면 confidence_score < 0.6으로 설정하고,
         사용자가 기억을 되살릴 수 있도록 부드러운 스무고개 역질문(예: "혹시 그때 찍으신 사진이 음식인가요, 풍경인가요? 아니면 기억나는 옷이나 배경 색상이 있을까요?")을 clarification_question에 생성하십시오.
    """

    user_prompt = f"""
    대화 기록:
    {history_text if history_text else "없음"}

    현재 사용자 질문: "{query}"

    위 내용을 종합하여 ParsedUserQuery 스키마의 JSON으로 응답하세요.
    """

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[user_prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ParsedUserQuery,
                temperature=0.1
            )
        )
        data = json.loads(response.text)
        return ParsedUserQuery(**data)
    except Exception as e:
        print(f"[Gemini Query Translation Error]: {e}")
        return _fallback_query_parser(query, current_date)

def _fallback_query_parser(query: str, current_date: str) -> ParsedUserQuery:
    """API 키 미등록 또는 오류 시 동작하는 자체 파서"""
    today = datetime.strptime(current_date, "%Y-%m-%d")
    start_date = None
    end_date = None
    locations = []
    target_category = None

    # 카테고리 유추
    if any(w in query for w in ["스크린샷", "캡처", "카톡"]):
        target_category = "SCREENSHOT"
    elif any(w in query for w in ["모니터", "화면 찍", "슬라이드", "영수증", "문서", "시간표", "포스터", "안내문"]):
        target_category = "MEMO_OBJECT"
    elif any(w in query for w in ["사람", "친구", "셀카", "셀피", "우리"]):
        target_category = "PERSON"
    elif any(w in query for w in ["음식", "밥", "고기", "카페", "커피", "디저트", "술", "맥주", "식사"]):
        target_category = "FOOD"
    elif any(w in query for w in ["풍경", "바다", "산", "야경", "하늘", "거리", "건물", "자연"]):
        target_category = "SCENERY"
    
    # 시간 유추
    if "작년" in query:
        last_year = today.year - 1
        if "이맘때" in query or "겨울" in query or "가을" in query:
            start_date = f"{last_year}-10-01"
            end_date = f"{last_year}-12-31"
        else:
            start_date = f"{last_year}-01-01"
            end_date = f"{last_year}-12-31"
    elif "재작년" in query:
        yr = today.year - 2
        start_date = f"{yr}-01-01"
        end_date = f"{yr}-12-31"

    # 주요 지명 패턴
    for loc in ["제주", "강릉", "부산", "속초", "여수", "경주", "홍대", "성수", "한강", "이태원"]:
        if loc in query:
            locations.append(loc)

    # 확신도 판정
    has_visual = any(w in query for w in ["벽", "패딩", "코트", "바다", "카페", "친구", "주황", "흰", "노란"])
    confidence = 0.85 if (has_visual or start_date or locations or target_category) else 0.4
    clarification = None
    if confidence < 0.6:
        clarification = "그날 찍으셨던 사진이 어떤 유형(음식, 풍경, 사람 등)이거나 기억나는 옷차림, 배경 색상이 있으실까요?"

    return ParsedUserQuery(
        target_category=target_category,
        location_candidates=locations,
        start_date=start_date,
        end_date=end_date,
        semantic_query=query,
        confidence_score=confidence,
        clarification_question=clarification
    )
