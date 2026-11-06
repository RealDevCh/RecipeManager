# RecipeManager v1.4.1

반도체 검사·계측 업무를 위한 **Recipe / 업무 요청 / 횡전개 / 설비 폴더 Diff / Code 고속 검색 / 동일 조건 복수 Handler 관리 통합 시스템**입니다.

## 📌 v1.4.1 신규 확장 기능
1. **📌 Recipe CRUD 내 공정 조건(Product, Step, Module, Purpose) 및 Device Code 자동완성 통합**:
   - Handler Recipe 등록/수정 시 어떤 제품과 공정에 쓰이는지 직접 지정할 수 있도록 폼을 개편했습니다.
   - Device Code(예: AAA)를 선택하면 등록된 Product, Module, Purpose가 자동으로 채워집니다.
2. **💡 동일 공정 조건 내 복수 Handler Recipe (1:N) & 구분 Description 관리**:
   - 동일한 (Product + Step + Module + Purpose) 조건이라도 현장 상황(표준 양산용, 저조도 튜닝용, 특정 설비 전용)에 따라 Handler가 N개 존재할 수 있습니다.
   - 각 Handler별로 **"동일 조건 내 구분 설명 (Condition Description)"** 필드를 신설하여 검색 화면과 목록에서 그 차이와 적용 목적을 즉시 파악할 수 있도록 구현했습니다.
3. **⚡ Code + Step 고속 역추적 검색 (SC-03, MD-05)**:
   - 디바이스 코드와 Step만으로 현재 유효한 공정 조건과 등록된 복수 Handler Recipe 옵션들을 구분 설명 및 Align 썸네일과 함께 탐색합니다.
4. **전수 안전성 검증 완료**:
   - `sqlite3.Row` UI 유입 차단(원시 타입 직렬화 Sanitization), Null/None 사전 가드, 멀티라인 표준 문자열 적용.

## 🚀 빠른 시작 가이드
```bash
pip install -r requirements.txt
streamlit run app.py
```
