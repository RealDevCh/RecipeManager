# RecipeManager v1.6.0 (통합 구조 · GitHub/모바일 배포 최적화)

`pages/` 하위 폴더 없이 **루트 디렉터리 파일 3개(`app.py`, `database.py`, `requirements.txt`)만으로 GitHub 및 Streamlit Cloud에 즉시 배포할 수 있는 통합 구조 패키지**입니다.

## 🚀 GitHub 웹/모바일 업로드 방법 (단 3개 파일)
1. GitHub 저장소(`RealDevCh/RecipeManager`)에서 **`Add file` → `Upload files`** (또는 모바일에서 파일 생성)를 선택합니다.
2. 아래 **3개 파일만** 루트 경로에 올리면 모든 기능과 샘플 데이터(`data/`, `sample_recipe_folder/`)가 실행 시 자동 생성됩니다.
   - `app.py`
   - `database.py`
   - `requirements.txt`

## 💻 로컬 PC 실행 방법
- **Windows**: `run.bat` 더블 클릭
- **터미널**: `pip install -r requirements.txt && streamlit run app.py`
