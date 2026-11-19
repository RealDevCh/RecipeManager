import streamlit as st
import database as db
import todo_view
import other_views

st.set_page_config(
    page_title="RecipeManager v2.1.0",
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
    st.markdown("### RecipeManager `v2.1.0`")
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
# 전역 MS Office Fluent CSS
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
section[data-testid="stSidebar"] {{
    background-color: #FAF9F8;
    border-right: 1px solid {theme['border']};
}}
.block-container {{
    padding-top: 1.1rem !important;
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

/* 버튼 규격화 (줄바꿈 및 셀 넘침 방지) */
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
