import os
import html
import inspect
import calendar
import unicodedata
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd
from PIL import Image
import database as db

try:
    from streamlit_paste_button import paste_image_button
    HAS_PASTE_BTN = True
except ImportError:
    HAS_PASTE_BTN = False

st.set_page_config(
    page_title="RecipeManager v1.9.0",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

# ==============================================================================
# Fluent UI 스타일시트
# 1) 할 일 표: 단일 체크박스 + 한 줄 전체 클릭 선택(셀 단위 아님) + 콤보박스 없음
# 2) 달력: 시안 B(풀폭 심리스 7열 격자 + 클릭 시 우측 세부정보 드로어) + 시안 C(상단 마일스톤 바)
# ==============================================================================
st.markdown("""
<style>
/* 공통 버튼 줄바꿈 및 넘침 방지 */
div[data-testid="stButton"] > button {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
div[data-testid="stButton"] > button p {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    margin: 0 !important;
}

/* [할 일 표] 전용 컨테이너: 행 간격을 좁히고 한 줄 전체를 표 행처럼 스타일링 */
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) > div[data-testid="stHorizontalBlock"] {
    gap: 4px !important;
    align-items: center !important;
    border-bottom: 1px solid #edebe9 !important;
    padding: 2px 0 !important;
    margin: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) div[data-testid="stButton"] > button {
    justify-content: flex-start !important;
    text-align: left !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 5px 10px !important;
    min-height: 34px !important;
    height: 34px !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) div[data-testid="stButton"] > button p {
    font-family: 'D2Coding', 'Consolas', 'Malgun Gothic', monospace !important;
    font-size: 12.5px !important;
    white-space: pre !important;
}
/* 미선택 행 (secondary) */
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) div[data-testid="stButton"] > button[kind="secondary"] {
    background: transparent !important;
    color: #201f1e !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #f3f2f1 !important;
}
/* 선택된 행 (primary) -> 한 줄 전체 하이라이트 */
div[data-testid="stVerticalBlock"]:has(> div .rm-todo-table-marker) div[data-testid="stButton"] > button[kind="primary"] {
    background: #eff6fc !important;
    color: #0f6cbd !important;
    border-left: 3px solid #0f6cbd !important;
    font-weight: 700 !important;
}

.rm-tbl-header {
    background: #f3f2f1;
    border-top: 1px solid #d2d0ce;
    border-bottom: 1px solid #d2d0ce;
    padding: 7px 10px;
    font-family: 'D2Coding', 'Consolas', 'Malgun Gothic', monospace;
    font-size: 12.5px;
    font-weight: 700;
    color: #323130;
    white-space: pre;
    overflow: hidden;
}
.rm-match-subline {
    font-size: 11px;
    color: #0f6cbd;
    background: #eff6fc;
    padding: 1px 8px;
    border-radius: 4px;
    margin: 0 0 3px 44px;
    display: inline-block;
}

/* [달력] 시안 B 스타일: 심리스(Seamless) 7열 헤어라인 그리드 & 슬림 이벤트 칩 */
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) > div[data-testid="stHorizontalBlock"] {
    gap: 0px !important;
    margin: 0 !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) > div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    border-right: 1px solid #e1dfdd !important;
    border-bottom: 1px solid #e1dfdd !important;
    padding: 5px 6px !important;
    min-height: 112px !important;
    background: #ffffff !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child,
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child {
    border-left: 1px solid #e1dfdd !important;
}
/* 달력 셀 내부의 일정 칩 버튼 */
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button {
    min-height: 23px !important;
    height: 23px !important;
    padding: 1px 6px !important;
    border-radius: 3px !important;
    justify-content: flex-start !important;
    text-align: left !important;
    margin-bottom: 2px !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button p {
    font-size: 11.5px !important;
    line-height: 1.2 !important;
}
/* 일반 실행 일정 칩 (secondary) */
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button[kind="secondary"] {
    background: #f0fdf4 !important;
    color: #1e4620 !important;
    border: none !important;
    border-left: 3px solid #107c10 !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #dcfce7 !important;
}
/* 큰 납기 / 긴급 강조 일정 칩 (primary) */
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button[kind="primary"] {
    background: #ebf8ff !important;
    color: #0f6cbd !important;
    border: none !important;
    border-left: 3px solid #0f6cbd !important;
    font-weight: 700 !important;
}
div[data-testid="stVerticalBlock"]:has(> div .rm-cal-grid-marker) div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #dbeafe !important;
}

.rm-cal-dow-bar {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    border: 1px solid #e1dfdd;
    background: #f8f9fa;
    border-radius: 6px 6px 0 0;
}
.rm-cal-dow-item {
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    padding: 7px 0;
    border-right: 1px solid #e1dfdd;
}
.rm-cal-dow-item:last-child {
    border-right: none;
}
.cal-day-num {
    font-size: 12px;
    font-weight: 700;
    color: #323130;
    margin-bottom: 4px;
}
.cal-day-muted {
    font-size: 11.5px;
    color: #a19f9d;
    margin-bottom: 4px;
}
.cal-today-badge {
    display: inline-block;
    background: #0f6cbd;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 10px;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

SUPPORTS_ACCEPT_NEW = "accept_new_options" in inspect.signature(st.selectbox).parameters


def display_width(text: str) -> int:
    """한글/이모지(폭 2)와 영문/숫자(폭 1)의 시각적 출력 폭 계산"""
    w = 0
    for ch in str(text):
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ("W", "F") else 1
    return w


def pad_display(text: str, target_width: int, align: str = "left") -> str:
    """시각적 출력 폭(target_width)에 맞춰 정확히 자르거나 공백 채우기"""
    s = str(text or "")
    cur_w = 0
    out_chars = []
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if cur_w + cw > target_width:
            if target_width >= 2 and out_chars:
                # 마지막 글자를 말줄임표(…)로 교체
                last_w = 2 if unicodedata.east_asian_width(out_chars[-1]) in ("W", "F") else 1
                out_chars.pop()
                cur_w -= last_w
                if cur_w + 2 <= target_width:
                    out_chars.append("…")
                    cur_w += 2
            break
        out_chars.append(ch)
        cur_w += cw

    trimmed = "".join(out_chars)
    pad_len = max(0, target_width - cur_w)
    if align == "right":
        return (" " * pad_len) + trimmed
    if align == "center":
        left_p = pad_len // 2
        return (" " * left_p) + trimmed + (" " * (pad_len - left_p))
    return trimmed + (" " * pad_len)


def format_todo_table_header() -> str:
    return (
        f"{pad_display('순서', 4, 'center')} │ "
        f"{pad_display('긴급', 6, 'center')} │ "
        f"{pad_display('할 일 키워드 (한 줄 클릭 시 우측 상세)', 32, 'left')} │ "
        f"{pad_display('목표기한', 10, 'center')} │ "
        f"{pad_display('담당자', 6, 'center')} │ "
        f"{pad_display('상태', 8, 'center')}"
    )


def format_todo_table_row(idx: int, t: dict, id_to_title: dict) -> str:
    p_tag = f"[{id_to_title[t['parent_id']]}] " if t.get("parent_id") in id_to_title else ""
    lvl_icon = "🎯" if t.get("task_level") == "납기(큰일)" else "⚡"
    urg_map = {"긴급": "🔴긴급", "높음": "🟠높음", "보통": "🔵보통", "낮음": "⚪낮음"}
    urg_str = urg_map.get(t.get("urgency") or "보통", "🔵보통")
    title_str = f"{lvl_icon}{p_tag}{t['title']}"
    due_str = (t.get("due_date") or "-")[:10]
    asg_str = t.get("assignee") or "유철형"
    stat_str = t.get("status") or "접수"

    return (
        f"{pad_display(f'{idx:02d}', 4, 'center')} │ "
        f"{pad_display(urg_str, 6, 'left')} │ "
        f"{pad_display(title_str, 32, 'left')} │ "
        f"{pad_display(due_str, 10, 'center')} │ "
        f"{pad_display(asg_str, 6, 'center')} │ "
        f"{pad_display(stat_str, 8, 'center')}"
    )


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
# 공통 세부정보 편집 폼 렌더러 (표 우측 패널 & 달력 우측 슬라이드 드로어 공용)
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

    # 상단 빠른 액션 바 (완료/복구 + 삭제 + [달력 드로어일 경우 닫기])
    if show_close_btn:
        act_c1, act_c2, act_c3 = st.columns([5.2, 2.6, 2.2])
    else:
        act_c1, act_c2 = st.columns([7, 3])
        act_c3 = None

    with act_c1:
        is_done = detail["status"] == "완료"
        if st.button(
            "↩️ 진행중 복구" if is_done else "✅ 완료 처리",
            type="primary" if not is_done else "secondary",
            use_container_width=True,
            key=f"{key_prefix}_toggle_{sel_id}"
        ):
            db.toggle_todo_complete(sel_id, detail["status"])
            st.rerun()
    with act_c2:
        with st.popover("🗑️ 삭제", use_container_width=True):
            st.warning("이 할 일과 증빙 이미지를 삭제할까요?")
            if st.button("삭제 확인", key=f"{key_prefix}_del_ok_{sel_id}", type="primary", use_container_width=True):
                db.delete_work_request(sel_id)
                if st.session_state.get("selected_todo_id") == sel_id:
                    st.session_state["selected_todo_id"] = None
                if st.session_state.get("checked_todo_id") == sel_id:
                    st.session_state["checked_todo_id"] = None
                if st.session_state.get("cal_selected_todo_id") == sel_id:
                    st.session_state["cal_selected_todo_id"] = None
                st.rerun()
    if act_c3 is not None:
        with act_c3:
            if st.button("✕ 닫기", use_container_width=True, key=f"{key_prefix}_drawer_close_{sel_id}"):
                st.session_state["cal_selected_todo_id"] = None
                st.rerun()

    with st.container(border=True):
        st.markdown(f"#### 🔍 #{detail['id']} 세부 정보")
        st.caption(
            f"등록일시: **{detail.get('created_at') or '-'}** | "
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
                st.caption("🎯 상단 로드맵 바에 표시되는 큰 납기 항목입니다.")
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
        st.markdown(f"**📎 증빙 이미지 ({len(atts)}건)**")
        if atts:
            img_cols = st.columns(3)
            for idx_a, att in enumerate(atts):
                if att.get("file_path") and os.path.exists(att["file_path"]):
                    with img_cols[idx_a % 3]:
                        st.image(att["file_path"], use_container_width=True)
                        b_z, b_d = st.columns(2)
                        with b_z:
                            with st.popover("🔍"):
                                st.image(att["file_path"], caption=att["file_name"], use_container_width=True)
                        with b_d:
                            if st.button("🗑️", key=f"{key_prefix}_del_att_{att['id']}", help="이미지 삭제"):
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
                    label="📋 Ctrl+V 추가",
                    background_color="#0f6cbd",
                    text_color="#ffffff",
                    key=f"{key_prefix}_paste_{sel_id}"
                )
                if p_add.image_data is not None:
                    db.save_todo_attachments(sel_id, pasted_images=[p_add.image_data])
                    st.rerun()

        if st.button("💾 수정사항 저장", type="primary", use_container_width=True, key=f"{key_prefix}_save_{sel_id}"):
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
                st.success("저장되었습니다.")
                st.rerun()


# ==============================================================================
# 바깥 클릭 시 닫히지 않는 중앙 모달 등록 창 (@st.dialog)
# ==============================================================================
@st.dialog("➕ 새 할 일 등록", width="large")
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
                "상위 업무 연결 (큰 일 선택 시 표·달력에 [상위업무] 자동 태깅)",
                ["(단독 실행 업무)"] + list(parent_map.keys()),
                key="dlg_parent_sel"
            )
            t_parent_id = parent_map.get(sel_parent_lbl)
        else:
            st.info("상단 마일스톤 바에 표시되는 큰 목표/납기로 등록됩니다.")
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
            "목표 기한 (달력 선택)*",
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

    st.markdown("**📎 증빙 이미지 첨부 (N개 다중 등록 가능)**")
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
                label="📋 클립보드 캡처 추가 (Ctrl+V)",
                background_color="#0f6cbd",
                text_color="#ffffff",
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
        if st.button("💾 할 일 등록 완료", type="primary", use_container_width=True, key="dlg_submit_btn"):
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
                st.rerun()
    with btn_c2:
        if st.button("닫기", use_container_width=True, key="dlg_close_btn"):
            st.session_state["dlg_pasted_imgs"] = []
            st.rerun()


# ==============================================================================
# 사이드바 내비게이션
# ==============================================================================
with st.sidebar:
    st.markdown("## ⚙️ RecipeManager `v1.9.0`")
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
# [메인 1] ✅ 할 일
# ==============================================================================
if menu == "✅ 할 일":
    if "checked_todo_id" not in st.session_state:
        st.session_state["checked_todo_id"] = None

    top_c1, top_c2, top_c3 = st.columns([4.2, 3.8, 2.0])
    with top_c1:
        st.subheader("✅ 할 일 관리")
    with top_c2:
        view_mode = st.radio(
            "보기 방식",
            ["📋 표 목록 + 세부정보", "📅 달력 (일 / 주 / 월)"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with top_c3:
        if st.button("➕ 새 할 일 등록", type="primary", use_container_width=True):
            open_new_todo_dialog()

    all_todos = db.get_todos_enriched(include_completed=True)
    id_to_title = {t["id"]: t["title"] for t in all_todos}

    # --------------------------------------------------------------------------
    # [뷰 1] 할 일 표 (단일 체크박스 우선순위 이동 + 한 줄 클릭 우측 상세 + 하단 콤보박스 없음)
    # --------------------------------------------------------------------------
    if view_mode == "📋 표 목록 + 세부정보":
        f_c1, f_c2, f_c3 = st.columns([2.3, 3.7, 4.0])
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
                placeholder="🔎 통합 검색 (제목, Lot ID, 부서, 의뢰자, 설비, 내용, 파일명 등)",
                label_visibility="collapsed"
            )

        base_todos = [
            t for t in all_todos
            if (show_completed or t["status"] != "완료")
            and (filter_level == "전체" or (t.get("task_level") or "실행(소규모)") == filter_level)
        ]
        todos = db.filter_todos_by_query(base_todos, search_kw)
        visible_ids = [t["id"] for t in todos]

        # 단일 체크 ID가 현재 목록에 없으면 초기화
        checked_id = st.session_state.get("checked_todo_id")
        if checked_id not in visible_ids:
            checked_id = None
            st.session_state["checked_todo_id"] = None

        col_tbl, col_detail = st.columns([5.8, 4.2])

        with col_tbl:
            # 표 바로 위 우선순위 조정 버튼 바
            prio_c1, prio_c2, prio_c3, prio_c4, prio_c5 = st.columns([1.4, 1.5, 1.5, 1.3, 4.3])
            has_checked = checked_id is not None
            with prio_c1:
                if st.button("▲ 위", disabled=not has_checked, use_container_width=True, help="체크한 항목을 위로 한 칸 이동"):
                    if db.move_single_checked_todo(visible_ids, checked_id, "up"):
                        st.rerun()
            with prio_c2:
                if st.button("▼ 아래", disabled=not has_checked, use_container_width=True, help="체크한 항목을 아래로 한 칸 이동"):
                    if db.move_single_checked_todo(visible_ids, checked_id, "down"):
                        st.rerun()
            with prio_c3:
                if st.button("⏫ 맨위", disabled=not has_checked, use_container_width=True, help="체크한 항목을 맨 위로 이동"):
                    if db.move_single_checked_todo(visible_ids, checked_id, "top"):
                        st.rerun()
            with prio_c4:
                if st.button("해제", disabled=not has_checked, use_container_width=True, help="체크 해제"):
                    st.session_state["checked_todo_id"] = None
                    for tid in visible_ids:
                        st.session_state[f"single_chk_{tid}"] = False
                    st.rerun()
            with prio_c5:
                if has_checked:
                    st.caption(f"✅ **#{checked_id}** 선택됨 — 위/아래 이동 시 체크 유지")
                else:
                    st.caption("☑️ 좌측 체크(1개): 순서 이동 · 한 줄 클릭: 우측 상세")

            if not todos:
                st.info("조건에 일치하는 할 일이 없습니다. 검색어를 지우거나 [➕ 새 할 일 등록]으로 추가하세요.")
            else:
                cur_sel_id = st.session_state.get("selected_todo_id")
                if not cur_sel_id or cur_sel_id not in visible_ids:
                    cur_sel_id = visible_ids[0]
                    st.session_state["selected_todo_id"] = cur_sel_id

                # 표 컨테이너 (CSS 마커로 각 행을 한 줄 그리드로 결합)
                with st.container():
                    st.markdown("<div class='rm-todo-table-marker'></div>", unsafe_allow_html=True)

                    # 헤더 행
                    h_c1, h_c2 = st.columns([0.55, 9.45])
                    h_c1.markdown("<div class='rm-tbl-header' style='text-align:center;padding-left:0;padding-right:0;'>이동</div>", unsafe_allow_html=True)
                    h_c2.markdown(f"<div class='rm-tbl-header'>{html.escape(format_todo_table_header())}</div>", unsafe_allow_html=True)

                    # 데이터 행 (1줄 = 단일 체크박스 + 전체 한 줄 클릭 버튼)
                    for idx, t in enumerate(todos, start=1):
                        tid = t["id"]
                        is_selected_row = (tid == cur_sel_id)
                        r_c1, r_c2 = st.columns([0.55, 9.45])

                        # 단일 선택 체크박스 (하나만 체크되도록 강제)
                        with r_c1:
                            chk_key = f"single_chk_{tid}"
                            st.session_state[chk_key] = (checked_id == tid)
                            new_val = st.checkbox("이동선택", key=chk_key, label_visibility="collapsed")
                            if new_val and checked_id != tid:
                                # 다른 항목의 체크를 모두 해제하고 현재 항목만 체크 유지
                                for other_id in visible_ids:
                                    if other_id != tid:
                                        st.session_state[f"single_chk_{other_id}"] = False
                                st.session_state["checked_todo_id"] = tid
                                st.rerun()
                            elif not new_val and checked_id == tid:
                                st.session_state["checked_todo_id"] = None
                                st.rerun()

                        # 한 줄 전체 클릭 버튼 (셀 단위가 아닌 항목 한 줄 전체 선택 -> 우측 상세 연동)
                        with r_c2:
                            row_label = format_todo_table_row(idx, t, id_to_title)
                            tooltip_txt = f"#{tid} {t['title']} | 부서: {t.get('department') or '-'} | 의뢰자: {t.get('requester') or '-'} | Lot: {t.get('lot_id') or '-'}"
                            if st.button(
                                row_label,
                                key=f"todo_fullrow_{tid}",
                                type="primary" if is_selected_row else "secondary",
                                use_container_width=True,
                                help=tooltip_txt
                            ):
                                st.session_state["selected_todo_id"] = tid
                                st.rerun()

                        if t.get("_match_reasons"):
                            reasons_str = html.escape(" · ".join(t["_match_reasons"]))
                            st.markdown(f"<div class='rm-match-subline'>🔎 {reasons_str}</div>", unsafe_allow_html=True)

        # 우측 세부정보 패널 (항목 선택 시 오른쪽에 즉시 표시)
        with col_detail:
            sel_id = st.session_state.get("selected_todo_id")
            if sel_id and sel_id in visible_ids:
                render_todo_detail_editor(sel_id, key_prefix="tbl_ed", show_close_btn=False)
            else:
                st.info("좌측 표에서 할 일 한 줄을 클릭하면 오른쪽에 세부 정보가 표시됩니다.")

    # --------------------------------------------------------------------------
    # [뷰 2] 📅 달력 UI (시안 B 풀폭 심리스 격자 + 우측 드로어 & 시안 C 상단 마일스톤 바)
    # --------------------------------------------------------------------------
    else:
        if "cal_ref_date" not in st.session_state:
            st.session_state["cal_ref_date"] = db.get_kst_today()
        if "cal_selected_milestone_id" not in st.session_state:
            st.session_state["cal_selected_milestone_id"] = None
        if "cal_selected_todo_id" not in st.session_state:
            st.session_state["cal_selected_todo_id"] = None

        # 1) 시안 C 요소: 상단 마일스톤 로드맵 바 (큰 납기 진행률 카드 & 클릭 필터)
        milestones = [t for t in all_todos if t.get("task_level") == "납기(큰일)"]
        if milestones:
            st.markdown("##### 🎯 상위 프로젝트 · 큰 납기 로드맵 (클릭 시 해당 프로젝트 일정만 달력에 필터링)")
            ms_cols = st.columns(min(len(milestones), 4) + 1)
            active_ms_id = st.session_state["cal_selected_milestone_id"]

            with ms_cols[0]:
                is_all_ms = (active_ms_id is None)
                if st.button(
                    "🌐 전체 일정 보기",
                    type="primary" if is_all_ms else "secondary",
                    use_container_width=True,
                    key="ms_filter_all"
                ):
                    st.session_state["cal_selected_milestone_id"] = None
                    st.rerun()
                st.caption(f"전체 등록 일정 {len(all_todos)}건")

            for idx_m, ms in enumerate(milestones[:4]):
                sub_tasks = [x for x in all_todos if x.get("parent_id") == ms["id"]]
                done_cnt = sum(1 for x in sub_tasks if x["status"] == "완료")
                total_sub = len(sub_tasks)
                pct = int((done_cnt / total_sub) * 100) if total_sub > 0 else (100 if ms["status"] == "완료" else 0)
                is_active_ms = (active_ms_id == ms["id"])

                with ms_cols[idx_m + 1]:
                    with st.container(border=True):
                        btn_lbl = f"{'✅ ' if is_active_ms else '🎯 '}{ms['title']}"
                        if st.button(
                            btn_lbl,
                            type="primary" if is_active_ms else "secondary",
                            use_container_width=True,
                            key=f"ms_card_btn_{ms['id']}"
                        ):
                            st.session_state["cal_selected_milestone_id"] = None if is_active_ms else ms["id"]
                            st.rerun()
                        st.progress(pct / 100.0)
                        st.caption(f"납기: **{ms.get('due_date') or '-'}** · 하위완료 {done_cnt}/{total_sub} ({pct}%)")

        st.divider()

        # 2) 달력 상단 제어 바
        cal_r1_c1, cal_r1_c2, cal_r1_c3 = st.columns([3.5, 4.0, 2.5])
        with cal_r1_c1:
            cal_scope = st.radio(
                "달력 단위",
                ["월간 (Month)", "주간 (Week)", "일간 (Day)"],
                horizontal=True,
                label_visibility="collapsed"
            )
        with cal_r1_c2:
            cal_layer = st.radio(
                "계층 필터",
                ["전체 보기", "🎯 큰 납기만", "⚡ 세부 실행만"],
                horizontal=True,
                label_visibility="collapsed"
            )
        with cal_r1_c3:
            nav1, nav2, nav3 = st.columns([1, 1.4, 1])
            step_days = 1 if cal_scope == "일간 (Day)" else (7 if cal_scope == "주간 (Week)" else 30)
            if nav1.button("◀", use_container_width=True, help="이전"):
                st.session_state["cal_ref_date"] -= timedelta(days=step_days)
                st.rerun()
            if nav2.button("오늘", use_container_width=True):
                st.session_state["cal_ref_date"] = db.get_kst_today()
                st.rerun()
            if nav3.button("▶", use_container_width=True, help="다음"):
                st.session_state["cal_ref_date"] += timedelta(days=step_days)
                st.rerun()

        cal_r2_c1, cal_r2_c2 = st.columns([7.5, 2.5])
        with cal_r2_c1:
            cal_search_kw = st.text_input(
                "달력 전방위 검색",
                placeholder="🔎 달력 통합 검색 (제목, Lot ID, 의뢰부서, 의뢰자, 설비, 파일명 등)",
                label_visibility="collapsed"
            )
        with cal_r2_c2:
            picked_date = st.date_input(
                "기준 날짜",
                value=st.session_state["cal_ref_date"],
                label_visibility="collapsed"
            )
            if picked_date != st.session_state["cal_ref_date"]:
                st.session_state["cal_ref_date"] = picked_date

        ref_date = st.session_state["cal_ref_date"]
        sel_ms_id = st.session_state["cal_selected_milestone_id"]

        cal_candidates = [
            t for t in all_todos
            if t.get("due_date")
            and (
                sel_ms_id is None
                or t["id"] == sel_ms_id
                or t.get("parent_id") == sel_ms_id
            )
            and (
                cal_layer == "전체 보기"
                or (cal_layer == "🎯 큰 납기만" and t.get("task_level") == "납기(큰일)")
                or (cal_layer == "⚡ 세부 실행만" and (t.get("task_level") or "실행(소규모)") == "실행(소규모)")
            )
        ]
        filtered_cal_todos = db.filter_todos_by_query(cal_candidates, cal_search_kw)

        events_by_date: dict[str, list[dict]] = {}
        for t in filtered_cal_todos:
            d_key = str(t["due_date"])[:10]
            events_by_date.setdefault(d_key, []).append(t)

        today_dt = db.get_kst_today()
        today_str = today_dt.strftime("%Y-%m-%d")

        # 3) 시안 B 레이아웃: 미선택 시 100% 풀폭, 일정 클릭 시 우측 세부정보 드로어 오픈
        cal_drawer_id = st.session_state.get("cal_selected_todo_id")
        if cal_drawer_id and not any(t["id"] == cal_drawer_id for t in all_todos):
            cal_drawer_id = None
            st.session_state["cal_selected_todo_id"] = None

        if cal_drawer_id:
            cal_main_col, cal_drawer_col = st.columns([6.4, 3.6])
        else:
            cal_main_col = st.container()
            cal_drawer_col = None

        with cal_main_col:
            st.caption("💡 일정 칩을 클릭하면 우측에 세부정보 패널이 열립니다.")

            def render_day_cell_items(d_str: str, key_scope: str, detailed: bool = False):
                items = events_by_date.get(d_str, [])
                if not items:
                    return
                for it in items:
                    is_m = (it.get("task_level") == "납기(큰일)")
                    is_urg = (it.get("urgency") == "긴급" and it["status"] != "완료")
                    p_tag = f"[{id_to_title[it['parent_id']]}] " if it.get("parent_id") in id_to_title else ""
                    done_mark = "✓ " if it["status"] == "완료" else ""
                    urg_mark = "🔴 " if is_urg else ""
                    prefix = "🎯 " if is_m else f"▸ {p_tag}"
                    btn_label = f"{done_mark}{urg_mark}{prefix}{it['title']}"

                    if st.button(
                        btn_label,
                        key=f"cal_ev_{key_scope}_{d_str}_{it['id']}",
                        type="primary" if ((is_m or is_urg) and it["status"] != "완료") else "secondary",
                        use_container_width=True,
                        help=f"{it['title']} (담당: {it.get('assignee') or '유철형'} / 기한: {d_str})"
                    ):
                        st.session_state["cal_selected_todo_id"] = it["id"]
                        st.rerun()

                    if detailed:
                        meta_parts = [
                            x for x in [
                                f"부서: {it['department']}" if it.get("department") else "",
                                f"의뢰자: {it['requester']}" if it.get("requester") else "",
                                f"Lot: {it['lot_id']}" if it.get("lot_id") else "",
                                f"담당: {it['assignee']}" if it.get("assignee") else "",
                                f"상태: {it['status']}"
                            ] if x
                        ]
                        st.caption(" | ".join(meta_parts))
                    elif it.get("_match_reasons"):
                        st.caption(f"🔎 {' · '.join(it['_match_reasons'])}")

            if cal_scope == "일간 (Day)":
                d_str = ref_date.strftime("%Y-%m-%d")
                day_names = ["월", "화", "수", "목", "금", "토", "일"]
                st.markdown(f"#### 📅 {ref_date.year}년 {ref_date.month}월 {ref_date.day}일 ({day_names[ref_date.weekday()]})")
                with st.container(border=True):
                    render_day_cell_items(d_str, key_scope="day", detailed=True)

            elif cal_scope == "주간 (Week)":
                start_week = ref_date - timedelta(days=ref_date.weekday())
                end_week = start_week + timedelta(days=6)
                st.markdown(f"#### 📅 {start_week.year}년 {start_week.month}월 {start_week.day}일 ~ {end_week.month}월 {end_week.day}일")

                st.markdown("""
                <div class='rm-cal-dow-bar'>
                    <div class='rm-cal-dow-item' style='color:#323130;'>월</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>화</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>수</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>목</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>금</div>
                    <div class='rm-cal-dow-item' style='color:#0f6cbd;'>토</div>
                    <div class='rm-cal-dow-item' style='color:#a4262c;'>일</div>
                </div>
                """, unsafe_allow_html=True)

                with st.container():
                    st.markdown("<div class='rm-cal-grid-marker'></div>", unsafe_allow_html=True)
                    w_cols = st.columns(7)
                    for i in range(7):
                        cur_d = start_week + timedelta(days=i)
                        d_str = cur_d.strftime("%Y-%m-%d")
                        is_today = (d_str == today_str)
                        with w_cols[i]:
                            if is_today:
                                st.markdown(f"<span class='cal-today-badge'>{cur_d.month}/{cur_d.day} · 오늘</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='cal-day-num'>{cur_d.month}/{cur_d.day}</div>", unsafe_allow_html=True)
                            render_day_cell_items(d_str, key_scope="week", detailed=False)

            else:  # 월간 (Month) - 심리스 7열 그리드
                st.markdown(f"#### 📅 {ref_date.year}년 {ref_date.month}월")
                cal_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(ref_date.year, ref_date.month)

                st.markdown("""
                <div class='rm-cal-dow-bar'>
                    <div class='rm-cal-dow-item' style='color:#323130;'>월</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>화</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>수</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>목</div>
                    <div class='rm-cal-dow-item' style='color:#323130;'>금</div>
                    <div class='rm-cal-dow-item' style='color:#0f6cbd;'>토</div>
                    <div class='rm-cal-dow-item' style='color:#a4262c;'>일</div>
                </div>
                """, unsafe_allow_html=True)

                with st.container():
                    st.markdown("<div class='rm-cal-grid-marker'></div>", unsafe_allow_html=True)
                    for week_dates in cal_weeks:
                        cols = st.columns(7)
                        for idx, cell_date in enumerate(week_dates):
                            d_str = cell_date.strftime("%Y-%m-%d")
                            is_cur_month = (cell_date.month == ref_date.month)
                            is_today = (d_str == today_str)
                            with cols[idx]:
                                if is_today:
                                    st.markdown(f"<span class='cal-today-badge'>{cell_date.day}일 · 오늘</span>", unsafe_allow_html=True)
                                elif is_cur_month:
                                    st.markdown(f"<div class='cal-day-num'>{cell_date.day}일</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='cal-day-muted'>{cell_date.month}/{cell_date.day}</div>", unsafe_allow_html=True)
                                render_day_cell_items(d_str, key_scope="month", detailed=False)

        if cal_drawer_col is not None and cal_drawer_id:
            with cal_drawer_col:
                render_todo_detail_editor(cal_drawer_id, key_prefix="cal_drawer", show_close_btn=True)


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
                                    <div style="background:#f8fafc; border-left:4px solid #0f6cbd; padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:13px;">
                                        <b>[{chg['change_type']}]</b> &rarr; <span style="color:#0f6cbd;font-weight:600;">{chg.get('evaluation_result') or '-'}</span><br>
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
                                        VALUES (NULL, ?, ?, ?, ?, ?, ?, '유철형', ?, ?)
                                    """, (t_kind, sel_rec["name"], c_type, b_val, a_val, c_rsn, e_res, db.get_kst_str()))
                                    conn.commit()
                                st.success("변경 이력이 기록되었습니다.")
                                st.rerun()

                    with st.expander("🖼️ Align / 참조 이미지 관리 (Ctrl+V)"):
                        img_tag = st.selectbox("이미지 태그", ["ALIGN", "PATTERN", "MASTER", "DEFECT"], key=f"tag_{sel_rec['id']}")
                        p_img = None
                        if HAS_PASTE_BTN:
                            pr = paste_image_button("📋 클립보드 붙여넣기 (Ctrl+V)", background_color="#0f6cbd", text_color="#ffffff")
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
                    v_usr = st.text_input("검증자", value="유철형")
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
                                    VALUES (?, ?, ?, ?, '유철형', ?)
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
                                top = st.text_input("작업자", value="유철형")
                                tvr = st.text_input("검증자", value="유철형")
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
# [보조 3] 🛠️ 기준정보 및 백업 (의뢰 부서 Department CRUD 포함)
# ==============================================================================
elif menu == "🛠️ 기준정보 및 백업":
    st.subheader("🛠️ 기준정보 · Device Code 이력 · 백업/복구")

    t_master, t_code, t_audit, t_backup = st.tabs([
        "⚙️ 공통 기준정보 CRUD (의뢰 부서 포함)",
        "🏷️ Device Code 매핑 이력",
        "📜 전체 변경 감사 로그",
        "💾 원클릭 백업 및 복구"
    ])

    with t_master:
        cats = ["Department", "Product", "Step", "Module", "Purpose", "Equipment", "DeviceCode"]
        c1, c2 = st.columns([4, 6])
        sel_cat = c1.selectbox(
            "카테고리 (Department = 의뢰 부서)",
            cats,
            format_func=lambda x: "Department (의뢰 부서)" if x == "Department" else x
        )
        with c2:
            st.write("")
            with st.popover(f"➕ 신규 {sel_cat} 추가"):
                with st.form("add_m_form"):
                    nm = st.text_input("항목명*", placeholder="예: 제조기술팀" if sel_cat == "Department" else "신규 항목 입력")
                    if st.form_submit_button("추가", type="primary"):
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
