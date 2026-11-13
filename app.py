import os
import streamlit as st
import pandas as pd
from PIL import Image
import database as db

try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BTN = True
except ImportError:
    HAS_PASTE_BTN = False

try:
    from streamlit_sortables import sort_items
    HAS_SORTABLES = True
except ImportError:
    HAS_SORTABLES = False

st.set_page_config(
    page_title="RecipeManager v1.6.0",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

URGENCY_STYLE = {
    "긴급": {"bg": "#fff5f5", "border": "#e53e3e", "badge": "🔴 긴급"},
    "높음": {"bg": "#fffaf0", "border": "#dd6b20", "badge": "🟠 높음"},
    "보통": {"bg": "#ebf8ff", "border": "#3182ce", "badge": "🔵 보통"},
    "낮음": {"bg": "#f7fafc", "border": "#a0aec0", "badge": "⚪ 낮음"},
}

# ==============================================================================
# 사이드바 내비게이션 (주요 2대 메뉴 우선 배치 + 보조 메뉴)
# ==============================================================================
with st.sidebar:
    st.markdown("## ⚙️ RecipeManager `v1.6.0`")
    st.caption("반도체 검사·계측 실무 통합 워크스페이스")

    menu = st.radio(
        "메뉴 선택",
        [
            "✅ 할 일",
            "🧩 레시피 확인",
            "⚙️ 레시피 등록 및 매핑",
            "🚀 설비 횡전개 및 Diff",
            "🛠️ 기준정보 및 백업",
        ],
        label_visibility="collapsed"
    )

    st.divider()
    with db.get_connection() as conn:
        open_cnt = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료'").fetchone()[0]
        urg_cnt = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료' AND urgency = '긴급'").fetchone()[0]
        hdl_cnt = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'HANDLER'").fetchone()[0]
        vis_cnt = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'VISION'").fetchone()[0]

    c_s1, c_s2 = st.columns(2)
    c_s1.metric("할 일", f"{open_cnt}건")
    c_s2.metric("🔴 긴급", f"{urg_cnt}건")
    c_s3, c_s4 = st.columns(2)
    c_s3.metric("Handler", f"{hdl_cnt}개")
    c_s4.metric("Vision", f"{vis_cnt}개")


# ==============================================================================
# [메인 1] ✅ 할 일 (키워드 목록 + 세부 정보 + 위아래/드래그 우선순위 + 완료 버튼 + 긴급도 색상)
# ==============================================================================
if menu == "✅ 할 일":
    c_head, c_done_tog, c_drag_tog, c_new = st.columns([4.2, 2.0, 2.0, 1.8])
    with c_head:
        st.subheader("✅ 할 일 목록 & 우선순위")
    with c_done_tog:
        st.write("")
        show_completed = st.toggle("완료된 일 표시", value=False)
    with c_drag_tog:
        st.write("")
        drag_mode = st.toggle("드래그로 순서 편집", value=False)
    with c_new:
        st.write("")
        with st.popover("➕ 새 할 일", use_container_width=True):
            with st.form("quick_add_todo"):
                t_kw = st.text_input("키워드 (제목)*", placeholder="예: Step01 Align 조도 보정")
                c_u1, c_u2 = st.columns(2)
                t_urg = c_u1.selectbox("긴급도", ["긴급", "높음", "보통", "낮음"], index=2)
                t_type = c_u2.selectbox("유형", ["할 일", "Recipe 변경", "Align Fail 조치", "신규 셋업", "횡전개", "파라미터 튜닝"])
                c_p1, c_p2, c_p3 = st.columns(3)
                t_prod = c_p1.selectbox("Product", [""] + db.get_master_names("Product"))
                t_step = c_p2.selectbox("Step", [""] + db.get_master_names("Step"))
                t_eqp = c_p3.selectbox("설비", [""] + db.get_master_names("Equipment"))
                t_due = st.text_input("목표 기한 (YYYY-MM-DD)", placeholder="예: 2026-11-20")
                t_desc = st.text_area("세부 정보", placeholder="상세 내용, 파라미터 목표, 조치 계획")
                if st.form_submit_button("할 일 등록", type="primary", use_container_width=True):
                    if not t_kw or not t_kw.strip():
                        st.error("키워드(제목)는 필수입니다.")
                    else:
                        new_id = db.create_todo(
                            title=t_kw.strip(),
                            content=t_desc,
                            urgency=t_urg,
                            req_type=t_type,
                            product=t_prod,
                            step=t_step,
                            equipment=t_eqp,
                            due_date=t_due.strip()
                        )
                        st.session_state["selected_todo_id"] = new_id
                        st.rerun()

    todos = db.get_todos(include_completed=show_completed)
    col_list, col_detail = st.columns([5.6, 4.4])

    with col_list:
        if not todos:
            st.info("표시할 할 일이 없습니다. 우측 상단 [➕ 새 할 일] 버튼으로 등록하세요.")
        elif drag_mode:
            st.caption("🖱️ 항목을 마우스로 위아래로 드래그한 뒤 [💾 드래그 순서 저장] 버튼을 누르면 즉시 반영됩니다.")
            if HAS_SORTABLES:
                labeled_items = [
                    f"#{t['id']} | [{t.get('urgency') or '보통'}] {t['title']}"
                    for t in todos
                ]
                sorted_labels = sort_items(labeled_items, direction="vertical")
                if st.button("💾 드래그 순서 저장", type="primary", use_container_width=True):
                    ordered_ids = []
                    for lbl in sorted_labels:
                        id_part = lbl.split("|")[0].replace("#", "").strip()
                        if id_part.isdigit():
                            ordered_ids.append(int(id_part))
                    if ordered_ids:
                        db.update_todo_orders_by_ids(ordered_ids)
                        st.success("우선순위가 저장되었습니다.")
                        st.rerun()
            else:
                st.warning("`streamlit-sortables` 패키지가 설치되어 있지 않습니다. 기본 ▲/▼ 버튼을 이용해 주세요.")
        else:
            for idx, item in enumerate(todos):
                urg = item.get("urgency") or "보통"
                style = URGENCY_STYLE.get(urg, URGENCY_STYLE["보통"])
                is_done = item["status"] == "완료"
                is_selected = (st.session_state.get("selected_todo_id") == item["id"])
                text_deco = "line-through" if is_done else "none"
                opacity = "0.6" if is_done else "1.0"
                outline = "2px solid #2b5c8f" if is_selected else "1px solid #e2e8f0"

                c_ord, c_card, c_act = st.columns([1.3, 7.1, 1.6])

                with c_ord:
                    b_up, b_dn = st.columns(2)
                    if b_up.button("▲", key=f"up_{item['id']}", disabled=(idx == 0), help="우선순위 위로"):
                        db.swap_todo_priority(item["id"], todos[idx - 1]["id"])
                        st.rerun()
                    if b_dn.button("▼", key=f"dn_{item['id']}", disabled=(idx == len(todos) - 1), help="우선순위 아래로"):
                        db.swap_todo_priority(item["id"], todos[idx + 1]["id"])
                        st.rerun()

                with c_card:
                    meta_txt = " · ".join([x for x in [item.get("product"), item.get("step"), item.get("equipment")] if x])
                    st.markdown(f"""
                    <div style="background:{style['bg']}; border-left:6px solid {style['border']};
                                border-top:{outline}; border-right:{outline}; border-bottom:{outline};
                                padding:8px 12px; border-radius:6px; opacity:{opacity}; margin-bottom:4px;">
                        <span style="font-size:12px; font-weight:700;">{style['badge']}</span>
                        <span style="font-size:14px; font-weight:700; text-decoration:{text_deco}; margin-left:6px; color:#1a202c;">
                            {item['title']}
                        </span>
                        <span style="font-size:12px; color:#4a5568; margin-left:8px;">{meta_txt}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"🔍 세부 정보 보기 (#{item['id']})", key=f"sel_{item['id']}", use_container_width=True):
                        st.session_state["selected_todo_id"] = item["id"]
                        st.rerun()

                with c_act:
                    btn_lbl = "↩️ 복구" if is_done else "✅ 완료"
                    if st.button(btn_lbl, key=f"done_{item['id']}", use_container_width=True):
                        db.toggle_todo_complete(item["id"], item["status"])
                        st.rerun()

    with col_detail:
        sel_id = st.session_state.get("selected_todo_id")
        if sel_id is None and todos:
            sel_id = todos[0]["id"]
            st.session_state["selected_todo_id"] = sel_id

        detail = db.get_todo_by_id(sel_id) if sel_id else None
        if detail:
            with st.container(border=True):
                h_col1, h_col2 = st.columns([7.5, 2.5])
                with h_col1:
                    st.markdown(f"#### 📌 #{detail['id']} {detail['title']}")
                with h_col2:
                    with st.popover("🗑️ 삭제", use_container_width=True):
                        st.warning("이 할 일과 첨부파일을 삭제할까요?")
                        if st.button("영구 삭제 확인", key=f"del_todo_{sel_id}", type="primary"):
                            db.delete_work_request(sel_id)
                            st.session_state["selected_todo_id"] = None
                            st.rerun()

                tab_edit, tab_evd = st.tabs(["📝 세부 정보 & 수정", "📎 증빙 이미지 (Ctrl+V)"])

                with tab_edit:
                    with st.form(f"todo_detail_form_{sel_id}"):
                        u_title = st.text_input("키워드 (제목)*", value=detail.get("title") or "")
                        c1, c2 = st.columns(2)
                        urg_opts = ["긴급", "높음", "보통", "낮음"]
                        cur_urg = detail.get("urgency") if detail.get("urgency") in urg_opts else "보통"
                        u_urg = c1.selectbox("긴급도", urg_opts, index=urg_opts.index(cur_urg))

                        stat_opts = ["접수", "진행중", "평가/검증", "완료", "보류"]
                        cur_stat = detail.get("status") if detail.get("status") in stat_opts else "접수"
                        u_stat = c2.selectbox("진행 상태", stat_opts, index=stat_opts.index(cur_stat))

                        c3, c4, c5 = st.columns(3)
                        prods = [""] + db.get_master_names("Product")
                        u_prod = c3.selectbox("Product", prods, index=prods.index(detail["product"]) if detail.get("product") in prods else 0)
                        steps = [""] + db.get_master_names("Step")
                        u_step = c4.selectbox("Step", steps, index=steps.index(detail["step"]) if detail.get("step") in steps else 0)
                        eqps = [""] + db.get_master_names("Equipment")
                        u_eqp = c5.selectbox("설비", eqps, index=eqps.index(detail["equipment"]) if detail.get("equipment") in eqps else 0)

                        c6, c7 = st.columns(2)
                        u_ass = c6.text_input("담당자", value=detail.get("assignee") or "")
                        u_due = c7.text_input("목표 기한", value=detail.get("due_date") or "")

                        u_content = st.text_area("세부 내용", value=detail.get("content") or "", height=160)
                        st.caption(f"등록: {detail.get('created_at') or '-'} | 최종 수정: {detail.get('updated_at') or '-'}")

                        if st.form_submit_button("💾 변경사항 저장", type="primary", use_container_width=True):
                            if not u_title.strip():
                                st.error("키워드를 입력하세요.")
                            else:
                                db.update_todo_detail(
                                    todo_id=sel_id,
                                    title=u_title,
                                    urgency=u_urg,
                                    status=u_stat,
                                    content=u_content,
                                    product=u_prod,
                                    step=u_step,
                                    equipment=u_eqp,
                                    assignee=u_ass,
                                    due_date=u_due
                                )
                                st.success("저장되었습니다.")
                                st.rerun()

                with tab_evd:
                    pasted_img = None
                    if HAS_PASTE_BTN:
                        p_res = paste_image_button(
                            label="📋 클립보드 이미지 붙여넣기 (Ctrl+V)",
                            background_color="#2b5c8f",
                            text_color="#ffffff"
                        )
                        if p_res.image_data is not None:
                            pasted_img = p_res.image_data

                    up_img = st.file_uploader("또는 이미지 파일 선택", type=["png", "jpg", "jpeg", "bmp"], key=f"evd_up_{sel_id}")
                    if up_img:
                        pasted_img = Image.open(up_img)

                    if pasted_img is not None:
                        st.image(pasted_img, caption="미리보기", use_container_width=True)
                        if st.button("증빙 저장", key=f"save_evd_{sel_id}", use_container_width=True):
                            att_dir = os.path.join(db.DATA_DIR, "attachments")
                            os.makedirs(att_dir, exist_ok=True)
                            fname = f"todo_{sel_id}_{db.get_kst_str('%Y%m%d_%H%M%S')}.png"
                            fpath = os.path.join(att_dir, fname)
                            pasted_img.save(fpath)
                            with db.get_connection() as conn:
                                conn.execute(
                                    "INSERT INTO attachments (request_id, file_name, file_path, created_at) VALUES (?, ?, ?, ?)",
                                    (int(sel_id), fname, fpath, db.get_kst_str())
                                )
                                conn.commit()
                            st.success("증빙 저장 완료")
                            st.rerun()

                    with db.get_connection() as conn:
                        atts = [dict(r) for r in conn.execute("SELECT * FROM attachments WHERE request_id = ? ORDER BY id DESC", (int(sel_id),)).fetchall()]
                    if atts:
                        st.divider()
                        cols = st.columns(2)
                        for idx_a, att in enumerate(atts):
                            if att.get("file_path") and os.path.exists(att["file_path"]):
                                with cols[idx_a % 2]:
                                    st.image(att["file_path"], use_container_width=True)
                                    if st.button("🗑️ 삭제", key=f"del_att_{att['id']}"):
                                        db.delete_attachment(att["id"])
                                        st.rerun()
        else:
            st.info("좌측 목록에서 할 일을 선택하면 세부 정보가 표시됩니다.")


# ==============================================================================
# [메인 2] 🧩 레시피 확인 (Handler 메인 노출 -> 클릭 시 연결 Vision + 주요 파라미터 + 변경점)
# ==============================================================================
elif menu == "🧩 레시피 확인":
    st.subheader("🧩 레시피 확인 (Handler → Vision 구성 · 파라미터 · 변경점)")

    f1, f2, f3, f4 = st.columns([2.3, 2.3, 2.4, 3.0])
    f_prod = f1.selectbox("Product", ["전체"] + db.get_master_names("Product"))
    f_step = f2.selectbox("Step", ["전체"] + db.get_master_names("Step"))
    f_code = f3.selectbox("Device Code 빠른 필터", ["선택 안 함"] + db.get_master_names("DeviceCode"))
    f_kw = f4.text_input("Handler 이름 / 구분 설명 검색", placeholder="예: ALPHA, 표준 양산")

    if f_code != "선택 안 함":
        code_info = db.get_active_code_mapping(f_code)
        if code_info:
            f_prod = code_info["product"]
            st.info(
                f"⚡ **Device Code `{f_code}` 매핑 적용됨** → Product: `{code_info['product']}` | "
                f"Module: `{code_info['module']}` | Purpose: `{code_info['purpose']}` ({code_info['certainty']})"
            )
        else:
            st.warning(f"Device Code `{f_code}`에 대한 활성 매핑이 없습니다.")

    handlers = db.get_handlers_with_conditions(product_filter=f_prod, step_filter=f_step, keyword=f_kw)

    if not handlers:
        st.info("조건에 일치하는 Handler Recipe가 없습니다. 좌측 [⚙️ 레시피 등록 및 매핑] 메뉴에서 등록하세요.")
    else:
        st.markdown("##### 1️⃣ Handler Recipe 목록 (확인할 Handler를 선택하세요)")
        df_h = pd.DataFrame(handlers)
        show_cols = ["id", "name", "version", "product", "step", "module", "purpose", "condition_desc", "description"]
        st.dataframe(df_h[show_cols], use_container_width=True, hide_index=True)

        unique_handlers = []
        seen_ids = set()
        for h in handlers:
            if h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                unique_handlers.append(h)

        sel_h = st.selectbox(
            "🔍 상세 조회할 Handler Recipe 선택",
            unique_handlers,
            format_func=lambda h: f"#{h['id']} {h['name']} ({h['version']}) — {h.get('product') or '-'} / {h.get('step') or '-'} [{h.get('condition_desc') or h.get('description') or '기본'}]"
        )

        if sel_h:
            with st.expander(f"📄 Handler 원본 XML 및 설명 보기 — {sel_h['name']} ({sel_h['version']})", expanded=False):
                st.caption(sel_h.get("description") or "설명 없음")
                st.code(sel_h.get("xml_content") or "", language="xml")

            st.divider()
            linked_visions = db.get_handler_linked_visions_detail(sel_h["id"])
            st.markdown(f"##### 2️⃣ `{sel_h['name']}` 에 물려 있는 Vision Recipe ({len(linked_visions)}개)")

            if not linked_visions:
                st.warning("이 Handler Recipe에 연결된 Vision Recipe가 없습니다. [⚙️ 레시피 등록 및 매핑] 메뉴에서 Vision을 연결하세요.")
            else:
                for v in linked_visions:
                    with st.container(border=True):
                        st.markdown(
                            f"#### `[순서 {v['seq_order']}]` 📷 **{v['name']}** (`{v['version']}`) "
                            f"<span style='font-size:13px; color:#4a5568;'>— {v.get('description') or ''}</span>",
                            unsafe_allow_html=True
                        )

                        col_param, col_chg = st.columns([5.2, 4.8])

                        with col_param:
                            st.markdown("**🔧 주요 파라미터 (XML 자동 추출)**")
                            if v["key_params"]:
                                st.dataframe(pd.DataFrame(v["key_params"]), use_container_width=True, hide_index=True)
                            else:
                                st.caption("추출된 XML 파라미터가 없습니다.")

                            with st.expander("원본 XML 보기"):
                                st.code(v.get("xml_content") or "", language="xml")

                        with col_chg:
                            st.markdown("**🕒 최근 변경점 (감사 로그)**")
                            if v["recent_changes"]:
                                for chg in v["recent_changes"]:
                                    st.markdown(f"""
                                    <div style="background:#f8fafc; border-left:4px solid #3182ce; padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:13px;">
                                        <b>[{chg['change_type']}]</b> &rarr; <span style="color:#2b6cb0;font-weight:600;">{chg.get('evaluation_result') or '-'}</span><br>
                                        <code>{chg.get('before_val') or '-'}</code> &rarr; <code>{chg.get('after_val') or '-'}</code><br>
                                        <span style="color:#718096; font-size:12px;">사유: {chg.get('change_reason') or '-'} | {chg.get('created_at') or '-'}</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                st.caption("기록된 변경 이력이 없습니다.")

                            if v.get("images"):
                                with st.expander(f"🖼️ 등록된 Align/참조 이미지 ({len(v['images'])}장)"):
                                    img_cols = st.columns(2)
                                    for idx_i, im in enumerate(v["images"]):
                                        if im.get("file_path") and os.path.exists(im["file_path"]):
                                            with img_cols[idx_i % 2]:
                                                st.image(im["file_path"], caption=f"[{im.get('tag', 'ALIGN')}] {im['file_name']}", use_container_width=True)


# ==============================================================================
# [보조 1] ⚙️ 레시피 등록 및 매핑
# ==============================================================================
elif menu == "⚙️ 레시피 등록 및 매핑":
    st.subheader("⚙️ 레시피 등록 · 수정 · 연결 매핑 · Align 이미지 관리")

    tab_master, tab_map, tab_impact = st.tabs([
        "📋 Handler / Vision 등록 및 수정 (CRUD)",
        "🔗 Handler ↔ Vision 연결 구성",
        "⚠️ 공유 Vision 영향도 역추적"
    ])

    with tab_master:
        c_top1, c_top2 = st.columns([6.5, 3.5])
        with c_top1:
            r_type_sel = st.radio("관리 대상 Recipe 종류", ["HANDLER", "VISION"], horizontal=True)
        with c_top2:
            st.write("")
            btn_label = "➕ 신규 Handler Recipe 등록" if r_type_sel == "HANDLER" else "➕ 신규 Vision Recipe 등록"
            with st.popover(btn_label, use_container_width=True):
                if r_type_sel == "HANDLER":
                    st.markdown("##### 📦 신규 Handler Recipe + 공정 조건 등록")
                    code_opt = st.selectbox("Device Code 자동완성 (선택)", ["직접 선택"] + db.get_master_names("DeviceCode"), key="pop_code_sel")
                    auto_prod, auto_mod, auto_purp = "", "", ""
                    if code_opt != "직접 선택":
                        cm = db.get_active_code_mapping(code_opt)
                        if cm:
                            auto_prod, auto_mod, auto_purp = cm["product"], cm["module"], cm["purpose"]

                    with st.form("pop_new_handler_form"):
                        nh_name = st.text_input("Handler Recipe 이름*", placeholder="예: HDL_GAMMA_01")
                        nh_ver = st.text_input("버전*", value="v1.0")
                        nh_desc = st.text_input("기본 설명", placeholder="용도 요약")

                        prods = db.get_master_names("Product")
                        steps = db.get_master_names("Step")
                        mods = db.get_master_names("Module")
                        purps = db.get_master_names("Purpose")

                        c1, c2 = st.columns(2)
                        p_idx = prods.index(auto_prod) if auto_prod in prods else 0
                        m_idx = mods.index(auto_mod) if auto_mod in mods else 0
                        pu_idx = purps.index(auto_purp) if auto_purp in purps else 0

                        sel_p = c1.selectbox("Product*", prods, index=p_idx if prods else 0)
                        sel_s = c1.selectbox("Step*", steps)
                        sel_m = c2.selectbox("Module*", mods, index=m_idx if mods else 0)
                        sel_pu = c2.selectbox("Purpose*", purps, index=pu_idx if purps else 0)
                        cond_desc = st.text_input("동일 조건 내 구분 설명 (1:N 분기용)", placeholder="예: 고반사 웨이퍼용 분기")
                        nh_xml = st.text_area(
                            "Handler XML 본문",
                            value="""<HandlerRecipe>
  <SequenceCount>1</SequenceCount>
  <RetryLimit>3</RetryLimit>
</HandlerRecipe>""",
                            height=100
                        )
                        if st.form_submit_button("Handler 등록 완료", type="primary", use_container_width=True):
                            if not nh_name.strip() or not nh_ver.strip():
                                st.error("이름과 버전은 필수입니다.")
                            else:
                                now_str = db.get_kst_str()
                                with db.get_connection() as conn:
                                    cur = conn.cursor()
                                    cur.execute("""
                                        INSERT OR IGNORE INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                                        VALUES ('HANDLER', ?, ?, ?, ?, ?)
                                    """, (nh_name.strip(), nh_ver.strip(), nh_desc, nh_xml, now_str))
                                    h_row = cur.execute(
                                        "SELECT id FROM recipes WHERE recipe_type='HANDLER' AND name=? AND version=?",
                                        (nh_name.strip(), nh_ver.strip())
                                    ).fetchone()
                                    if h_row and sel_p and sel_s and sel_m and sel_pu:
                                        cur.execute("""
                                            INSERT OR IGNORE INTO recipe_conditions (product, step, module, purpose, handler_id, condition_desc, created_at)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (sel_p, sel_s, sel_m, sel_pu, h_row["id"], cond_desc, now_str))
                                    conn.commit()
                                st.success("Handler Recipe가 등록되었습니다.")
                                st.rerun()
                else:
                    st.markdown("##### 📷 신규 Vision Recipe 등록")
                    with st.form("pop_new_vision_form"):
                        nv_name = st.text_input("Vision Recipe 이름*", placeholder="예: VIS_ALIGN_CAM2")
                        nv_ver = st.text_input("버전*", value="v1.0")
                        nv_desc = st.text_input("설명", placeholder="검사/얼라인 목적")
                        nv_xml = st.text_area(
                            "파라미터 XML 본문",
                            value="""<VisionRecipe>
  <ExposureUs>2500</ExposureUs>
  <Gain>1.20</Gain>
  <Threshold>120</Threshold>
</VisionRecipe>""",
                            height=120
                        )
                        if st.form_submit_button("Vision 등록 완료", type="primary", use_container_width=True):
                            if not nv_name.strip() or not nv_ver.strip():
                                st.error("이름과 버전은 필수입니다.")
                            else:
                                with db.get_connection() as conn:
                                    conn.execute("""
                                        INSERT OR IGNORE INTO recipes (recipe_type, name, version, description, xml_content, created_at)
                                        VALUES ('VISION', ?, ?, ?, ?, ?)
                                    """, (nv_name.strip(), nv_ver.strip(), nv_desc, nv_xml, db.get_kst_str()))
                                    conn.commit()
                                st.success("Vision Recipe가 등록되었습니다.")
                                st.rerun()

        st.divider()
        with db.get_connection() as conn:
            rec_list = [dict(r) for r in conn.execute(
                "SELECT * FROM recipes WHERE recipe_type = ? ORDER BY id DESC", (r_type_sel,)
            ).fetchall()]

        c_tbl, c_edt = st.columns([5.5, 4.5])
        with c_tbl:
            if rec_list:
                df_r = pd.DataFrame(rec_list)[["id", "name", "version", "description", "created_at"]]
                st.dataframe(df_r, use_container_width=True, hide_index=True)
                sel_rec = st.selectbox(
                    f"수정/삭제할 {r_type_sel} 선택",
                    rec_list,
                    format_func=lambda x: f"#{x['id']} {x['name']} ({x['version']})"
                )
            else:
                st.info(f"등록된 {r_type_sel} Recipe가 없습니다. 상단 등록 버튼을 이용하세요.")
                sel_rec = None

        with c_edt:
            if sel_rec:
                with st.container(border=True):
                    st.markdown(f"##### ✏️ #{sel_rec['id']} {sel_rec['name']} 상세 수정")
                    with st.form(f"edit_rec_{sel_rec['id']}"):
                        e_name = st.text_input("명칭*", value=sel_rec["name"])
                        e_ver = st.text_input("버전*", value=sel_rec["version"])
                        e_desc = st.text_input("설명", value=sel_rec.get("description") or "")
                        e_xml = st.text_area("XML 본문", value=sel_rec.get("xml_content") or "", height=140)
                        if st.form_submit_button("수정 저장", type="primary", use_container_width=True):
                            if e_name.strip() and e_ver.strip():
                                db.update_recipe(sel_rec["id"], e_name, e_ver, e_desc, e_xml)
                                st.success("수정되었습니다.")
                                st.rerun()

                    with st.expander("🕒 변경점(감사 로그) 수동 기록"):
                        with st.form(f"log_chg_rec_{sel_rec['id']}"):
                            c_type = st.selectbox("변경 유형", ["파라미터 변경", "Align 보정", "신규 분기", "버전 롤백"])
                            b_val = st.text_input("변경 전 값", placeholder="예: Threshold: 120")
                            a_val = st.text_input("변경 후 값", placeholder="예: Threshold: 145")
                            c_rsn = st.text_input("변경 사유", placeholder="조도 편차 보정")
                            e_res = st.selectbox("평가 결과", ["양호(적용가능)", "평가중", "Fail(원복)"])
                            if st.form_submit_button("변경점 기록 추가"):
                                t_kind = "Vision" if r_type_sel == "VISION" else "Handler"
                                with db.get_connection() as conn:
                                    conn.execute("""
                                        INSERT INTO recipe_changes (request_id, target_type, target_name, change_type, before_val, after_val, change_reason, operator, evaluation_result, created_at)
                                        VALUES (NULL, ?, ?, ?, ?, ?, ?, '엔지니어', ?, ?)
                                    """, (t_kind, sel_rec["name"], c_type, b_val, a_val, c_rsn, e_res, db.get_kst_str()))
                                    conn.commit()
                                st.success("변경 이력이 기록되었습니다.")
                                st.rerun()

                    with st.expander("🖼️ Align / 참조 이미지 관리 (Ctrl+V)"):
                        img_tag = st.selectbox("이미지 태그", ["ALIGN", "PATTERN", "MASTER", "DEFECT"], key=f"tag_{sel_rec['id']}")
                        p_img = None
                        if HAS_PASTE_BTN:
                            pr = paste_image_button("📋 클립보드 붙여넣기 (Ctrl+V)", background_color="#2b5c8f", text_color="#ffffff")
                            if pr.image_data is not None:
                                p_img = pr.image_data
                        up_i = st.file_uploader("이미지 파일 업로드", type=["png", "jpg", "jpeg", "bmp"], key=f"up_ri_{sel_rec['id']}")
                        if up_i:
                            p_img = Image.open(up_i)
                        if p_img is not None:
                            st.image(p_img, caption="미리보기", use_container_width=True)
                            if st.button("이미지 등록", key=f"save_ri_{sel_rec['id']}", use_container_width=True):
                                r_img_dir = os.path.join(db.DATA_DIR, "recipe_images")
                                os.makedirs(r_img_dir, exist_ok=True)
                                fn = f"rec_{sel_rec['id']}_{db.get_kst_str('%Y%m%d_%H%M%S')}.png"
                                fp = os.path.join(r_img_dir, fn)
                                p_img.save(fp)
                                db.add_recipe_image(sel_rec["id"], fn, fp, tag=img_tag)
                                st.success("이미지가 등록되었습니다.")
                                st.rerun()

                        existing_imgs = db.get_recipe_images(sel_rec["id"])
                        if existing_imgs:
                            ic = st.columns(2)
                            for idx_im, im in enumerate(existing_imgs):
                                if im.get("file_path") and os.path.exists(im["file_path"]):
                                    with ic[idx_im % 2]:
                                        st.image(im["file_path"], caption=f"[{im['tag']}]", use_container_width=True)
                                        if st.button("🗑️ 삭제", key=f"del_ri_{im['id']}"):
                                            db.delete_recipe_image(im["id"])
                                            st.rerun()

                    with st.popover(f"🗑️ #{sel_rec['id']} 영구 삭제"):
                        st.warning("연결된 매핑 및 이미지가 함께 삭제됩니다.")
                        if st.button("삭제 확인", key=f"del_r_ok_{sel_rec['id']}", type="primary"):
                            db.delete_recipe(sel_rec["id"])
                            st.rerun()

    with tab_map:
        with db.get_connection() as conn:
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'HANDLER' ORDER BY id DESC").fetchall()]
            visions = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'VISION' ORDER BY id DESC").fetchall()]
            maps = [dict(r) for r in conn.execute("""
                SELECT m.id, h.name as handler_name, h.version as handler_ver, m.seq_order, v.name as vision_name, v.version as vision_ver
                FROM handler_vision_map m
                JOIN recipes h ON m.handler_id = h.id
                JOIN recipes v ON m.vision_id = v.id
                ORDER BY h.name ASC, m.seq_order ASC
            """).fetchall()]

        cm1, cm2 = st.columns([6, 4])
        with cm1:
            st.markdown("##### 현재 연결된 Handler ↔ Vision 체인")
            if maps:
                df_m = pd.DataFrame(maps)
                st.dataframe(df_m, use_container_width=True, hide_index=True)
                sel_m = st.selectbox("해제할 연결 선택", maps, format_func=lambda x: f"#{x['id']} {x['handler_name']} ➔ [순서 {x['seq_order']}] {x['vision_name']}")
                if st.button("🗑️ 선택 연결 해제", key="del_hv_map"):
                    db.delete_handler_vision_map(sel_m["id"])
                    st.rerun()
            else:
                st.info("연결된 Handler-Vision 관계가 없습니다.")

        with cm2:
            st.markdown("##### ➕ 새 Vision 연결 추가")
            if handlers and visions:
                with st.form("add_hv_map_form"):
                    sh = st.selectbox("Handler Recipe*", handlers, format_func=lambda x: x["label"])
                    sv = st.selectbox("연결할 Vision Recipe*", visions, format_func=lambda x: x["label"])
                    seq = st.number_input("실행/참조 순서 (seq_order)*", min_value=1, value=1)
                    if st.form_submit_button("연결 저장", type="primary", use_container_width=True):
                        with db.get_connection() as conn:
                            conn.execute("""
                                INSERT INTO handler_vision_map (handler_id, vision_id, seq_order, created_at)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(handler_id, vision_id) DO UPDATE SET seq_order = excluded.seq_order
                            """, (sh["id"], sv["id"], int(seq), db.get_kst_str()))
                            conn.commit()
                        st.success("연결되었습니다.")
                        st.rerun()
            else:
                st.warning("Handler와 Vision Recipe가 각각 1개 이상 필요합니다.")

    with tab_impact:
        st.markdown("##### ⚠️ Vision Recipe 변경 시 영향받는 Handler 역추적")
        with db.get_connection() as conn:
            visions = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'VISION' ORDER BY name ASC").fetchall()]
        if visions:
            tv = st.selectbox("점검할 Vision Recipe 선택", visions, format_func=lambda x: x["label"])
            with db.get_connection() as conn:
                impacts = [dict(r) for r in conn.execute("""
                    SELECT h.id, h.name as handler_name, h.version as handler_ver, m.seq_order, h.description
                    FROM handler_vision_map m
                    JOIN recipes h ON m.handler_id = h.id
                    WHERE m.vision_id = ?
                    ORDER BY h.name ASC
                """, (tv["id"],)).fetchall()]
            if impacts:
                st.warning(f"⚠️ **{tv['label']}** 수정 시 아래 **{len(impacts)}개**의 Handler Recipe가 영향을 받습니다.")
                st.dataframe(pd.DataFrame(impacts), use_container_width=True, hide_index=True)
            else:
                st.success("현재 이 Vision Recipe를 참조하는 Handler가 없습니다.")
        else:
            st.info("등록된 Vision Recipe가 없습니다.")


# ==============================================================================
# [보조 2] 🚀 설비 횡전개 및 Diff
# ==============================================================================
elif menu == "🚀 설비 횡전개 및 Diff":
    st.subheader("🚀 설비 적용 · 횡전개 · 정밀 Diff 검증")

    tab_eqp, tab_dep, tab_diff = st.tabs([
        "📊 설비별 적용 현황 (DP-01)",
        "🚀 다중 설비 횡전개 트래커 (DP-02~05)",
        "🔬 폴더 · XML · 픽셀 정밀 Diff (FV-01~03)"
    ])

    with tab_eqp:
        with db.get_connection() as conn:
            eqps = db.get_master_names("Equipment")
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label, version FROM recipes WHERE recipe_type = 'HANDLER'").fetchall()]
            rows_st = [dict(r) for r in conn.execute("""
                SELECT s.equipment, r.name as handler_name, r.version as target_version,
                       s.verified_version, s.sync_status, s.last_verified_at, s.verifier
                FROM equipment_recipe_status s
                LEFT JOIN recipes r ON s.handler_id = r.id
                ORDER BY s.equipment ASC
            """).fetchall()]

        c1, c2 = st.columns([6.8, 3.2])
        with c1:
            if rows_st:
                st.dataframe(pd.DataFrame(rows_st), use_container_width=True, hide_index=True)
            else:
                st.info("등록된 설비 상태가 없습니다. 우측 폼에서 설비별 목표/확인 버전을 등록하세요.")
        with c2:
            if eqps and handlers:
                with st.form("eqp_sync_form"):
                    st.markdown("###### 설비 상태 갱신")
                    s_eq = st.selectbox("설비*", eqps)
                    s_hd = st.selectbox("목표 Handler*", handlers, format_func=lambda x: x["label"])
                    v_ver = st.text_input("현장 확인 버전", placeholder="예: v2.1")
                    s_st = st.selectbox("동기화 상태", ["일치", "불일치", "미확인"])
                    v_usr = st.text_input("검증자", placeholder="엔지니어")
                    if st.form_submit_button("저장", type="primary", use_container_width=True):
                        with db.get_connection() as conn:
                            conn.execute("""
                                INSERT INTO equipment_recipe_status (equipment, handler_id, target_version, verified_version, sync_status, last_verified_at, verifier)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(equipment) DO UPDATE SET
                                    handler_id = excluded.handler_id,
                                    target_version = excluded.target_version,
                                    verified_version = excluded.verified_version,
                                    sync_status = excluded.sync_status,
                                    last_verified_at = excluded.last_verified_at,
                                    verifier = excluded.verifier
                            """, (s_eq, s_hd["id"], s_hd["version"], v_ver, s_st, db.get_kst_str(), v_usr))
                            conn.commit()
                        st.success("저장되었습니다.")
                        st.rerun()

    with tab_dep:
        with db.get_connection() as conn:
            handlers = [dict(r) for r in conn.execute("SELECT id, name || ' (' || version || ')' as label FROM recipes WHERE recipe_type = 'HANDLER'").fetchall()]
            todos = [dict(r) for r in conn.execute("SELECT id, title FROM work_requests ORDER BY id DESC").fetchall()]
            all_eqps = db.get_master_names("Equipment")

        with st.expander("➕ 신규 횡전개 계획 등록", expanded=False):
            if handlers and all_eqps:
                with st.form("new_dep_form"):
                    d_title = st.text_input("횡전개 프로젝트명*", placeholder="예: HDL_ALPHA_MAIN v2.1 전 호기 횡전개")
                    d_h = st.selectbox("기준 Handler Recipe*", handlers, format_func=lambda x: x["label"])
                    d_req = st.selectbox("연계 할 일", [None] + todos, format_func=lambda x: f"#{x['id']} {x['title']}" if x else "없음")
                    d_eqs = st.multiselect("대상 설비*", all_eqps, default=all_eqps)
                    d_rsn = st.text_input("사유", placeholder="표준 파라미터 양산 전개")
                    if st.form_submit_button("횡전개 생성", type="primary"):
                        if d_title.strip() and d_eqs:
                            now_str = db.get_kst_str()
                            with db.get_connection() as conn:
                                cur = conn.cursor()
                                cur.execute("""
                                    INSERT INTO deployments (title, handler_id, request_id, reason, created_by, created_at)
                                    VALUES (?, ?, ?, ?, '엔지니어', ?)
                                """, (d_title.strip(), d_h["id"], d_req["id"] if d_req else None, d_rsn, now_str))
                                dep_id = cur.lastrowid
                                for eq in d_eqs:
                                    cur.execute("INSERT INTO deployment_targets (deployment_id, equipment, status) VALUES (?, ?, '대기')", (dep_id, eq))
                                conn.commit()
                            st.rerun()

        with db.get_connection() as conn:
            deps = [dict(r) for r in conn.execute("""
                SELECT d.id, d.title, r.name as handler_name, r.version as handler_ver, d.status, d.created_at
                FROM deployments d
                JOIN recipes r ON d.handler_id = r.id
                ORDER BY d.id DESC
            """).fetchall()]

        if deps:
            for dep in deps:
                with st.expander(f"📦 #{dep['id']} {dep['title']} ({dep['handler_name']} {dep['handler_ver']}) [{dep['status']}]", expanded=True):
                    with db.get_connection() as conn:
                        tgs = [dict(r) for r in conn.execute("SELECT * FROM deployment_targets WHERE deployment_id = ? ORDER BY equipment ASC", (dep["id"],)).fetchall()]
                    ct1, ct2 = st.columns([7, 3])
                    with ct1:
                        if tgs:
                            st.dataframe(pd.DataFrame(tgs)[["equipment", "status", "operator", "applied_at", "verifier", "verified_at", "hold_reason"]], use_container_width=True, hide_index=True)
                    with ct2:
                        if tgs:
                            with st.form(f"upd_tg_{dep['id']}"):
                                teq = st.selectbox("설비", [t["equipment"] for t in tgs])
                                tst = st.selectbox("상태", ["대기", "진행중", "검증완료", "실패", "보류"])
                                top = st.text_input("작업자")
                                tvr = st.text_input("검증자")
                                thold = st.text_input("비고/보류사유")
                                if st.form_submit_button("상태 반영"):
                                    now_str = db.get_kst_str()
                                    with db.get_connection() as conn:
                                        conn.execute("""
                                            UPDATE deployment_targets
                                            SET status = ?, operator = ?, verifier = ?, hold_reason = ?,
                                                applied_at = CASE WHEN ? IN ('진행중', '검증완료') THEN ? ELSE applied_at END,
                                                verified_at = CASE WHEN ? = '검증완료' THEN ? ELSE verified_at END
                                            WHERE deployment_id = ? AND equipment = ?
                                        """, (tst, top, tvr, thold, tst, now_str, tst, now_str, dep["id"], teq))
                                        conn.commit()
                                    st.rerun()
                        if st.button("🗑️ 프로젝트 삭제", key=f"del_dp_{dep['id']}"):
                            db.delete_deployment(dep["id"])
                            st.rerun()
        else:
            st.info("등록된 횡전개 프로젝트가 없습니다.")

    with tab_diff:
        diff_mode = st.radio(
            "비교 모드 선택",
            ["📁 폴더 트리 전체 비교 (SHA256 + Line Diff)", "📄 XML / 텍스트 직접 비교", "🖼️ Align 이미지 픽셀 Diff 오차 마스크"],
            horizontal=True
        )

        if diff_mode == "📁 폴더 트리 전체 비교 (SHA256 + Line Diff)":
            default_src, default_tgt = db.ensure_sample_recipe_folder()
            cf1, cf2 = st.columns(2)
            src_dir = cf1.text_input("기준 폴더 경로 (Source)", value=default_src)
            tgt_dir = cf2.text_input("설비 수집 폴더 경로 (Target)", value=default_tgt)

            if st.button("🔍 폴더 트리 해시 대조 실행", type="primary", use_container_width=True):
                st.session_state["folder_diff_res"] = db.compare_folders(src_dir, tgt_dir)

            f_res = st.session_state.get("folder_diff_res")
            if f_res:
                df_fd = pd.DataFrame(f_res)
                st.dataframe(df_fd[["파일경로", "상태", "기준크기(B)", "설비크기(B)", "기준해시", "설비해시"]], use_container_width=True, hide_index=True)

                changed = [r for r in f_res if r["상태"] == "🟡 내용 변경"]
                if changed:
                    sel_f = st.selectbox("상세 Diff 확인할 변경 파일 선택", changed, format_func=lambda x: x["파일경로"])
                    if sel_f and sel_f["src_path"] and sel_f["tgt_path"]:
                        if sel_f["ext"] in db.IMAGE_EXTS:
                            im1, im2 = Image.open(sel_f["src_path"]), Image.open(sel_f["tgt_path"])
                            px = db.compute_image_pixel_diff(im1, im2, threshold=15)
                            ic1, ic2, ic3 = st.columns(3)
                            ic1.image(im1, caption="Source", use_container_width=True)
                            ic2.image(im2, caption="Target", use_container_width=True)
                            ic3.image(px["diff_visual"], caption=f"Diff (일치율 {px['match_ratio']}%)", use_container_width=True)
                        else:
                            with open(sel_f["src_path"], "r", encoding="utf-8", errors="replace") as f1:
                                t1 = f1.read()
                            with open(sel_f["tgt_path"], "r", encoding="utf-8", errors="replace") as f2:
                                t2 = f2.read()
                            _, html_diff = db.compute_text_diff_html(t1, t2)
                            st.markdown(f"<div style='background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-family:monospace;'><pre>{html_diff}</pre></div>", unsafe_allow_html=True)

        elif diff_mode == "📄 XML / 텍스트 직접 비교":
            with db.get_connection() as conn:
                recs = [dict(r) for r in conn.execute("SELECT id, recipe_type, name, version, xml_content FROM recipes ORDER BY id DESC").fetchall()]
            ca, cb = st.columns(2)
            with ca:
                ra = st.selectbox("기준 Recipe A", [None] + recs, format_func=lambda x: f"[{x['recipe_type']}] {x['name']} ({x['version']})" if x else "직접 입력")
                txt_a = st.text_area("Source A 내용", value=(ra["xml_content"] if ra else "<Recipe><Threshold>120</Threshold></Recipe>"), height=200)
            with cb:
                rb = st.selectbox("대상 Recipe B", [None] + recs, format_func=lambda x: f"[{x['recipe_type']}] {x['name']} ({x['version']})" if x else "직접 입력")
                txt_b = st.text_area("Target B 내용", value=(rb["xml_content"] if rb else "<Recipe><Threshold>145</Threshold></Recipe>"), height=200)

            if st.button("🔍 텍스트 Diff 비교", type="primary", use_container_width=True):
                same, html_d = db.compute_text_diff_html(txt_a, txt_b)
                if same:
                    st.success("✅ 두 내용이 완전히 일치합니다.")
                else:
                    st.warning("⚠️ 차이점이 발견되었습니다.")
                    st.markdown(f"<div style='background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;font-family:monospace;'><pre>{html_d}</pre></div>", unsafe_allow_html=True)

        else:
            thresh = st.slider("픽셀 오차 감지 임계값 (Threshold)", min_value=1, max_value=100, value=15)
            ci1, ci2 = st.columns(2)
            up1 = ci1.file_uploader("기준 이미지 (Source A)", type=["png", "jpg", "jpeg", "bmp"], key="px_a")
            up2 = ci2.file_uploader("비교 이미지 (Target B)", type=["png", "jpg", "jpeg", "bmp"], key="px_b")
            if up1 and up2:
                im1, im2 = Image.open(up1), Image.open(up2)
                res = db.compute_image_pixel_diff(im1, im2, threshold=thresh)
                st.metric("픽셀 일치율", f"{res['match_ratio']}%", delta=f"오차 픽셀: {res['diff_pixels']} px")
                v1, v2, v3 = st.columns(3)
                v1.image(im1, caption="Source A", use_container_width=True)
                v2.image(im2, caption="Target B", use_container_width=True)
                v3.image(res["diff_visual"], caption="Diff 오차 마스크 (붉은색)", use_container_width=True)


# ==============================================================================
# [보조 3] 🛠️ 기준정보 및 백업
# ==============================================================================
elif menu == "🛠️ 기준정보 및 백업":
    st.subheader("🛠️ 기준정보 · Device Code 이력 · 백업/복구")

    t_master, t_code, t_audit, t_backup = st.tabs([
        "⚙️ 공통 기준정보 CRUD",
        "🏷️ Device Code 매핑 이력",
        "📜 전체 변경 감사 로그",
        "💾 원클릭 백업 및 복구"
    ])

    with t_master:
        cats = ["Product", "Step", "Module", "Purpose", "Department", "Equipment", "DeviceCode"]
        c1, c2 = st.columns([4, 6])
        sel_cat = c1.selectbox("카테고리", cats)
        with c2:
            st.write("")
            with st.popover(f"➕ 신규 {sel_cat} 추가"):
                with st.form("add_m_form"):
                    nm = st.text_input("항목명*")
                    if st.form_submit_button("추가"):
                        if db.add_master_data(sel_cat, nm):
                            st.rerun()

        items = db.get_master_data(sel_cat, active_only=False)
        for itm in items:
            m1, m2, m3, m4 = st.columns([4.5, 1.5, 2, 2])
            un = m1.text_input("명칭", value=itm["name"], key=f"mn_{itm['id']}", label_visibility="collapsed")
            ua = m2.checkbox("활성", value=bool(itm["is_active"]), key=f"ma_{itm['id']}")
            if m3.button("저장", key=f"ms_{itm['id']}"):
                db.update_master_data(itm["id"], un, 1 if ua else 0)
                st.rerun()
            if m4.button("🗑️ 삭제", key=f"md_{itm['id']}"):
                db.delete_master_data(itm["id"])
                st.rerun()

    with t_code:
        st.markdown("##### 🏷️ Device Code → (Product · Module · Purpose) 불변 이력 관리")
        with st.expander("➕ Device Code 매핑 등록 / 갱신"):
            with st.form("code_map_form"):
                c_code = st.text_input("Device Code*", placeholder="예: AAA")
                c_prod = st.selectbox("Product*", db.get_master_names("Product"))
                c_mod = st.selectbox("Module*", db.get_master_names("Module"))
                c_purp = st.selectbox("Purpose*", db.get_master_names("Purpose"))
                c_cert = st.selectbox("확실성", ["확정", "추정", "검토필요"])
                c_rsn = st.text_input("변경/등록 사유", placeholder="양산 기준 변경")
                if st.form_submit_button("매핑 저장", type="primary"):
                    if c_code.strip():
                        db.add_or_update_code_mapping(c_code.strip(), c_prod, c_mod, c_purp, c_rsn, c_cert)
                        st.success("저장되었습니다.")
                        st.rerun()

        hist = db.get_code_mapping_history()
        if hist:
            st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

    with t_audit:
        with db.get_connection() as conn:
            logs = [dict(r) for r in conn.execute("""
                SELECT rc.id, rc.target_type, rc.target_name, rc.change_type,
                       rc.before_val, rc.after_val, rc.change_reason, rc.evaluation_result, rc.created_at
                FROM recipe_changes rc
                ORDER BY rc.id DESC
            """).fetchall()]
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        else:
            st.info("기록된 감사 로그가 없습니다.")

    with t_backup:
        st.markdown("##### 💾 시스템 전체 원클릭 백업 및 무손실 복구")
        b1, b2 = st.columns(2)
        with b1:
            with st.container(border=True):
                st.markdown("###### 📤 전체 데이터 백업 다운로드")
                st.caption("SQLite DB, 할 일 증빙, Align 이미지 전체를 ZIP으로 저장합니다.")
                zip_data = db.create_system_backup()
                fname = f"RecipeManager_Backup_{db.get_kst_str('%Y%m%d_%H%M%S')}.zip"
                st.download_button("⬇️ 백업 ZIP 다운로드", data=zip_data, file_name=fname, mime="application/zip", type="primary", use_container_width=True)

        with b2:
            with st.container(border=True):
                st.markdown("###### 📥 백업 파일에서 복원 (구버전 DB 자동 마이그레이션 지원)")
                up_zip = st.file_uploader("백업 ZIP 파일 선택", type=["zip"])
                if up_zip is not None:
                    if st.button("⚠️ 선택한 백업으로 복원 실행", type="primary", use_container_width=True):
                        ok, msg = db.restore_system_backup(up_zip.read())
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
