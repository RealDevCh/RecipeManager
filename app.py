import streamlit as st
import pandas as pd
import os
import difflib
from datetime import datetime
from PIL import Image
import database as db

APP_VERSION = "v1.4.2"

try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BTN = True
except ImportError:
    HAS_PASTE_BTN = False

st.set_page_config(
    page_title=f"RecipeManager {APP_VERSION}",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

# 커스텀 SaaS 스타일 CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #f8f9fb 0%, #edf2f7 100%);
        border-radius: 10px;
        padding: 14px 18px;
        border-left: 5px solid #2b5c8f;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        margin-bottom: 8px;
    }
    .metric-card h3 {
        margin: 2px 0 0 0;
        font-size: 22px;
        color: #1a202c;
    }
    .kanban-col {
        background-color: #f7fafc;
        border-radius: 8px;
        padding: 10px;
        border: 1px solid #e2e8f0;
        min-height: 480px;
    }
    .kanban-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: transform 0.1s ease-in-out;
    }
    .kanban-card:hover {
        border-color: #cbd5e0;
        transform: translateY(-2px);
    }
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        background-color: #edf2f7;
        color: #4a5568;
    }
    .diff-box {
        font-family: 'Consolas', 'Courier New', monospace;
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 14px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 12px;
        line-height: 1.5;
    }
    .diff-added { color: #4ec9b0; font-weight: bold; }
    .diff-removed { color: #f14c4c; font-weight: bold; }
    .img-box {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 8px;
        background: #ffffff;
        text-align: center;
        margin-bottom: 8px;
    }
    .search-card {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .handler-card {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #2b5c8f;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 4대 업무 중심 사이드바 -----------------
with st.sidebar:
    st.title("⚙️ RecipeManager")
    st.caption(f"시스템 버전: **{APP_VERSION}** (상단 신규 등록 팝오버 직관화)")
    st.divider()
    menu = st.radio(
        "워크플로우 메뉴",
        [
            "📋 1. 업무 요청 & 조치",
            "🧩 2. Recipe 통합 관리 & 검색",
            "🚀 3. 설비 적용 & 횡전개 검증",
            "⚙️ 4. 기준정보 및 감사 관리"
        ],
        label_visibility="collapsed"
    )
    st.divider()
    st.markdown("""
    **💡 워크플로우 가이드**
    1. **요청/조치**: 접수·증빙·변경이력 인라인 완결
    2. **Recipe & 검색**: 공정조건 1:N 복수 Handler + Description 관리
    3. **설비/횡전개**: 설비 폴더 트리 Diff + 횡전개 검증
    4. **기준정보**: 공통코드 완전 CRUD 및 감사로그
    """)

# ========================================================
# 1. 📋 업무 요청 & 조치 (Work Order Management)
# ========================================================
if menu == "📋 1. 업무 요청 & 조치":
    st.title("📋 업무 요청 & 조치 (Work Order)")
    st.caption("현장 요청 접수부터 Handler/Vision 파라미터 보정, Ctrl+V 증빙, 평가 완료까지 1-Screen으로 완결합니다.")

    with db.get_connection() as conn:
        df_all = pd.read_sql_query("SELECT * FROM work_requests ORDER BY id DESC", conn)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='metric-card'><span>전체 요청</span><h3>{len(df_all)}건</h3></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><span>접수 대기</span><h3>{len(df_all[df_all['status'] == '접수'])}건</h3></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='metric-card'><span>진행 / 평가중</span><h3>{len(df_all[df_all['status'].isin(['진행중', '평가/검증'])])}건</h3></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='metric-card'><span>조치 완료</span><h3>{len(df_all[df_all['status'] == '완료'])}건</h3></div>", unsafe_allow_html=True)

    st.write("")
    col_ctrl, col_act = st.columns([7.5, 2.5])
    with col_ctrl:
        view_mode = st.radio("보기 모드 전환", ["테이블 뷰", "칸반 보드 뷰"], horizontal=True)
    with col_act:
        with st.popover("➕ 신규 업무 요청 접수", use_container_width=True):
            with st.form("new_request_form"):
                st.markdown("##### 📝 신규 업무 요청 접수")
                r_type = st.selectbox("요청 유형*", ["Recipe 변경", "Align Fail 조치", "신규 셋업", "횡전개", "파라미터 튜닝", "기타"])
                title = st.text_input("제목*", placeholder="예: [Prod_Alpha] Step01 Align 보정 요청")
                c_a, c_b = st.columns(2)
                with c_a:
                    product = st.selectbox("Product", [""] + db.get_master_names("Product"))
                    step = st.selectbox("Step", [""] + db.get_master_names("Step"))
                    eqp = st.selectbox("설비 (Equipment)", [""] + db.get_master_names("Equipment"))
                with c_b:
                    dept = st.selectbox("요청부서", [""] + db.get_master_names("Department"))
                    requester = st.text_input("요청자")
                    assignee = st.text_input("담당자")
                content = st.text_area("상세 요청 내용", placeholder="발생 현상, 변경 목표 및 세부 사항")
                submitted = st.form_submit_button("요청 등록 완료", use_container_width=True)
                if submitted:
                    if not title or not title.strip():
                        st.error("제목은 필수 항목입니다.")
                    else:
                        with db.get_connection() as conn:
                            conn.execute("""
                                INSERT INTO work_requests (req_type, title, content, product, step, equipment, department, requester, assignee)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (r_type, title.strip(), content, product, step, eqp, dept, requester, assignee))
                            conn.commit()
                        st.success("업무 요청이 등록되었습니다.")
                        st.rerun()

    selected_id = None
    if view_mode == "테이블 뷰":
        col_main, col_detail = st.columns([6, 4])
        with col_main:
            if not df_all.empty:
                display_cols = ['id', 'status', 'req_type', 'title', 'product', 'step', 'assignee', 'created_at']
                st.dataframe(df_all[display_cols], use_container_width=True, hide_index=True)
                id_list = [int(x) for x in df_all['id'].tolist()]
                selected_id = st.selectbox("상세/조치 대상 요청 선택 (ID)", id_list)
            else:
                st.info("등록된 업무 요청이 없습니다.")
    else:
        col_main, col_detail = st.columns([6.8, 3.2])
        with col_main:
            statuses = ['접수', '진행중', '평가/검증', '완료']
            k_cols = st.columns(len(statuses))
            for idx, stat in enumerate(statuses):
                with k_cols[idx]:
                    sub_df = df_all[df_all['status'] == stat]
                    st.markdown(f"**{stat}** `({len(sub_df)})`")
                    st.markdown("<div class='kanban-col'>", unsafe_allow_html=True)
                    for _, row in sub_df.iterrows():
                        st.markdown(f"""
                        <div class='kanban-card'>
                            <span class='badge'>#{row['id']} {row['req_type']}</span><br>
                            <b style='font-size:14px;'>{row['title']}</b><br>
                            <small style='color:#718096;'>{row['product'] or '-'} · {row['assignee'] or '미지정'}</small>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"선택 #{row['id']}", key=f"kanban_btn_{row['id']}", use_container_width=True):
                            st.session_state['selected_req_id'] = int(row['id'])
                    st.markdown("</div>", unsafe_allow_html=True)
            if 'selected_req_id' in st.session_state and st.session_state['selected_req_id'] in df_all['id'].values:
                selected_id = st.session_state['selected_req_id']
            elif not df_all.empty:
                selected_id = int(df_all['id'].iloc[0])

    # 상세 및 증빙/조치 패널 (Split Panel)
    with col_detail:
        if selected_id:
            with db.get_connection() as conn:
                row_item = conn.execute("SELECT * FROM work_requests WHERE id = ?", (selected_id,)).fetchone()
            
            if row_item:
                item = dict(row_item)
                st.markdown(f"### 🔍 #{item['id']} 요청 상세")
                c_st, c_del = st.columns([7, 3])
                with c_st:
                    status_choices = ['접수', '진행중', '평가/검증', '완료', '보류']
                    current_idx = status_choices.index(item['status']) if item['status'] in status_choices else 0
                    curr_status = st.selectbox(
                        "진행 상태",
                        status_choices,
                        index=current_idx,
                        key=f"status_sel_{selected_id}"
                    )
                    if curr_status != item['status']:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE work_requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (curr_status, selected_id))
                            conn.commit()
                        st.success(f"상태가 '{curr_status}'(으)로 갱신되었습니다.")
                        st.rerun()
                with c_del:
                    st.write("")
                    with st.popover("🗑️ 요청 삭제"):
                        st.warning(f"#{item['id']} 요청 및 첨부파일을 완전히 삭제할까요?")
                        if st.button("확인 후 영구 삭제", key=f"del_req_{selected_id}", type="primary"):
                            db.delete_work_request(selected_id)
                            st.success("삭제되었습니다.")
                            st.rerun()

                tab_info, tab_clip, tab_hist, tab_edit = st.tabs(["기본정보", "증빙(Ctrl+V)", "변경이력", "✏️수정"])
                
                with tab_info:
                    st.markdown(f"**유형:** `{item['req_type']}` | **설비:** `{item['equipment'] or '-'}`")
                    st.markdown(f"**공정:** `{item['product']}` / `{item['step']}`")
                    st.markdown(f"**담당자:** `{item['assignee'] or '-'}` | **요청자:** `{item['requester'] or '-'}`")
                    st.text_area("상세 내용", value=item['content'] or '', disabled=True, height=110)

                with tab_clip:
                    st.markdown("##### 📎 이미지 증빙 첨부")
                    pasted_img = None
                    if HAS_PASTE_BTN:
                        paste_result = paste_image_button(
                            label="📋 클립보드 붙여넣기 (Ctrl+V)",
                            background_color="#2b5c8f",
                            text_color="#ffffff"
                        )
                        if paste_result.image_data is not None:
                            pasted_img = paste_result.image_data
                    
                    up_file = st.file_uploader("또는 이미지 파일 업로드", type=["png", "jpg", "jpeg", "bmp"], key=f"up_{selected_id}")
                    if up_file:
                        pasted_img = Image.open(up_file)

                    if pasted_img:
                        st.image(pasted_img, caption="입력된 이미지", use_column_width=True)
                        if st.button("증빙 저장하기", key=f"save_img_{selected_id}", use_container_width=True):
                            img_dir = os.path.join(os.path.dirname(__file__), "data", "attachments")
                            os.makedirs(img_dir, exist_ok=True)
                            file_name = f"req_{selected_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            file_path = os.path.join(img_dir, file_name)
                            pasted_img.save(file_path)
                            
                            with db.get_connection() as conn:
                                conn.execute("INSERT INTO attachments (request_id, file_name, file_path) VALUES (?, ?, ?)",
                                             (selected_id, file_name, file_path))
                                conn.commit()
                            st.success("증빙 저장 완료")
                            st.rerun()

                    with db.get_connection() as conn:
                        rows_att = conn.execute("SELECT * FROM attachments WHERE request_id = ? ORDER BY id DESC", (selected_id,)).fetchall()
                        atts = [dict(r) for r in rows_att]
                    if atts:
                        st.divider()
                        st.caption(f"등록된 증빙 ({len(atts)}건)")
                        att_cols = st.columns(2)
                        for a_idx, att in enumerate(atts):
                            if att['file_path'] and os.path.exists(att['file_path']):
                                with att_cols[a_idx % 2]:
                                    st.image(att['file_path'], use_column_width=True)
                                    c_a1, c_a2 = st.columns([6, 4])
                                    with c_a1:
                                        with st.popover("🔍 확대"):
                                            st.image(att['file_path'], caption=att['file_name'], use_column_width=True)
                                    with c_a2:
                                        if st.button("🗑️삭제", key=f"del_att_{att['id']}"):
                                            db.delete_attachment(att['id'])
                                            st.rerun()

                with tab_hist:
                    st.markdown("##### 📝 Recipe 변경 이력 연계")
                    with st.expander("➕ 변경 이력 추가", expanded=False):
                        with st.form(f"chg_form_{selected_id}"):
                            t_type = st.selectbox("대상 종류", ["Handler", "Vision", "기타 파라미터"])
                            t_name = st.text_input("대상 Recipe/항목명*", placeholder="예: Recipe_A_Align")
                            c_type = st.selectbox("변경 유형", ["파라미터 변경", "신규 분기", "버전 롤백", "Align 보정"])
                            b_val = st.text_input("변경 전 값", placeholder="예: Threshold 120")
                            a_val = st.text_input("변경 후 값", placeholder="예: Threshold 145")
                            reason = st.text_input("변경 사유", placeholder="조도 저하 보정")
                            eval_res = st.selectbox("평가 결과", ["양호(적용가능)", "평가중", "Fail(원복)"])
                            if st.form_submit_button("이력 저장", use_container_width=True):
                                if not t_name or not t_name.strip():
                                    st.error("대상 항목명은 필수입니다.")
                                else:
                                    with db.get_connection() as conn:
                                        conn.execute("""
                                            INSERT INTO recipe_changes (request_id, target_type, target_name, change_type, before_val, after_val, change_reason, evaluation_result)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (selected_id, t_type, t_name.strip(), c_type, b_val, a_val, reason, eval_res))
                                        conn.commit()
                                    st.success("이력 등록 완료")
                                    st.rerun()

                    with db.get_connection() as conn:
                        rows_chgs = conn.execute("SELECT * FROM recipe_changes WHERE request_id = ? ORDER BY id DESC", (selected_id,)).fetchall()
                        chgs = [dict(r) for r in rows_chgs]
                    if chgs:
                        for c in chgs:
                            with st.container():
                                st.markdown(f"""
                                <div style='background:#f7fafc; border-left:3px solid #4a5568; padding:8px; margin-bottom:4px; font-size:12px;'>
                                    <b>[{c['target_type']}] {c['target_name']}</b> ({c['change_type']}) &rarr; <b>{c['evaluation_result']}</b><br>
                                    <code>{c['before_val'] or '-'}</code> &rarr; <code>{c['after_val'] or '-'}</code><br>
                                    <span style='color:gray;'>사유: {c['change_reason'] or '미입력'}</span>
                                </div>
                                """, unsafe_allow_html=True)
                                if st.button("이력 삭제", key=f"del_chg_{c['id']}", help="해당 변경 감사 이력을 삭제합니다"):
                                    db.delete_recipe_change(c['id'])
                                    st.rerun()
                    else:
                        st.caption("등록된 변경 이력이 없습니다.")

                with tab_edit:
                    st.markdown("##### ✏️ 요청 내용 수정")
                    with st.form(f"edit_req_form_{selected_id}"):
                        types_list = ["Recipe 변경", "Align Fail 조치", "신규 셋업", "횡전개", "파라미터 튜닝", "기타"]
                        e_type = st.selectbox("유형", types_list, index=types_list.index(item['req_type']) if item['req_type'] in types_list else 0)
                        e_title = st.text_input("제목", value=item['title'] or '')
                        c_e1, c_e2 = st.columns(2)
                        with c_e1:
                            prods = [""] + db.get_master_names("Product")
                            e_prod = st.selectbox("Product", prods, index=prods.index(item['product']) if item['product'] in prods else 0)
                            steps = [""] + db.get_master_names("Step")
                            e_step = st.selectbox("Step", steps, index=steps.index(item['step']) if item['step'] in steps else 0)
                            eqps = [""] + db.get_master_names("Equipment")
                            e_eqp = st.selectbox("설비", eqps, index=eqps.index(item['equipment']) if item['equipment'] in eqps else 0)
                        with c_e2:
                            depts = [""] + db.get_master_names("Department")
                            e_dept = st.selectbox("부서", depts, index=depts.index(item['department']) if item['department'] in depts else 0)
                            e_req = st.text_input("요청자", value=item['requester'] or '')
                            e_ass = st.text_input("담당자", value=item['assignee'] or '')
                        e_content = st.text_area("내용", value=item['content'] or '', height=100)
                        if st.form_submit_button("수정 내용 저장", use_container_width=True):
                            db.update_work_request(selected_id, e_type, e_title, e_content, e_prod, e_step, e_eqp, e_dept, e_req, e_ass)
                            st.success("수정 완료되었습니다.")
                            st.rerun()

# ========================================================
# 2. 🧩 Recipe 통합 관리 & 검색 (SC-03, MD-04, MD-05)
# ========================================================
elif menu == "🧩 2. Recipe 통합 관리 & 검색":
    st.title("🧩 Recipe 통합 관리 & 검색 (Catalog & Impact)")
    st.caption("Code + Step 역추적 검색, 공정 조건 조합 검색, 동일 조건 내 N개 Handler 및 Description 관리 기능을 지원합니다.")

    tab_search, tab_recipe, tab_rel, tab_impact, tab_code_mgmt = st.tabs([
        "🔍 Recipe 고속 검색 (Code+Step / 조건)",
        "📋 Recipe 마스터 & 공정 조건 매핑 (CRUD)",
        "🔗 Handler-Vision 매핑 구성",
        "⚠️ 공유 Vision 영향도 분석",
        "📜 Code 매핑 이력 관리 (MD-04)"
    ])

    # --- 탭 1: Recipe 고속 검색 ---
    with tab_search:
        search_mode = st.radio("검색 모드 선택", ["⚡ Code + Step 고속 역추적 (SC-03, MD-05)", "📌 공정 조건 조합 검색 (Product → Step → Module)"], horizontal=True)

        if search_mode == "⚡ Code + Step 고속 역추적 (SC-03, MD-05)":
            st.markdown("##### ⚡ Device/PKG Code + Step 기반 Recipe 즉시 역추적")
            st.caption("디바이스 코드와 공정 Step만으로 현재 유효한 공정 조건과 등록된 Handler Recipe 목록(N개) 및 구분 설명을 탐색합니다.")

            c_cs1, c_cs2, c_cs3 = st.columns([3, 3, 2])
            with c_cs1:
                available_codes = db.get_master_names("DeviceCode")
                if not available_codes:
                    available_codes = ["AAA", "BBB", "B01", "C10"]
                sel_code = st.selectbox("Device / PKG Code*", available_codes)
            with c_cs2:
                available_steps = db.get_master_names("Step")
                sel_step = st.selectbox("공정 Step*", available_steps)
            with c_cs3:
                st.write("")
                st.write("")
                btn_cs_search = st.button("🔍 고속 역추적 실행", type="primary", use_container_width=True)

            active_map = db.get_active_code_mapping(sel_code)

            if active_map:
                st.markdown(f"""
                <div class='search-card'>
                    <b>📌 Code 매핑 정보 (MD-04 유효 기준)</b><br>
                    • <b>Device Code:</b> <code>{active_map['code']}</code> &nbsp;|&nbsp; 
                    • <b>Product:</b> <code>{active_map['product']}</code> &nbsp;|&nbsp; 
                    • <b>Module:</b> <code>{active_map['module']}</code> &nbsp;|&nbsp; 
                    • <b>Purpose:</b> <code>{active_map['purpose']}</code><br>
                    • <b>확실성:</b> <span class='badge' style='background:#c6f6d5; color:#22543d;'>{active_map['certainty']}</span> &nbsp;|&nbsp; 
                    • <b>유효 시작일:</b> {active_map['valid_from']} &nbsp;|&nbsp; 
                    • <b>매핑 근거:</b> {active_map['reason'] or '근거 미입력'}
                </div>
                """, unsafe_allow_html=True)

                with db.get_connection() as conn:
                    h_match = conn.execute("""
                        SELECT rc.id as cond_id, rc.condition_desc, h.id as handler_id, h.name as handler_name, h.version as handler_version,
                               h.description as handler_desc, h.xml_content
                        FROM recipe_conditions rc
                        JOIN recipes h ON rc.handler_id = h.id
                        WHERE rc.product = ? AND rc.step = ? AND rc.module = ? AND rc.purpose = ?
                        ORDER BY h.id ASC
                    """, (active_map['product'], sel_step, active_map['module'], active_map['purpose'])).fetchall()
                    h_results = [dict(r) for r in h_match]

                if h_results:
                    st.success(f"🎉 **Code '{sel_code}' + '{sel_step}'** 조건에 매핑된 Handler Recipe: 총 **{len(h_results)}개**")
                    for h_idx, h_item in enumerate(h_results):
                        st.markdown(f"""
                        <div class='handler-card'>
                            <span class='badge' style='background:#2b5c8f; color:#fff;'>옵션 #{h_idx+1}</span>
                            <b style='font-size:16px; color:#2b5c8f;'>{h_item['handler_name']} ({h_item['handler_version']})</b><br>
                            <span style='font-size:13px; color:#2d3748;'><b>💡 동일 조건 내 구분 설명:</b> {h_item['condition_desc'] or '미입력'}</span><br>
                            <small style='color:#718096;'>기본 설명: {h_item['handler_desc'] or '-'}</small>
                        </div>
                        """, unsafe_allow_html=True)

                        c_h1, c_h2 = st.columns([6, 4])
                        with c_h1:
                            with st.expander(f"📄 #{h_item['handler_id']} {h_item['handler_name']} XML 파라미터 보기"):
                                st.code(h_item['xml_content'] or "파라미터 없음", language="xml")
                        with c_h2:
                            with db.get_connection() as conn:
                                v_chain_rows = conn.execute("""
                                    SELECT v.id as vision_id, v.name, v.version, m.seq_order
                                    FROM handler_vision_map m
                                    JOIN recipes v ON m.vision_id = v.id
                                    WHERE m.handler_id = ?
                                    ORDER BY m.seq_order ASC
                                """, (h_item['handler_id'],)).fetchall()
                                v_chain = [dict(r) for r in v_chain_rows]
                            if v_chain:
                                st.caption(f"연결 Vision 체인 ({len(v_chain)}개)")
                                for vc in v_chain:
                                    st.markdown(f"- **순서 {vc['seq_order']}**: `{vc['name']}` ({vc['version']})")
                            else:
                                st.caption("연결된 Vision Recipe 없음")
                else:
                    st.warning(f"⚠️ Code '{sel_code}'의 공정 조건({active_map['product']} / {active_map['module']} / {active_map['purpose']})에 대한 **'{sel_step}'** Handler Recipe 매핑이 아직 없습니다.")
            else:
                st.error(f"❌ Device Code '{sel_code}'에 유효한 공정 조건 매핑이 없습니다.")

        else:
            st.markdown("##### 📌 공정 조건 조합 검색 (Product → Step → Module → Purpose)")
            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            with c_s1:
                s_prod = st.selectbox("Product", ["전체"] + db.get_master_names("Product"), key="c_prod")
            with c_s2:
                s_step = st.selectbox("Step", ["전체"] + db.get_master_names("Step"), key="c_step")
            with c_s3:
                s_mod = st.selectbox("Module", ["전체"] + db.get_master_names("Module"), key="c_mod")
            with c_s4:
                s_purp = st.selectbox("Purpose", ["전체"] + db.get_master_names("Purpose"), key="c_purp")

            query = """
                SELECT rc.id as cond_id, rc.product, rc.step, rc.module, rc.purpose, rc.condition_desc,
                       h.name as handler_name, h.version as handler_version, h.id as handler_id
                FROM recipe_conditions rc
                JOIN recipes h ON rc.handler_id = h.id
                WHERE 1=1
            """
            params = []
            if s_prod != "전체":
                query += " AND rc.product = ?"
                params.append(s_prod)
            if s_step != "전체":
                query += " AND rc.step = ?"
                params.append(s_step)
            if s_mod != "전체":
                query += " AND rc.module = ?"
                params.append(s_mod)
            if s_purp != "전체":
                query += " AND rc.purpose = ?"
                params.append(s_purp)

            with db.get_connection() as conn:
                df_cond = pd.read_sql_query(query, conn, params=params)

            col_c_list, col_c_detail = st.columns([6, 4])
            with col_c_list:
                if not df_cond.empty:
                    st.dataframe(df_cond[['cond_id', 'product', 'step', 'module', 'purpose', 'handler_name', 'handler_version', 'condition_desc']], use_container_width=True, hide_index=True)
                    cond_ids = [int(x) for x in df_cond['cond_id'].tolist()]
                    sel_cond_id = st.selectbox("선택 조건 매핑", cond_ids, format_func=lambda x: f"매핑 #{x} ({df_cond[df_cond['cond_id']==x]['handler_name'].values[0]})")
                else:
                    st.info("조건에 부합하는 Recipe 매핑이 없습니다.")
                    sel_cond_id = None

            with col_c_detail:
                if sel_cond_id:
                    row_sel = df_cond[df_cond['cond_id'] == sel_cond_id].iloc[0]
                    st.markdown("###### 🔗 연결된 Vision Recipe 순서 체인")
                    st.info(f"**구분 설명:** {row_sel['condition_desc'] or '미입력'}")
                    with db.get_connection() as conn:
                        rows_vc = conn.execute("""
                            SELECT v.name, v.version, v.description, m.seq_order
                            FROM handler_vision_map m
                            JOIN recipes v ON m.vision_id = v.id
                            WHERE m.handler_id = ?
                            ORDER BY m.seq_order ASC
                        """, (int(row_sel['handler_id']),)).fetchall()
                        v_chain = [dict(r) for r in rows_vc]
                    if v_chain:
                        for v in v_chain:
                            st.markdown(f"- **순서 {v['seq_order']}**: `{v['name']}` ({v['version']})")
                    else:
                        st.caption("연결된 Vision Recipe가 없습니다.")
                    
                    st.write("")
                    if st.button("🗑️ 이 조건 매핑 삭제", key=f"del_cond_{sel_cond_id}"):
                        db.delete_recipe_condition(sel_cond_id)
                        st.success("조건 매핑이 삭제되었습니다.")
                        st.rerun()

    # --- 탭 2: Recipe 마스터 & 공정 조건 매핑 (CRUD) ---
    with tab_recipe:
        st.markdown("##### 📋 Recipe 마스터 등록 / 수정 / 삭제 및 공정 조건(1:N) & Align 이미지 관리")
        
        c_top_radio, c_top_btn = st.columns([6.5, 3.5])
        with c_top_radio:
            r_type_sel = st.radio("Recipe 종류 선택", ["HANDLER", "VISION"], horizontal=True)

        if r_type_sel == "HANDLER":
            with c_top_btn:
                st.write("")
                with st.popover("➕ 신규 Handler Recipe 등록", use_container_width=True):
                    with st.form("new_handler_full_form_top"):
                        st.markdown("##### 1. 공정 조건 지정 (Device Code 연동 자동완성)")
                        code_options = ["직접 입력/선택"] + db.get_master_names("DeviceCode")
                        sel_fill_code = st.selectbox("Device / PKG Code (선택 시 자동 세팅)", code_options, key="top_sel_code")

                        default_prod_idx = 0
                        default_mod_idx = 0
                        default_purp_idx = 0
                        prods_list = db.get_master_names("Product")
                        mods_list = db.get_master_names("Module")
                        purps_list = db.get_master_names("Purpose")

                        if sel_fill_code != "직접 입력/선택":
                            ac_map = db.get_active_code_mapping(sel_fill_code)
                            if ac_map:
                                if ac_map['product'] in prods_list: default_prod_idx = prods_list.index(ac_map['product'])
                                if ac_map['module'] in mods_list: default_mod_idx = mods_list.index(ac_map['module'])
                                if ac_map['purpose'] in purps_list: default_purp_idx = purps_list.index(ac_map['purpose'])

                        c_nf1, c_nf2 = st.columns(2)
                        with c_nf1:
                            new_h_prod = st.selectbox("Product*", prods_list, index=default_prod_idx, key="top_h_prod")
                            new_h_step = st.selectbox("Step*", db.get_master_names("Step"), key="top_h_step")
                        with c_nf2:
                            new_h_mod = st.selectbox("Module*", mods_list, index=default_mod_idx, key="top_h_mod")
                            new_h_purp = st.selectbox("Purpose*", purps_list, index=default_purp_idx, key="top_h_purp")

                        st.markdown("##### 2. Handler 식별 및 동일 조건 내 구분 설명")
                        c_nh1, c_nh2 = st.columns(2)
                        with c_nh1:
                            new_h_name = st.text_input("Handler Recipe 이름*", placeholder="예: HANDLER_ALPHA_MARGIN", key="top_h_name")
                        with c_nh2:
                            new_h_ver = st.text_input("버전*", value="v1.0", key="top_h_ver")

                        new_h_cond_desc = st.text_input(
                            "동일 조건 내 구분 설명 (Condition Description)*",
                            placeholder="예: 야간 저조도 마진 튜닝본 / EQP-01 전용 마진 보정 / 표준 양산 기준",
                            help="동일한 Product+Step+Module+Purpose 조건에 여러 Handler가 존재할 때 차이점을 설명합니다.",
                            key="top_h_cond_desc"
                        )
                        new_h_desc = st.text_input("기본 설명 (선택)", placeholder="엔지니어 메모", key="top_h_desc")
                        
                        default_xml_h = """<Recipe>
  <Align>
    <Threshold>120</Threshold>
  </Align>
</Recipe>"""
                        new_h_xml = st.text_area("파라미터 / XML 내용", value=default_xml_h, height=100, key="top_h_xml")

                        if st.form_submit_button("Handler Recipe 등록 완료", type="primary", use_container_width=True):
                            if not new_h_name or not new_h_name.strip() or not new_h_ver or not new_h_ver.strip():
                                st.error("Recipe 이름과 버전은 필수입니다.")
                            else:
                                new_hid = db.create_handler_recipe_with_condition(
                                    new_h_name, new_h_ver, new_h_desc, new_h_xml,
                                    new_h_prod, new_h_step, new_h_mod, new_h_purp, new_h_cond_desc
                                )
                                st.success(f"Handler Recipe #{new_hid} 및 공정 조건 매핑이 등록되었습니다.")
                                st.rerun()

            handlers_with_cond = db.get_handlers_with_conditions()
            col_r_tbl, col_r_edit = st.columns([5.5, 4.5])

            with col_r_tbl:
                st.markdown("###### 📦 Handler Recipe 목록 (공정 조건 및 구분 설명 포함)")
                if handlers_with_cond:
                    df_handlers = pd.DataFrame(handlers_with_cond)
                    display_cols = ['id', 'name', 'version', 'product', 'step', 'module', 'purpose', 'condition_desc']
                    st.dataframe(df_handlers[display_cols], use_container_width=True, hide_index=True)
                    h_ids = [int(x) for x in df_handlers['id'].tolist()]
                    sel_h_id = st.selectbox(
                        "수정/조회할 Handler Recipe 선택 (ID)", 
                        h_ids, 
                        format_func=lambda x: f"#{x} {df_handlers[df_handlers['id']==x]['name'].values[0]} ({df_handlers[df_handlers['id']==x]['product'].values[0] or '-'}/{df_handlers[df_handlers['id']==x]['step'].values[0] or '-'}) - {df_handlers[df_handlers['id']==x]['condition_desc'].values[0] or ''}"
                    )
                else:
                    st.info("등록된 Handler Recipe가 없습니다. 상단 '➕ 신규 Handler Recipe 등록' 버튼을 눌러 등록하세요.")
                    sel_h_id = None

            with col_r_edit:
                if sel_h_id:
                    with db.get_connection() as conn:
                        r_cur = conn.execute("""
                            SELECT r.*, rc.product, rc.step, rc.module, rc.purpose, rc.condition_desc
                            FROM recipes r
                            LEFT JOIN recipe_conditions rc ON r.id = rc.handler_id
                            WHERE r.id = ?
                        """, (sel_h_id,)).fetchone()
                    cur_h = dict(r_cur) if r_cur else {}

                    if cur_h:
                        st.markdown(f"###### ✏️ #{cur_h['id']} Handler 상세 및 수정")
                        subtab_h_spec, subtab_h_images = st.tabs(["스펙 & 공정 조건", "📷 Align/참조 이미지"])

                        with subtab_h_spec:
                            with st.form(f"edit_h_form_{sel_h_id}"):
                                eh_name = st.text_input("Handler Recipe 명칭*", value=cur_h.get('name', ''))
                                eh_ver = st.text_input("버전*", value=cur_h.get('version', ''))
                                
                                st.markdown("###### 📌 공정 조건 매핑 정보")
                                c_eh1, c_eh2 = st.columns(2)
                                with c_eh1:
                                    prods = db.get_master_names("Product")
                                    eh_prod = st.selectbox("Product*", prods, index=prods.index(cur_h['product']) if cur_h.get('product') in prods else 0)
                                    steps = db.get_master_names("Step")
                                    eh_step = st.selectbox("Step*", steps, index=steps.index(cur_h['step']) if cur_h.get('step') in steps else 0)
                                with c_eh2:
                                    mods = db.get_master_names("Module")
                                    eh_mod = st.selectbox("Module*", mods, index=mods.index(cur_h['module']) if cur_h.get('module') in mods else 0)
                                    purps = db.get_master_names("Purpose")
                                    eh_purp = st.selectbox("Purpose*", purps, index=purps.index(cur_h['purpose']) if cur_h.get('purpose') in purps else 0)
                                
                                eh_cond_desc = st.text_input(
                                    "동일 조건 내 구분 설명 (Condition Description)*",
                                    value=cur_h.get('condition_desc', '') or '',
                                    help="동일한 Product+Step+Module+Purpose 조건에 여러 Handler가 존재할 때 차이점을 설명 (예: '야간 조도 보정용', '표준 양산용', 'EQP-02 전용')"
                                )
                                eh_rec_desc = st.text_input("기본 설명 (Description)", value=cur_h.get('description', '') or '')
                                eh_xml = st.text_area("파라미터 / XML 내용", value=cur_h.get('xml_content', '') or '', height=120)

                                if st.form_submit_button("수정 저장", use_container_width=True):
                                    if not eh_name.strip() or not eh_ver.strip():
                                        st.error("명칭과 버전은 필수입니다.")
                                    else:
                                        db.update_recipe(sel_h_id, eh_name.strip(), eh_ver.strip(), eh_rec_desc, eh_xml)
                                        db.update_handler_condition(sel_h_id, eh_prod, eh_step, eh_mod, eh_purp, eh_cond_desc.strip())
                                        st.success("Handler 및 공정 조건/설명이 수정되었습니다.")
                                        st.rerun()

                            with st.popover(f"🗑️ #{cur_h['id']} 완전 삭제"):
                                st.warning("이 Handler Recipe 및 연결된 조건/이미지가 함께 삭제됩니다. 계속할까요?")
                                if st.button("확인 후 삭제", key=f"del_h_{sel_h_id}", type="primary"):
                                    db.delete_recipe(sel_h_id)
                                    st.success("삭제되었습니다.")
                                    st.rerun()

                        with subtab_h_images:
                            pasted_align_img = None
                            if HAS_PASTE_BTN:
                                align_paste_result = paste_image_button(
                                    label="📋 클립보드 붙여넣기 (Ctrl+V)",
                                    background_color="#2b5c8f",
                                    text_color="#ffffff",
                                    key=f"paste_align_h_{sel_h_id}"
                                )
                                if align_paste_result.image_data is not None:
                                    pasted_align_img = align_paste_result.image_data
                            
                            up_align_file = st.file_uploader("또는 이미지 파일 업로드", type=["png", "jpg", "jpeg", "bmp"], key=f"up_align_h_{sel_h_id}")
                            if up_align_file:
                                pasted_align_img = Image.open(up_align_file)

                            img_tag = st.selectbox("이미지 태그/구분", ["ALIGN", "PATTERN", "MASTER", "DEFECT", "REFERENCE"], key=f"tag_h_{sel_h_id}")

                            if pasted_align_img:
                                st.image(pasted_align_img, caption="입력된 이미지", width=180)
                                if st.button("이 Align 이미지 저장", key=f"save_img_h_{sel_h_id}", use_container_width=True):
                                    img_dir = os.path.join(os.path.dirname(__file__), "data", "recipe_images")
                                    os.makedirs(img_dir, exist_ok=True)
                                    fname = f"recipe_{sel_h_id}_{img_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                    fpath = os.path.join(img_dir, fname)
                                    pasted_align_img.save(fpath)
                                    db.add_recipe_image(sel_h_id, fname, fpath, tag=img_tag)
                                    st.success("Align 이미지가 추가되었습니다.")
                                    st.rerun()

                            h_images = db.get_recipe_images(sel_h_id)
                            st.write("")
                            st.markdown(f"###### 🖼️ 등록된 Align 이미지 ({len(h_images)}건)")
                            if h_images:
                                img_cols = st.columns(2)
                                for idx, img_item in enumerate(h_images):
                                    if os.path.exists(img_item['file_path']):
                                        with img_cols[idx % 2]:
                                            st.markdown(f"<div class='img-box'><b>[{img_item['tag']}]</b> {img_item['file_name']}", unsafe_allow_html=True)
                                            st.image(img_item['file_path'], use_column_width=True)
                                            b1, b2 = st.columns([6, 4])
                                            with b1:
                                                with st.popover("🔍 확대"):
                                                    st.image(img_item['file_path'], caption=f"{img_item['tag']} - {img_item['file_name']}", use_column_width=True)
                                            with b2:
                                                if st.button("🗑️삭제", key=f"del_h_img_{img_item['id']}"):
                                                    db.delete_recipe_image(img_item['id'])
                                                    st.success("삭제 완료")
                                                    st.rerun()
                                            st.markdown("</div>", unsafe_allow_html=True)
                            else:
                                st.caption("등록된 Align 이미지가 없습니다.")
                else:
                    st.caption("좌측 목록에서 항목을 선택하면 수정/이미지 등록이 가능합니다.")

        else:
            # VISION RECIPE 관리
            with c_top_btn:
                st.write("")
                with st.popover("➕ 신규 Vision Recipe 등록", use_container_width=True):
                    with st.form("new_vision_form_top"):
                        nv_name = st.text_input("Vision Recipe 이름*", placeholder="예: VIS_ALIGN_CAM2", key="top_v_name")
                        nv_ver = st.text_input("버전*", value="v1.0", key="top_v_ver")
                        nv_desc = st.text_input("설명", placeholder="공용 Align 비전", key="top_v_desc")
                        default_xml_v = """<Vision>
  <Exposure>25</Exposure>
  <Gain>1.2</Gain>
</Vision>"""
                        nv_xml = st.text_area("파라미터 / XML", value=default_xml_v, height=100, key="top_v_xml")
                        if st.form_submit_button("Vision Recipe 등록 완료", type="primary", use_container_width=True):
                            if nv_name.strip() and nv_ver.strip():
                                db.create_vision_recipe(nv_name, nv_ver, nv_desc, nv_xml)
                                st.success("Vision Recipe가 등록되었습니다.")
                                st.rerun()
                            else:
                                st.error("명칭과 버전은 필수입니다.")

            with db.get_connection() as conn:
                recipes_df = pd.read_sql_query("SELECT id, name, version, description, created_at FROM recipes WHERE recipe_type = 'VISION' ORDER BY id DESC", conn)

            col_v_tbl, col_v_edit = st.columns([5.5, 4.5])
            with col_v_tbl:
                st.markdown("###### 📷 Vision Recipe 목록 (공용 참조 가능)")
                if not recipes_df.empty:
                    st.dataframe(recipes_df, use_container_width=True, hide_index=True)
                    v_ids = [int(x) for x in recipes_df['id'].tolist()]
                    sel_v_id = st.selectbox("수정/조회할 Vision Recipe 선택", v_ids, format_func=lambda x: f"#{x} {recipes_df[recipes_df['id']==x]['name'].values[0]} ({recipes_df[recipes_df['id']==x]['version'].values[0]})")
                else:
                    st.info("등록된 Vision Recipe가 없습니다. 상단 '➕ 신규 Vision Recipe 등록' 버튼을 눌러 등록하세요.")
                    sel_v_id = None

            with col_v_edit:
                if sel_v_id:
                    with db.get_connection() as conn:
                        r_v_cur = conn.execute("SELECT * FROM recipes WHERE id = ?", (sel_v_id,)).fetchone()
                    cur_v = dict(r_v_cur) if r_v_cur else {}

                    if cur_v:
                        st.markdown(f"###### ✏️ #{cur_v['id']} Vision 상세 및 Align 이미지 관리")
                        with st.form(f"edit_v_form_{sel_v_id}"):
                            ev_name = st.text_input("Vision Recipe 명칭*", value=cur_v.get('name', ''))
                            ev_ver = st.text_input("버전*", value=cur_v.get('version', ''))
                            ev_desc = st.text_input("설명", value=cur_v.get('description', '') or '')
                            ev_xml = st.text_area("파라미터 / XML", value=cur_v.get('xml_content', '') or '', height=120)
                            if st.form_submit_button("Vision 수정 저장"):
                                db.update_recipe(sel_v_id, ev_name.strip(), ev_ver.strip(), ev_desc, ev_xml)
                                st.success("수정 완료되었습니다.")
                                st.rerun()

                        with st.popover(f"🗑️ #{cur_v['id']} Vision 완전 삭제"):
                            st.warning("이 Vision Recipe 및 연결 이미지가 삭제됩니다. 계속할까요?")
                            if st.button("확인 후 삭제", key=f"del_v_{sel_v_id}", type="primary"):
                                db.delete_recipe(sel_v_id)
                                st.success("삭제되었습니다.")
                                st.rerun()

                        st.divider()
                        st.markdown("###### ➕ Align 이미지 추가 (Ctrl+V)")
                        pasted_align_v = None
                        if HAS_PASTE_BTN:
                            align_paste_v = paste_image_button(
                                label="📋 클립보드 붙여넣기 (Ctrl+V)",
                                background_color="#2b5c8f",
                                text_color="#ffffff",
                                key=f"paste_v_{sel_v_id}"
                            )
                            if align_paste_v.image_data is not None:
                                pasted_align_v = align_paste_v.image_data
                        
                        up_align_v = st.file_uploader("또는 이미지 파일 업로드", type=["png", "jpg", "jpeg", "bmp"], key=f"up_v_{sel_v_id}")
                        if up_align_v:
                            pasted_align_v = Image.open(up_align_v)

                        tag_v = st.selectbox("이미지 태그", ["ALIGN", "PATTERN", "MASTER", "DEFECT", "REFERENCE"], key=f"tag_v_{sel_v_id}")

                        if pasted_align_v:
                            st.image(pasted_align_v, caption="입력된 이미지", width=180)
                            if st.button("Vision Align 이미지 저장", key=f"save_v_img_{sel_v_id}", use_container_width=True):
                                img_dir = os.path.join(os.path.dirname(__file__), "data", "recipe_images")
                                os.makedirs(img_dir, exist_ok=True)
                                fname = f"recipe_{sel_v_id}_{tag_v}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                fpath = os.path.join(img_dir, fname)
                                pasted_align_v.save(fpath)
                                db.add_recipe_image(sel_v_id, fname, fpath, tag=tag_v)
                                st.success("Align 이미지가 저장되었습니다.")
                                st.rerun()

                        v_images = db.get_recipe_images(sel_v_id)
                        if v_images:
                            v_img_cols = st.columns(2)
                            for idx, img_item in enumerate(v_images):
                                if os.path.exists(img_item['file_path']):
                                    with v_img_cols[idx % 2]:
                                        st.markdown(f"<div class='img-box'><b>[{img_item['tag']}]</b> {img_item['file_name']}", unsafe_allow_html=True)
                                        st.image(img_item['file_path'], use_column_width=True)
                                        vb1, vb2 = st.columns([6, 4])
                                        with vb1:
                                            with st.popover("🔍 확대"):
                                                st.image(img_item['file_path'], caption=f"{img_item['tag']} - {img_item['file_name']}", use_column_width=True)
                                        with vb2:
                                            if st.button("🗑️삭제", key=f"del_v_img_{img_item['id']}"):
                                                db.delete_recipe_image(img_item['id'])
                                                st.success("삭제 완료")
                                                st.rerun()
                                        st.markdown("</div>", unsafe_allow_html=True)

    with tab_rel:
        st.markdown("##### 🔗 Handler ↔ Vision N:M 참조 관계 구성 및 순서 조정")
        with db.get_connection() as conn:
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'HANDLER'").fetchall()]
            visions = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'VISION'").fetchall()]
            mappings = [dict(r) for r in conn.execute("""
                SELECT m.id, h.name as h_name, h.version as h_ver, v.name as v_name, v.version as v_ver, m.seq_order
                FROM handler_vision_map m
                JOIN recipes h ON m.handler_id = h.id
                JOIN recipes v ON m.vision_id = v.id
                ORDER BY h.name, m.seq_order ASC
            """).fetchall()]

        c_map1, c_map2 = st.columns([6, 4])
        with c_map1:
            st.markdown("###### 현재 연결된 Handler-Vision 관계 목록")
            if mappings:
                df_maps = pd.DataFrame(mappings)
                st.dataframe(df_maps, use_container_width=True, hide_index=True)
                map_ids = [int(x) for x in df_maps['id'].tolist()]
                sel_map_id = st.selectbox("삭제할 연결 관계 선택", map_ids, format_func=lambda x: f"#{x} Handler: {df_maps[df_maps['id']==x]['h_name'].values[0]} ↔ Vision: {df_maps[df_maps['id']==x]['v_name'].values[0]}")
                if st.button("🗑️ 선택된 연결 관계 해제", key=f"del_map_{sel_map_id}"):
                    db.delete_handler_vision_map(sel_map_id)
                    st.success("연결이 해제되었습니다.")
                    st.rerun()
            else:
                st.info("등록된 Handler-Vision 참조 관계가 없습니다.")

        with c_map2:
            st.markdown("###### 신규 참조 연결 추가")
            if handlers and visions:
                with st.form("new_map_form"):
                    sel_h = st.selectbox("Handler Recipe*", handlers, format_func=lambda x: x['label'] if x else "")
                    sel_v = st.selectbox("Vision Recipe*", visions, format_func=lambda x: x['label'] if x else "")
                    seq_ord = st.number_input("참조 순서 (Sequence)*", min_value=1, value=1)
                    if st.form_submit_button("참조 연결 저장"):
                        if sel_h and sel_v:
                            with db.get_connection() as conn:
                                conn.execute("""
                                    INSERT OR IGNORE INTO handler_vision_map (handler_id, vision_id, seq_order)
                                    VALUES (?, ?, ?)
                                """, (sel_h['id'], sel_v['id'], seq_ord))
                                conn.commit()
                            st.success("연결 완료되었습니다.")
                            st.rerun()
            else:
                st.warning("Handler와 Vision Recipe가 최소 1개 이상 등록되어 있어야 합니다.")

    # --- 탭 4: 공유 Vision 영향도 분석 ---
    with tab_impact:
        st.markdown("##### ⚠️ 공유 Vision Recipe 수정 시 영향도 분석 (역추적)")
        with db.get_connection() as conn:
            visions = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'VISION'").fetchall()]

        if visions:
            sel_target_v = st.selectbox("영향 범위를 조회할 Vision Recipe 선택", visions, format_func=lambda x: x['label'] if x else "")
            if sel_target_v and 'id' in sel_target_v:
                with db.get_connection() as conn:
                    impacts = [dict(r) for r in conn.execute("""
                        SELECT h.name as handler_name, h.version as handler_version, h.description, m.seq_order
                        FROM handler_vision_map m
                        JOIN recipes h ON m.handler_id = h.id
                        WHERE m.vision_id = ?
                        ORDER BY h.name ASC
                    """, (sel_target_v['id'],)).fetchall()]
                if impacts:
                    st.warning(f"⚠️ **{sel_target_v['label']}** 수정 시 다음 **{len(impacts)}개**의 Handler Recipe가 직접적인 영향을 받습니다.")
                    st.dataframe(pd.DataFrame(impacts), use_container_width=True)
                else:
                    st.success("현재 해당 Vision Recipe를 참조하고 있는 Handler Recipe가 없습니다. 안전하게 수정할 수 있습니다.")
        else:
            st.info("등록된 Vision Recipe가 없습니다.")

    # --- 탭 5: Code 매핑 이력 관리 (MD-04) ---
    with tab_code_mgmt:
        st.markdown("##### 📜 PKG/Device Code 매핑 이력 및 재사용 관리 (MD-04)")
        st.caption("재사용되는 디바이스 Code와 공정 조건의 시점별 유효 기간, 변경 사유 및 확실성을 무손실 이력으로 누적 관리합니다.")

        col_cm1, col_cm2 = st.columns([4, 6])
        with col_cm1:
            st.markdown("###### ➕ Code 매핑 신규 / 갱신 등록")
            with st.form("new_code_map_form"):
                in_code = st.text_input("Device / PKG Code*", placeholder="예: AAA, B01")
                in_prod = st.selectbox("Product*", db.get_master_names("Product"))
                in_mod = st.selectbox("Module*", db.get_master_names("Module"))
                in_purp = st.selectbox("Purpose*", db.get_master_names("Purpose"))
                in_cert = st.selectbox("확실성 (Certainty)*", ["확정", "추정", "검토필요"])
                in_user = st.text_input("작업자*", value="홍길동")
                in_reason = st.text_input("매핑 근거 / 사유*", placeholder="예: 신규 디바이스 도입에 따른 기준 매핑")
                if st.form_submit_button("Code 매핑 저장 (기존 매핑 무손실 종료)", use_container_width=True):
                    if not in_code.strip() or not in_reason.strip():
                        st.error("Code와 매핑 근거는 필수 입력입니다.")
                    else:
                        db.add_or_update_code_mapping(in_code.strip(), in_prod, in_mod, in_purp, in_reason.strip(), in_cert, in_user)
                        st.success(f"Code '{in_code}' 매핑이 이력으로 등록되었습니다.")
                        st.rerun()

        with col_cm2:
            st.markdown("###### 📋 Code 매핑 타임라인 이력")
            filter_code = st.selectbox("조회할 Code 선택 (전체 조회 가능)", ["전체"] + db.get_master_names("DeviceCode"))
            hist_rows = db.get_code_mapping_history(None if filter_code == "전체" else filter_code)

            if hist_rows:
                df_hist = pd.DataFrame(hist_rows)
                df_hist['상태'] = df_hist['valid_to'].apply(lambda x: "🟢 현재 유효" if pd.isna(x) else f"⚪ 종료 ({x})")
                show_cols = ['id', 'code', 'product', 'module', 'purpose', 'certainty', '상태', 'valid_from', 'reason', 'created_by']
                st.dataframe(df_hist[show_cols], use_container_width=True, hide_index=True)
            else:
                st.info("등록된 Code 매핑 이력이 없습니다.")

# ========================================================
# 3. 🚀 설비 적용 & 횡전개 검증 (Deployment & Diff)
# ========================================================
elif menu == "🚀 3. 설비 적용 & 횡전개 검증":
    st.title("🚀 설비 적용 & 횡전개 검증 (Deployment & Diff)")
    st.caption("설비별 목표 Recipe 상태 관리, 다중 설비 일괄 횡전개 추적 및 로컬/USB 설비 폴더 전체 파일 트리 Diff 비교 검증을 지원합니다.")

    tab_eqp_stat, tab_deploy_plan, tab_diff_val = st.tabs([
        "📊 설비별 적용 현황 (DP-01)",
        "🚀 횡전개 계획 및 검증 트래커 (DP-02~05)",
        "🔬 파일 비교 검증 (FV-01 ~ FV-05)"
    ])

    # --- 탭 1: 설비별 적용 현황 ---
    with tab_eqp_stat:
        st.markdown("##### 📌 설비별 목표 vs 현장 확인 버전 매트릭스")
        with db.get_connection() as conn:
            eqp_list = db.get_master_names("Equipment")
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'HANDLER'").fetchall()]
            df_status = pd.read_sql_query("""
                SELECT s.equipment, r.name as handler_name, r.version as target_version,
                       s.verified_version, s.sync_status, s.last_verified_at, s.verifier
                FROM equipment_recipe_status s
                LEFT JOIN recipes r ON s.handler_id = r.id
            """, conn)

        c_eq1, c_eq2 = st.columns([7, 3])
        with c_eq1:
            if not df_status.empty:
                st.dataframe(df_status, use_container_width=True, hide_index=True)
            else:
                st.info("등록된 설비별 적용 상태가 없습니다. 우측 폼에서 목표 설비 상태를 설정하세요.")
        with c_eq2:
            if eqp_list and handlers:
                with st.form("set_eqp_status_form"):
                    st.markdown("###### 설비별 목표/검증 상태 갱신")
                    t_eq = st.selectbox("설비 선택*", eqp_list)
                    t_hd = st.selectbox("적용 목표 Handler*", handlers, format_func=lambda x: x['label'] if x else "")
                    v_ver = st.text_input("현장 확인된 실제 버전", placeholder="예: v1.0")
                    sync_s = st.selectbox("검증 상태*", ["일치", "불일치", "미확인"])
                    v_user = st.text_input("검증자", placeholder="검증 엔지니어")
                    if st.form_submit_button("상태 저장"):
                        if t_eq and t_hd:
                            with db.get_connection() as conn:
                                conn.execute("""
                                    INSERT INTO equipment_recipe_status (equipment, handler_id, verified_version, sync_status, last_verified_at, verifier)
                                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                                    ON CONFLICT(equipment) DO UPDATE SET
                                        handler_id=excluded.handler_id,
                                        verified_version=excluded.verified_version,
                                        sync_status=excluded.sync_status,
                                        last_verified_at=CURRENT_TIMESTAMP,
                                        verifier=excluded.verifier
                                """, (t_eq, t_hd['id'], v_ver, sync_s, v_user))
                                conn.commit()
                            st.success("설비 상태가 저장되었습니다.")
                            st.rerun()
            else:
                st.warning("기준정보의 설비(Equipment) 및 Handler Recipe가 먼저 등록되어야 합니다.")

    # --- 탭 2: 횡전개 계획 및 검증 트래커 ---
    with tab_deploy_plan:
        st.markdown("##### 🚀 다중 설비 일괄 횡전개 계획 수립")
        with db.get_connection() as conn:
            req_list = [dict(r) for r in conn.execute("SELECT id, title FROM work_requests ORDER BY id DESC").fetchall()]
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'HANDLER'").fetchall()]
            all_eqps = db.get_master_names("Equipment")

        with st.expander("➕ 신규 횡전개 계획 등록 (Handler + 참조 Vision 일괄 전개)", expanded=False):
            if handlers and all_eqps:
                with st.form("new_dp_form"):
                    dp_title = st.text_input("횡전개 프로젝트명*", placeholder="예: [Prod_Alpha] Step01 파라미터 전 설비 횡전개")
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        dp_h = st.selectbox("기준 Handler Recipe (종속 Vision 자동 포함)*", handlers, format_func=lambda x: x['label'] if x else "")
                        req_choices = [None] + req_list
                        dp_req = st.selectbox("연계 업무 요청", req_choices, format_func=lambda x: f"#{x['id']} {x['title']}" if x else "없음")
                    with col_d2:
                        dp_targets = st.multiselect("대상 설비 다중 선택*", all_eqps, default=all_eqps)
                        dp_creator = st.text_input("계획 수립자", placeholder="홍길동")
                    dp_memo = st.text_input("횡전개 사유", placeholder="조도 변경 파라미터 양산 설비 횡전개")
                    if st.form_submit_button("횡전개 계획 생성"):
                        if not dp_title or not dp_title.strip() or not dp_targets or not dp_h:
                            st.error("프로젝트명, 기준 Recipe, 대상 설비를 올바르게 지정해주세요.")
                        else:
                            with db.get_connection() as conn:
                                cur = conn.cursor()
                                cur.execute("""
                                    INSERT INTO deployments (title, handler_id, request_id, reason, created_by)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (dp_title.strip(), dp_h['id'], dp_req['id'] if dp_req else None, dp_memo, dp_creator))
                                new_d_id = cur.lastrowid
                                for eq in dp_targets:
                                    cur.execute("INSERT INTO deployment_targets (deployment_id, equipment, status) VALUES (?, ?, '대기')", (new_d_id, eq))
                                conn.commit()
                            st.success("횡전개 계획이 등록되었습니다.")
                            st.rerun()
            else:
                st.warning("Handler Recipe 및 설비 기준정보가 필요합니다.")

        st.divider()
        st.markdown("##### 📋 횡전개 프로젝트 현황 및 설비별 검증")
        with db.get_connection() as conn:
            deployments = [dict(r) for r in conn.execute("""
                SELECT d.id, d.title, r.name as handler_name, r.version as handler_version, d.status, d.created_at
                FROM deployments d
                JOIN recipes r ON d.handler_id = r.id
                ORDER BY d.id DESC
            """).fetchall()]

        if deployments:
            for dep in deployments:
                with st.expander(f"📦 #{dep['id']} {dep['title']} (기준: {dep['handler_name']} {dep['handler_version']}) - 상태: [{dep['status']}]", expanded=True):
                    with db.get_connection() as conn:
                        targets = [dict(r) for r in conn.execute("SELECT * FROM deployment_targets WHERE deployment_id = ?", (dep['id'],)).fetchall()]

                    c_tg1, c_tg2 = st.columns([7, 3])
                    with c_tg1:
                        df_tg = pd.DataFrame(targets)
                        if not df_tg.empty:
                            show_cols = ['equipment', 'status', 'operator', 'applied_at', 'verifier', 'verified_at', 'hold_reason']
                            st.dataframe(df_tg[show_cols], use_container_width=True, hide_index=True)
                    with c_tg2:
                        target_eqps = [t['equipment'] for t in targets]
                        if target_eqps:
                            with st.form(f"up_target_{dep['id']}"):
                                st.markdown("###### 대상 설비 상태 갱신")
                                sel_eq = st.selectbox("설비 선택", target_eqps)
                                n_stat = st.selectbox("상태", ["대기", "진행중", "검증완료", "실패", "보류"])
                                n_op = st.text_input("작업자")
                                n_vr = st.text_input("검증자")
                                n_hold = st.text_input("보류/실패 사유", placeholder="설비 점검 등")
                                if st.form_submit_button("상태 갱신"):
                                    with db.get_connection() as conn:
                                        conn.execute("""
                                            UPDATE deployment_targets
                                            SET status = ?, operator = ?, verifier = ?, hold_reason = ?,
                                                applied_at = CASE WHEN ? IN ('진행중', '검증완료') THEN CURRENT_TIMESTAMP ELSE applied_at END,
                                                verified_at = CASE WHEN ? = '검증완료' THEN CURRENT_TIMESTAMP ELSE verified_at END
                                            WHERE deployment_id = ? AND equipment = ?
                                        """, (n_stat, n_op, n_vr, n_hold, n_stat, n_stat, dep['id'], sel_eq))
                                        conn.commit()
                                    st.success("갱신되었습니다.")
                                    st.rerun()

                        if st.button("🗑️ 프로젝트 삭제", key=f"del_dep_{dep['id']}"):
                            db.delete_deployment(dep['id'])
                            st.success("횡전개 프로젝트가 삭제되었습니다.")
                            st.rerun()
        else:
            st.info("등록된 횡전개 프로젝트가 없습니다.")

    # --- 탭 3: 파일 비교 검증 (FV-01 ~ FV-05) ---
    with tab_diff_val:
        st.markdown("##### 🔬 설비 수집 폴더 다중 파일 트리 & XML Diff 검증 (FV-01 ~ FV-05)")
        st.caption("압축할 필요 없이 USB나 로컬 폴더 경로를 직접 입력하여 전체 파일의 해시 일치 여부와 세부 Diff를 분석합니다.")

        diff_sub_mode = st.radio("비교 모드 선택", ["📁 설비 수집 폴더 전체 파일 트리 대조 (권장)", "📝 단일 텍스트 / XML 파라미터 직접 비교"], horizontal=True)

        if diff_sub_mode == "📁 설비 수집 폴더 전체 파일 트리 대조 (권장)":
            col_p1, col_p2 = st.columns(2)
            default_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_recipe_folder", "source_pkg"))
            default_tgt = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample_recipe_folder", "target_eqp01"))

            with col_p1:
                src_folder = st.text_input("기준(Source A) Recipe 폴더 경로", value=default_src, help="승인된 기준 Recipe가 보관된 폴더")
            with col_p2:
                tgt_folder = st.text_input("설비 수집(Target B) 폴더 경로", value=default_tgt, help="현장 설비 또는 USB에서 복사해온 폴더")

            if st.button("🔍 폴더 전체 파일 트리 Diff 분석 실행", type="primary", use_container_width=True):
                st.session_state['run_folder_diff'] = True

            if st.session_state.get('run_folder_diff', False):
                if not os.path.exists(src_folder) or not os.path.exists(tgt_folder):
                    st.error("입력한 폴더 경로가 존재하지 않습니다. 경로를 확인해주세요.")
                else:
                    src_files = db.scan_recipe_folder(src_folder)
                    tgt_files = db.scan_recipe_folder(tgt_folder)

                    all_rel_paths = sorted(list(set(src_files.keys()) | set(tgt_files.keys())))

                    res_rows = []
                    cnt_identical = 0
                    cnt_modified = 0
                    cnt_missing = 0
                    cnt_added = 0

                    for p in all_rel_paths:
                        in_src = p in src_files
                        in_tgt = p in tgt_files

                        if in_src and in_tgt:
                            if src_files[p]['hash'] == tgt_files[p]['hash']:
                                status = "🟢 일치"
                                cnt_identical += 1
                            else:
                                status = "🟡 내용 변경"
                                cnt_modified += 1
                            size_info = f"{src_files[p]['size']} B ➔ {tgt_files[p]['size']} B"
                        elif in_src and not in_tgt:
                            status = "🔴 누락 (설비에 없음)"
                            cnt_missing += 1
                            size_info = f"{src_files[p]['size']} B"
                        else:
                            status = "🔵 추가 (신규 파일)"
                            cnt_added += 1
                            size_info = f"{tgt_files[p]['size']} B"

                        res_rows.append({
                            "파일 상대 경로": p,
                            "상태": status,
                            "파일 크기": size_info,
                            "기준 SHA256": src_files[p]['hash'][:10] + "..." if in_src else "-",
                            "설비 SHA256": tgt_files[p]['hash'][:10] + "..." if in_tgt else "-"
                        })

                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.markdown(f"<div class='metric-card'><span>🟢 일치 파일</span><h3>{cnt_identical}건</h3></div>", unsafe_allow_html=True)
                    with m2:
                        st.markdown(f"<div class='metric-card'><span>🟡 변경 파일</span><h3>{cnt_modified}건</h3></div>", unsafe_allow_html=True)
                    with m3:
                        st.markdown(f"<div class='metric-card'><span>🔴 누락 파일</span><h3>{cnt_missing}건</h3></div>", unsafe_allow_html=True)
                    with m4:
                        st.markdown(f"<div class='metric-card'><span>🔵 추가 파일</span><h3>{cnt_added}건</h3></div>", unsafe_allow_html=True)

                    st.markdown("##### 📋 파일별 대조 매트릭스")
                    df_res = pd.DataFrame(res_rows)
                    st.dataframe(df_res, use_container_width=True, hide_index=True)

                    actionable_paths = [r['파일 상대 경로'] for r in res_rows if r['상태'] != "🟢 일치"]
                    if actionable_paths:
                        st.divider()
                        st.markdown("##### 🔬 변경/차이 파일 세부 Diff 뷰어")
                        sel_diff_file = st.selectbox("세부 내용을 비교할 파일 선택", actionable_paths)

                        src_file_info = src_files.get(sel_diff_file)
                        tgt_file_info = tgt_files.get(sel_diff_file)

                        is_image = any(sel_diff_file.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp"])

                        if is_image:
                            st.info(f"🖼️ 이미지 파일 비교: `{sel_diff_file}`")
                            img_c1, img_c2 = st.columns(2)
                            with img_c1:
                                st.markdown("**[기준 Source A]**")
                                if src_file_info and os.path.exists(src_file_info['full_path']):
                                    st.image(src_file_info['full_path'], use_column_width=True)
                                else:
                                    st.warning("기준 이미지가 존재하지 않습니다.")
                            with img_c2:
                                st.markdown("**[설비 Target B]**")
                                if tgt_file_info and os.path.exists(tgt_file_info['full_path']):
                                    st.image(tgt_file_info['full_path'], use_column_width=True)
                                else:
                                    st.warning("설비 이미지가 존재하지 않습니다.")
                        else:
                            text_src = ""
                            text_tgt = ""
                            if src_file_info:
                                try:
                                    with open(src_file_info['full_path'], "r", encoding="utf-8", errors="ignore") as f:
                                        text_src = f.read()
                                except Exception as e:
                                    text_src = f"[읽기 오류: {e}]"

                            if tgt_file_info:
                                try:
                                    with open(tgt_file_info['full_path'], "r", encoding="utf-8", errors="ignore") as f:
                                        text_tgt = f.read()
                                except Exception as e:
                                    text_tgt = f"[읽기 오류: {e}]"

                            diff_lines = list(difflib.unified_diff(
                                text_src.splitlines(keepends=True),
                                text_tgt.splitlines(keepends=True),
                                fromfile=f"Source/{sel_diff_file}",
                                tofile=f"Target/{sel_diff_file}"
                            ))

                            diff_html = []
                            for line in diff_lines:
                                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                                if escaped.startswith("+") and not escaped.startswith("+++"):
                                    diff_html.append(f"<span class='diff-added'>{escaped}</span>")
                                elif escaped.startswith("-") and not escaped.startswith("---"):
                                    diff_html.append(f"<span class='diff-removed'>{escaped}</span>")
                                else:
                                    diff_html.append(escaped)

                            st.markdown(f"<div class='diff-box'><pre>{''.join(diff_html)}</pre></div>", unsafe_allow_html=True)
                    else:
                        st.success("🎉 기준 폴더와 설비 폴더의 모든 파일이 100% 동일합니다.")

        else:
            with db.get_connection() as conn:
                all_recipes = [dict(r) for r in conn.execute("SELECT id, recipe_type, name, version, xml_content FROM recipes ORDER BY id DESC").fetchall()]

            c_df1, c_df2 = st.columns(2)
            default_text_a = """<Recipe>
  <Align>
    <Threshold>120</Threshold>
    <Timeout>5000</Timeout>
  </Align>
</Recipe>"""
            default_text_b = """<Recipe>
  <Align>
    <Threshold>145</Threshold>
    <Timeout>5000</Timeout>
    <RetryCount>3</RetryCount>
  </Align>
</Recipe>"""

            with c_df1:
                st.markdown("###### [기준 Source A]")
                if all_recipes:
                    r_a = st.selectbox("기준 Recipe A 선택", all_recipes, format_func=lambda x: f"[{x['recipe_type']}] {x['name']} ({x['version']})" if x else "", key="diff_a")
                    val_a = (r_a['xml_content'] if r_a and r_a.get('xml_content') else default_text_a)
                else:
                    st.info("등록된 Recipe가 없습니다. 텍스트를 직접 입력하세요.")
                    val_a = default_text_a
                text_a = st.text_area("기준 XML/텍스트 내용", value=val_a, height=220, key="txt_a")

            with c_df2:
                st.markdown("###### [비교 Target B]")
                if all_recipes:
                    r_b = st.selectbox("비교 대상 Recipe B 선택", all_recipes, format_func=lambda x: f"[{x['recipe_type']}] {x['name']} ({x['version']})" if x else "", key="diff_b")
                    val_b = (r_b['xml_content'] if r_b and r_b.get('xml_content') else default_text_b)
                else:
                    st.info("등록된 Recipe가 없습니다. 텍스트를 직접 입력하세요.")
                    val_b = default_text_b
                text_b = st.text_area("대상 XML/텍스트 내용", value=val_b, height=220, key="txt_b")

            st.write("")
            if st.button("🔍 Diff 파라미터 정밀 분석 실행", use_container_width=True, type="primary"):
                safe_text_a = text_a or ""
                safe_text_b = text_b or ""
                lines_a = safe_text_a.splitlines(keepends=True)
                lines_b = safe_text_b.splitlines(keepends=True)
                diff_lines = list(difflib.unified_diff(lines_a, lines_b, fromfile="Source_A", tofile="Target_B"))

                if not diff_lines:
                    st.success("✅ 두 파라미터 내용이 완전히 일치합니다.")
                else:
                    st.warning("⚠️ 차이점(Diff) 발견 - 변경 파라미터를 확인하세요.")
                    diff_html = []
                    for line in diff_lines:
                        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        if escaped.startswith("+") and not escaped.startswith("+++"):
                            diff_html.append(f"<span class='diff-added'>{escaped}</span>")
                        elif escaped.startswith("-") and not escaped.startswith("---"):
                            diff_html.append(f"<span class='diff-removed'>{escaped}</span>")
                        else:
                            diff_html.append(escaped)
                    st.markdown(f"<div class='diff-box'><pre>{''.join(diff_html)}</pre></div>", unsafe_allow_html=True)

# ========================================================
# 4. ⚙️ 기준정보 및 감사 관리 (Master Data & Audit)
# ========================================================
elif menu == "⚙️ 4. 기준정보 및 감사 관리":
    st.title("⚙️ 기준정보 및 감사 관리 (Master Data & Audit)")
    st.caption("공통 선택 항목의 완전한 CRUD(등록·수정·비활성화·삭제) 및 Recipe 변경 감사 로그를 관리합니다.")

    tab_master, tab_audit = st.tabs(["⚙️ 공통 기준정보 관리 (CRUD)", "📜 종합 변경 감사 로그 (Audit Log)"])

    # --- 탭 1: 기준정보 CRUD ---
    with tab_master:
        st.markdown("##### 📌 공통 기준정보 관리")
        categories = ["Product", "Step", "Module", "Purpose", "Department", "Equipment", "DeviceCode"]
        c_top1, c_top2 = st.columns([4, 6])
        with c_top1:
            sel_cat = st.selectbox("분류 카테고리 선택", categories)
        with c_top2:
            st.write("")
            with st.popover(f"➕ 신규 {sel_cat} 등록"):
                with st.form("add_master_form"):
                    new_item_name = st.text_input(f"신규 {sel_cat} 명칭*")
                    if st.form_submit_button("추가 완료"):
                        if new_item_name and new_item_name.strip():
                            db.add_master_data(sel_cat, new_item_name.strip())
                            st.success(f"'{new_item_name}' 등록되었습니다.")
                            st.rerun()
                        else:
                            st.error("명칭을 입력하세요.")

        items = db.get_master_data(sel_cat, active_only=False)
        st.write("")
        st.markdown(f"###### 현재 등록된 `{sel_cat}` 항목 목록 ({len(items)}개)")
        
        if items:
            for itm in items:
                col_i1, col_i2, col_i3, col_i4 = st.columns([4, 2, 2, 2])
                with col_i1:
                    u_name = st.text_input("명칭", value=itm.get('name', ''), key=f"name_{itm['id']}", label_visibility="collapsed")
                with col_i2:
                    u_act = st.checkbox("활성", value=bool(itm.get('is_active', 1)), key=f"act_{itm['id']}")
                with col_i3:
                    if st.button("수정 저장", key=f"save_{itm['id']}"):
                        db.update_master_data(itm['id'], u_name, 1 if u_act else 0)
                        st.success("수정 완료")
                        st.rerun()
                with col_i4:
                    if st.button("🗑️삭제", key=f"del_m_{itm['id']}"):
                        db.delete_master_data(itm['id'])
                        st.success("삭제 완료")
                        st.rerun()
        else:
            st.info(f"등록된 {sel_cat} 데이터가 없습니다.")

    # --- 탭 2: 종합 변경 감사 로그 ---
    with tab_audit:
        st.markdown("##### 📜 Recipe 파라미터 변경 이력 감사 로그")
        st.caption("작업 요청과 연결된 모든 Recipe 파라미터 수정 내역 및 평가 결과입니다.")
        with db.get_connection() as conn:
            df_hist = pd.read_sql_query("""
                SELECT rc.id, rc.request_id, wr.title as req_title, rc.target_type, rc.target_name,
                       rc.change_type, rc.before_val, rc.after_val, rc.change_reason, rc.evaluation_result, rc.created_at
                FROM recipe_changes rc
                LEFT JOIN work_requests wr ON rc.request_id = wr.id
                ORDER BY rc.id DESC
            """, conn)
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("등록된 변경 감사 이력이 없습니다.")
