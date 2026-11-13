# RecipeManager v1.6.0 (완성본)

반도체 검사·계측 업무를 위한 **할 일 우선순위 관리 · Handler/Vision 레시피 확인 · 설비 횡전개 · 정밀 Diff · 시스템 백업 통합 관리 시스템**입니다.

## 🚀 빠른 실행 방법
### Windows
1. 압축 해제 후 폴더 안의 **`run.bat`** 파일을 더블 클릭합니다.
2. 패키지 자동 설치 후 브라우저에서 `http://localhost:8501`이 열립니다.

### Mac / Linux / VS Code 터미널
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📌 v1.6.0 핵심 구성
- **`✅ 할 일`**: 키워드 목록 + 우측 세부 정보(Split-View), `▲`/`▼` 버튼 및 마우스 드래그 우선순위 조절, 원클릭 완료, 완료 표시 토글, 긴급도별 색상 강조, `Ctrl+V` 이미지 증빙
- **`🧩 레시피 확인`**: Handler Recipe 메인 노출 → 클릭 시 연결된 Vision Recipe 체인 + 주요 파라미터(XML 자동 추출) + 최근 변경점 + Align 이미지 확인
- **`⚙️ 레시피 등록 및 매핑`**: 상단 팝오버 신규 등록, 1:N 공정 조건 및 Device Code 자동완성, Handler-Vision N:M 연결, 공유 Vision 영향도 역추적
- **`🚀 설비 횡전개 및 Diff`**: 설비별 동기화 현황, 다중 설비 횡전개 트래커, 폴더 트리 SHA256 Diff, XML Diff, 픽셀 오차 마스크 Diff
- **`🛠️ 기준정보 및 백업`**: 공통 코드 CRUD, Device Code 매핑 이력, 감사 로그, 원클릭 백업/복원(구버전 DB 자동 마이그레이션 포함)
