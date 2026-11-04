import sqlite3
import json
import os

conn = sqlite3.connect('gallery.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT * FROM photos ORDER BY captured_date DESC, id ASC')
photos = [dict(r) for r in cursor.fetchall()]

for p in photos:
    try:
        p['main_objects'] = json.loads(p['main_objects']) if p.get('main_objects') else []
    except:
        p['main_objects'] = []

photos_json = json.dumps(photos, ensure_ascii=False)

html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>스마트 갤러리 메타데이터 대시보드 (108장)</title>
    <style>
        :root {
            --bg-color: #f4f6f9;
            --card-bg: #ffffff;
            --primary: #4361ee;
            --text-main: #2b2d42;
            --text-sub: #6c757d;
            --border: #e9ecef;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Pretendard', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px;
        }
        header {
            background: #fff;
            padding: 20px 24px;
            border-radius: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            margin-bottom: 24px;
            position: sticky;
            top: 12px;
            z-index: 100;
        }
        h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; color: #1e1e24; }
        p.subtitle { font-size: 13px; color: var(--text-sub); }
        
        .controls {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 16px;
            align-items: center;
        }
        .search-box {
            flex: 1;
            min-width: 280px;
        }
        .search-box input {
            width: 100%;
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid #ced4da;
            font-size: 14px;
            outline: none;
            transition: border 0.2s;
        }
        .search-box input:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(67,97,238,0.2); }
        
        .filter-chips {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .chip {
            padding: 7px 13px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            background: #e9ecef;
            color: #495057;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }
        .chip:hover { background: #dee2e6; }
        .chip.active { background: var(--primary); color: #fff; }
        
        .stats-bar {
            margin-top: 12px;
            font-size: 13px;
            color: var(--text-sub);
            font-weight: 600;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 20px;
        }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border);
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.1);
        }
        .card-img-wrap {
            width: 100%;
            height: 230px;
            background-color: #e9ecef;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }
        .card-img-wrap img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .badge-cat {
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            color: white;
            text-transform: uppercase;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .cat-FOOD { background: #e63946; }
        .cat-PERSON { background: #4361ee; }
        .cat-SCENERY { background: #2a9d8f; }
        .cat-SCREENSHOT { background: #7209b7; }
        .cat-MEMO_OBJECT { background: #f77f00; }
        .cat-OTHER { background: #6c757d; }
        
        .badge-id {
            position: absolute;
            bottom: 8px;
            right: 8px;
            background: rgba(0,0,0,0.7);
            color: #fff;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-family: monospace;
        }
        
        .card-body {
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            flex: 1;
            font-size: 13px;
        }
        .row-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: var(--text-sub);
            border-bottom: 1px dashed var(--border);
            padding-bottom: 8px;
        }
        .row-meta .date { font-weight: 600; color: #212529; }
        .meta-field {
            margin-top: 2px;
        }
        .meta-label {
            font-weight: 600;
            color: #495057;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
            margin-bottom: 3px;
        }
        .meta-value {
            color: #212529;
            line-height: 1.45;
            word-break: break-all;
            background: #f8f9fa;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 12.5px;
            border: 1px solid #f1f3f5;
        }
        .tag-pill {
            display: inline-block;
            background: #eef2ff;
            color: #3b5bdb;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin: 2px 3px 2px 0;
            font-weight: 500;
        }
        .no-data {
            color: #adb5bd;
            font-style: italic;
        }
    </style>
</head>
<body>

<header>
    <h1>📸 스마트 갤러리 메타데이터 대시보드</h1>
    <p class="subtitle">gallery.db 및 ChromaDB에 인덱싱된 108장 사진의 비전 분석 메타데이터 열람 및 검색 진단</p>
    
    <div class="controls">
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="키워드 검색 (예: 주황, 패딩, 카페, 바다, 2026-10)..." oninput="render()">
        </div>
        <div class="filter-chips" id="categoryFilters">
            <button class="chip active" onclick="selectCategory('ALL', this)">전체 (108)</button>
            <button class="chip" onclick="selectCategory('PERSON', this)">인물 (PERSON: 24)</button>
            <button class="chip" onclick="selectCategory('FOOD', this)">음식 (FOOD: 22)</button>
            <button class="chip" onclick="selectCategory('SCENERY', this)">풍경 (SCENERY: 28)</button>
            <button class="chip" onclick="selectCategory('SCREENSHOT', this)">스크린샷 (SCREENSHOT: 15)</button>
            <button class="chip" onclick="selectCategory('MEMO_OBJECT', this)">메모/사물 (MEMO: 11)</button>
            <button class="chip" onclick="selectCategory('OTHER', this)">기타 (OTHER: 8)</button>
        </div>
    </div>
    <div class="stats-bar" id="statsBar">표시 중: 108장</div>
</header>

<main class="grid" id="photoGrid"></main>

<script>
const photos = __PHOTOS_JSON_PLACEHOLDER__;
let selectedCategory = 'ALL';

function selectCategory(cat, btn) {
    selectedCategory = cat;
    document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    render();
}

function render() {
    const q = document.getElementById('searchInput').value.trim().toLowerCase();
    const grid = document.getElementById('photoGrid');
    grid.innerHTML = '';
    
    const filtered = photos.filter(p => {
        if (selectedCategory !== 'ALL' && p.photo_category !== selectedCategory) {
            return false;
        }
        if (!q) return true;
        
        const haystack = [
            p.id,
            p.file_path,
            p.photo_category || '',
            p.captured_date || '',
            p.location_name || '',
            p.people_traits || '',
            p.atmosphere || '',
            p.background_details || '',
            (p.main_objects || []).join(' ')
        ].join(' ').toLowerCase();
        
        return haystack.includes(q);
    });
    
    document.getElementById('statsBar').innerText = `검색 결과: ${filtered.length} / 108장`;
    
    filtered.forEach(p => {
        const card = document.createElement('div');
        card.className = 'card';
        
        const cat = p.photo_category || 'OTHER';
        const filename = p.file_path.split('/').pop();
        const imgPath = window.location.protocol.startsWith('http') ? `/photos/${filename}` : '../' + p.file_path;
        
        let objectsHtml = '<span class="no-data">사물 정보 없음</span>';
        if (p.main_objects && p.main_objects.length > 0) {
            objectsHtml = p.main_objects.map(obj => `<span class="tag-pill">#${obj}</span>`).join('');
        }
        
        card.innerHTML = `
            <div class="card-img-wrap">
                <span class="badge-cat cat-${cat}">${cat}</span>
                <img src="${imgPath}" alt="${p.id}" loading="lazy" onerror="this.onerror=null; this.src='https://placehold.co/400x300?text=No+Image';">
                <span class="badge-id">${p.id}</span>
            </div>
            <div class="card-body">
                <div class="row-meta">
                    <span class="date">📅 ${p.captured_date || '<span class="no-data">EXIF 결측</span>'}</span>
                    <span>📍 ${p.location_name || '<span class="no-data">위치 미상</span>'}</span>
                </div>
                
                ${p.people_traits ? `
                <div class="meta-field">
                    <div class="meta-label">👥 인물 외형 / 의상</div>
                    <div class="meta-value">${p.people_traits}</div>
                </div>` : ''}
                
                ${p.background_details ? `
                <div class="meta-field">
                    <div class="meta-label">🎨 미시적 배경 특징</div>
                    <div class="meta-value">${p.background_details}</div>
                </div>` : ''}
                
                ${p.atmosphere ? `
                <div class="meta-field">
                    <div class="meta-label">✨ 분위기 / 시간대</div>
                    <div class="meta-value">${p.atmosphere}</div>
                </div>` : ''}
                
                <div class="meta-field">
                    <div class="meta-label">🏷️ 주요 사물 (Objects)</div>
                    <div style="margin-top: 4px;">${objectsHtml}</div>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

render();
</script>

</body>
</html>
"""

html_content = html_template.replace("__PHOTOS_JSON_PLACEHOLDER__", photos_json)

os.makedirs('reports', exist_ok=True)
with open('reports/metadata_viewer.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print('Viewer created successfully: reports/metadata_viewer.html')
