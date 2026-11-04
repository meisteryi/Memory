import os
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import piexif

OUTPUT_DIR = "assets/sample_photos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 시나리오 테마들 (PRD 예시 포함)
THEMES = [
    {
        "name": "orange_wall_padding",
        "bg_color": (245, 130, 32), # 주황색 벽
        "title": "주황색 벽 앞 패딩",
        "date_offset_days": 365, # 작년 이맘때
        "location": "서울 성동구 성수동",
        "lat": 37.5446, "lon": 127.0560,
        "desc": "오렌지색 아트월 앞에서 두툼한 검정 숏패딩을 입고 활짝 웃고 있는 모습"
    },
    {
        "name": "white_wall_friends",
        "bg_color": (240, 240, 245), # 흰 벽
        "title": "흰 벽 스튜디오 친구들",
        "date_offset_days": 360, # 작년 이맘때
        "location": "서울 마포구 연남동",
        "lat": 37.5621, "lon": 126.9240,
        "desc": "깔끔한 화이트 벽 배경에서 친구 3명과 함께 브이 포즈를 취한 스튜디오 사진"
    },
    {
        "name": "winter_cafe_latte",
        "bg_color": (160, 110, 80),
        "title": "겨울 카페 라떼",
        "date_offset_days": 350,
        "location": "강원도 강릉시 안목해변",
        "lat": 37.7718, "lon": 128.9483,
        "desc": "따뜻한 조명의 원목 카페에서 따뜻한 라떼 잔을 들고 있는 겨울 풍경"
    },
    {
        "name": "summer_beach_sea",
        "bg_color": (40, 140, 215), # 푸른 바다
        "title": "제주 협재 푸른 바다",
        "date_offset_days": 120, # 지난 여름
        "location": "제주특별자치도 제주시 한림읍 협재해변",
        "lat": 33.3941, "lon": 126.2397,
        "desc": "에메랄드빛 바다와 하얀 백사장을 배경으로 밀짚모자와 반팔 티셔츠를 입은 여름 휴가"
    },
    {
        "name": "fall_park_coat",
        "bg_color": (195, 140, 50),
        "title": "가을 단풍 공원 코트",
        "date_offset_days": 380,
        "location": "서울 송파구 올림픽공원",
        "lat": 37.5209, "lon": 127.1215,
        "desc": "노란 은행잎 나무 아래에서 베이지색 롱코트를 입고 낙엽을 바라보는 가을 오후"
    },
    {
        "name": "kakao_screenshot_food",
        "bg_color": (210, 80, 70),
        "title": "카톡 다운로드 맛집 사진",
        "date_offset_days": None, # EXIF 결측 사진!
        "location": None,
        "lat": None, "lon": None,
        "desc": "붉은 양념 떡볶이와 튀김이 놓인 분식집 테이블 사진 (카톡 전달받아 메타데이터 없음)"
    },
    {
        "name": "night_han_river",
        "bg_color": (25, 30, 65),
        "title": "한강 야경 산책",
        "date_offset_days": 40,
        "location": "서울 서초구 반포한강공원",
        "lat": 37.5113, "lon": 126.9950,
        "desc": "빛나는 다리 조명과 강변 잔디밭에서 후드티를 입고 야경을 즐기는 밤"
    }
]

def make_gps_ifd(lat, lon):
    def to_deg(val, ref_pos, ref_neg):
        ref = ref_pos if val >= 0 else ref_neg
        val = abs(val)
        d = int(val)
        m = int((val - d) * 60)
        s = int(((val - d) * 60 - m) * 3600 * 100)
        return ((d, 1), (m, 1), (s, 100)), ref

    lat_tuple, lat_ref = to_deg(lat, 'N', 'S')
    lon_tuple, lon_ref = to_deg(lon, 'E', 'W')
    return {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: lat_tuple,
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: lon_tuple,
    }

def generate_100_photos():
    now = datetime.now()
    print(f"100장 샘플 사진 생성 시작... (저장 위치: {OUTPUT_DIR})")

    for i in range(1, 101):
        theme = THEMES[(i - 1) % len(THEMES)]
        
        # 이미지 캔버스 생성 (600x600)
        img = Image.new("RGB", (600, 600), color=theme["bg_color"])
        draw = ImageDraw.Draw(img)

        # 패턴 및 시각적 도형 그리기
        for _ in range(5):
            x1 = random.randint(20, 500)
            y1 = random.randint(20, 500)
            w = random.randint(40, 150)
            h = random.randint(40, 150)
            color_variation = (
                max(0, min(255, theme["bg_color"][0] + random.randint(-30, 30))),
                max(0, min(255, theme["bg_color"][1] + random.randint(-30, 30))),
                max(0, min(255, theme["bg_color"][2] + random.randint(-30, 30)))
            )
            draw.rectangle([x1, y1, x1+w, y1+h], fill=color_variation)

        # 텍스트 오버레이
        draw.rectangle([30, 240, 570, 360], fill=(0, 0, 0, 180))
        draw.text((50, 260), f"Sample #{i:03d}: {theme['title']}", fill=(255, 255, 255))
        draw.text((50, 300), f"특징: {theme['name']}", fill=(220, 220, 220))

        filename = f"photo_{i:03d}_{theme['name']}.jpg"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # EXIF 생성 (결측치 시나리오: 7로 나누어 떨어지는 사진은 카카오톡 사진처럼 EXIF 누락)
        is_missing_exif = (theme["date_offset_days"] is None) or (i % 7 == 0)

        if not is_missing_exif:
            # 타임스탬프 계산 (일부 사진은 같은 날 또는 당일 전후로 묶어서 Day-Context 테스트)
            offset = theme["date_offset_days"] + (i % 4) # 당일 및 ±1일 클러스터 형성
            photo_time = now - timedelta(days=offset, hours=random.randint(1, 12), minutes=random.randint(0, 59))
            date_str = photo_time.strftime("%Y:%m:%d %H:%M:%S")

            exif_dict = {
                "0th": {
                    piexif.ImageIFD.Make: "SmartPhone",
                    piexif.ImageIFD.Model: "Galaxy / iPhone",
                    piexif.ImageIFD.DateTime: date_str
                },
                "Exif": {
                    piexif.ExifIFD.DateTimeOriginal: date_str,
                    piexif.ExifIFD.DateTimeDigitized: date_str
                }
            }

            if theme["lat"] and theme["lon"]:
                exif_dict["GPS"] = make_gps_ifd(theme["lat"] + random.uniform(-0.01, 0.01), theme["lon"] + random.uniform(-0.01, 0.01))

            exif_bytes = piexif.dump(exif_dict)
            img.save(filepath, "jpeg", exif=exif_bytes)
        else:
            # EXIF 없는 사진 (웹 캡처/카톡 사진 방어 테스트용)
            img.save(filepath, "jpeg")

    print(f"✓ 100장의 무작위 및 EXIF 결측 방어 샘플 사진 생성 완료!")

if __name__ == "__main__":
    generate_100_photos()

