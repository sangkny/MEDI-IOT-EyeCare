#!/usr/bin/env python3
"""
파일명: scripts/inspect_korean_gl_crops.py
목적:   한국인 녹내장 전처리 크롭 결과 시각적 검증
        원본 합본 이미지 vs OD/OS 크롭 결과를 HTML로 나란히 비교
IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
import base64
import csv
import random
from pathlib import Path

DATASET_ROOT = Path('/dataset/korean_glaucoma_fundus')
INPUT_ROOT   = Path('/dataset/korean_fundus_input')
OUTPUT_HTML  = Path('/workspace/inspect_korean_gl_crops.html')
N_SAMPLES    = 10

def img_to_b64(path: Path) -> str:
    if not path.exists():
        return ''
    return base64.b64encode(path.read_bytes()).decode()

def make_html(samples: list, stats: dict) -> str:
    rows = []
    for s in samples:
        img_no = s['image_no']
        eye    = s['eye']
        grade  = s['grade']
        diag   = s['diagnosis']
        fname  = s['filename']
        mod    = s.get('modality', 'color')

        sub       = 'OD' if eye == 'R' else 'OS'
        eye_label = '우안(OD)' if eye == 'R' else '좌안(OS)'
        color     = 'blue' if eye == 'R' else 'green'

        crop_path = DATASET_ROOT / 'modified' / mod / sub / fname
        orig_path = INPUT_ROOT / 'glaucoma_modified' / f'{img_no}.jpg'

        crop_b64 = img_to_b64(crop_path)
        orig_b64 = img_to_b64(orig_path)

        crop_img = (f'<img src="data:image/jpeg;base64,{crop_b64}" '
                    f'style="width:280px;border:3px solid {color};border-radius:4px">'
                    if crop_b64 else '<div style="color:red;padding:20px">❌ 파일없음</div>')
        orig_img = (f'<img src="data:image/jpeg;base64,{orig_b64}" '
                    f'style="width:380px;border:1px solid #ccc;border-radius:4px">'
                    if orig_b64 else '<div style="color:red;padding:20px">❌ 원본없음</div>')

        status = '✅' if crop_b64 else '❌'
        rows.append(f'''
        <tr>
          <td style="padding:12px;font-size:13px;vertical-align:top;min-width:120px">
            <b style="font-size:15px">No.{img_no}</b><br><br>
            <span style="background:{"#e3f0ff" if eye=="R" else "#e3ffe3"};
                  padding:3px 8px;border-radius:10px;font-size:12px">
              {eye_label}
            </span><br><br>
            Grade <b>{grade}</b><br>
            <small style="color:#666">{diag}</small><br><br>
            {status} {'정상' if crop_b64 else '누락'}
          </td>
          <td style="padding:8px;vertical-align:top">
            <div style="font-size:11px;color:#888;margin-bottom:4px">
              ← 원본 합본 (1500×1159)
            </div>
            {orig_img}
          </td>
          <td style="padding:8px;vertical-align:top">
            <div style="font-size:11px;color:{color};margin-bottom:4px">
              ← 크롭 결과 {eye_label} (512×512, CLAHE)
            </div>
            {crop_img}
          </td>
        </tr>''')

    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>한국인 녹내장 크롭 검증</title>
  <style>
    body {{ font-family: "Malgun Gothic", sans-serif; margin: 24px; background:#fafafa; }}
    h2 {{ color: #1a1a2e; }}
    .warn {{ background:#fff3cd; padding:10px 16px; border-radius:6px;
             border-left:4px solid #ffc107; margin-bottom:16px; }}
    .stat {{ background:#e8f4fd; padding:10px 16px; border-radius:6px;
             margin-bottom:20px; font-size:13px; }}
    table {{ border-collapse: collapse; width:100%; background:white;
             box-shadow:0 1px 4px rgba(0,0,0,0.1); border-radius:8px;
             overflow:hidden; }}
    tr {{ border-bottom: 1px solid #eee; }}
    tr:hover {{ background:#f0f7ff; }}
    th {{ background:#2c3e50; color:white; padding:12px; text-align:left; }}
  </style>
</head>
<body>
  <h2>🔬 한국인 녹내장 전처리 크롭 검증</h2>
  <div class="warn">
    ⚠️ IRB 2019 승인 데이터 — 로컬 전용, 외부 반출 금지
  </div>
  <div class="stat">
    <b>전체 통계:</b>
    총 color 레코드 {stats["total"]}장 |
    OD {stats["od"]}장 | OS {stats["os"]}장 |
    파일 누락 {stats["missing"]}장 |
    Grade 분포: {stats["grades"]} |
    진단: {stats["diags"]}
  </div>
  <p style="color:#666;font-size:13px">
    검사 샘플 {len(samples)}장 |
    <span style="color:blue">■ 파란 테두리 = 우안(OD)</span> &nbsp;
    <span style="color:green">■ 초록 테두리 = 좌안(OS)</span>
  </p>
  <table>
    <tr>
      <th>정보</th>
      <th>원본 합본</th>
      <th>크롭 결과</th>
    </tr>
    {''.join(rows)}
  </table>
  <p style="color:#aaa;font-size:11px;margin-top:20px">
    생성: inspect_korean_gl_crops.py | 국내 임상기관 IRB 2019
  </p>
</body>
</html>'''

def main():
    csv_path = DATASET_ROOT / 'labels_modified.csv'
    if not csv_path.exists():
        print(f'오류: {csv_path} 없음')
        return

    records = list(csv.DictReader(open(csv_path, encoding='utf-8')))
    color_r = [r for r in records if r.get('modality') == 'color']
    print(f'전체 color 레코드: {len(color_r)}장')

    od = [r for r in color_r if r['eye'] == 'R']
    os_ = [r for r in color_r if r['eye'] == 'L']

    # 파일 존재 확인 (전체)
    missing = 0
    for r in color_r:
        sub  = 'OD' if r['eye'] == 'R' else 'OS'
        path = DATASET_ROOT / 'modified' / 'color' / sub / r['filename']
        if not path.exists():
            missing += 1
    print(f'파일 누락: {missing}/{len(color_r)}장')

    # Grade/진단 분포
    grades = {}
    diags  = {}
    for r in color_r:
        g = r.get('grade', '?')
        d = r.get('diagnosis', '?')
        grades[g] = grades.get(g, 0) + 1
        diags[d]  = diags.get(d, 0) + 1
    print('Grade 분포:', grades)
    print('진단 분포:', diags)

    # 샘플 선택 (OD/OS 균형)
    n_each  = N_SAMPLES // 2
    samples = (random.sample(od, min(n_each, len(od))) +
               random.sample(os_, min(n_each, len(os_))))
    random.shuffle(samples)

    stats = {
        'total': len(color_r),
        'od': len(od), 'os': len(os_),
        'missing': missing,
        'grades': str(grades),
        'diags': str(diags),
    }

    html = make_html(samples, stats)
    OUTPUT_HTML.write_text(html, encoding='utf-8')
    print(f'\nHTML 리포트: {OUTPUT_HTML}')

if __name__ == '__main__':
    main()