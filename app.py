import streamlit as st
import database as db
import todo_view
import other_views

st.set_page_config(
    page_title="RecipeManager v2.2.2",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

# ==============================================================================
# MS Office Fluent UI 테마 정의
# ==============================================================================
FLUENT_THEMES = {
    "MS Office 블루 (기본)": {
        "accent": "#0F6CBD",
        "accent_hover": "#115EA3",
        "accent_soft": "#EFF6FC",
        "bg_canvas": "#F3F2F1",
        "bg_card": "#FFFFFF",
        "text_main": "#201F1E",
        "text_sub": "#605E5C",
        "border": "#E1DFDD",
    },
    "MS Office 그린 (Excel)": {
        "accent": "#107C41",
        "accent_hover": "#0E6B37",
        "accent_soft": "#ECFDF5",
        "bg_canvas": "#F3F2F1",
        "bg_card": "#FFFFFF",
        "text_main": "#201F1E",
        "text_sub": "#605E5C",
        "border": "#E1DFDD",
    },
    "MS Office 슬레이트 (무채색)": {
        "accent": "#323130",
        "accent_hover": "#201F1E",
        "accent_soft": "#EDEBE9",
        "bg_canvas": "#F3F2F1",
        "bg_card": "#FFFFFF",
        "text_main": "#201F1E",
        "text_sub": "#605E5C",
        "border": "#D2D0CE",
    },
}

with st.sidebar:
    st.markdown("### RecipeManager `v2.2.2`")
    st.caption("반도체 검사·계측 실무 통합 워크스페이스")

    menu = st.radio(
        "메뉴 선택",
        [
            "할 일",
            "레시피 확인",
            "레시피 등록 및 매핑",
            "설비 횡전개 및 Diff",
            "기준정보 및 백업",
        ],
        label_visibility="collapsed",
        key="main_sidebar_menu"
    )

    st.divider()
    with db.get_connection() as conn:
        open_cnt = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료'").fetchone()[0]
        urg_cnt = conn.execute("SELECT COUNT(*) FROM work_requests WHERE status != '완료' AND urgency = '긴급'").fetchone()[0]
        hdl_cnt = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'HANDLER'").fetchone()[0]
        vis_cnt = conn.execute("SELECT COUNT(*) FROM recipes WHERE recipe_type = 'VISION'").fetchone()[0]

    c_s1, c_s2 = st.columns(2)
    c_s1.metric("할 일", f"{open_cnt}건")
    c_s2.metric("긴급", f"{urg_cnt}건")
    c_s3, c_s4 = st.columns(2)
    c_s3.metric("Handler", f"{hdl_cnt}개")
    c_s4.metric("Vision", f"{vis_cnt}개")

    st.divider()
    theme_name = st.selectbox("화면 테마", list(FLUENT_THEMES.keys()), index=0, key="ui_theme_select")

theme = FLUENT_THEMES[theme_name]

# ==============================================================================
# 전역 MS Office Fluent CSS (상단 흰색 헤더 박스 제거 + 체크박스 없는 행 선택 테이블)
# ==============================================================================
st.markdown(f"""
<style>
html, body, [class*="css"] {{
    font-family: 'Segoe UI', 'Malgun Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
}}
.stApp {{
    background-color: {theme['bg_canvas']};
    color: {theme['text_main']};
}}
/* 상단 흰색 헤더 바 제거 (배경 투명화 & 본문 겹침 방지) */
header[data-testid="stHeader"] {{
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    height: 2.2rem !important;
}}
section[data-testid="stSidebar"] {{
    background-color: #FAF9F8;
    border-right: 1px solid {theme['border']};
}}
.block-container {{
    padding-top: 2.3rem !important;
    padding-bottom: 2rem !important;
}}

/* Office 리본 상단 바 */
.office-ribbon {{
    background: {theme['bg_card']};
    border: 1px solid {theme['border']};
    border-top: 3px solid {theme['accent']};
    border-radius: 4px;
    padding: 8px 16px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.office-ribbon-title {{
    font-size: 14px;
    font-weight: 700;
    color: {theme['text_main']};
}}
.office-ribbon-sub {{
    font-size: 12px;
    color: {theme['text_sub']};
}}

/* 일반 버튼 규격화 */
div[data-testid="stButton"] > button {{
    border-radius: 4px !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    padding-left: 8px !important;
    padding-right: 8px !important;
}}
div[data-testid="stButton"] > button p {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 12px !important;
    margin: 0 !important;
}}
div[data-testid="stButton"] > button[kind="primary"] {{
    background-color: {theme['accent']} !important;
    border-color: {theme['accent']} !important;
    color: #FFFFFF !important;
}}
div[data-testid="stButton"] > button[kind="primary"]:hover {{
    background-color: {theme['accent_hover']} !important;
    border-color: {theme['accent_hover']} !important;
}}
div[data-testid="stButton"] > button[kind="secondary"] {{
    background-color: #F8F9FA !important;
    border: 1px solid {theme['border']} !important;
    color: {theme['text_main']} !important;
}}
div[data-testid="stButton"] > button[kind="secondary"]:hover {{
    background-color: {theme['accent_soft']} !important;
    border-color: {theme['accent']} !important;
}}

/* ============================================================================
   [할 일 테이블] 체크박스 없음 · 버튼 테두리 없음 · 한 행 전체 클릭 & 파란색 강조
   ============================================================================ */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.rm-clean-table) {{
    background-color: {theme['bg_card']} !important;
    border: 1px solid {theme['border']} !important;
    border-radius: 6px !important;
    padding: 0 !important;
    overflow: hidden !important;
}}
div[data-testid="stVerticalBlock"]:has(.rm-clean-table) {{
    gap: 0px !important;
    padding: 0 !important;
    background-color: {theme['bg_card']} !important;
}}

/* 마커 요소 컨테이너의 여백 완전 제거 */
div[data-testid="stElementContainer"]:has(.rm-clean-table),
div[data-testid="stElementContainer"]:has(.rm-row-state) {{
    display: none !important;
}}

/* 헤더 행 */
div[data-testid="stHorizontalBlock"]:has(.rm-th-cell) {{
    gap: 0px !important;
    margin: 0px !important;
    background-color: #FAF9F8 !important;
    border-bottom: 1px solid {theme['border']} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-th-cell) > div {{
    min-width: 0 !important;
    padding: 0 !important;
}}
.rm-th-cell {{
    font-size: 12px;
    font-weight: 600;
    color: {theme['text_sub']};
    padding: 8px 8px;
    border-right: 1px solid #EDEBE9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.rm-th-center {{ text-align: center; }}
.rm-th-left {{ text-align: left; }}

/* 데이터 행 전체 스타일 */
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) {{
    gap: 0px !important;
    margin: 0px !important;
    align-items: center !important;
    background-color: #FFFFFF !important;
    border-bottom: 1px solid #EDEBE9 !important;
    transition: background-color 0.08s ease;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-state):last-child {{
    border-bottom: none !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) > div {{
    min-width: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}}

/* 긴급 / 완료 / 마우스 호버 / 선택된 행 강조 */
div[data-testid="stHorizontalBlock"]:has(.rm-state-urgent) {{
    background-color: #FDF3F4 !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-state-urgent) button p {{
    color: #A4262C !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-state-done) button p {{
    color: #8A8886 !important;
    text-decoration: line-through !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-state):hover {{
    background-color: #F5F5F4 !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-state-selected) {{
    background-color: {theme['accent_soft']} !important;
    box-shadow: inset 3px 0 0 {theme['accent']} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-state-selected):hover {{
    background-color: {theme['accent_soft']} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-state-selected) button p {{
    color: {theme['accent']} !important;
    font-weight: 700 !important;
}}

/* 행 내부 셀 버튼은 테두리/배경 없이 투명한 표 셀처럼 처리 */
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) div[data-testid="stButton"] > button,
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) div[data-testid="stButton"] > button:hover,
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) div[data-testid="stButton"] > button:focus,
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) div[data-testid="stButton"] > button:active {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-right: 1px solid #F3F2F1 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    min-height: 35px !important;
    height: 35px !important;
    padding: 0 8px !important;
    margin: 0 !important;
    justify-content: flex-start !important;
    text-align: left !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) > div:first-child div[data-testid="stButton"] > button {{
    justify-content: center !important;
    text-align: center !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-state) > div:last-child div[data-testid="stButton"] > button {{
    border-right: none !important;
}}

/* 달력 요일 헤더 */
.cal-dow-row {{
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    background: #FFFFFF;
    border: 1px solid {theme['border']};
    border-radius: 4px;
    margin-bottom: 6px;
}}
.cal-dow-cell {{
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    color: {theme['text_main']};
    padding: 7px 0;
    border-right: 1px solid {theme['border']};
}}
.cal-dow-cell:last-child {{
    border-right: none;
}}
.cal-dow-cell.sat {{ color: #0F6CBD; }}
.cal-dow-cell.sun {{ color: #A4262C; }}

.cal-date-num {{
    font-size: 12px;
    font-weight: 700;
    color: {theme['text_main']};
    margin-bottom: 4px;
}}
.cal-date-num.sat {{ color: #0F6CBD; }}
.cal-date-num.sun {{ color: #A4262C; }}
.cal-date-muted {{
    font-size: 11.5px;
    color: #A19F9D;
    margin-bottom: 4px;
}}
.cal-today-num {{
    display: inline-block;
    background: {theme['accent']};
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 10px;
    margin-bottom: 4px;
}}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="office-ribbon">
    <div>
        <span class="office-ribbon-title">RecipeManager Workspace</span>
        <span class="office-ribbon-sub"> &nbsp;|&nbsp; 현재 메뉴: <b>{menu}</b></span>
    </div>
    <div class="office-ribbon-sub">기준시각(KST): {db.get_kst_str('%Y-%m-%d %H:%M')}</div>
</div>
""", unsafe_allow_html=True)

if menu == "할 일":
    todo_view.render_todo_module(theme)
elif menu == "레시피 확인":
    other_views.render_recipe_check_view()
elif menu == "레시피 등록 및 매핑":
    other_views.render_recipe_manage_view()
elif menu == "설비 횡전개 및 Diff":
    other_views.render_deploy_and_diff_view()
elif menu == "기준정보 및 백업":
    other_views.render_master_and_backup_view()
