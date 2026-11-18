import os
import html
import inspect
import calendar
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd
import database as db

try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BTN = True
except ImportError:
    HAS_PASTE_BTN = False

SUPPORTS_ACCEPT_NEW = "accept_new_options" in inspect.signature(st.selectbox).parameters


def smart_combobox(
    label: str,
    options: list[str],
    default_val: str = "",
    key: str = None,
    placeholder: str = "선택 또는 직접 입력"
) -> str:
    """목록 선택 + 타이핑 자동완성 + 직접 입력을 모두 지원하는 콤보박스"""
    clean_opts = [str(o).strip() for o in options if o and str(o).strip()]
    clean_def = str(default_val).strip() if default_val else ""
    if clean_def and clean_def not in clean_opts:
        clean_opts = [clean_def] + clean_opts

    if SUPPORTS_ACCEPT_NEW:
        idx = clean_opts.index(clean_def) if clean_def in clean_opts else None
        val = st.selectbox(
            label,
            options=clean_opts,
            index=idx,
            placeholder=placeholder,
            accept_new_options=True,
            key=key
        )
        return (str(val) if val is not None else "").strip()
    else:
        sel_opts = ["(직접 입력)"] + clean_opts
        idx = sel_opts.index(clean_def) if clean_def in sel_opts else 0
        picked = st.selectbox(label, sel_opts, index=idx, key=f"{key}_sel")
        if picked == "(직접 입력)":
            return st.text_input(
                f"{label} 직접 입력",
                value=clean_def,
                placeholder=placeholder,
                key=f"{key}_txt"
            ).strip()
        return picked


def parse_date_safe(d_str: str | None) -> date:
    if d_str:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(str(d_str).strip()[:10], fmt).date()
            except ValueError:
                continue
    return db.get_kst_today()


# ==============================================================================
# 1. 세부정보 편집 패널 (표 우측 패널 & 달력 우측 드로어 공용)
# ==============================================================================
def render_todo_detail_editor(sel_id: int, key_prefix: str = "ed", show_close_btn: bool = False):
    detail = db.get_todo_by_id(sel_id)
    if not detail:
        st.info("선택된 항목을 찾을 수 없습니다.")
        return

    milestones = db.get_open_milestones()
    milestone_label_to_id = {
        f"#{m['id']} {m['title']} (납기: {m.get('due_date') or '-'})": m["id"]
        for m in milestones if m["id"] != sel_id
    }
    milestone_id_to_label = {v: k for k, v in milestone_label_to_id.items()}

    if show_close_btn:
        act_c1, act_c2, act_c3 = st.columns([5.2, 2.5, 2.3])
    else:
        act_c1, act_c2 = st.columns([7, 3])
        act_c3 = None

    with act_c1:
        is_done = detail["status"] == "완료"
        if st.button(
            "진행중 복구" if is_done else "완료 처리",
            type="primary" if not is_done else "secondary",
            use_container_width=True,
            key=f"{key_prefix}_toggle_{sel_id}"
        ):
            db.toggle_todo_complete(sel_id, detail["status"])
            st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
            st.rerun()

    with act_c2:
        with st.popover("삭제", use_container_width=True):
            st.warning("이 할 일과 증빙 이미지를 삭제할까요?")
            if st.button("삭제 확인", key=f"{key_prefix}_del_ok_{sel_id}", type="primary", use_container_width=True):
                db.delete_work_request(sel_id)
                if st.session_state.get("selected_todo_id") == sel_id:
                    st.session_state["selected_todo_id"] = None
                if st.session_state.get("cal_selected_todo_id") == sel_id:
                    st.session_state["cal_selected_todo_id"] = None
                st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
                st.rerun()

    if act_c3 is not None:
        with act_c3:
            if st.button("닫기", use_container_width=True, key=f"{key_prefix}_drawer_close_{sel_id}"):
                st.session_state["cal_selected_todo_id"] = None
                st.rerun()

    with st.container(border=True):
        st.markdown(f"#### #{detail['id']} 세부 정보")
        st.caption(
            f"등록일시: **{detail.get('created_at') or '-'}**  |  "
            f"최종수정: {detail.get('updated_at') or '-'}"
        )

        e_title = smart_combobox(
            "키워드 (제목)*",
            db.get_autocomplete_options("title"),
            default_val=detail.get("title") or "",
            key=f"{key_prefix}_title_{sel_id}"
        )

        el_c1, el_c2 = st.columns([4.4, 5.6])
        with el_c1:
            cur_lvl = detail.get("task_level") if detail.get("task_level") in ["실행(소규모)", "납기(큰일)"] else "실행(소규모)"
            e_level = st.radio(
                "업무 구분",
                ["실행(소규모)", "납기(큰일)"],
                index=["실행(소규모)", "납기(큰일)"].index(cur_lvl),
                horizontal=True,
                key=f"{key_prefix}_lvl_{sel_id}"
            )
        with el_c2:
            if e_level == "실행(소규모)":
                avail_parents = ["(단독 실행 업무)"] + list(milestone_label_to_id.keys())
                cur_p_lbl = milestone_id_to_label.get(detail.get("parent_id"), "(단독 실행 업무)")
                p_idx = avail_parents.index(cur_p_lbl) if cur_p_lbl in avail_parents else 0
                picked_p_lbl = st.selectbox("상위 업무 연결", avail_parents, index=p_idx, key=f"{key_prefix}_par_{sel_id}")
                e_parent_id = milestone_label_to_id.get(picked_p_lbl)
            else:
                st.caption("달력 상단 마일스톤 바에 표시되는 큰 납기 항목입니다.")
                e_parent_id = None

        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            e_urg = smart_combobox(
                "긴급도",
                db.get_autocomplete_options("urgency", defaults=["긴급", "높음", "보통", "낮음"]),
                default_val=detail.get("urgency") or "보통",
                key=f"{key_prefix}_urg_{sel_id}"
            )
        with ec2:
            e_due = st.date_input(
                "목표 기한",
                value=parse_date_safe(detail.get("due_date")),
                key=f"{key_prefix}_due_{sel_id}"
            )
        with ec3:
            stat_opts = ["접수", "진행중", "평가/검증", "완료", "보류"]
            cur_stat = detail.get("status") if detail.get("status") in stat_opts else "접수"
            e_stat = st.selectbox("상태", stat_opts, index=stat_opts.index(cur_stat), key=f"{key_prefix}_stat_{sel_id}")

        ec4, ec5, ec6 = st.columns(3)
        with ec4:
            e_dept = smart_combobox(
                "의뢰 부서",
                db.get_autocomplete_options("department", master_category="Department"),
                default_val=detail.get("department") or "",
                key=f"{key_prefix}_dept_{sel_id}"
            )
        with ec5:
            e_req = smart_combobox(
                "의뢰자",
                db.get_autocomplete_options("requester"),
                default_val=detail.get("requester") or "",
                key=f"{key_prefix}_req_{sel_id}"
            )
        with ec6:
            e_lot = smart_combobox(
                "Lot ID",
                db.get_autocomplete_options("lot_id"),
                default_val=detail.get("lot_id") or "",
                key=f"{key_prefix}_lot_{sel_id}"
            )

        ec7, ec8, ec9 = st.columns(3)
        with ec7:
            e_prod = smart_combobox(
                "Product",
                db.get_autocomplete_options("product", master_category="Product"),
                default_val=detail.get("product") or "",
                key=f"{key_prefix}_prod_{sel_id}"
            )
        with ec8:
            e_step = smart_combobox(
                "Step",
                db.get_autocomplete_options("step", master_category="Step"),
                default_val=detail.get("step") or "",
                key=f"{key_prefix}_step_{sel_id}"
            )
        with ec9:
            e_asg = smart_combobox(
                "담당자",
                db.get_autocomplete_options("assignee", defaults=["유철형"]),
                default_val=detail.get("assignee") or "유철형",
                key=f"{key_prefix}_asg_{sel_id}"
            )

        e_eqp = smart_combobox(
            "설비 (Equipment)",
            db.get_autocomplete_options("equipment", master_category="Equipment"),
            default_val=detail.get("equipment") or "",
            key=f"{key_prefix}_eqp_{sel_id}"
        )

        e_content = st.text_area(
            "세부 내용",
            value=detail.get("content") or "",
            height=90,
            key=f"{key_prefix}_cnt_{sel_id}"
        )

        # 증빙 이미지 갤러리 (N개) & 추가 첨부
        atts = db.get_todo_attachments(sel_id)
        st.markdown(f"**증빙 이미지 ({len(atts)}건)**")
        if atts:
            img_cols = st.columns(3)
            for idx_a, att in enumerate(atts):
                if att.get("file_path") and os.path.exists(att["file_path"]):
                    with img_cols[idx_a % 3]:
                        st.image(att["file_path"], use_container_width=True)
                        b_z, b_d = st.columns(2)
                        with b_z:
                            with st.popover("확대"):
                                st.image(att["file_path"], caption=att["file_name"], use_container_width=True)
                        with b_d:
                            if st.button("삭제", key=f"{key_prefix}_del_att_{att['id']}"):
                                db.delete_attachment(att["id"])
                                st.rerun()

        add_c1, add_c2 = st.columns([6.2, 3.8])
        with add_c1:
            more_files = st.file_uploader(
                "증빙 이미지 추가 (다중 선택)",
                type=["png", "jpg", "jpeg", "bmp"],
                accept_multiple_files=True,
                key=f"{key_prefix}_more_files_{sel_id}",
                label_visibility="collapsed"
            )
        with add_c2:
            if HAS_PASTE_BTN:
                p_add = paste_image_button(
                    label="Ctrl+V 이미지 추가",
                    background_color="#0F6CBD",
                    text_color="#FFFFFF",
                    key=f"{key_prefix}_paste_{sel_id}"
                )
                if p_add.image_data is not None:
                    db.save_todo_attachments(sel_id, pasted_images=[p_add.image_data])
                    st.rerun()

        if st.button("수정사항 저장", type="primary", use_container_width=True, key=f"{key_prefix}_save_{sel_id}"):
            if not e_title:
                st.error("키워드(제목)를 입력해 주세요.")
            else:
                db.update_todo_detail(
                    todo_id=sel_id,
                    title=e_title,
                    urgency=e_urg or "보통",
                    status=e_stat,
                    content=e_content,
                    product=e_prod,
                    step=e_step,
                    equipment=e_eqp,
                    department=e_dept,
                    requester=e_req,
                    assignee=e_asg or "유철형",
                    lot_id=e_lot,
                    due_date=e_due.strftime("%Y-%m-%d"),
                    task_level=e_level,
                    parent_id=e_parent_id
                )
                if more_files:
                    db.save_todo_attachments(sel_id, uploaded_files=more_files)
                st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
                st.success("저장되었습니다.")
                st.rerun()


# ==============================================================================
# 2. 새 할 일 등록 모달 다이얼로그 (@st.dialog - 바깥 클릭 시 닫히지 않음)
# ==============================================================================
@st.dialog("새 할 일 등록", width="large")
def open_new_todo_dialog():
    if "dlg_pasted_imgs" not in st.session_state:
        st.session_state["dlg_pasted_imgs"] = []

    milestones = db.get_open_milestones()
    parent_map = {
        f"#{m['id']} {m['title']} (납기: {m.get('due_date') or '-'})": m["id"]
        for m in milestones
    }

    c_lvl, c_par = st.columns([3.5, 6.5])
    with c_lvl:
        t_level = st.radio(
            "업무 성격 구분",
            ["실행(소규모)", "납기(큰일)"],
            horizontal=True,
            key="dlg_task_level"
        )
    with c_par:
        if t_level == "실행(소규모)":
            sel_parent_lbl = st.selectbox(
                "상위 업무 연결 (큰 일 선택 시 [상위업무] 자동 태깅)",
                ["(단독 실행 업무)"] + list(parent_map.keys()),
                key="dlg_parent_sel"
            )
            t_parent_id = parent_map.get(sel_parent_lbl)
        else:
            st.info("달력 상단 마일스톤 바에 표시되는 큰 목표/납기로 등록됩니다.")
            t_parent_id = None

    t_title = smart_combobox(
        "할 일 키워드 (제목)*",
        db.get_autocomplete_options("title"),
        placeholder="핵심 작업 키워드 입력 또는 기존 이력 선택",
        key="dlg_title"
    )

    r1_c1, r1_c2, r1_c3 = st.columns(3)
    with r1_c1:
        t_urgency = smart_combobox(
            "긴급도",
            db.get_autocomplete_options("urgency", defaults=["긴급", "높음", "보통", "낮음"]),
            default_val="보통",
            key="dlg_urgency"
        )
    with r1_c2:
        t_due = st.date_input(
            "목표 기한 (기본값: 오늘)*",
            value=db.get_kst_today(),
            key="dlg_due_date"
        )
    with r1_c3:
        t_assignee = smart_combobox(
            "담당자",
            db.get_autocomplete_options("assignee", defaults=["유철형"]),
            default_val="유철형",
            key="dlg_assignee"
        )

    r2_c1, r2_c2, r2_c3 = st.columns(3)
    with r2_c1:
        t_dept = smart_combobox(
            "의뢰 부서",
            db.get_autocomplete_options("department", master_category="Department"),
            key="dlg_dept"
        )
    with r2_c2:
        t_requester = smart_combobox(
            "의뢰자",
            db.get_autocomplete_options("requester"),
            key="dlg_requester"
        )
    with r2_c3:
        t_lot = smart_combobox(
            "Lot ID",
            db.get_autocomplete_options("lot_id"),
            key="dlg_lot_id"
        )

    r3_c1, r3_c2, r3_c3 = st.columns(3)
    with r3_c1:
        t_prod = smart_combobox(
            "Product",
            db.get_autocomplete_options("product", master_category="Product"),
            key="dlg_prod"
        )
    with r3_c2:
        t_step = smart_combobox(
            "Step",
            db.get_autocomplete_options("step", master_category="Step"),
            key="dlg_step"
        )
    with r3_c3:
        t_eqp = smart_combobox(
            "설비 (Equipment)",
            db.get_autocomplete_options("equipment", master_category="Equipment"),
            key="dlg_eqp"
        )

    t_detail = st.text_area(
        "세부 내용",
        placeholder="상세 요청 사항, 파라미터 목표, 조치 계획 입력",
        height=95,
        key="dlg_detail"
    )

    st.markdown("**증빙 이미지 첨부 (N개 다중 등록 가능)**")
    img_c1, img_c2 = st.columns([6.2, 3.8])
    with img_c1:
        up_files = st.file_uploader(
            "이미지 파일 선택 (여러 장 동시 선택 가능)",
            type=["png", "jpg", "jpeg", "bmp"],
            accept_multiple_files=True,
            key="dlg_up_files"
        )
    with img_c2:
        if HAS_PASTE_BTN:
            st.write("")
            paste_res = paste_image_button(
                label="클립보드 캡처 추가 (Ctrl+V)",
                background_color="#0F6CBD",
                text_color="#FFFFFF",
                key="dlg_paste_btn"
            )
            if paste_res.image_data is not None:
                st.session_state["dlg_pasted_imgs"].append(paste_res.image_data)
        if st.session_state["dlg_pasted_imgs"]:
            st.caption(f"클립보드 캡처 {len(st.session_state['dlg_pasted_imgs'])}장 대기 중")
            if st.button("캡처 목록 비우기", key="dlg_clear_paste"):
                st.session_state["dlg_pasted_imgs"] = []

    st.divider()
    btn_c1, btn_c2 = st.columns([7, 3])
    with btn_c1:
        if st.button("할 일 등록 완료", type="primary", use_container_width=True, key="dlg_submit_btn"):
            if not t_title:
                st.error("할 일 키워드(제목)를 입력하거나 선택해 주세요.")
            else:
                new_id = db.create_todo(
                    title=t_title,
                    content=t_detail,
                    urgency=t_urgency or "보통",
                    req_type="할 일",
                    product=t_prod,
                    step=t_step,
                    equipment=t_eqp,
                    department=t_dept,
                    requester=t_requester,
                    assignee=t_assignee or "유철형",
                    lot_id=t_lot,
                    due_date=t_due.strftime("%Y-%m-%d"),
                    task_level=t_level,
                    parent_id=t_parent_id
                )
                db.save_todo_attachments(
                    request_id=new_id,
                    uploaded_files=up_files,
                    pasted_images=st.session_state["dlg_pasted_imgs"]
                )
                st.session_state["dlg_pasted_imgs"] = []
                st.session_state["selected_todo_id"] = new_id
                st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
                st.rerun()
    with btn_c2:
        if st.button("닫기", use_container_width=True, key="dlg_close_btn"):
            st.session_state["dlg_pasted_imgs"] = []
            st.rerun()


# ==============================================================================
# 3. [할 일] 표 뷰 (st.dataframe 단일 행 선택 + 표 위 우선순위 조정 + 전방위 검색)
# ==============================================================================
def render_todo_table_view(all_todos: list[dict], id_to_title: dict[int, str], theme: dict):
    if "todo_table_rev" not in st.session_state:
        st.session_state["todo_table_rev"] = 0
    if "last_df_sel_rows" not in st.session_state:
        st.session_state["last_df_sel_rows"] = []

    f_c1, f_c2, f_c3 = st.columns([2.2, 3.6, 4.2])
    with f_c1:
        show_completed = st.toggle("완료된 일 표시", value=False)
    with f_c2:
        filter_level = st.radio(
            "업무 구분 필터",
            ["전체", "실행(소규모)", "납기(큰일)"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with f_c3:
        search_kw = st.text_input(
            "전방위 검색",
            placeholder="통합 검색 (제목, Lot ID, 의뢰부서, 의뢰자, 설비, 내용, 첨부파일명 등)",
            label_visibility="collapsed"
        )

    base_todos = [
        t for t in all_todos
        if (show_completed or t["status"] != "완료")
        and (filter_level == "전체" or (t.get("task_level") or "실행(소규모)") == filter_level)
    ]
    todos = db.filter_todos_by_query(base_todos, search_kw)
    visible_ids = [t["id"] for t in todos]

    col_tbl, col_detail = st.columns([5.8, 4.2])

    with col_tbl:
        if not todos:
            st.info("조건에 일치하는 할 일이 없습니다. 검색어를 지우거나 [+ 새 할 일 등록]으로 추가하세요.")
        else:
            cur_sel_id = st.session_state.get("selected_todo_id")
            if not cur_sel_id or cur_sel_id not in visible_ids:
                cur_sel_id = visible_ids[0]
                st.session_state["selected_todo_id"] = cur_sel_id

            # 표 위에 위치하는 우선순위 조정 바 (선택된 1개 항목을 체크 유지하며 위/아래 이동)
            p_c1, p_c2, p_c3, p_c4 = st.columns([1.6, 1.7, 1.7, 5.0])
            with p_c1:
                if st.button("▲ 위로", use_container_width=True, help="선택한 항목을 위로 한 칸 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "up"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c2:
                if st.button("▼ 아래로", use_container_width=True, help="선택한 항목을 아래로 한 칸 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "down"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c3:
                if st.button("⏫ 최상단", use_container_width=True, help="선택한 항목을 맨 위로 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "top"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c4:
                cur_rank = visible_ids.index(cur_sel_id) + 1
                st.caption(f"선택됨: **#{cur_sel_id}** (현재 {cur_rank}순위) · 행 클릭 시 우측 세부정보 표시")

            # 깔끔한 스프레드시트 데이터프레임 구성
            rows_data = []
            for idx, t in enumerate(todos, start=1):
                tid = t["id"]
                is_sel = (tid == cur_sel_id)
                p_tag = f"[{id_to_title[t['parent_id']]}] " if t.get("parent_id") in id_to_title else ""
                is_big = (t.get("task_level") == "납기(큰일)")
                match_note = f"  [검색일치: {' · '.join(t['_match_reasons'])}]" if t.get("_match_reasons") else ""

                rows_data.append({
                    "선택": "☑" if is_sel else "☐",
                    "순서": idx,
                    "긴급도": t.get("urgency") or "보통",
                    "구분": "큰납기" if is_big else "실행",
                    "할 일 키워드": f"{p_tag}{t['title']}{match_note}",
                    "목표기한": t.get("due_date") or "-",
                    "의뢰부서": t.get("department") or "-",
                    "담당자": t.get("assignee") or "유철형",
                    "상태": t.get("status") or "접수",
                    "_tid": tid,
                })

            df_display = pd.DataFrame(rows_data)
            sel_bg = theme["accent_soft"]
            sel_fg = theme["accent"]

            def style_todo_rows(row):
                if row["_tid"] == cur_sel_id:
                    return [f"background-color: {sel_bg}; color: {sel_fg}; font-weight: 700;"] * len(row)
                if row["상태"] == "완료":
                    return ["color: #8A8886;"] * len(row)
                if row["긴급도"] == "긴급":
                    return ["background-color: #FDF3F4; color: #A4262C;"] * len(row)
                return [""] * len(row)

            styled_df = df_display.style.apply(style_todo_rows, axis=1)

            event = st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"todo_main_df_{st.session_state['todo_table_rev']}",
                column_config={
                    "_tid": None,
                    "선택": st.column_config.TextColumn("선택", width="small"),
                    "순서": st.column_config.NumberColumn("순서", format="%d", width="small"),
                    "긴급도": st.column_config.TextColumn("긴급도", width="small"),
                    "구분": st.column_config.TextColumn("구분", width="small"),
                    "할 일 키워드": st.column_config.TextColumn("할 일 키워드", width="large"),
                    "목표기한": st.column_config.TextColumn("목표기한", width="small"),
                    "의뢰부서": st.column_config.TextColumn("의뢰부서", width="small"),
                    "담당자": st.column_config.TextColumn("담당자", width="small"),
                    "상태": st.column_config.TextColumn("상태", width="small"),
                }
            )

            if event and event.selection and event.selection.rows:
                sel_rows = list(event.selection.rows)
                if sel_rows != st.session_state["last_df_sel_rows"]:
                    st.session_state["last_df_sel_rows"] = sel_rows
                    clicked_idx = sel_rows[0]
                    if 0 <= clicked_idx < len(visible_ids):
                        st.session_state["selected_todo_id"] = visible_ids[clicked_idx]
                        st.rerun()

    with col_detail:
        sel_id = st.session_state.get("selected_todo_id")
        if sel_id and sel_id in visible_ids:
            render_todo_detail_editor(sel_id, key_prefix="tbl_ed", show_close_btn=False)
        else:
            st.info("좌측 표에서 항목 한 줄을 클릭하면 오른쪽에 세부 정보가 표시됩니다.")


# ==============================================================================
# 4. [할 일] 달력 뷰 (시안 B 풀폭 심리스 7열 격자 + 우측 드로어 & 시안 C 상단 마일스톤 바)
# ==============================================================================
def render_todo_calendar_view(all_todos: list[dict], id_to_title: dict[int, str], theme: dict):
    if "cal_ref_date" not in st.session_state:
        st.session_state["cal_ref_date"] = db.get_kst_today()
    if "cal_selected_milestone_id" not in st.session_state:
        st.session_state["cal_selected_milestone_id"] = None
    if "cal_selected_todo_id" not in st.session_state:
        st.session_state["cal_selected_todo_id"] = None

    # URL 쿼리 파라미터 클릭 이벤트 수신 (동일 탭 전환)
    qp = st.query_params
    if "cal_todo" in qp:
        try:
            st.session_state["cal_selected_todo_id"] = int(qp["cal_todo"])
        except ValueError:
            pass
        del qp["cal_todo"]
        st.rerun()

    if "cal_ms" in qp:
        ms_raw = qp["cal_ms"]
        if ms_raw == "all":
            st.session_state["cal_selected_milestone_id"] = None
        else:
            try:
                ms_val = int(ms_raw)
                cur_ms = st.session_state.get("cal_selected_milestone_id")
                st.session_state["cal_selected_milestone_id"] = None if cur_ms == ms_val else ms_val
            except ValueError:
                pass
        del qp["cal_ms"]
        st.rerun()

    # --------------------------------------------------------------------------
    # [시안 C 요소] 상단 마일스톤 로드맵 바 (큰 납기 진행률 카드 & 클릭 필터링)
    # --------------------------------------------------------------------------
    milestones = [t for t in all_todos if t.get("task_level") == "납기(큰일)"]
    active_ms_id = st.session_state["cal_selected_milestone_id"]

    if milestones:
        cards_html = []
        is_all_active = "active" if active_ms_id is None else ""
        cards_html.append(f"""
        <a href="?cal_ms=all" target="_self" class="ms-roadmap-card {is_all_active}">
            <div class="ms-card-top">
                <span class="ms-badge-all">전체 일정</span>
                <span class="ms-card-cnt">{len(all_todos)}건</span>
            </div>
            <div class="ms-card-title">전체 프로젝트 · 일정 보기</div>
            <div class="ms-card-sub">모든 큰 납기 및 실행 할 일 표시</div>
        </a>
        """)

        for ms in milestones[:4]:
            sub_tasks = [x for x in all_todos if x.get("parent_id") == ms["id"]]
            done_cnt = sum(1 for x in sub_tasks if x["status"] == "완료")
            total_sub = len(sub_tasks)
            pct = int((done_cnt / total_sub) * 100) if total_sub > 0 else (100 if ms["status"] == "완료" else 0)
            is_act = "active" if active_ms_id == ms["id"] else ""
            safe_title = html.escape(ms["title"])
            safe_due = html.escape(ms.get("due_date") or "-")

            cards_html.append(f"""
            <a href="?cal_ms={ms['id']}" target="_self" class="ms-roadmap-card {is_act}">
                <div class="ms-card-top">
                    <span class="ms-badge-target">큰 납기</span>
                    <span class="ms-card-cnt">납기 {safe_due}</span>
                </div>
                <div class="ms-card-title" title="{safe_title}">{safe_title}</div>
                <div class="ms-prog-track"><div class="ms-prog-fill" style="width:{pct}%;"></div></div>
                <div class="ms-card-sub">하위 실행 완료: <b>{done_cnt}/{total_sub}</b> ({pct}%)</div>
            </a>
            """)

        st.markdown(f"<div class='ms-roadmap-bar'>{''.join(cards_html)}</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 달력 상단 제어 툴바 (월간/주간/일간 + 계층 필터 + 통합 검색 + 날짜 이동)
    # --------------------------------------------------------------------------
    c1, c2, c3, c4, c5 = st.columns([2.4, 2.7, 2.6, 1.1, 1.2])
    with c1:
        cal_scope = st.radio(
            "달력 단위",
            ["월간 (Month)", "주간 (Week)", "일간 (Day)"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with c2:
        cal_layer = st.radio(
            "계층 필터",
            ["전체 보기", "큰 납기만", "세부 실행만"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with c3:
        cal_search_kw = st.text_input(
            "달력 검색",
            placeholder="달력 통합 검색 (제목, Lot ID, 부서, 의뢰자 등)",
            label_visibility="collapsed"
        )
    with c4:
        picked_date = st.date_input(
            "기준 날짜",
            value=st.session_state["cal_ref_date"],
            label_visibility="collapsed"
        )
        if picked_date != st.session_state["cal_ref_date"]:
            st.session_state["cal_ref_date"] = picked_date
    with c5:
        n1, n2, n3 = st.columns([1, 1.5, 1])
        step_days = 1 if cal_scope == "일간 (Day)" else (7 if cal_scope == "주간 (Week)" else 30)
        if n1.button("◀", use_container_width=True, help="이전"):
            st.session_state["cal_ref_date"] -= timedelta(days=step_days)
            st.rerun()
        if n2.button("오늘", use_container_width=True):
            st.session_state["cal_ref_date"] = db.get_kst_today()
            st.rerun()
        if n3.button("▶", use_container_width=True, help="다음"):
            st.session_state["cal_ref_date"] += timedelta(days=step_days)
            st.rerun()

    ref_date = st.session_state["cal_ref_date"]
    cal_candidates = [
        t for t in all_todos
        if t.get("due_date")
        and (
            active_ms_id is None
            or t["id"] == active_ms_id
            or t.get("parent_id") == active_ms_id
        )
        and (
            cal_layer == "전체 보기"
            or (cal_layer == "큰 납기만" and t.get("task_level") == "납기(큰일)")
            or (cal_layer == "세부 실행만" and (t.get("task_level") or "실행(소규모)") == "실행(소규모)")
        )
    ]
    filtered_cal_todos = db.filter_todos_by_query(cal_candidates, cal_search_kw)

    events_by_date: dict[str, list[dict]] = {}
    for t in filtered_cal_todos:
        d_key = str(t["due_date"])[:10]
        events_by_date.setdefault(d_key, []).append(t)

    today_str = db.get_kst_today().strftime("%Y-%m-%d")
    drawer_id = st.session_state.get("cal_selected_todo_id")
    if drawer_id and not any(t["id"] == drawer_id for t in all_todos):
        drawer_id = None
        st.session_state["cal_selected_todo_id"] = None

    # --------------------------------------------------------------------------
    # [시안 B 요소] 미선택 시 100% 풀폭 달력 / 일정 클릭 시 우측 세부정보 드로어 오픈
    # --------------------------------------------------------------------------
    if drawer_id:
        cal_col, drawer_col = st.columns([6.3, 3.7])
    else:
        cal_col = st.container()
        drawer_col = None

    def build_event_pills_html(d_str: str, show_meta: bool = False) -> str:
        items = events_by_date.get(d_str, [])
        if not items:
            return ""
        pills = []
        for it in items:
            tid = it["id"]
            is_big = (it.get("task_level") == "납기(큰일)")
            is_done = (it["status"] == "완료")
            urg = it.get("urgency") or "보통"
            p_tag = f"[{id_to_title[it['parent_id']]}] " if it.get("parent_id") in id_to_title else ""

            if is_done:
                cls = "pill-done"
            elif is_big:
                cls = "pill-milestone"
            elif urg == "긴급":
                cls = "pill-urgent"
            elif urg == "높음":
                cls = "pill-high"
            else:
                cls = "pill-normal"

            sel_cls = "pill-selected" if tid == drawer_id else ""
            prefix = "[납기] " if is_big else p_tag
            full_text = f"{prefix}{it['title']}"
            safe_label = html.escape(full_text)
            tooltip = html.escape(f"#{tid} {full_text} | 담당: {it.get('assignee') or '유철형'} | 상태: {it['status']}")

            meta_html = ""
            if show_meta:
                meta_items = [
                    x for x in [
                        f"부서: {it['department']}" if it.get("department") else "",
                        f"의뢰자: {it['requester']}" if it.get("requester") else "",
                        f"Lot: {it['lot_id']}" if it.get("lot_id") else "",
                        f"담당: {it['assignee']}" if it.get("assignee") else "",
                        f"상태: {it['status']}"
                    ] if x
                ]
                meta_html = f"<div class='cal-pill-meta'>{html.escape(' · '.join(meta_items))}</div>"
            elif it.get("_match_reasons"):
                meta_html = f"<div class='cal-pill-meta'>검색: {html.escape(' · '.join(it['_match_reasons']))}</div>"

            pills.append(
                f"<a href='?cal_todo={tid}' target='_self' class='cal-event-pill {cls} {sel_cls}' title='{tooltip}'>"
                f"<div class='cal-pill-title'>{safe_label}</div>{meta_html}</a>"
            )
        return "".join(pills)

    with cal_col:
        if cal_scope == "일간 (Day)":
            d_str = ref_date.strftime("%Y-%m-%d")
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            st.markdown(f"#### {ref_date.year}년 {ref_date.month}월 {ref_date.day}일 ({day_names[ref_date.weekday()]})")
            pills_html = build_event_pills_html(d_str, show_meta=True)
            if not pills_html:
                pills_html = "<div class='cal-empty-day'>등록된 일정이 없습니다.</div>"
            st.markdown(f"<div class='cal-day-board'>{pills_html}</div>", unsafe_allow_html=True)

        elif cal_scope == "주간 (Week)":
            start_week = ref_date - timedelta(days=ref_date.weekday())
            end_week = start_week + timedelta(days=6)
            st.markdown(f"#### {start_week.year}년 {start_week.month}월 {start_week.day}일 ~ {end_week.month}월 {end_week.day}일")
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            dow_html = "".join(
                f"<div class='cal-dow-cell {'sun' if i==6 else ('sat' if i==5 else '')}'>{day_names[i]}</div>"
                for i in range(7)
            )
            cells_html = []
            for i in range(7):
                cur_d = start_week + timedelta(days=i)
                d_str = cur_d.strftime("%Y-%m-%d")
                is_today = (d_str == today_str)
                date_badge = (
                    f"<span class='cal-today-num'>{cur_d.month}/{cur_d.day} 오늘</span>"
                    if is_today else
                    f"<span class='cal-date-num'>{cur_d.month}/{cur_d.day}</span>"
                )
                cells_html.append(
                    f"<div class='cal-grid-cell week-cell {'is-today' if is_today else ''}'>"
                    f"<div class='cal-cell-top'>{date_badge}</div>"
                    f"<div class='cal-cell-body'>{build_event_pills_html(d_str, show_meta=True)}</div>"
                    f"</div>"
                )
            st.markdown(
                f"<div class='cal-wrapper'><div class='cal-dow-row'>{dow_html}</div>"
                f"<div class='cal-body-grid'>{''.join(cells_html)}</div></div>",
                unsafe_allow_html=True
            )

        else:  # 월간 (Month)
            st.markdown(f"#### {ref_date.year}년 {ref_date.month}월")
            cal_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(ref_date.year, ref_date.month)
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            dow_html = "".join(
                f"<div class='cal-dow-cell {'sun' if i==6 else ('sat' if i==5 else '')}'>{day_names[i]}</div>"
                for i in range(7)
            )
            cells_html = []
            for week_dates in cal_weeks:
                for cell_date in week_dates:
                    d_str = cell_date.strftime("%Y-%m-%d")
                    is_cur_month = (cell_date.month == ref_date.month)
                    is_today = (d_str == today_str)
                    if is_today:
                        date_badge = f"<span class='cal-today-num'>{cell_date.day}일 · 오늘</span>"
                    elif is_cur_month:
                        date_badge = f"<span class='cal-date-num'>{cell_date.day}일</span>"
                    else:
                        date_badge = f"<span class='cal-date-muted'>{cell_date.month}/{cell_date.day}</span>"

                    cells_html.append(
                        f"<div class='cal-grid-cell {'is-today' if is_today else ''} {'is-muted' if not is_cur_month else ''}'>"
                        f"<div class='cal-cell-top'>{date_badge}</div>"
                        f"<div class='cal-cell-body'>{build_event_pills_html(d_str, show_meta=False)}</div>"
                        f"</div>"
                    )
            st.markdown(
                f"<div class='cal-wrapper'><div class='cal-dow-row'>{dow_html}</div>"
                f"<div class='cal-body-grid'>{''.join(cells_html)}</div></div>",
                unsafe_allow_html=True
            )

    if drawer_col is not None and drawer_id:
        with drawer_col:
            render_todo_detail_editor(drawer_id, key_prefix="cal_drawer", show_close_btn=True)


# ==============================================================================
# 5. 메인 [할 일] 엔트리포인트
# ==============================================================================
def render_todo_module(theme: dict):
    top_c1, top_c2, top_c3 = st.columns([4.2, 3.8, 2.0])
    with top_c1:
        st.subheader("할 일 관리")
    with top_c2:
        view_mode = st.radio(
            "보기 방식",
            ["표 목록 + 세부정보", "달력 (일 / 주 / 월)"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with top_c3:
        if st.button("+ 새 할 일 등록", type="primary", use_container_width=True):
            open_new_todo_dialog()

    all_todos = db.get_todos_enriched(include_completed=True)
    id_to_title = {t["id"]: t["title"] for t in all_todos}

    if view_mode == "표 목록 + 세부정보":
        render_todo_table_view(all_todos, id_to_title, theme)
    else:
        render_todo_calendar_view(all_todos, id_to_title, theme)
