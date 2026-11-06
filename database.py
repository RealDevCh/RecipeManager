import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "recipe_manager.db")

def init_db():
    """데이터베이스 초기화 및 테이블 생성 (FK 활성화)"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # 1. 기준정보 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, name)
            );
        """)
        
        # 2. Recipe 마스터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_type TEXT NOT NULL CHECK(recipe_type IN ('HANDLER', 'VISION')),
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT,
                xml_content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(recipe_type, name, version)
            );
        """)

        # 3. Recipe Align 및 참조 이미지 테이블 (다중 이미지 1:N)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                tag TEXT DEFAULT 'ALIGN',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            );
        """)
        
        # 4. Handler-Vision 참조 관계 (N:M, 순서 유지)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS handler_vision_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                handler_id INTEGER NOT NULL,
                vision_id INTEGER NOT NULL,
                seq_order INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (vision_id) REFERENCES recipes(id) ON DELETE CASCADE,
                UNIQUE(handler_id, vision_id)
            );
        """)

        # 5. 조건별 Recipe 매핑 (Product-Step-Module-Purpose -> Handler N개 가능, condition_desc 포함)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                step TEXT NOT NULL,
                module TEXT NOT NULL,
                purpose TEXT NOT NULL,
                handler_id INTEGER NOT NULL,
                condition_desc TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                UNIQUE(product, step, module, purpose, handler_id)
            );
        """)

        # 6. PKG / Device Code 매핑 이력 테이블 (MD-04, MD-05)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                product TEXT NOT NULL,
                module TEXT NOT NULL,
                purpose TEXT NOT NULL,
                valid_from DATETIME DEFAULT CURRENT_TIMESTAMP,
                valid_to DATETIME,
                reason TEXT,
                certainty TEXT DEFAULT '확정' CHECK(certainty IN ('확정', '추정', '검토필요')),
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 7. 업무 요청 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                req_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                product TEXT,
                step TEXT,
                module TEXT,
                purpose TEXT,
                equipment TEXT,
                department TEXT,
                requester TEXT,
                assignee TEXT,
                lot_id TEXT,
                recipe_id TEXT,
                status TEXT DEFAULT '접수' CHECK(status IN ('접수', '진행중', '평가/검증', '완료', '보류')),
                due_date TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 8. 첨부 증빙 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE CASCADE
            );
        """)

        # 9. Recipe 변경 이력 감사 로그
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_name TEXT NOT NULL,
                change_type TEXT NOT NULL,
                before_val TEXT,
                after_val TEXT,
                change_reason TEXT,
                operator TEXT,
                evaluation_result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE CASCADE
            );
        """)

        # 10. 횡전개(Deployment) 마스터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                handler_id INTEGER NOT NULL,
                request_id INTEGER,
                reason TEXT,
                created_by TEXT,
                status TEXT DEFAULT '진행중' CHECK(status IN ('대기', '진행중', '완료', '보류')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (request_id) REFERENCES work_requests(id) ON DELETE SET NULL
            );
        """)

        # 11. 횡전개 대상 설비별 상세 진행 상태
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id INTEGER NOT NULL,
                equipment TEXT NOT NULL,
                status TEXT DEFAULT '대기' CHECK(status IN ('대기', '진행중', '검증완료', '실패', '보류')),
                operator TEXT,
                applied_at DATETIME,
                verifier TEXT,
                verified_at DATETIME,
                hold_reason TEXT,
                memo TEXT,
                FOREIGN KEY (deployment_id) REFERENCES deployments(id) ON DELETE CASCADE,
                UNIQUE(deployment_id, equipment)
            );
        """)

        # 12. 설비별 Recipe 최종 확인 상태
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment_recipe_status (
                equipment TEXT PRIMARY KEY,
                handler_id INTEGER,
                target_version TEXT,
                verified_version TEXT,
                sync_status TEXT DEFAULT '미확인' CHECK(sync_status IN ('일치', '불일치', '미확인')),
                last_verified_at DATETIME,
                verifier TEXT,
                FOREIGN KEY (handler_id) REFERENCES recipes(id) ON DELETE SET NULL
            );
        """)

        # 초기 기준정보 및 샘플 데이터 시딩
        cur_cnt = cursor.execute("SELECT COUNT(*) FROM master_data").fetchone()[0]
        if cur_cnt == 0:
            default_items = [
                ('Product', 'Prod_Alpha'), ('Product', 'Prod_Beta'), ('Product', 'Prod_Gamma'),
                ('Step', 'Step01_Align'), ('Step', 'Step02_Inspect'), ('Step', 'Step03_Review'),
                ('Module', 'Mod_Front'), ('Module', 'Mod_Rear'), ('Module', 'Mod_Side'),
                ('Purpose', 'Mass_Production'), ('Purpose', 'Evaluation'), ('Purpose', 'Setup'),
                ('Department', '제조기술팀'), ('Department', '공정설계팀'), ('Department', '품질보증팀'),
                ('Equipment', 'EQP-01'), ('Equipment', 'EQP-02'), ('Equipment', 'EQP-03'), ('Equipment', 'EQP-04'),
                ('DeviceCode', 'AAA'), ('DeviceCode', 'BBB'), ('DeviceCode', 'B01'), ('DeviceCode', 'C10')
            ]
            for cat, val in default_items:
                cursor.execute("INSERT OR IGNORE INTO master_data (category, name) VALUES (?, ?)", (cat, val))
            
            # 기본 Code 매핑 시드
            cursor.execute("""
                INSERT OR IGNORE INTO code_mappings (code, product, module, purpose, reason, certainty, created_by)
                VALUES ('AAA', 'Prod_Alpha', 'Mod_Front', 'Mass_Production', '양산 초기 기준 매핑 승인', '확정', '관리자')
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO code_mappings (code, product, module, purpose, reason, certainty, created_by)
                VALUES ('BBB', 'Prod_Beta', 'Mod_Rear', 'Evaluation', '신규 디바이스 평가 셋업', '확정', '엔지니어')
            """)

            # 기본 Handler 및 동일 조건 내 복수 Handler 샘플 시딩
            cursor.execute("""
                INSERT OR IGNORE INTO recipes (id, recipe_type, name, version, description, xml_content)
                VALUES (1, 'HANDLER', 'HANDLER_ALPHA_STD', 'v1.0', '표준 양산 핸들러 레시피', '<Recipe>\n  <Align>\n    <Threshold>120</Threshold>\n  </Align>\n</Recipe>')
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO recipes (id, recipe_type, name, version, description, xml_content)
                VALUES (2, 'HANDLER', 'HANDLER_ALPHA_LOWLIGHT', 'v1.1', '야간 조도 저하 대응 튜닝본', '<Recipe>\n  <Align>\n    <Threshold>145</Threshold>\n    <Gain>1.3</Gain>\n  </Align>\n</Recipe>')
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO recipes (id, recipe_type, name, version, description, xml_content)
                VALUES (3, 'VISION', 'VIS_ALIGN_CAM1', 'v1.0', '카메라1 기본 Align 비전', '<Vision>\n  <Exposure>25</Exposure>\n</Vision>')
            """)
            
            # 동일한 (Prod_Alpha + Step01_Align + Mod_Front + Mass_Production) 조건에 N개 Handler 매핑
            cursor.execute("""
                INSERT OR IGNORE INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc)
                VALUES ('Prod_Alpha', 'Step01_Align', 'Mod_Front', 'Mass_Production', 1, '주간 기본 양산 전용 표준 레시피')
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc)
                VALUES ('Prod_Alpha', 'Step01_Align', 'Mod_Front', 'Mass_Production', 2, '야간 조도 변화 시 적용하는 마진 튜닝 레시피')
            """)

            # Handler-Vision 연결
            cursor.execute("INSERT OR IGNORE INTO handler_vision_map (handler_id, vision_id, seq_order) VALUES (1, 3, 1)")
            cursor.execute("INSERT OR IGNORE INTO handler_vision_map (handler_id, vision_id, seq_order) VALUES (2, 3, 1)")

        conn.commit()

def get_connection():
    """SQLite 커넥션 획득 (Row Factory 및 FK 활성화)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

# --- 기준정보 CRUD (안전한 원시 dict 반환 보장) ---
def get_master_data(category, active_only=True):
    with get_connection() as conn:
        q = "SELECT * FROM master_data WHERE category = ?"
        if active_only:
            q += " AND is_active = 1"
        q += " ORDER BY name ASC"
        rows = conn.execute(q, (category,)).fetchall()
        return [dict(r) for r in rows]

def get_master_names(category):
    items = get_master_data(category, active_only=True)
    return [r['name'] for r in items]

def add_master_data(category, name):
    if not name or not name.strip():
        return False
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO master_data (category, name) VALUES (?, ?)", (category, name.strip()))
        conn.commit()
    return True

def update_master_data(item_id, new_name, is_active):
    with get_connection() as conn:
        conn.execute("UPDATE master_data SET name = ?, is_active = ? WHERE id = ?", (new_name.strip(), is_active, item_id))
        conn.commit()

def delete_master_data(item_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM master_data WHERE id = ?", (item_id,))
        conn.commit()

# --- Code 매핑 이력 CRUD (MD-04, MD-05) ---
def get_active_code_mapping(code):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM code_mappings 
            WHERE code = ? AND valid_to IS NULL 
            ORDER BY id DESC LIMIT 1
        """, (code,)).fetchone()
        return dict(row) if row else None

def get_code_mapping_history(code=None):
    with get_connection() as conn:
        q = "SELECT * FROM code_mappings"
        params = []
        if code:
            q += " WHERE code = ?"
            params.append(code)
        q += " ORDER BY id DESC"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

def add_or_update_code_mapping(code, product, module, purpose, reason, certainty="확정", user="작업자"):
    with get_connection() as conn:
        conn.execute("""
            UPDATE code_mappings 
            SET valid_to = CURRENT_TIMESTAMP 
            WHERE code = ? AND valid_to IS NULL
        """, (code,))
        conn.execute("""
            INSERT INTO code_mappings (code, product, module, purpose, reason, certainty, created_by, valid_from)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (code, product, module, purpose, reason, certainty, user))
        conn.execute("INSERT OR IGNORE INTO master_data (category, name) VALUES ('DeviceCode', ?)", (code,))
        conn.commit()
    return True

def delete_code_mapping(mapping_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM code_mappings WHERE id = ?", (mapping_id,))
        conn.commit()

# --- Recipe & 공정 조건 통합 CRUD ---
def create_handler_recipe_with_condition(name, version, recipe_desc, xml_content, product, step, module, purpose, condition_desc):
    """Handler Recipe 생성과 공정 조건 매핑(Description 포함)을 단일 트랜잭션으로 처리"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recipes (recipe_type, name, version, description, xml_content)
            VALUES ('HANDLER', ?, ?, ?, ?)
        """, (name.strip(), version.strip(), recipe_desc, xml_content))
        handler_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product, step, module, purpose, handler_id, condition_desc.strip() if condition_desc else ""))
        conn.commit()
        return handler_id

def create_vision_recipe(name, version, description, xml_content):
    """공용 Vision Recipe 등록"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recipes (recipe_type, name, version, description, xml_content)
            VALUES ('VISION', ?, ?, ?, ?)
        """, (name.strip(), version.strip(), description, xml_content))
        conn.commit()
        return cursor.lastrowid

def update_recipe(recipe_id, name, version, description, xml_content):
    with get_connection() as conn:
        conn.execute("""
            UPDATE recipes
            SET name = ?, version = ?, description = ?, xml_content = ?
            WHERE id = ?
        """, (name, version, description, xml_content, recipe_id))
        conn.commit()

def update_handler_condition(handler_id, product, step, module, purpose, condition_desc):
    with get_connection() as conn:
        conn.execute("""
            UPDATE recipe_conditions
            SET product = ?, step = ?, module = ?, purpose = ?, condition_desc = ?
            WHERE handler_id = ?
        """, (product, step, module, purpose, condition_desc, handler_id))
        conn.commit()

def delete_recipe(recipe_id):
    with get_connection() as conn:
        imgs = conn.execute("SELECT file_path FROM recipe_images WHERE recipe_id=?", (recipe_id,)).fetchall()
        for img in imgs:
            fp = img['file_path']
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()

def get_handlers_with_conditions():
    """Handler 목록 및 매핑된 공정 조건, 동일 조건 내 구분 Description 반환"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT r.id, r.name, r.version, r.description as recipe_desc, r.xml_content, r.created_at,
                   rc.id as cond_id, rc.product, rc.step, rc.module, rc.purpose, rc.condition_desc
            FROM recipes r
            LEFT JOIN recipe_conditions rc ON r.id = rc.handler_id
            WHERE r.recipe_type = 'HANDLER'
            ORDER BY rc.product, rc.step, r.name, r.id DESC
        """).fetchall()
        return [dict(r) for r in rows]

# --- Recipe Align 이미지 CRUD ---
def get_recipe_images(recipe_id):
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM recipe_images WHERE recipe_id = ? ORDER BY id DESC", (recipe_id,)).fetchall()
        return [dict(r) for r in rows]

def add_recipe_image(recipe_id, file_name, file_path, tag="ALIGN"):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO recipe_images (recipe_id, file_name, file_path, tag)
            VALUES (?, ?, ?, ?)
        """, (recipe_id, file_name, file_path, tag))
        conn.commit()

def delete_recipe_image(image_id):
    with get_connection() as conn:
        img = conn.execute("SELECT file_path FROM recipe_images WHERE id = ?", (image_id,)).fetchone()
        if img and img['file_path'] and os.path.exists(img['file_path']):
            try:
                os.remove(img['file_path'])
            except Exception:
                pass
        conn.execute("DELETE FROM recipe_images WHERE id = ?", (image_id,))
        conn.commit()

# --- 조건 매핑 / 참조 관계 삭제 ---
def delete_recipe_condition(cond_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM recipe_conditions WHERE id = ?", (cond_id,))
        conn.commit()

def delete_handler_vision_map(map_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM handler_vision_map WHERE id = ?", (map_id,))
        conn.commit()

def delete_attachment(att_id):
    with get_connection() as conn:
        att = conn.execute("SELECT file_path FROM attachments WHERE id = ?", (att_id,)).fetchone()
        if att and att['file_path'] and os.path.exists(att['file_path']):
            try:
                os.remove(att['file_path'])
            except Exception:
                pass
        conn.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
        conn.commit()

def delete_recipe_change(chg_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM recipe_changes WHERE id = ?", (chg_id,))
        conn.commit()

def delete_deployment(dep_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM deployments WHERE id = ?", (dep_id,))
        conn.commit()

# --- 업무 요청 CRUD ---
def update_work_request(req_id, req_type, title, content, product, step, equipment, department, requester, assignee):
    with get_connection() as conn:
        conn.execute("""
            UPDATE work_requests 
            SET req_type=?, title=?, content=?, product=?, step=?, equipment=?, department=?, requester=?, assignee=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (req_type, title, content, product, step, equipment, department, requester, assignee, req_id))
        conn.commit()

def delete_work_request(req_id):
    with get_connection() as conn:
        atts = conn.execute("SELECT file_path FROM attachments WHERE request_id=?", (req_id,)).fetchall()
        for a in atts:
            fp = a['file_path']
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        conn.execute("DELETE FROM work_requests WHERE id = ?", (req_id,))
        conn.commit()

# --- 폴더 스캔 및 해시 추출 헬퍼 ---
def scan_recipe_folder(folder_path):
    file_map = {}
    if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return file_map
    
    for root, _, files in os.walk(folder_path):
        for f in files:
            full_path = os.path.join(root, f)
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
                    "size": stat.st_size,
                    "hash": sha256.hexdigest(),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception:
                pass
    return file_map
