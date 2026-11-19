import streamlit as st
import database as db
import todo_view
import other_views

st.set_page_config(
    page_title="RecipeManager v2.2.0",
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
    st.markdown("### RecipeManager `v2.2.0`")
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
# 전역 MS Office Fluent CSS (한 행 전체 선택 테이블 + 심리스 달력)
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
   [할 일 테이블] 체크박스 없음 + 셀이 아닌 '한 행 전체' 선택 & 하이라이트
   ============================================================================ */
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) {{
    background: {theme['bg_card']} !important;
    border: 1px solid {theme['border']} !important;
    border-radius: 6px !important;
    overflow: hidden !important;
    gap: 0px !important;
}}

/* 헤더 및 모든 데이터 행의 컬럼 간격 제거 및 수직 정렬 */
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) > div[data-testid="stHorizontalBlock"] {{
    gap: 0px !important;
    margin: 0px !important;
    align-items: center !important;
    border-bottom: 1px solid {theme['border']} !important;
    transition: background-color 0.1s ease;
}}
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) > div[data-testid="stHorizontalBlock"]:last-child {{
    border-bottom: none !important;
}}

/* 각 컬럼이 좁아져도 절대 아래로 꺾이지 않도록 고정 */
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) div[data-testid="column"],
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) div[data-testid="stColumn"] {{
    min-width: 0 !important;
    overflow: hidden !important;
    padding: 0 !important;
}}

/* 숨겨진 행 상태 마커가 차지하는 여백 제거 */
div[data-testid="stVerticalBlock"]:has(> div .rm-fullrow-table-marker) div[data-testid="stMarkdownContainer"]:has(.rm-row-marker) {{
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}}

/* 테이블 헤더 셀 */
.rm-th-cell {{
    background: #FAF9F8;
    font-size: 12px;
    font-weight: 700;
    color: {theme['text_sub']};
    padding: 9px 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.rm-th-center {{ text-align: center; }}
.rm-th-left {{ text-align: left; padding-left: 8px; }}

/* 데이터 행 전체 상태 스타일 (긴급 / 완료 / 선택됨) */
div[data-testid="stHorizontalBlock"]:has(.rm-row-urgent) {{
    background-color: #FDF3F4 !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-urgent) button p {{
    color: #A4262C !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-done) button p {{
    color: #8A8886 !important;
    text-decoration: line-through !important;
}}

/* 한 행 전체 호버 효과 */
div[data-testid="stHorizontalBlock"]:has(.rm-row-marker):hover {{
    background-color: #F3F2F1 !important;
}}

/* 한 행 전체 선택됨 (체크박스 선택과 동일한 역할 + 좌측 강조 바) */
div[data-testid="stHorizontalBlock"]:has(.rm-row-selected) {{
    background-color: {theme['accent_soft']} !important;
    box-shadow: inset 3px 0 0 {theme['accent']} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-selected):hover {{
    background-color: {theme['accent_soft']} !important;
}}
div[data-testid="stHorizontalBlock"]:has(.rm-row-selected) button p {{
    color: {theme['accent']} !important;
    font-weight: 700 !important;
}}

/* 행 내부 개별 셀 버튼은 테두리/배경 없이 투명하게 통합 */
div[data-testid="stHorizontalBlock"]:has(.rm-row-marker) div[data-testid="stButton"] > button {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    min-height: 35px !important;
    height: 35px !important;
    padding: 0 4px !important;
    justify-content: center !important;
    text-align: center !important;
}}
/* 4번째 컬럼(할 일 키워드)만 좌측 정렬 */
div[data-testid="stHorizontalBlock"]:has(.rm-row-marker) > div:nth-child(4) div[data-testid="stButton"] > button {{
    justify-content: flex-start !important;
    text-align: left !important;
    padding-left: 8px !important;
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
