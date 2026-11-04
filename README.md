# [Project PRD] 인지 모방형 스마트 갤러리: 기억 복원 및 맥락 확장 에이전트
> **Memory-Tracing Smart Gallery**  
> *"실제 사람이 기억하는 것처럼 원하는 사진을 찾아가는 지능형 갤러리 서비스"*

---

## 📌 1. 시스템 개요 및 아키텍처

본 프로젝트는 불완전하고 모호한 인간의 실제 기억 표현(예: *"작년 이맘때쯤 친구들이랑 흰 벽 배경으로 찍은 사진"*, *"주황색 벽 앞에서 패딩 입었던 거"*)을 수용하여, **대화형 스무고개 조율(Multi-turn Clarification)**과 **미시적 시각 단서(Micro-Visual Cues)** 추적을 통해 원하는 사진을 찾아내고, 기준 사진의 시공간 메타데이터를 역추적하여 **당일의 타임라인 스토리 카드(Day-Context Expansion)**를 연쇄적으로 동시 복원하는 스마트 갤러리 풀스택 솔루션입니다.

```
┌────────────────────────────────────────────────────────┐
│                   Flutter Client                       │
│  - 3열 갤러리 그리드 (GridView.builder)                │
│  - 스무고개 채팅 바텀시트 (ChatSheet / Multi-turn)     │
│  - 메인 타겟 사진 하이라이트 + XAI 매칭 태그 칩스      │
│  - 당일 발자취 가로 캐러셀 슬라이더 (StoryCarousel)     │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP REST API (JSON)
┌──────────────────────────▼─────────────────────────────┐
│                 FastAPI Brain Server                   │
│  - POST /api/search : 단일 샷 자연어 하이브리드 검색   │
│  - POST /api/chat   : 멀티턴 스무고개 대화형 조율     │
│  - GET  /api/photos : 100장 갤러리 초기 렌더링          │
│  - GET  /photos/{fn}: 고속 정적 이미지 스트리밍        │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
┌──────────────▼──────────┐    ┌──────────▼──────────────┐
│  SQLite (gallery.db)    │    │ ChromaDB (chroma_data/) │
│  - 정형 메타데이터       │    │ - 미시 시각 단서 임베딩 │
│  - EXIF 일자/위경도/장소 │    │ - 의상/배경/분위기 벡터 │
│  - 1차 고속 하드 필터링 │    │ - Dense 코사인 유사도   │
│  - 당일(±1일) 컨텍스트  │    │ - 결측 시 소프트 우회   │
└─────────────────────────┘    └─────────────────────────┘
```

---

## 🚀 2. 주요 차별화 기능 및 엔지니어링 명세

1. **EXIF 결측치 방어 메커니즘 (Fallback Policy)**
   - 카카오톡 다운로드 사진, 웹 스크린샷 등 EXIF(촬영일자, GPS) 메타데이터가 누락된 이미지가 다수 존재할 때도 크래시 없이 `captured_date` 및 `gps_location`을 `NULL`로 안전하게 적재.
   - 검색 시 SQL 하드 필터 결과가 0건일 경우 시스템 크래시 없이 자동으로 ChromaDB 소프트 벡터 검색 단독 모드로 우회(Fallback).
2. **Gemini Flash 무료 API 쿼터 방어**
   - 100장 이미지 인덱싱 시 15 RPM을 준수하여 호출 간 **최소 4.5초 대기(`time.sleep(4.5)`)** 및 `429 Too Many Requests` 지수 백오프 핸들러 탑재.
   - API 키 부재 시에도 자체 휴리스틱 파서 및 고성능 온디바이스 벡터 임베딩(`all-MiniLM-L6-v2`)으로 오프라인 데모 보장.
3. **하이브리드 랭킹 (Dense Vector + Sparse Keyword Re-ranking)**
   - 시맨틱 코사인 유사도와 미시적 시각 단서(의상, 벽 색상, 장소명)의 매칭 점수를 결합하여 정밀 타격.
4. **설명 가능한 AI (XAI) 매칭 태그**
   - `[🎯 날짜 일치 (2025-11-01)]`, `[🧥 의상 일치 (패딩)]`, `[🎨 배경 일치 (주황, 벽)]` 칩 제공.
5. **그날의 스토리 확장 (Day-Context Expansion)**
   - 타겟 사진 확정 시 해당 일자(±1일)에 함께 촬영된 사진들을 가로 카드 슬라이더(캐러셀) 형태로 자동 복원.

---

## 📂 3. 디렉토리 구조

```
Memory/
├── assets/
│   └── sample_photos/           # 100장의 사진 데이터셋 (EXIF 정상 + 결측 사진 포함)
├── backend/
│   ├── venv/                    # 파이썬 가상환경
│   ├── requirements.txt         # 백엔드 의존성 (fastapi, chromadb, google-genai 등)
│   ├── models.py                # Pydantic 데이터 모델 (PhotoVisionAnalysis, ParsedUserQuery)
│   ├── db.py                    # SQLite (gallery.db) 제어 및 Day-Context 확장 모듈
│   ├── vector_store.py          # ChromaDB 로컬 벡터 인덱스 및 코사인 검색
│   ├── gemini_service.py        # Gemini Flash Vision 분석 및 Temporal Anchor 쿼리 파서
│   ├── indexer.py               # 100장 배치 인덱서 (EXIF 추출, 4.5s 슬립, 429 Retry)
│   └── server.py                # FastAPI 서버 엔드포인트 (/api/search, /api/chat, /api/photos)
├── frontend/
│   ├── lib/
│   │   ├── models/photo_model.dart       # 플러터 데이터 모델
│   │   ├── services/api_service.dart     # 백엔드 연동 HTTP 서비스
│   │   ├── widgets/chat_sheet.dart       # 스무고개 멀티턴 대화형 바텀시트
│   │   ├── widgets/result_view.dart      # 타겟 사진 하이라이트 + XAI 태그 뷰
│   │   ├── widgets/story_carousel.dart   # 당일 발자취 가로 슬라이더
│   │   └── main.dart                     # 3열 갤러리 메인 화면 및 FAB
│   └── pubspec.yaml
├── scripts/
│   └── generate_sample_dataset.py       # 100장 샘플 이미지 생성기
├── gallery.db                   # 로컬 SQLite 데이터베이스
├── chroma_data/                 # 로컬 ChromaDB 벡터 인덱스 저장소
├── .env.example                 # 환경 변수 템플릿
└── .env                         # Gemini API Key 설정 파일
```

---

## 🛠️ 4. 빠른 실행 가이드 (Quick Start)

### 4.1 환경 변수 설정
`.env` 파일에 발급받은 Gemini API Key를 입력합니다:
```bash
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
```

### 4.2 사진 인덱싱 실행
갤러리 100장 사진을 SQLite와 ChromaDB에 인덱싱합니다:
```bash
# 가상환경 파이썬으로 인덱서 실행
./backend/venv/bin/python -m backend.indexer
```

### 4.3 백엔드 서버 구동
FastAPI 서버를 실행합니다:
```bash
./backend/venv/bin/uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
```
- API 헬스체크: `http://127.0.0.1:8000/api/health`
- Swagger 문서: `http://127.0.0.1:8000/docs`

### 4.4 플러터 앱 실행
별도의 터미널 창에서 프론트엔드를 실행합니다:
```bash
cd frontend
flutter run -d macos    # macOS 데스크톱 구동 (또는 chrome / ios / android)
```

