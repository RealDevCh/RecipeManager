import streamlit as st
import database as db
import todo_view
import other_views

st.set_page_config(
    page_title="RecipeManager v2.0.0",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

# ==============================================================================
# MS Office Fluent UI 테마 정의 (일관된 엔터프라이즈 디자인 시스템)
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
    st.markdown("### RecipeManager `v2.0.0`")
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
    c_s2.metric("긴급", f"{urg_cnt}건")
    c_s3, c_s4 = st.columns(2)
    c_s3.metric("Handler", f"{hdl_cnt}개")
    c_s4.metric("Vision", f"{vis_cnt}개")

    st.divider()
    theme_name = st.selectbox("화면 테마", list(FLUENT_THEMES.keys()), index=0)

theme = FLUENT_THEMES[theme_name]

# ==============================================================================
# 전역 MS Office Fluent CSS (리본 헤더 + 상단 마일스톤 로드맵 + 심리스 7열 달력)
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

/* 버튼 기본 규격화 (줄바꿈/넘침 방지) */
div[data-testid="stButton"] > button {{
    border-radius: 4px !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}}
div[data-testid="stButton"] > button p {{
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 12.5px !important;
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

/* [시안 C] 상단 마일스톤 로드맵 바 */
.ms-roadmap-bar {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 10px;
    margin-bottom: 12px;
}}
a.ms-roadmap-card {{
    display: block;
    text-decoration: none !important;
    background: {theme['bg_card']};
    border: 1px solid {theme['border']};
    border-left: 4px solid #8A8886;
    border-radius: 6px;
    padding: 10px 12px;
    color: {theme['text_main']} !important;
    transition: all 0.15s ease;
}}
a.ms-roadmap-card:hover {{
    border-color: {theme['accent']};
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}}
a.ms-roadmap-card.active {{
    background: {theme['accent_soft']};
    border-color: {theme['accent']};
    border-left: 4px solid {theme['accent']};
}}
.ms-card-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}}
.ms-badge-all {{
    font-size: 11px;
    font-weight: 700;
    color: {theme['text_sub']};
    background: #F3F2F1;
    padding: 1px 6px;
    border-radius: 4px;
}}
.ms-badge-target {{
    font-size: 11px;
    font-weight: 700;
    color: {theme['accent']};
    background: {theme['accent_soft']};
    padding: 1px 6px;
    border-radius: 4px;
}}
.ms-card-cnt {{
    font-size: 11px;
    color: {theme['text_sub']};
}}
.ms-card-title {{
    font-size: 13px;
    font-weight: 700;
    color: {theme['text_main']};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 6px;
}}
.ms-prog-track {{
    width: 100%;
    height: 5px;
    background: #EDEBE9;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 5px;
}}
.ms-prog-fill {{
    height: 100%;
    background: {theme['accent']};
    border-radius: 3px;
}}
.ms-card-sub {{
    font-size: 11px;
    color: {theme['text_sub']};
}}

/* [시안 B] 풀폭 심리스 7열 달력 그리드 & 슬림 이벤트 칩 */
.cal-wrapper {{
    background: {theme['bg_card']};
    border: 1px solid {theme['border']};
    border-radius: 6px;
    overflow: hidden;
}}
.cal-dow-row {{
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    background: #FAF9F8;
    border-bottom: 1px solid {theme['border']};
}}
.cal-dow-cell {{
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    color: {theme['text_main']};
    padding: 8px 0;
    border-right: 1px solid {theme['border']};
}}
.cal-dow-cell:last-child {{
    border-right: none;
}}
.cal-dow-cell.sat {{ color: #0F6CBD; }}
.cal-dow-cell.sun {{ color: #A4262C; }}

.cal-body-grid {{
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}}
.cal-grid-cell {{
    min-height: 116px;
    padding: 6px 7px;
    border-right: 1px solid {theme['border']};
    border-bottom: 1px solid {theme['border']};
    background: #FFFFFF;
    display: flex;
    flex-direction: column;
    gap: 4px;
}}
.cal-grid-cell.week-cell {{
    min-height: 260px;
}}
.cal-grid-cell:nth-child(7n) {{
    border-right: none;
}}
.cal-grid-cell.is-muted {{
    background: #FAF9F8;
}}
.cal-grid-cell.is-today {{
    background: #F8FBFF;
}}
.cal-cell-top {{
    display: flex;
    align-items: center;
    margin-bottom: 2px;
}}
.cal-date-num {{
    font-size: 12px;
    font-weight: 600;
    color: {theme['text_main']};
}}
.cal-date-muted {{
    font-size: 11.5px;
    color: #A19F9D;
}}
.cal-today-num {{
    display: inline-block;
    background: {theme['accent']};
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 10px;
}}
.cal-cell-body {{
    display: flex;
    flex-direction: column;
    gap: 3px;
}}

/* 달력 이벤트 칩 (<a target="_self">) */
a.cal-event-pill {{
    display: block;
    text-decoration: none !important;
    padding: 3px 6px;
    border-radius: 3px;
    font-size: 11.5px;
    line-height: 1.3;
    border-left: 3px solid {theme['accent']};
    background: {theme['accent_soft']};
    color: {theme['text_main']} !important;
    transition: filter 0.12s ease;
}}
a.cal-event-pill:hover {{
    filter: brightness(0.96);
}}
a.cal-event-pill.pill-milestone {{
    background: #EBF5FF;
    border-left-color: #0F6CBD;
    color: #004578 !important;
    font-weight: 700;
}}
a.cal-event-pill.pill-urgent {{
    background: #FDF3F4;
    border-left-color: #C50F1F;
    color: #750B1C !important;
    font-weight: 600;
}}
a.cal-event-pill.pill-high {{
    background: #FFF9F0;
    border-left-color: #D83B01;
    color: #6B2900 !important;
}}
a.cal-event-pill.pill-normal {{
    background: #F1FAF1;
    border-left-color: #107C41;
    color: #0B532B !important;
}}
a.cal-event-pill.pill-done {{
    background: #F3F2F1;
    border-left-color: #A19F9D;
    color: #605E5C !important;
    text-decoration: line-through !important;
}}
a.cal-event-pill.pill-selected {{
    outline: 2px solid {theme['accent']};
}}
.cal-pill-title {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.cal-pill-meta {{
    font-size: 10.5px;
    color: #605E5C;
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.cal-day-board {{
    background: #FFFFFF;
    border: 1px solid {theme['border']};
    border-radius: 6px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}}
.cal-empty-day {{
    color: #8A8886;
    font-size: 13px;
    padding: 24px 0;
    text-align: center;
}}
</style>
""", unsafe_allow_html=True)

# 상단 Office 리본 헤더
st.markdown(f"""
<div class="office-ribbon">
    <div>
        <span class="office-ribbon-title">RecipeManager Workspace</span>
        <span class="office-ribbon-sub"> &nbsp;|&nbsp; 현재 메뉴: <b>{menu}</b></span>
    </div>
    <div class="office-ribbon-sub">기준시각(KST): {db.get_kst_str('%Y-%m-%d %H:%M')}</div>
</div>
""", unsafe_allow_html=True)

# 메뉴 라우팅
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
