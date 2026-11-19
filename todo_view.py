import os
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
    placeholder: str = "선택 또는 직접 입력 (공란 가능)"
) -> str:
    """
    목록 선택 + 타이핑 자동완성 + 직접 입력 + 공란(Clear) 모두 지원하며,
    rerun 시에도 사용자가 입력한 값이 사라지지 않도록 session_state를 보존합니다.
    """
    clean_opts = [str(o).strip() for o in options if o and str(o).strip()]
    clean_def = str(default_val).strip() if default_val else ""

    if key and key in st.session_state and st.session_state[key] is not None:
        cur_ss = str(st.session_state[key]).strip()
        if cur_ss and cur_ss not in clean_opts:
            clean_opts = [cur_ss] + clean_opts
    elif clean_def and clean_def not in clean_opts:
        clean_opts = [clean_def] + clean_opts

    if SUPPORTS_ACCEPT_NEW:
        if key and key in st.session_state:
            cur_val = st.session_state[key]
            idx = clean_opts.index(cur_val) if (cur_val in clean_opts) else None
        else:
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
        sel_opts = ["(공란 / 직접 입력)"] + clean_opts
        idx = sel_opts.index(clean_def) if clean_def in sel_opts else 0
        picked = st.selectbox(label, sel_opts, index=idx, key=f"{key}_sel")
        if picked == "(공란 / 직접 입력)":
            return st.text_input(
                f"{label} 직접 입력",
                value=clean_def,
                placeholder=placeholder,
                key=f"{key}_txt"
            ).strip()
        return picked


def parse_date_optional(d_str: str | None) -> date | None:
    if d_str and str(d_str).strip():
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(str(d_str).strip()[:10], fmt).date()
            except ValueError:
                continue
    return None


def reset_new_todo_dialog_state():
    """새 할 일 등록 모달을 새로 열 때 이전 입력 잔여물 초기화"""
    for k in list(st.session_state.keys()):
        if k.startswith("dlg_"):
            del st.session_state[k]
    st.session_state["dlg_pasted_imgs"] = []
    st.session_state["dlg_paste_nonce"] = 0


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
        f"#{m['id']} {(m['title'] or '(제목 없음)')} (납기: {m.get('due_date') or '-'})": m["id"]
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
            "할 일 키워드 (제목)",
            db.get_autocomplete_options("title"),
            default_val=detail.get("title") or "",
            key=f"{key_prefix}_title_{sel_id}"
        )

        el_c1, el_c2 = st.columns([4.5, 5.5])
        with el_c1:
            is_cur_ms = db.is_milestone_level(detail.get("task_level"))
            e_level = st.radio(
                "업무 성격",
                ["일반/단독 실행", "프로젝트/큰 납기"],
                index=1 if is_cur_ms else 0,
                horizontal=True,
                key=f"{key_prefix}_lvl_{sel_id}"
            )
        with el_c2:
            if e_level == "일반/단독 실행":
                avail_parents = ["(상위 프로젝트 없음 - 단독 건)"] + list(milestone_label_to_id.keys())
                cur_p_lbl = milestone_id_to_label.get(detail.get("parent_id"), "(상위 프로젝트 없음 - 단독 건)")
                p_idx = avail_parents.index(cur_p_lbl) if cur_p_lbl in avail_parents else 0
                picked_p_lbl = st.selectbox("상위 프로젝트 연결", avail_parents, index=p_idx, key=f"{key_prefix}_par_{sel_id}")
                e_parent_id = milestone_label_to_id.get(picked_p_lbl)
            else:
                st.caption("달력 상단 마일스톤 바에 고정되어 하위 진행률을 집계합니다.")
                e_parent_id = None

        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            e_urg = smart_combobox(
                "긴급도",
                db.get_autocomplete_options("urgency", defaults=["긴급", "높음", "보통", "낮음"]),
                default_val=detail.get("urgency") or "",
                key=f"{key_prefix}_urg_{sel_id}"
            )
        with ec2:
            e_due = st.date_input(
                "목표 기한",
                value=parse_date_optional(detail.get("due_date")),
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
            e_mod = smart_combobox(
                "Module",
                db.get_autocomplete_options("module", master_category="Module"),
                default_val=detail.get("module") or "",
                key=f"{key_prefix}_mod_{sel_id}"
            )

        ec10, ec11, ec12 = st.columns(3)
        with ec10:
            e_purp = smart_combobox(
                "Purpose",
                db.get_autocomplete_options("purpose", master_category="Purpose"),
                default_val=detail.get("purpose") or "",
                key=f"{key_prefix}_purp_{sel_id}"
            )
        with ec11:
            e_eqp = smart_combobox(
                "설비 (Equipment)",
                db.get_autocomplete_options("equipment", master_category="Equipment"),
                default_val=detail.get("equipment") or "",
                key=f"{key_prefix}_eqp_{sel_id}"
            )
        with ec12:
            e_rcp = smart_combobox(
                "Recipe",
                db.get_autocomplete_options("recipe_id"),
                default_val=detail.get("recipe_id") or "",
                key=f"{key_prefix}_rcp_{sel_id}"
            )

        e_asg = smart_combobox(
            "담당자",
            db.get_autocomplete_options("assignee", defaults=["유철형"]),
            default_val=detail.get("assignee") or "",
            key=f"{key_prefix}_asg_{sel_id}"
        )

        e_content = st.text_area(
            "세부 내용",
            value=detail.get("content") or "",
            height=90,
            key=f"{key_prefix}_cnt_{sel_id}"
        )

        # 증빙 이미지 갤러리 (N개) & 단발성 추가 첨부 (무한 루프 방지 nonce 적용)
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
                nonce_key = f"{key_prefix}_paste_nonce_{sel_id}"
                if nonce_key not in st.session_state:
                    st.session_state[nonce_key] = 0
                cur_nonce = st.session_state[nonce_key]

                p_add = paste_image_button(
                    label="Ctrl+V 이미지 추가",
                    background_color="#0F6CBD",
                    text_color="#FFFFFF",
                    key=f"{key_prefix}_paste_{sel_id}_{cur_nonce}"
                )
                if p_add.image_data is not None:
                    db.save_todo_attachments(sel_id, pasted_images=[p_add.image_data])
                    st.session_state[nonce_key] = cur_nonce + 1
                    st.rerun()

        if st.button("수정사항 저장", type="primary", use_container_width=True, key=f"{key_prefix}_save_{sel_id}"):
            db.update_todo_detail(
                todo_id=sel_id,
                title=e_title,
                urgency=e_urg,
                status=e_stat,
                content=e_content,
                product=e_prod,
                step=e_step,
                module=e_mod,
                purpose=e_purp,
                equipment=e_eqp,
                recipe_id=e_rcp,
                department=e_dept,
                requester=e_req,
                assignee=e_asg,
                lot_id=e_lot,
                due_date=e_due.strftime("%Y-%m-%d") if e_due else "",
                task_level=e_level,
                parent_id=e_parent_id
            )
            if more_files:
                db.save_todo_attachments(sel_id, uploaded_files=more_files)
            st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
            st.success("저장되었습니다.")
            st.rerun()


# ==============================================================================
# 2. 새 할 일 등록 모달 다이얼로그 (@st.dialog - 모든 란 공란 가능 & 입력값 유지)
# ==============================================================================
@st.dialog("새 할 일 등록", width="large")
def open_new_todo_dialog():
    if "dlg_pasted_imgs" not in st.session_state:
        st.session_state["dlg_pasted_imgs"] = []
    if "dlg_paste_nonce" not in st.session_state:
        st.session_state["dlg_paste_nonce"] = 0

    milestones = db.get_open_milestones()
    parent_map = {
        f"#{m['id']} {(m['title'] or '(제목 없음)')} (납기: {m.get('due_date') or '-'})": m["id"]
        for m in milestones
    }

    c_lvl, c_par = st.columns([4.2, 5.8])
    with c_lvl:
        t_level = st.radio(
            "업무 성격",
            ["일반/단독 실행", "프로젝트/큰 납기"],
            horizontal=True,
            key="dlg_task_level"
        )
    with c_par:
        if t_level == "일반/단독 실행":
            sel_parent_lbl = st.selectbox(
                "상위 프로젝트 연결 (단발성 요청은 그대로 두세요)",
                ["(상위 프로젝트 없음 - 단독 건)"] + list(parent_map.keys()),
                key="dlg_parent_sel"
            )
            t_parent_id = parent_map.get(sel_parent_lbl)
        else:
            st.info("달력 상단 마일스톤 바에 고정되어 하위 할 일들의 진행률을 집계합니다.")
            t_parent_id = None

    # 제목 (st.text_input + 과거 키워드 빠른 선택 보조 -> 타이핑 중 절대 사라지지 않고 100% 안정적)
    t_title = st.text_input(
        "할 일 키워드 (제목)",
        placeholder="핵심 작업 키워드 입력 (공란 가능)",
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
            "목표 기한 (기본값: 오늘 / 지우기 가능)",
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
        t_mod = smart_combobox(
            "Module",
            db.get_autocomplete_options("module", master_category="Module"),
            key="dlg_mod"
        )

    r4_c1, r4_c2, r4_c3 = st.columns(3)
    with r4_c1:
        t_purp = smart_combobox(
            "Purpose",
            db.get_autocomplete_options("purpose", master_category="Purpose"),
            key="dlg_purp"
        )
    with r4_c2:
        t_eqp = smart_combobox(
            "설비 (Equipment)",
            db.get_autocomplete_options("equipment", master_category="Equipment"),
            key="dlg_eqp"
        )
    with r4_c3:
        t_rcp = smart_combobox(
            "Recipe",
            db.get_autocomplete_options("recipe_id"),
            key="dlg_rcp"
        )

    t_detail = st.text_area(
        "세부 내용",
        placeholder="상세 요청 사항, 파라미터 목표, 조치 계획 입력 (공란 가능)",
        height=90,
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
            dlg_nonce = st.session_state["dlg_paste_nonce"]
            paste_res = paste_image_button(
                label="클립보드 캡처 추가 (Ctrl+V)",
                background_color="#0F6CBD",
                text_color="#FFFFFF",
                key=f"dlg_paste_btn_{dlg_nonce}"
            )
            if paste_res.image_data is not None:
                st.session_state["dlg_pasted_imgs"].append(paste_res.image_data)
                st.session_state["dlg_paste_nonce"] = dlg_nonce + 1
                st.rerun()

    if st.session_state["dlg_pasted_imgs"]:
        st.caption(f"클립보드 캡처 {len(st.session_state['dlg_pasted_imgs'])}장 첨부 대기 중")
        p_cols = st.columns(min(len(st.session_state["dlg_pasted_imgs"]), 4))
        for idx_p, p_im in enumerate(st.session_state["dlg_pasted_imgs"]):
            with p_cols[idx_p % 4]:
                st.image(p_im, caption=f"캡처 #{idx_p + 1}", use_container_width=True)
        if st.button("캡처 목록 비우기", key="dlg_clear_paste"):
            st.session_state["dlg_pasted_imgs"] = []
            st.rerun()

    st.divider()
    btn_c1, btn_c2 = st.columns([7, 3])
    with btn_c1:
        if st.button("할 일 등록 완료", type="primary", use_container_width=True, key="dlg_submit_btn"):
            new_id = db.create_todo(
                title=t_title,
                content=t_detail,
                urgency=t_urgency,
                req_type="할 일",
                product=t_prod,
                step=t_step,
                module=t_mod,
                purpose=t_purp,
                equipment=t_eqp,
                recipe_id=t_rcp,
                department=t_dept,
                requester=t_requester,
                assignee=t_assignee,
                lot_id=t_lot,
                due_date=t_due.strftime("%Y-%m-%d") if t_due else "",
                task_level=t_level,
                parent_id=t_parent_id
            )
            db.save_todo_attachments(
                request_id=new_id,
                uploaded_files=up_files,
                pasted_images=st.session_state["dlg_pasted_imgs"]
            )
            reset_new_todo_dialog_state()
            st.session_state["selected_todo_id"] = new_id
            st.session_state["todo_table_rev"] = st.session_state.get("todo_table_rev", 0) + 1
            st.rerun()
    with btn_c2:
        if st.button("닫기", use_container_width=True, key="dlg_close_btn"):
            reset_new_todo_dialog_state()
            st.rerun()


# ==============================================================================
# 3. [할 일] 표 뷰 ('선택' 컬럼 제거 + 순서/긴급/구분 최소 폭 + 행 클릭 선택/우선순위 이동)
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
            ["전체", "일반/단독 실행", "프로젝트/큰 납기"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with f_c3:
        search_kw = st.text_input(
            "전방위 검색",
            placeholder="통합 검색 (제목, Lot ID, 부서, 의뢰자, Module, Purpose, Recipe, 첨부파일명 등)",
            label_visibility="collapsed"
        )

    base_todos = [
        t for t in all_todos
        if (show_completed or t["status"] != "완료")
        and (
            filter_level == "전체"
            or (filter_level == "프로젝트/큰 납기" and t["is_milestone"])
            or (filter_level == "일반/단독 실행" and not t["is_milestone"])
        )
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

            # 표 위에 위치하는 우선순위 조정 바 (테이블에서 선택한 항목 바로 이동)
            p_c1, p_c2, p_c3, p_c4 = st.columns([1.6, 1.7, 1.7, 5.0])
            with p_c1:
                if st.button("▲ 위로", use_container_width=True, help="테이블에서 선택한 항목을 위로 한 칸 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "up"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c2:
                if st.button("▼ 아래로", use_container_width=True, help="테이블에서 선택한 항목을 아래로 한 칸 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "down"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c3:
                if st.button("⏫ 최상단", use_container_width=True, help="테이블에서 선택한 항목을 맨 위로 이동"):
                    if db.move_selected_todo(visible_ids, cur_sel_id, "top"):
                        st.session_state["todo_table_rev"] += 1
                        st.session_state["last_df_sel_rows"] = []
                        st.rerun()
            with p_c4:
                cur_rank = visible_ids.index(cur_sel_id) + 1
                st.caption(f"선택 행: **#{cur_sel_id}** ({cur_rank}순위) · 행 클릭 시 상세보기 및 순서 이동")

            rows_data = []
            for idx, t in enumerate(todos, start=1):
                tid = t["id"]
                p_tag = f"[{id_to_title[t['parent_id']]}] " if t.get("parent_id") in id_to_title else ""
                match_note = f"  [검색일치: {' · '.join(t['_match_reasons'])}]" if t.get("_match_reasons") else ""

                rows_data.append({
                    "순서": idx,
                    "긴급": t.get("urgency") or "-",
                    "구분": "납기" if t["is_milestone"] else "실행",
                    "할 일 키워드": f"{p_tag}{t['display_title']}{match_note}",
                    "목표기한": t.get("due_date") or "-",
                    "의뢰부서": t.get("department") or "-",
                    "담당자": t.get("assignee") or "-",
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
                if row["긴급"] == "긴급":
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
                    "순서": st.column_config.NumberColumn("순서", format="%d", width="small"),
                    "긴급": st.column_config.TextColumn("긴급", width="small"),
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
# 4. [할 일] 달력 뷰 (페이지 리로드 없는 순수 Streamlit 인메모리 상태 + 드로어)
# ==============================================================================
def render_todo_calendar_view(all_todos: list[dict], id_to_title: dict[int, str], theme: dict):
    if "cal_ref_date" not in st.session_state:
        st.session_state["cal_ref_date"] = db.get_kst_today()
    if "cal_selected_milestone_id" not in st.session_state:
        st.session_state["cal_selected_milestone_id"] = None
    if "cal_selected_todo_id" not in st.session_state:
        st.session_state["cal_selected_todo_id"] = None

    # 상단 마일스톤 로드맵 바
    milestones = [t for t in all_todos if t["is_milestone"]]
    active_ms_id = st.session_state["cal_selected_milestone_id"]

    if milestones:
        ms_cols = st.columns(min(len(milestones), 4) + 1, gap="small")
        with ms_cols[0]:
            with st.container(border=True):
                is_all_act = (active_ms_id is None)
                if st.button(
                    f"전체 일정 ({len(all_todos)}건)",
                    type="primary" if is_all_act else "secondary",
                    use_container_width=True,
                    key="ms_btn_all"
                ):
                    st.session_state["cal_selected_milestone_id"] = None
                    st.rerun()
                st.caption("모든 프로젝트 및 단독 실행 건")

        for idx_m, ms in enumerate(milestones[:4]):
            sub_tasks = [x for x in all_todos if x.get("parent_id") == ms["id"]]
            done_cnt = sum(1 for x in sub_tasks if x["status"] == "완료")
            total_sub = len(sub_tasks)
            pct = int((done_cnt / total_sub) * 100) if total_sub > 0 else (100 if ms["status"] == "완료" else 0)
            is_act = (active_ms_id == ms["id"])

            with ms_cols[idx_m + 1]:
                with st.container(border=True):
                    if st.button(
                        f"[납기] {ms['display_title']}",
                        type="primary" if is_act else "secondary",
                        use_container_width=True,
                        key=f"ms_btn_{ms['id']}",
                        help=f"{ms['display_title']} (목표기한: {ms.get('due_date') or '-'})"
                    ):
                        st.session_state["cal_selected_milestone_id"] = None if is_act else ms["id"]
                        st.rerun()
                    st.progress(pct / 100.0)
                    st.caption(f"기한 {ms.get('due_date') or '-'} · 완료 {done_cnt}/{total_sub} ({pct}%)")

    # 달력 상단 제어 툴바
    c1, c2, c3, c4, c5 = st.columns([2.4, 2.7, 2.6, 1.1, 1.2])
    with c1:
        cal_scope = st.radio(
            "달력 단위",
            ["월간 (Month)", "주간 (Week)", "일간 (Day)"],
            horizontal=True,
            label_visibility="collapsed",
            key="cal_scope_radio"
        )
    with c2:
        cal_layer = st.radio(
            "계층 필터",
            ["전체 보기", "큰 납기만", "실행 할 일만"],
            horizontal=True,
            label_visibility="collapsed",
            key="cal_layer_radio"
        )
    with c3:
        cal_search_kw = st.text_input(
            "달력 검색",
            placeholder="달력 통합 검색 (제목, Lot ID, 부서, Recipe 등)",
            label_visibility="collapsed",
            key="cal_search_input"
        )
    with c4:
        picked_date = st.date_input(
            "기준 날짜",
            value=st.session_state["cal_ref_date"],
            label_visibility="collapsed",
            key="cal_date_picker"
        )
        if picked_date != st.session_state["cal_ref_date"]:
            st.session_state["cal_ref_date"] = picked_date
            st.rerun()
    with c5:
        n1, n2, n3 = st.columns([1, 1.5, 1])
        step_days = 1 if cal_scope == "일간 (Day)" else (7 if cal_scope == "주간 (Week)" else 30)
        if n1.button("◀", use_container_width=True, help="이전", key="cal_nav_prev"):
            st.session_state["cal_ref_date"] -= timedelta(days=step_days)
            st.rerun()
        if n2.button("오늘", use_container_width=True, key="cal_nav_today"):
            st.session_state["cal_ref_date"] = db.get_kst_today()
            st.rerun()
        if n3.button("▶", use_container_width=True, help="다음", key="cal_nav_next"):
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
            or (cal_layer == "큰 납기만" and t["is_milestone"])
            or (cal_layer == "실행 할 일만" and not t["is_milestone"])
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

    if drawer_id:
        cal_col, drawer_col = st.columns([6.3, 3.7])
    else:
        cal_col = st.container()
        drawer_col = None

    def render_cell_events(d_str: str, key_scope: str, show_meta: bool = False):
        items = events_by_date.get(d_str, [])
        if not items:
            st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)
            return

        for it in items:
            tid = it["id"]
            is_big = it["is_milestone"]
            is_done = (it["status"] == "완료")
            urg = it.get("urgency") or ""
            p_tag = f"[{id_to_title[it['parent_id']]}] " if it.get("parent_id") in id_to_title else ""

            prefix = "[납기] " if is_big else p_tag
            done_tag = "(완료) " if is_done else ("! " if urg == "긴급" else "")
            btn_text = f"{done_tag}{prefix}{it['display_title']}"
            is_selected = (tid == drawer_id)

            if st.button(
                btn_text,
                key=f"cal_chip_{key_scope}_{d_str}_{tid}",
                type="primary" if (is_selected or (is_big and not is_done)) else "secondary",
                use_container_width=True,
                help=f"#{tid} {prefix}{it['display_title']} | 담당: {it.get('assignee') or '-'} | 상태: {it['status']}"
            ):
                st.session_state["cal_selected_todo_id"] = tid
                st.rerun()

            if show_meta:
                meta_items = [
                    x for x in [
                        f"부서: {it['department']}" if it.get("department") else "",
                        f"의뢰자: {it['requester']}" if it.get("requester") else "",
                        f"Lot: {it['lot_id']}" if it.get("lot_id") else "",
                        f"Recipe: {it['recipe_id']}" if it.get("recipe_id") else "",
                        f"담당: {it['assignee']}" if it.get("assignee") else "",
                        f"상태: {it['status']}"
                    ] if x
                ]
                st.caption(" · ".join(meta_items))
            elif it.get("_match_reasons"):
                st.caption(f"검색: {' · '.join(it['_match_reasons'])}")

    with cal_col:
        if cal_scope == "일간 (Day)":
            d_str = ref_date.strftime("%Y-%m-%d")
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            st.markdown(f"#### {ref_date.year}년 {ref_date.month}월 {ref_date.day}일 ({day_names[ref_date.weekday()]})")
            with st.container(border=True):
                if d_str not in events_by_date:
                    st.info("해당 날짜에 등록된 일정이 없습니다.")
                else:
                    render_cell_events(d_str, key_scope="day", show_meta=True)

        elif cal_scope == "주간 (Week)":
            start_week = ref_date - timedelta(days=ref_date.weekday())
            end_week = start_week + timedelta(days=6)
            st.markdown(f"#### {start_week.year}년 {start_week.month}월 {start_week.day}일 ~ {end_week.month}월 {end_week.day}일")
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            w_cols = st.columns(7, gap="small")
            for i in range(7):
                cur_d = start_week + timedelta(days=i)
                d_str = cur_d.strftime("%Y-%m-%d")
                is_today = (d_str == today_str)
                with w_cols[i]:
                    with st.container(border=True):
                        if is_today:
                            st.markdown(f"<span class='cal-today-num'>{cur_d.month}/{cur_d.day} ({day_names[i]}) 오늘</span>", unsafe_allow_html=True)
                        else:
                            dow_cls = "sun" if i == 6 else ("sat" if i == 5 else "")
                            st.markdown(f"<div class='cal-date-num {dow_cls}'>{cur_d.month}/{cur_d.day} ({day_names[i]})</div>", unsafe_allow_html=True)
                        render_cell_events(d_str, key_scope="week", show_meta=True)

        else:  # 월간 (Month)
            st.markdown(f"#### {ref_date.year}년 {ref_date.month}월")
            cal_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(ref_date.year, ref_date.month)
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            dow_html = "".join(
                f"<div class='cal-dow-cell {'sun' if i==6 else ('sat' if i==5 else '')}'>{day_names[i]}</div>"
                for i in range(7)
            )
            st.markdown(f"<div class='cal-dow-row'>{dow_html}</div>", unsafe_allow_html=True)

            for week_dates in cal_weeks:
                cols = st.columns(7, gap="small")
                for idx, cell_date in enumerate(week_dates):
                    d_str = cell_date.strftime("%Y-%m-%d")
                    is_cur_month = (cell_date.month == ref_date.month)
                    is_today = (d_str == today_str)
                    with cols[idx]:
                        with st.container(border=True):
                            if is_today:
                                st.markdown(f"<span class='cal-today-num'>{cell_date.day}일 · 오늘</span>", unsafe_allow_html=True)
                            elif is_cur_month:
                                st.markdown(f"<div class='cal-date-num'>{cell_date.day}일</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='cal-date-muted'>{cell_date.month}/{cell_date.day}</div>", unsafe_allow_html=True)
                            render_cell_events(d_str, key_scope="month", show_meta=False)

    if drawer_col is not None and drawer_id:
        with drawer_col:
            render_todo_detail_editor(drawer_id, key_prefix="cal_drawer", show_close_btn=True)


# ==============================================================================
# 5. 메인 [할 일] 엔트리포인트
# ==============================================================================
def render_todo_module(theme: dict):
    if "todo_view_mode" not in st.session_state:
        st.session_state["todo_view_mode"] = "표 목록 + 세부정보"

    top_c1, top_c2, top_c3 = st.columns([4.2, 3.8, 2.0])
    with top_c1:
        st.subheader("할 일 관리")
    with top_c2:
        view_mode = st.radio(
            "보기 방식",
            ["표 목록 + 세부정보", "달력 (일 / 주 / 월)"],
            horizontal=True,
            label_visibility="collapsed",
            key="todo_view_mode"
        )
    with top_c3:
        if st.button("+ 새 할 일 등록", type="primary", use_container_width=True):
            reset_new_todo_dialog_state()
            open_new_todo_dialog()

    all_todos = db.get_todos_enriched(include_completed=True)
    id_to_title = {t["id"]: t["display_title"] for t in all_todos}

    if view_mode == "표 목록 + 세부정보":
        render_todo_table_view(all_todos, id_to_title, theme)
    else:
        render_todo_calendar_view(all_todos, id_to_title, theme)
