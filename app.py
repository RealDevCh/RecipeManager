import streamlit as st
import database as db
import backup_utils

st.set_page_config(
    page_title="RecipeManager v1.6.0",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

db.init_db()

st.markdown("""
<style>
    .hero-box {
        background: linear-gradient(135deg, #1e3a5f 0%, #2b5c8f 100%);
        color: #ffffff;
        padding: 20px 24px;
        border-radius: 12px;
        margin-bottom: 16px;
    }
    .hero-box h2 { margin: 0 0 6px 0; color: #ffffff; }
    .hero-box p { margin: 0; opacity: 0.9; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-box">
    <h2>⚙️ RecipeManager v1.6.0</h2>
    <p>실무 중심 2대 메인 워크스페이스(<b>✅ 할 일</b> · <b>🧩 레시피 확인</b>) 및 횡전개·Diff·백업 통합 관리 시스템</p>
</div>
""", unsafe_allow_html=True)

today_kst = db.get_kst_str("%Y-%m-%d")
with db.get_connection() as conn:
    overdue_cnt = conn.execute(
        "SELECT COUNT(*) FROM work_requests WHERE due_date IS NOT NULL AND due_date != '' AND due_date < ? AND status NOT IN ('완료', '보류')",
        (today_kst,)
    ).fetchone()[0]
    urgent_todos = [dict(r) for r in conn.execute(
        "SELECT id, title, product, step FROM work_requests WHERE status != '완료' AND urgency = '긴급' ORDER BY priority_order ASC"
    ).fetchall()]

if urgent_todos or overdue_cnt > 0:
    urgent_titles = ", ".join([f"#{u['id']} {u['title']}" for u in urgent_todos[:3]])
    st.error(
        f"🚨 **[긴급 / 지연 알림]** 긴급 미완료 할 일: **{len(urgent_todos)}건** ({urgent_titles or '-'}) | "
        f"기한 초과: **{overdue_cnt}건** (기준: {today_kst} KST)"
    )

stats = backup_utils.get_system_stats()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("미완료 할 일", f"{stats['todo_open']}건")
k2.metric("🔴 긴급 할 일", f"{stats['todo_urgent']}건")
k3.metric("Handler Recipe", f"{stats['handlers']}개")
k4.metric("Vision Recipe", f"{stats['visions']}개")
k5.metric("횡전개 프로젝트", f"{stats['deployments']}건")

st.divider()

st.subheader("🚀 주요 업무 바로가기")
c_main1, c_main2 = st.columns(2)

with c_main1:
    with st.container(border=True):
        st.markdown("### ✅ 1. 할 일 (To-Do & 우선순위)")
        st.write("• 키워드 중심 압축 목록 & 우측 세부 정보 패널(Split-View)")
        st.write("• **▲/▼ 버튼** 및 **마우스 드래그** 우선순위 실시간 조정")
        st.write("• 원클릭 **✅ 완료** 버튼, **완료된 일 표시** 토글, 긴급도별 색상 강조")
        st.page_link("pages/1_✅_할_일.py", label="👉 ✅ 할 일 화면 열기", use_container_width=True)

with c_main2:
    with st.container(border=True):
        st.markdown("### 🧩 2. 레시피 확인 (Handler → Vision)")
        st.write("• **Handler Recipe** 목록 메인 노출 및 공정 조건 필터링")
        st.write("• Handler 선택 시 연결된 **Vision Recipe 체인** 드릴다운")
        st.write("• 각 Vision별 **주요 파라미터(XML 파싱)** & **최근 변경점** 동시 확인")
        st.page_link("pages/2_🧩_레시피_확인.py", label="👉 🧩 레시피 확인 화면 열기", use_container_width=True)

st.write("")
st.caption("보조 기능 바로가기")
b1, b2, b3 = st.columns(3)
with b1:
    st.page_link("pages/3_⚙️_레시피_등록_및_매핑.py", label="⚙️ 레시피 등록 및 매핑", use_container_width=True)
with b2:
    st.page_link("pages/4_🚀_설비_횡전개_및_Diff.py", label="🚀 설비 횡전개 및 Diff 검증", use_container_width=True)
with b3:
    st.page_link("pages/5_🛠️_기준정보_및_백업.py", label="🛠️ 기준정보 및 백업/복구", use_container_width=True)
