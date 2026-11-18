import sqlite3
import os
import io
import zipfile
import hashlib
import difflib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date
from PIL import Image, ImageChops

KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "recipe_manager.db")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
TEXT_EXTS = {".xml", ".txt", ".ini", ".cfg", ".json", ".csv", ".dat", ".log", ".rcp"}


def get_kst_now() -> datetime:
    return datetime.now(KST)


def get_kst_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return get_kst_now().strftime(fmt)


def get_kst_today() -> date:
    return get_kst_now().date()


def get_connection() -> sqlite3.Connection:
    """SQLite 커넥션 획득 (Row Factory 및 FK 활성화)"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """데이터베이스 초기화, 스키마 생성, 무손실 마이그레이션 및 초기 시드 데이터 세팅"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                UNIQUE(category, name)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_type TEXT NOT NULL CHECK(recipe_type IN ('HANDLER', 'VISION')),
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT,
                xml_content TEXT,
                created_at TEXT,
                UNIQUE(recipe_type, name, version)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                tag TEXT DEFAULT 'ALIGN',
                created_at TEXT,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS handler_vision_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                handler_id INTEGER NOT NULL,
                vision_id INTEGER NOT NULL,
                seq_order INTEGER DEFAULT 1,
                created_at TEXT,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (vision_id) REFERENCES recipes(id) ON DELETE CASCADE,
                UNIQUE(handler_id, vision_id)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                step TEXT NOT NULL,
                module TEXT NOT NULL,
                purpose TEXT NOT NULL,
                handler_id INTEGER NOT NULL,
                condition_desc TEXT DEFAULT '',
                created_at TEXT,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                UNIQUE(product, step, module, purpose, handler_id)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                product TEXT NOT NULL,
                module TEXT NOT NULL,
                purpose TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                reason TEXT,
                certainty TEXT DEFAULT '확정' CHECK(certainty IN ('확정', '추정', '검토필요')),
                created_by TEXT,
                created_at TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                req_type TEXT NOT NULL DEFAULT '할 일',
                title TEXT NOT NULL,
                content TEXT,
                product TEXT,
                step TEXT,
                module TEXT,
                purpose TEXT,
                equipment TEXT,
                department TEXT,
                requester TEXT,
                assignee TEXT DEFAULT '유철형',
                lot_id TEXT,
                recipe_id TEXT,
                urgency TEXT DEFAULT '보통',
                priority_order INTEGER DEFAULT 0,
                task_level TEXT DEFAULT '실행(소규모)',
                parent_id INTEGER DEFAULT NULL,
                status TEXT DEFAULT '접수' CHECK(status IN ('접수', '진행중', '평가/검증', '완료', '보류')),
                due_date TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                target_type TEXT NOT NULL,
                target_name TEXT NOT NULL,
                change_type TEXT NOT NULL,
                before_val TEXT,
                after_val TEXT,
                change_reason TEXT,
                operator TEXT,
                evaluation_result TEXT,
                created_at TEXT,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE SET NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                handler_id INTEGER NOT NULL,
                request_id INTEGER,
                reason TEXT,
                created_by TEXT,
                status TEXT DEFAULT '진행중' CHECK(status IN ('대기', '진행중', '완료', '보류')),
                created_at TEXT,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE SET NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id INTEGER NOT NULL,
                equipment TEXT NOT NULL,
                status TEXT DEFAULT '대기' CHECK(status IN ('대기', '진행중', '검증완료', '실패', '보류')),
                operator TEXT,
                applied_at TEXT,
                verifier TEXT,
                verified_at TEXT,
                hold_reason TEXT,
                memo TEXT,
                FOREIGN KEY (deployment_id) REFERENCES deployments(id) ON DELETE CASCADE,
                UNIQUE(deployment_id, equipment)
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment_recipe_status (
                equipment TEXT PRIMARY KEY,
                handler_id INTEGER,
                target_version TEXT,
                verified_version TEXT,
                sync_status TEXT DEFAULT '미확인' CHECK(sync_status IN ('일치', '불일치', '미확인')),
                last_verified_at TEXT,
                verifier TEXT,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE SET NULL
            );
        """)

        conn.commit()

    migrate_schema()
    _seed_initial_data()


def migrate_schema():
    """구버전 DB 백업 복원 시에도 무손실로 최신 컬럼을 자동 추가"""
    wr_new_cols = {
        "urgency": "TEXT DEFAULT '보통'",
        "priority_order": "INTEGER DEFAULT 0",
        "department": "TEXT DEFAULT ''",
        "requester": "TEXT DEFAULT ''",
        "assignee": "TEXT DEFAULT '유철형'",
        "lot_id": "TEXT DEFAULT ''",
        "task_level": "TEXT DEFAULT '실행(소규모)'",
        "parent_id": "INTEGER DEFAULT NULL",
    }
    with get_connection() as conn:
        wr_cols = [row["name"] for row in conn.execute("PRAGMA table_info(work_requests)").fetchall()]
        for col_name, col_def in wr_new_cols.items():
            if col_name not in wr_cols:
                conn.execute(f"ALTER TABLE work_requests ADD COLUMN {col_name} {col_def}")
        conn.execute("UPDATE work_requests SET priority_order = id WHERE priority_order IS NULL OR priority_order = 0")
        conn.execute("UPDATE work_requests SET task_level = '실행(소규모)' WHERE task_level IS NULL OR TRIM(task_level) = ''")

        rc_cols = [row["name"] for row in conn.execute("PRAGMA table_info(recipe_conditions)").fetchall()]
        if "condition_desc" not in rc_cols:
            conn.execute("ALTER TABLE recipe_conditions ADD COLUMN condition_desc TEXT DEFAULT ''")
        conn.commit()


def _seed_initial_data():
    """초기 구동 시 즉시 체험 가능한 기본 기준정보 및 샘플 데이터 생성"""
    now_str = get_kst_str()
    today_dt = get_kst_today()
    today_str = today_dt.strftime("%Y-%m-%d")
    plus2_str = (today_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    plus5_str = (today_dt + timedelta(days=5)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        cur = conn.cursor()
        if cur.execute("SELECT COUNT(*) FROM master_data").fetchone()[0] == 0:
            default_items = [
                ("Product", "Prod_Alpha"), ("Product", "Prod_Beta"), ("Product", "Prod_Gamma"),
                ("Step", "Step01_Align"), ("Step", "Step02_Inspect"), ("Step", "Step03_Review"),
                ("Module", "Mod_Front"), ("Module", "Mod_Rear"), ("Module", "Mod_Side"),
                ("Purpose", "Mass_Production"), ("Purpose", "Evaluation"), ("Purpose", "Setup"),
                ("Department", "제조기술팀"), ("Department", "공정설계팀"), ("Department", "품질보증팀"), ("Department", "설비기술팀"),
                ("Equipment", "EQP-01"), ("Equipment", "EQP-02"), ("Equipment", "EQP-03"), ("Equipment", "EQP-04"),
                ("DeviceCode", "AAA"), ("DeviceCode", "BBB"), ("DeviceCode", "B01"), ("DeviceCode", "C10"),
            ]
            for cat, val in default_items:
                cur.execute("INSERT OR IGNORE INTO master_data (category, name, created_at) VALUES (?, ?, ?)", (cat, val, now_str))

            cur.execute("""
                INSERT OR IGNORE INTO code_mappings (code, product, module, purpose, valid_from, reason, certainty, created_by, created_at)
                VALUES ('AAA', 'Prod_Alpha', 'Mod_Front', 'Mass_Production', ?, '양산 초기 기준 매핑 승인', '확정', '관리자', ?)
            """, (now_str, now_str))
            cur.execute("""
                INSERT OR IGNORE INTO code_mappings (code, product, module, purpose, valid_from, reason, certainty, created_by, created_at)
                VALUES ('BBB', 'Prod_Beta', 'Mod_Rear', 'Evaluation', ?, '신규 디바이스 평가 셋업', '확정', '엔지니어', ?)
            """, (now_str, now_str))

        if cur.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                VALUES ('HANDLER', 'HDL_ALPHA_MAIN', 'v2.1', 'Prod_Alpha 양산 메인 핸들러', ?, ?)
            """, ("""<HandlerRecipe>
  <SequenceCount>2</SequenceCount>
  <RetryLimit>3</RetryLimit>
  <TimeoutMs>5000</TimeoutMs>
</HandlerRecipe>""", now_str))
            h1_id = cur.lastrowid

            cur.execute("""
                INSERT INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                VALUES ('HANDLER', 'HDL_BETA_EVAL', 'v1.0', 'Prod_Beta 평가용 분기 핸들러', ?, ?)
            """, ("""<HandlerRecipe>
  <SequenceCount>1</SequenceCount>
  <RetryLimit>2</RetryLimit>
  <TimeoutMs>4000</TimeoutMs>
</HandlerRecipe>""", now_str))
            h2_id = cur.lastrowid

            cur.execute("""
                INSERT INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                VALUES ('VISION', 'VIS_ALIGN_MARK_A', 'v1.4', '1차 Fiducial Align 비전', ?, ?)
            """, ("""<VisionRecipe>
  <ExposureUs>2500</ExposureUs>
  <Gain>1.35</Gain>
  <MatchThreshold>82</MatchThreshold>
  <LightCh1>180</LightCh1>
</VisionRecipe>""", now_str))
            v1_id = cur.lastrowid

            cur.execute("""
                INSERT INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                VALUES ('VISION', 'VIS_INSPECT_SURFACE', 'v3.0', '2차 표면 결함 검사 비전', ?, ?)
            """, ("""<VisionRecipe>
  <ExposureUs>3200</ExposureUs>
  <Gain>1.10</Gain>
  <DefectSensitivity>65</DefectSensitivity>
  <MinBlobArea>12</MinBlobArea>
</VisionRecipe>""", now_str))
            v2_id = cur.lastrowid

            cur.execute("""
                INSERT INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                VALUES ('VISION', 'VIS_BETA_EDGE', 'v1.0', 'Beta 엣지 측정 비전', ?, ?)
            """, ("""<VisionRecipe>
  <ExposureUs>2800</ExposureUs>
  <EdgeContrast>45</EdgeContrast>
  <FilterSigma>1.5</FilterSigma>
</VisionRecipe>""", now_str))
            v3_id = cur.lastrowid

            cur.execute("INSERT INTO handler_vision_map (handler_id, vision_id, seq_order, created_at) VALUES (?, ?, 1, ?)", (h1_id, v1_id, now_str))
            cur.execute("INSERT INTO handler_vision_map (handler_id, vision_id, seq_order, created_at) VALUES (?, ?, 2, ?)", (h1_id, v2_id, now_str))
            cur.execute("INSERT INTO handler_vision_map (handler_id, vision_id, seq_order, created_at) VALUES (?, ?, 1, ?)", (h2_id, v3_id, now_str))

            cur.execute("""
                INSERT INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc, created_at)
                VALUES ('Prod_Alpha', 'Step01_Align', 'Mod_Front', 'Mass_Production', ?, '표준 양산 조건', ?)
            """, (h1_id, now_str))
            cur.execute("""
                INSERT INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc, created_at)
                VALUES ('Prod_Beta', 'Step02_Inspect', 'Mod_Rear', 'Evaluation', ?, '신규 조도 평가 조건', ?)
            """, (h2_id, now_str))

        if cur.execute("SELECT COUNT(*) FROM work_requests").fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO work_requests (
                    req_type, title, content, product, step, equipment,
                    department, requester, assignee, lot_id,
                    urgency, priority_order, task_level, parent_id, status, due_date, created_at, updated_at
                )
                VALUES ('신규 셋업', 'Prod_Alpha 양산 안정화 및 전 설비 횡전개', 'Step01~02 조도/과검 개선 후 EQP-01~04 일괄 전개 마일스톤',
                        'Prod_Alpha', 'Step01_Align', 'EQP-01', '공정설계팀', '김민수', '유철형', 'LOT-26A01',
                        '높음', 1, '납기(큰일)', NULL, '진행중', ?, ?, ?)
            """, (plus5_str, now_str, now_str))
            milestone_id = cur.lastrowid

            sample_todos = [
                ("Align Fail 조치", "EQP-01 Step01 Align 조도 보정", "조도 저하로 인한 마크 인식률 하락 보정 (LightCh1 160 -> 180)",
                 "Prod_Alpha", "Step01_Align", "EQP-01", "제조기술팀", "박지훈", "유철형", "LOT-26A01",
                 "긴급", 2, "실행(소규모)", milestone_id, "진행중", today_str),
                ("파라미터 튜닝", "VIS_INSPECT_SURFACE 민감도 재검증", "과검(False Call) 저감을 위한 MinBlobArea 10 -> 12 상향 평가",
                 "Prod_Alpha", "Step02_Inspect", "EQP-02", "품질보증팀", "이서연", "유철형", "LOT-26A02",
                 "높음", 3, "실행(소규모)", milestone_id, "평가/검증", today_str),
                ("횡전개", "HDL_ALPHA_MAIN v2.1 전 설비 횡전개", "EQP-01 검증 완료 후 EQP-02~04 일괄 적용 및 Diff 대조",
                 "Prod_Alpha", "Step01_Align", "EQP-03", "설비기술팀", "정현우", "유철형", "LOT-26A03",
                 "보통", 4, "실행(소규모)", milestone_id, "접수", plus2_str),
                ("신규 셋업", "Prod_Beta 신규 평가 레시피 백업", "평가 완료 후 마스터 DB 스냅샷 저장",
                 "Prod_Beta", "Step02_Inspect", "EQP-04", "공정설계팀", "김민수", "유철형", "LOT-26B01",
                 "낮음", 5, "실행(소규모)", None, "접수", plus2_str),
            ]
            for r_type, title, content, prod, step, eqp, dept, reqr, asg, lot, urg, p_ord, t_lvl, p_id, stat, d_date in sample_todos:
                cur.execute("""
                    INSERT INTO work_requests (
                        req_type, title, content, product, step, equipment,
                        department, requester, assignee, lot_id,
                        urgency, priority_order, task_level, parent_id, status, due_date, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (r_type, title, content, prod, step, eqp, dept, reqr, asg, lot, urg, p_ord, t_lvl, p_id, stat, d_date, now_str, now_str))

            cur.execute("""
                INSERT INTO recipe_changes (request_id, target_type, target_name, change_type, before_val, after_val, change_reason, operator, evaluation_result, created_at)
                VALUES (?, 'Vision', 'VIS_ALIGN_MARK_A', '파라미터 변경', 'LightCh1: 160 / Gain: 1.20', 'LightCh1: 180 / Gain: 1.35', '챔버 조명 노후화 보상 및 인식률 개선', '유철형', '양호(적용가능)', ?)
            """, (milestone_id, now_str))
            cur.execute("""
                INSERT INTO recipe_changes (request_id, target_type, target_name, change_type, before_val, after_val, change_reason, operator, evaluation_result, created_at)
                VALUES (?, 'Vision', 'VIS_INSPECT_SURFACE', '파라미터 변경', 'MinBlobArea: 10', 'MinBlobArea: 12', '미세 노이즈 과검 필터링', '유철형', '평가중', ?)
            """, (milestone_id, now_str))
            cur.execute("""
                INSERT INTO recipe_changes (request_id, target_type, target_name, change_type, before_val, after_val, change_reason, operator, evaluation_result, created_at)
                VALUES (?, 'Vision', 'VIS_BETA_EDGE', '신규 분기', '-', 'EdgeContrast: 45 / FilterSigma: 1.5', 'Prod_Beta 신규 평가 셋업', '유철형', '평가중', ?)
            """, (milestone_id, now_str))

        conn.commit()


def ensure_sample_recipe_folder() -> tuple[str, str]:
    """폴더 Diff 테스트용 샘플 디렉터리가 없으면 자동 생성 후 (source_dir, target_dir) 반환"""
    src_dir = os.path.join(BASE_DIR, "sample_recipe_folder", "source_pkg")
    tgt_dir = os.path.join(BASE_DIR, "sample_recipe_folder", "target_eqp01")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(tgt_dir, exist_ok=True)

    s_main = os.path.join(src_dir, "Main_Recipe.xml")
    if not os.path.exists(s_main):
        with open(s_main, "w", encoding="utf-8") as f:
            f.write("<Recipe>\n  <Product>Prod_Alpha</Product>\n  <Align>\n    <Threshold>120</Threshold>\n    <Timeout>5000</Timeout>\n  </Align>\n</Recipe>")

    s_vis = os.path.join(src_dir, "Vision_Cam1.xml")
    if not os.path.exists(s_vis):
        with open(s_vis, "w", encoding="utf-8") as f:
            f.write("<Vision>\n  <ExposureUs>2500</ExposureUs>\n  <Gain>1.20</Gain>\n</Vision>")

    t_main = os.path.join(tgt_dir, "Main_Recipe.xml")
    if not os.path.exists(t_main):
        with open(t_main, "w", encoding="utf-8") as f:
            f.write("<Recipe>\n  <Product>Prod_Alpha</Product>\n  <Align>\n    <Threshold>145</Threshold>\n    <Timeout>5000</Timeout>\n    <RetryCount>3</RetryCount>\n  </Align>\n</Recipe>")

    t_vis = os.path.join(tgt_dir, "Vision_Cam1.xml")
    if not os.path.exists(t_vis):
        with open(t_vis, "w", encoding="utf-8") as f:
            f.write("<Vision>\n  <ExposureUs>2500</ExposureUs>\n  <Gain>1.20</Gain>\n</Vision>")

    return src_dir, tgt_dir


# ==============================================================================
# 자동완성 & 단일 항목 우선순위 이동 & 전방위 통합 검색
# ==============================================================================

def get_autocomplete_options(column_name: str, master_category: str = None, defaults: list[str] = None) -> list[str]:
    """기준정보(master_data) + 과거 work_requests 입력 이력을 중복 제거해 자동완성 목록 생성"""
    options = []
    if defaults:
        options.extend(defaults)
    if master_category:
        try:
            options.extend(get_master_names(master_category))
        except Exception:
            pass

    allowed_cols = {
        "title", "department", "requester", "lot_id",
        "product", "step", "module", "purpose", "equipment", "assignee", "req_type", "urgency"
    }
    if column_name in allowed_cols:
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT {column_name} FROM work_requests "
                f"WHERE {column_name} IS NOT NULL AND TRIM({column_name}) != '' "
                f"ORDER BY id DESC LIMIT 150"
            ).fetchall()
            options.extend([str(r[0]).strip() for r in rows if r[0]])

    seen = set()
    unique_opts = []
    for item in options:
        clean = str(item).strip()
        if clean and clean not in seen:
            seen.add(clean)
            unique_opts.append(clean)
    return unique_opts


def move_selected_todo(visible_ordered_ids: list[int], target_id: int | None, direction: str) -> bool:
    """선택된 1개 할 일 항목을 위(up) / 아래(down) / 최상단(top)으로 이동"""
    if target_id is None or int(target_id) not in visible_ordered_ids or len(visible_ordered_ids) < 2:
        return False

    tid = int(target_id)
    ids = [int(x) for x in visible_ordered_ids]
    idx = ids.index(tid)
    moved = False

    if direction == "up" and idx > 0:
        ids[idx - 1], ids[idx] = ids[idx], ids[idx - 1]
        moved = True
    elif direction == "down" and idx < len(ids) - 1:
        ids[idx + 1], ids[idx] = ids[idx], ids[idx + 1]
        moved = True
    elif direction == "top" and idx > 0:
        ids.pop(idx)
        ids.insert(0, tid)
        moved = True

    if not moved:
        return False

    with get_connection() as conn:
        placeholders = ",".join(["?"] * len(ids))
        rows = conn.execute(
            f"SELECT id, priority_order FROM work_requests WHERE id IN ({placeholders})",
            ids
        ).fetchall()
        sorted_slots = sorted([r["priority_order"] for r in rows])
        if len(set(sorted_slots)) < len(sorted_slots):
            base_slot = min(sorted_slots) if sorted_slots else 1
            sorted_slots = [base_slot + i for i in range(len(ids))]

        now_str = get_kst_str()
        for slot_val, item_id in zip(sorted_slots, ids):
            conn.execute(
                "UPDATE work_requests SET priority_order = ?, updated_at = ? WHERE id = ?",
                (slot_val, now_str, item_id)
            )
        conn.commit()
    return True


def get_todos_enriched(include_completed: bool = True) -> list[dict]:
    """할 일의 모든 컬럼 + 비노출 연관 정보(상위/하위업무, 첨부파일명, 레시피 변경이력, 횡전개)를 결합해 반환"""
    query = "SELECT * FROM work_requests"
    if not include_completed:
        query += " WHERE status != '완료'"
    query += " ORDER BY priority_order ASC, id DESC"

    with get_connection() as conn:
        todos = [dict(r) for r in conn.execute(query).fetchall()]
        all_rows = [dict(r) for r in conn.execute("SELECT id, title, lot_id, parent_id FROM work_requests").fetchall()]
        atts = [dict(r) for r in conn.execute("SELECT request_id, file_name FROM attachments").fetchall()]
        chgs = [dict(r) for r in conn.execute(
            "SELECT request_id, target_name, before_val, after_val, change_reason FROM recipe_changes WHERE request_id IS NOT NULL"
        ).fetchall()]
        deps = [dict(r) for r in conn.execute(
            "SELECT request_id, title FROM deployments WHERE request_id IS NOT NULL"
        ).fetchall()]

    id_to_title = {r["id"]: r["title"] for r in all_rows}
    parent_to_children_text: dict[int, list[str]] = {}
    for r in all_rows:
        pid = r.get("parent_id")
        if pid:
            parent_to_children_text.setdefault(pid, []).append(f"{r.get('title', '')} {r.get('lot_id', '')}")

    req_to_atts: dict[int, list[str]] = {}
    for a in atts:
        req_to_atts.setdefault(a["request_id"], []).append(a.get("file_name") or "")

    req_to_chgs: dict[int, list[str]] = {}
    for c in chgs:
        req_to_chgs.setdefault(c["request_id"], []).append(
            f"{c.get('target_name', '')} {c.get('before_val', '')} {c.get('after_val', '')} {c.get('change_reason', '')}"
        )

    req_to_deps: dict[int, list[str]] = {}
    for d in deps:
        req_to_deps.setdefault(d["request_id"], []).append(d.get("title") or "")

    for t in todos:
        tid = t["id"]
        pid = t.get("parent_id")
        t["parent_title"] = id_to_title.get(pid, "") if pid else ""
        t["child_summary"] = " ".join(parent_to_children_text.get(tid, []))
        t["attachment_names"] = " ".join(req_to_atts.get(tid, []))
        t["change_summary"] = " ".join(req_to_chgs.get(tid, []))
        t["deploy_summary"] = " ".join(req_to_deps.get(tid, []))

        t["_search_fields"] = {
            "ID": f"#{tid} {tid}",
            "할 일 키워드": t.get("title") or "",
            "세부 내용": t.get("content") or "",
            "Lot ID": t.get("lot_id") or "",
            "의뢰 부서": t.get("department") or "",
            "의뢰자": t.get("requester") or "",
            "담당자": t.get("assignee") or "",
            "Product": t.get("product") or "",
            "Step": t.get("step") or "",
            "Module": t.get("module") or "",
            "Purpose": t.get("purpose") or "",
            "설비(Equipment)": t.get("equipment") or "",
            "목표 기한": t.get("due_date") or "",
            "상태": t.get("status") or "",
            "긴급도": t.get("urgency") or "",
            "업무 구분": t.get("task_level") or "",
            "요청 유형": t.get("req_type") or "",
            "등록일시": t.get("created_at") or "",
            "상위 업무": t["parent_title"],
            "하위 실행 항목": t["child_summary"],
            "첨부 이미지": t["attachment_names"],
            "연관 레시피 변경": t["change_summary"],
            "연관 횡전개": t["deploy_summary"],
        }
        t["_search_blob"] = " ".join(v for v in t["_search_fields"].values() if v).lower()

    return todos


def filter_todos_by_query(todos: list[dict], query: str) -> list[dict]:
    """공백으로 구분된 다중 키워드(AND)로 할 일의 모든 컬럼·연관 데이터에서 검색하고 매칭 사유를 기록"""
    clean_q = (query or "").strip().lower()
    if not clean_q:
        for t in todos:
            t["_match_reasons"] = []
        return todos

    tokens = [tok for tok in clean_q.split() if tok]
    direct_matched = []
    related_matched = []

    for t in todos:
        blob = t.get("_search_blob", "")
        if all(tok in blob for tok in tokens):
            reasons = []
            s_fields = t.get("_search_fields", {})
            is_only_child_match = True
            for fname, fval in s_fields.items():
                if not fval:
                    continue
                fval_low = fval.lower()
                if any(tok in fval_low for tok in tokens):
                    if fname != "하위 실행 항목":
                        is_only_child_match = False
                    if fname != "할 일 키워드":
                        short_val = fval.strip()
                        if len(short_val) > 26:
                            short_val = short_val[:26] + "…"
                        reasons.append(f"{fname}: {short_val}")
            t["_match_reasons"] = reasons[:3]
            if is_only_child_match:
                related_matched.append(t)
            else:
                direct_matched.append(t)

    return direct_matched + related_matched


# ==============================================================================
# 할 일 CRUD & 다중 증빙 이미지 저장
# ==============================================================================

def get_open_milestones() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, due_date, status, department, requester, assignee, lot_id
            FROM work_requests
            WHERE task_level = '납기(큰일)'
            ORDER BY CASE WHEN status = '완료' THEN 1 ELSE 0 END ASC, priority_order ASC, id DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_todo_by_id(todo_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM work_requests WHERE id = ?", (int(todo_id),)).fetchone()
        return dict(row) if row else None


def create_todo(
    title: str,
    content: str = "",
    urgency: str = "보통",
    req_type: str = "할 일",
    product: str = "",
    step: str = "",
    equipment: str = "",
    department: str = "",
    requester: str = "",
    assignee: str = "유철형",
    lot_id: str = "",
    due_date: str = "",
    task_level: str = "실행(소규모)",
    parent_id: int | None = None
) -> int:
    now_str = get_kst_str()
    clean_assignee = (assignee or "").strip() or "유철형"
    with get_connection() as conn:
        cur = conn.cursor()
        min_row = cur.execute("SELECT MIN(priority_order) as min_ord FROM work_requests WHERE status != '완료'").fetchone()
        next_ord = (min_row["min_ord"] - 1) if (min_row and min_row["min_ord"] is not None and min_row["min_ord"] > 1) else 0

        cur.execute("""
            INSERT INTO work_requests (
                req_type, title, content, product, step, equipment,
                department, requester, assignee, lot_id,
                urgency, priority_order, task_level, parent_id,
                status, due_date, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '접수', ?, ?, ?)
        """, (
            req_type, title.strip(), content, product, step, equipment,
            department, requester, clean_assignee, lot_id,
            urgency, next_ord, task_level, parent_id,
            due_date, now_str, now_str
        ))
        new_id = cur.lastrowid
        if next_ord == 0:
            cur.execute("UPDATE work_requests SET priority_order = ? WHERE id = ?", (new_id, new_id))
        conn.commit()
        return int(new_id)


def update_todo_detail(
    todo_id: int,
    title: str,
    urgency: str,
    status: str,
    content: str,
    product: str = "",
    step: str = "",
    equipment: str = "",
    department: str = "",
    requester: str = "",
    assignee: str = "유철형",
    lot_id: str = "",
    due_date: str = "",
    task_level: str = "실행(소규모)",
    parent_id: int | None = None
):
    clean_assignee = (assignee or "").strip() or "유철형"
    with get_connection() as conn:
        conn.execute("""
            UPDATE work_requests
            SET title = ?, urgency = ?, status = ?, content = ?,
                product = ?, step = ?, equipment = ?,
                department = ?, requester = ?, assignee = ?, lot_id = ?,
                due_date = ?, task_level = ?, parent_id = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            title.strip(), urgency, status, content,
            product, step, equipment,
            department, requester, clean_assignee, lot_id,
            due_date, task_level, parent_id,
            get_kst_str(), int(todo_id)
        ))
        conn.commit()


def save_todo_attachments(request_id: int, uploaded_files: list = None, pasted_images: list = None):
    """N개의 업로드 파일과 클립보드 이미지를 일괄 저장"""
    att_dir = os.path.join(DATA_DIR, "attachments")
    os.makedirs(att_dir, exist_ok=True)
    now_ts = get_kst_str("%Y%m%d_%H%M%S")
    now_str = get_kst_str()

    with get_connection() as conn:
        for idx, up_f in enumerate(uploaded_files or []):
            ext = os.path.splitext(up_f.name)[1] or ".png"
            fname = f"todo_{request_id}_{now_ts}_f{idx}{ext}"
            fpath = os.path.join(att_dir, fname)
            with open(fpath, "wb") as out_f:
                out_f.write(up_f.getbuffer())
            conn.execute(
                "INSERT INTO attachments (request_id, file_name, file_path, created_at) VALUES (?, ?, ?, ?)",
                (int(request_id), fname, fpath, now_str)
            )

        for idx, p_img in enumerate(pasted_images or []):
            fname = f"todo_{request_id}_{now_ts}_p{idx}.png"
            fpath = os.path.join(att_dir, fname)
            p_img.save(fpath)
            conn.execute(
                "INSERT INTO attachments (request_id, file_name, file_path, created_at) VALUES (?, ?, ?, ?)",
                (int(request_id), fname, fpath, now_str)
            )
        conn.commit()


def get_todo_attachments(request_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM attachments WHERE request_id = ? ORDER BY id DESC",
            (int(request_id),)
        ).fetchall()
        return [dict(r) for r in rows]


def toggle_todo_complete(todo_id: int, current_status: str):
    next_status = "진행중" if current_status == "완료" else "완료"
    with get_connection() as conn:
        conn.execute(
            "UPDATE work_requests SET status = ?, updated_at = ? WHERE id = ?",
            (next_status, get_kst_str(), int(todo_id))
        )
        conn.commit()


def delete_work_request(req_id: int):
    with get_connection() as conn:
        atts = conn.execute("SELECT file_path FROM attachments WHERE request_id = ?", (int(req_id),)).fetchall()
        for a in atts:
            fp = a["file_path"]
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        conn.execute("UPDATE work_requests SET parent_id = NULL WHERE parent_id = ?", (int(req_id),))
        conn.execute("DELETE FROM work_requests WHERE id = ?", (int(req_id),))
        conn.commit()


def delete_attachment(att_id: int):
    with get_connection() as conn:
        att = conn.execute("SELECT file_path FROM attachments WHERE id = ?", (int(att_id),)).fetchone()
        if att and att["file_path"] and os.path.exists(att["file_path"]):
            try:
                os.remove(att["file_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM attachments WHERE id = ?", (int(att_id),))
        conn.commit()


# ==============================================================================
# XML 파싱 & Handler-Vision 상세 조회
# ==============================================================================

def parse_xml_key_params(xml_str: str) -> list[dict]:
    if not xml_str or not xml_str.strip():
        return []
    try:
        root = ET.fromstring(xml_str.strip())
        params = []
        for elem in root.iter():
            if len(elem) == 0 and elem.text and elem.text.strip():
                params.append({"파라미터": elem.tag, "설정값": elem.text.strip()})
        return params
    except ET.ParseError:
        fallback = []
        for line in xml_str.splitlines():
            clean = line.strip()
            if not clean:
                continue
            if "=" in clean:
                k, v = clean.split("=", 1)
                fallback.append({"파라미터": k.strip(), "설정값": v.strip()})
            else:
                fallback.append({"파라미터": "RAW", "설정값": clean})
        return fallback


def get_handler_linked_visions_detail(handler_id: int) -> list[dict]:
    with get_connection() as conn:
        visions = conn.execute("""
            SELECT v.id, v.name, v.version, v.description, v.xml_content, m.seq_order
            FROM handler_vision_map m
            JOIN recipes v ON m.vision_id = v.id
            WHERE m.handler_id = ?
            ORDER BY m.seq_order ASC, v.id ASC
        """, (int(handler_id),)).fetchall()

        results = []
        for v in visions:
            v_dict = dict(v)
            v_dict["key_params"] = parse_xml_key_params(v_dict.get("xml_content", ""))
            changes = conn.execute("""
                SELECT id, change_type, before_val, after_val, change_reason, operator, evaluation_result, created_at
                FROM recipe_changes
                WHERE target_name = ? AND LOWER(target_type) = 'vision'
                ORDER BY id DESC LIMIT 5
            """, (v_dict["name"],)).fetchall()
            v_dict["recent_changes"] = [dict(c) for c in changes]
            imgs = conn.execute("""
                SELECT id, file_name, file_path, tag, created_at
                FROM recipe_images
                WHERE recipe_id = ?
                ORDER BY id DESC
            """, (v_dict["id"],)).fetchall()
            v_dict["images"] = [dict(im) for im in imgs]
            results.append(v_dict)
        return results


# ==============================================================================
# 기준정보 & Code 매핑 이력 CRUD
# ==============================================================================

def get_master_data(category: str, active_only: bool = True) -> list[dict]:
    with get_connection() as conn:
        q = "SELECT * FROM master_data WHERE category = ?"
        if active_only:
            q += " AND is_active = 1"
        q += " ORDER BY name ASC"
        rows = conn.execute(q, (category,)).fetchall()
        return [dict(r) for r in rows]


def get_master_names(category: str) -> list[str]:
    return [r["name"] for r in get_master_data(category, active_only=True)]


def add_master_data(category: str, name: str) -> bool:
    if not name or not name.strip():
        return False
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO master_data (category, name, created_at) VALUES (?, ?, ?)",
            (category, name.strip(), get_kst_str())
        )
        conn.commit()
    return True


def update_master_data(item_id: int, new_name: str, is_active: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE master_data SET name = ?, is_active = ? WHERE id = ?",
            (new_name.strip(), int(is_active), int(item_id))
        )
        conn.commit()


def delete_master_data(item_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM master_data WHERE id = ?", (int(item_id),))
        conn.commit()


def get_active_code_mapping(code: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM code_mappings
            WHERE code = ? AND valid_to IS NULL
            ORDER BY id DESC LIMIT 1
        """, (code,)).fetchone()
        return dict(row) if row else None


def get_code_mapping_history(code: str = None) -> list[dict]:
    with get_connection() as conn:
        q = "SELECT * FROM code_mappings"
        params = []
        if code:
            q += " WHERE code = ?"
            params.append(code)
        q += " ORDER BY id DESC"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def add_or_update_code_mapping(code: str, product: str, module: str, purpose: str, reason: str, certainty: str = "확정", user: str = "엔지니어") -> bool:
    now_str = get_kst_str()
    with get_connection() as conn:
        conn.execute("UPDATE code_mappings SET valid_to = ? WHERE code = ? AND valid_to IS NULL", (now_str, code))
        conn.execute("""
            INSERT INTO code_mappings (code, product, module, purpose, valid_from, reason, certainty, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (code, product, module, purpose, now_str, reason, certainty, user, now_str))
        conn.execute("INSERT OR IGNORE INTO master_data (category, name, created_at) VALUES ('DeviceCode', ?, ?)", (code, now_str))
        conn.commit()
    return True


# ==============================================================================
# Recipe & Condition & Image CRUD
# ==============================================================================

def get_handlers_with_conditions(product_filter: str = "전체", step_filter: str = "전체", keyword: str = "") -> list[dict]:
    sql = """
        SELECT h.id, h.name, h.version, h.description, h.xml_content, h.created_at,
               rc.id as cond_id, rc.product, rc.step, rc.module, rc.purpose, rc.condition_desc
        FROM recipes h
        LEFT JOIN recipe_conditions rc ON h.id = rc.handler_id
        WHERE h.recipe_type = 'HANDLER'
    """
    params = []
    if product_filter and product_filter != "전체":
        sql += " AND rc.product = ?"
        params.append(product_filter)
    if step_filter and step_filter != "전체":
        sql += " AND rc.step = ?"
        params.append(step_filter)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        sql += " AND (h.name LIKE ? OR h.description LIKE ? OR rc.condition_desc LIKE ?)"
        params.extend([kw, kw, kw])
    sql += " ORDER BY h.id DESC, rc.id ASC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def update_recipe(recipe_id: int, name: str, version: str, description: str, xml_content: str):
    with get_connection() as conn:
        conn.execute("""
            UPDATE recipes
            SET name = ?, version = ?, description = ?, xml_content = ?
            WHERE id = ?
        """, (name.strip(), version.strip(), description, xml_content, int(recipe_id)))
        conn.commit()


def delete_recipe(recipe_id: int):
    with get_connection() as conn:
        imgs = conn.execute("SELECT file_path FROM recipe_images WHERE recipe_id = ?", (int(recipe_id),)).fetchall()
        for img in imgs:
            fp = img["file_path"]
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        conn.execute("DELETE FROM recipes WHERE id = ?", (int(recipe_id),))
        conn.commit()


def get_recipe_images(recipe_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM recipe_images WHERE recipe_id = ? ORDER BY id DESC", (int(recipe_id),)).fetchall()
        return [dict(r) for r in rows]


def add_recipe_image(recipe_id: int, file_name: str, file_path: str, tag: str = "ALIGN"):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO recipe_images (recipe_id, file_name, file_path, tag, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (int(recipe_id), file_name, file_path, tag, get_kst_str()))
        conn.commit()


def delete_recipe_image(image_id: int):
    with get_connection() as conn:
        img = conn.execute("SELECT file_path FROM recipe_images WHERE id = ?", (int(image_id),)).fetchone()
        if img and img["file_path"] and os.path.exists(img["file_path"]):
            try:
                os.remove(img["file_path"])
            except Exception:
                pass
        conn.execute("DELETE FROM recipe_images WHERE id = ?", (int(image_id),))
        conn.commit()


def delete_handler_vision_map(map_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM handler_vision_map WHERE id = ?", (int(map_id),))
        conn.commit()


def delete_deployment(dep_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM deployments WHERE id = ?", (int(dep_id),))
        conn.commit()


# ==============================================================================
# Diff 검증 엔진 & 백업/복원 엔진
# ==============================================================================

def scan_recipe_folder(folder_path: str) -> dict:
    file_map = {}
    if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return file_map

    for root, _, files in os.walk(folder_path):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, start=folder_path).replace("\\", "/")
            try:
                stat = os.stat(full_path)
                sha256 = hashlib.sha256()
                with open(full_path, "rb") as bf:
                    for chunk in iter(lambda: bf.read(65536), b""):
                        sha256.update(chunk)
                file_map[rel_path] = {
                    "full_path": full_path,
                    "rel_path": rel_path,
                    "ext": os.path.splitext(fname)[1].lower(),
                    "size": stat.st_size,
                    "hash": sha256.hexdigest(),
                }
            except Exception:
                pass
    return file_map


def compare_folders(source_dir: str, target_dir: str) -> list[dict]:
    src_map = scan_recipe_folder(source_dir)
    tgt_map = scan_recipe_folder(target_dir)
    all_keys = sorted(set(src_map.keys()) | set(tgt_map.keys()))

    results = []
    for k in all_keys:
        in_src = k in src_map
        in_tgt = k in tgt_map
        if in_src and in_tgt:
            status = "일치" if src_map[k]["hash"] == tgt_map[k]["hash"] else "내용 변경"
            results.append({
                "파일경로": k,
                "상태": status,
                "기준크기(B)": src_map[k]["size"],
                "설비크기(B)": tgt_map[k]["size"],
                "기준해시": src_map[k]["hash"][:12],
                "설비해시": tgt_map[k]["hash"][:12],
                "src_path": src_map[k]["full_path"],
                "tgt_path": tgt_map[k]["full_path"],
                "ext": src_map[k]["ext"],
            })
        elif in_src and not in_tgt:
            results.append({
                "파일경로": k,
                "상태": "누락 (설비에 없음)",
                "기준크기(B)": src_map[k]["size"],
                "설비크기(B)": 0,
                "기준해시": src_map[k]["hash"][:12],
                "설비해시": "-",
                "src_path": src_map[k]["full_path"],
                "tgt_path": None,
                "ext": src_map[k]["ext"],
            })
        else:
            results.append({
                "파일경로": k,
                "상태": "추가 (신규 파일)",
                "기준크기(B)": 0,
                "설비크기(B)": tgt_map[k]["size"],
                "기준해시": "-",
                "설비해시": tgt_map[k]["hash"][:12],
                "src_path": None,
                "tgt_path": tgt_map[k]["full_path"],
                "ext": tgt_map[k]["ext"],
            })
    return results


def compute_text_diff_html(text_a: str, text_b: str) -> tuple[bool, str]:
    lines_a = (text_a or "").splitlines(keepends=True)
    lines_b = (text_b or "").splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(lines_a, lines_b, fromfile="Source_A", tofile="Target_B"))
    if not diff_lines:
        return True, ""

    html_parts = []
    for line in diff_lines:
        esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if esc.startswith("+") and not esc.startswith("+++"):
            html_parts.append(f"<span style='color:#4ec9b0;font-weight:bold;'>{esc}</span>")
        elif esc.startswith("-") and not esc.startswith("---"):
            html_parts.append(f"<span style='color:#f14c4c;font-weight:bold;'>{esc}</span>")
        else:
            html_parts.append(esc)
    return False, "".join(html_parts)


def compute_image_pixel_diff(img1: Image.Image, img2: Image.Image, threshold: int = 15) -> dict:
    im1 = img1.convert("RGB")
    im2 = img2.convert("RGB")
    if im1.size != im2.size:
        im2_comp = im2.resize(im1.size, Image.Resampling.BILINEAR)
    else:
        im2_comp = im2

    diff_gray = ImageChops.difference(im1, im2_comp).convert("L")
    mask_l = diff_gray.point(lambda p: 255 if p >= threshold else 0, mode="L")
    hist = mask_l.histogram()
    diff_pixels = hist[255] if len(hist) > 255 else 0
    total_pixels = im1.size[0] * im1.size[1]
    diff_ratio = (diff_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    base_gray = im1.convert("L").convert("RGBA")
    red_layer = Image.new("RGBA", im1.size, (255, 0, 0, 210))
    diff_visual = Image.composite(red_layer, base_gray, mask_l)

    return {
        "total_pixels": total_pixels,
        "diff_pixels": diff_pixels,
        "diff_ratio": round(diff_ratio, 2),
        "match_ratio": round(100.0 - diff_ratio, 2),
        "diff_visual": diff_visual,
    }


def create_system_backup() -> bytes:
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

        migrate_schema()
        return True, "데이터베이스 및 첨부 이미지가 성공적으로 복원되었습니다."
    except Exception as e:
        return False, f"복원 중 오류 발생: {e}"
