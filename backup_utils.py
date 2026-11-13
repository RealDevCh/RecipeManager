import os
import io
import zipfile
import sqlite3
from database import DB_PATH, get_connection, migrate_todo_and_recipe_views

DATA_DIR = os.path.dirname(DB_PATH)


def get_system_stats() -> dict:
    """대시보드 요약 통계 산출"""
    with get_connection() as conn:
        todo_open = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료'").fetchone()[0]
        todo_urgent = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료' AND urgency = '긴급'").fetchone()[0]
        handlers = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'HANDLER'").fetchone()[0]
        visions = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'VISION'").fetchone()[0]
        deployments = conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0]
    return {
        "todo_open": int(todo_open),
        "todo_urgent": int(todo_urgent),
        "handlers": int(handlers),
        "visions": int(visions),
        "deployments": int(deployments),
    }


def create_system_backup() -> bytes:
    """data/ 디렉터리 전체(SQLite DB + 증빙 이미지 + Align 이미지)를 ZIP 바이트로 패키징"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DATA_DIR):
            for root, _, files in os.walk(DATA_DIR):
                for fname in files:
                    full_p = os.path.join(root, fname)
                    rel_p = os.path.relpath(full_p, start=DATA_DIR)
                    zf.write(full_p, os.path.join("data", rel_p))
    buf.seek(0)
    return buf.getvalue()


def restore_system_backup(zip_bytes: bytes) -> tuple[bool, str]:
    """업로드된 백업 ZIP 검증 후 data/ 디렉터리에 무손실 복원 및 스키마 마이그레이션"""
    buf = io.BytesIO(zip_bytes)
    try:
        with zipfile.ZipFile(buf, "r") as zf:
            namelist = zf.namelist()
            if not any("recipe_manager.db" in name for name in namelist):
                return False, "백업 파일 내에 'recipe_manager.db'가 없어 복원할 수 없습니다."

            os.makedirs(DATA_DIR, exist_ok=True)
            for item in zf.infolist():
                if item.is_dir():
                    continue
                clean_name = item.filename.replace("\\", "/")
                if clean_name.startswith("data/"):
                    clean_name = clean_name[5:]
                if ".." in clean_name:
                    continue
                target_path = os.path.join(DATA_DIR, clean_name)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as out_f:
                    out_f.write(zf.read(item.filename))

        with sqlite3.connect(DB_PATH) as check_conn:
            res = check_conn.execute("PRAGMA integrity_check;").fetchone()
            if not res or res[0] != "ok":
                return False, "복원된 데이터베이스 무결성 검사에 실패했습니다."

        migrate_todo_and_recipe_views()
        return True, "데이터베이스 및 첨부 이미지가 성공적으로 복원되었습니다."
    except Exception as e:
        return False, f"복원 중 오류 발생: {e}"
