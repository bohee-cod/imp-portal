# -*- coding: utf-8 -*-
"""(주)아이엠피 재무·세무 포털 — 세법·관계법령 / 정부지원 / 동종업계 비교"""
import html
import json
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

BASE = Path(__file__).parent
DATA = BASE / "data"
ASOF = "2026. 10. 27."  # 화면 기준일 — 내용 수정 시 함께 변경

st.set_page_config(page_title="IMP 재무·세무 포털", page_icon="▣", layout="wide",
                   initial_sidebar_state="expanded")

# ------------------------------------------------------------------ 스타일
st.markdown("""
<style>
html, body, [class*="css"], .stMarkdown, p, li, div { word-break: keep-all; overflow-wrap: break-word; }
.block-container { padding-top: 2.2rem; max-width: 1240px; }
h1, h2, h3 { letter-spacing: -0.01em; }
.eyebrow { font-size: 12px; color: #5A6774; letter-spacing: .06em; margin-bottom: 2px; }
.asof { font-size: 12px; color: #5A6774; }
.badges { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
.b { font-size:11px; padding:2px 9px; border-radius:100px; background:#E7EBEF; color:#5A6774; white-space:nowrap; }
.b.ok { background:rgba(46,122,87,.12); color:#2E7A57; }
.b.warn { background:rgba(154,106,18,.13); color:#8A5E0F; }
.b.rel { background:rgba(181,98,0,.11); color:#B56200; font-weight:600; }
.b.imp { background:rgba(42,98,166,.10); color:#2A62A6; }
.b.crit { background:rgba(180,35,24,.10); color:#B42318; font-weight:600; }
.ttl { font-size:16px; font-weight:700; line-height:1.45; margin:2px 0 6px; }
.ttl.urgent { color:#B42318; }
.body { font-size:14px; line-height:1.7; margin:0 0 8px; }
.body b, .apply b { color:#B56200; }
.apply { background:#F1F3F5; border-radius:6px; padding:10px 14px; font-size:13.5px; line-height:1.65; margin-bottom:8px; }
.apply .lbl { display:block; font-size:11px; font-weight:700; color:#B56200; letter-spacing:.05em; margin-bottom:2px; }
.src { font-size:12px; color:#5A6774; }
.src a { color:#2A62A6; text-decoration:none; margin-right:12px; }
.todo { background:rgba(181,98,0,.07); border:1px solid rgba(181,98,0,.45); border-radius:8px; padding:14px 18px; }
.todo h4 { margin:0 0 6px; color:#B56200; font-size:15px; }
.todo ol { margin:0; padding-left:20px; }
.todo li { margin:3px 0; font-size:14px; }
.certs { display:flex; flex-wrap:wrap; gap:6px; }
.cert { font-size:12px; padding:3px 10px; border:1px solid #D3DAE1; border-radius:100px; background:#fff; color:#3D4A57; }
.note { font-size:12.5px; color:#5A6774; }
.up { color:#D7263D; font-weight:600; }   /* 상승 = 빨강 */
.down { color:#1F5FBF; font-weight:600; } /* 하락 = 파랑 */
.neg { color:#D7263D; }                   /* 값 자체가 마이너스 = 빨강 */
.kpi { background:#fff; border:1px solid #D3DAE1; border-radius:8px; padding:12px 16px; height:100%; }
.kpi .k { font-size:12px; color:#5A6774; }
.kpi .v { font-size:24px; font-weight:700; font-variant-numeric:tabular-nums; }
.kpi .d { font-size:12.5px; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ 로그인
def check_login() -> bool:
    if st.session_state.get("auth"):
        return True
    pw_set = st.secrets.get("password", None) if hasattr(st, "secrets") else None
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div class='eyebrow'>(주)아이엠피</div>", unsafe_allow_html=True)
        st.subheader("재무·세무 포털")
        with st.form("login"):
            pw = st.text_input("비밀번호", type="password")
            ok = st.form_submit_button("로그인", width="stretch")
        if ok:
            if pw_set and pw == pw_set:
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("비밀번호가 맞지 않습니다.")
        if not pw_set:
            st.caption("관리자: Secrets에 password 값을 설정해야 로그인할 수 있습니다.")
    return False


# ------------------------------------------------------------------ 데이터
@st.cache_data
def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


TAX = load("tax.json")
SUP = load("support.json")
PEERS = load("peers.json")

STATUS = {
    "tax": {"시행됨": ("시행 중", "ok"), "확정예정": ("시행 예정", "warn"), "입법예고": ("입법예고·미확정", "")},
    "support": {"시행됨": ("신청·활용 가능", "ok"), "확정예정": ("개편·예정", "warn"), "입법예고": ("확인·주의", "")},
}
CAT_ORDER = {
    "tax": ["법인세", "부가가치세", "원천세·소득세", "지방세", "공공조달·계약", "업종 규제(공사·인증)",
            "노무·안전", "자산과세", "수출입·관세", "국제조세", "기타"],
    "support": ["공공조달·판로", "R&D·기술인증", "제조·스마트공장", "정책자금·보증", "수출·해외진출",
                "세액공제·감면", "고용·인건비", "일·가정 양립", "복지·안전·교육", "지식재산·브랜드", "디지털·IT"],
}
EMOJI = re.compile(r"^[\U0001F300-\U0001FAFF☀-➿\s]+")


def is_urgent(it):
    return it["title"].startswith("🚨")


def md(s):
    s = html.escape(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def fmt_date(d):
    if not d:
        return ""
    p = d.split("-")
    return f"{p[0]}.{int(p[1])}.{int(p[2])}" if len(p) == 3 else ".".join(p)


def card(it, view):
    lab, cls = STATUS[view].get(it["status"], (it["status"], ""))
    urgent = is_urgent(it)
    badges = []
    if urgent:
        badges.append("<span class='b crit'>우선 확인</span>")
    badges.append(f"<span class='b {cls}'>{lab}</span>")
    if it.get("company"):
        badges.append("<span class='b rel'>당사 관련</span>")
    badges.append(f"<span class='b {'imp' if it.get('origin') == 'imp' else ''}'>"
                  f"{'업종 특화' if it.get('origin') == 'imp' else '공통'}</span>")
    if it.get("date"):
        badges.append(f"<span class='b'>{fmt_date(it['date'])}</span>")
    parts = it["body"].split("**아이엠피 적용**")
    body = parts[0].strip()
    apply = parts[1].strip() if len(parts) > 1 else ""
    srcs = "".join(f"<a href='{html.escape(s['url'])}' target='_blank'>{html.escape(s.get('name') or '링크')} ↗</a>"
                   for s in it.get("sources", []) if s.get("url"))
    out = f"<div class='badges'>{''.join(badges)}</div>"
    out += f"<div class='ttl{' urgent' if urgent else ''}'>{md(EMOJI.sub('', it['title']))}</div>"
    if body:
        out += f"<p class='body'>{md(body)}</p>"
    if apply:
        out += f"<div class='apply'><span class='lbl'>당사 적용</span>{md(apply)}</div>"
    if srcs:
        out += f"<div class='src'>출처 · {srcs}</div>"
    with st.container(border=True):
        st.markdown(out, unsafe_allow_html=True)


def tracker(view, items, title, lede, todo, notice):
    st.markdown(f"<div class='eyebrow'>(주)아이엠피 · 기준일 {ASOF}</div>", unsafe_allow_html=True)
    st.title(title)
    st.caption(lede)

    cats = [c for c in CAT_ORDER[view] if any(i["cat"] == c for i in items)]
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.1, 1.6, 1.4, 1.4])
        only_rel = c1.toggle("당사 관련만", value=True, key=f"{view}_rel")
        sel_cat = c2.multiselect("분야", cats, key=f"{view}_cat", placeholder="전체")
        sel_st = c3.multiselect("상태", list(STATUS[view].keys()), key=f"{view}_st",
                                format_func=lambda k: STATUS[view][k][0], placeholder="전체")
        q = c4.text_input("검색", key=f"{view}_q", placeholder="예: 우수조달, R&D")
        origin = st.radio("항목 구분", ["전체", "업종 특화", "공통"], horizontal=True, key=f"{view}_org",
                          label_visibility="collapsed")

    def keep(it):
        if only_rel and not it.get("company"):
            return False
        if sel_cat and it["cat"] not in sel_cat:
            return False
        if sel_st and it["status"] not in sel_st:
            return False
        if origin == "업종 특화" and it.get("origin") != "imp":
            return False
        if origin == "공통" and it.get("origin") == "imp":
            return False
        if q and q.lower() not in (it["title"] + it["body"] + it["cat"]).lower():
            return False
        return True

    shown = [i for i in items if keep(i)]
    k = st.columns(4)
    for col, (lab, val) in zip(k, [("수록 항목", len(items)), ("당사 관련", sum(1 for i in items if i.get("company"))),
                                    ("우선 확인", sum(1 for i in items if is_urgent(i))), ("현재 표시", len(shown))]):
        col.markdown(f"<div class='kpi'><div class='k'>{lab}</div><div class='v'>{val}<span class='note'> 건</span></div></div>",
                     unsafe_allow_html=True)
    st.write("")
    st.markdown("<div class='todo'><h4>지금 챙길 것</h4><ol>" + "".join(f"<li>{t}</li>" for t in todo) + "</ol></div>",
                unsafe_allow_html=True)
    st.caption(notice)

    if not shown:
        st.info("조건에 맞는 항목이 없습니다. 필터를 줄여 보세요.")
        return
    for c in [c for c in cats if any(i["cat"] == c for i in shown)]:
        group = sorted([i for i in shown if i["cat"] == c],
                       key=lambda i: (not is_urgent(i), not i.get("company"), i.get("origin") != "imp"))
        st.subheader(f"{c}  ·  {len(group)}건")
        for it in group:
            card(it, view)


# ------------------------------------------------------------------ 동종업계
SERIES_COLORS = {"아이엠피": "#2a78d6", "인터엠": "#eb6834", "대경바스컴": "#1baf7a"}


def peers_frame():
    rows = []
    for c in PEERS["companies"]:
        for y, (rev, op, ni) in sorted(c["years"].items()):
            rows.append({"회사": c["name"], "연도": y, "매출액": rev, "영업이익": op, "당기순이익": ni})
    df = pd.DataFrame(rows)
    df["영업이익률"] = (df["영업이익"] / df["매출액"] * 100).round(1)
    df["순이익률"] = (df["당기순이익"] / df["매출액"] * 100).round(1)
    df = df.sort_values(["회사", "연도"])
    df["매출 증감률"] = (df.groupby("회사")["매출액"].pct_change() * 100).round(1)
    return df


def color_val(v, kind):
    """kind='chg' → 상승 빨강/하락 파랑, kind='lvl' → 음수만 빨강"""
    if pd.isna(v):
        return "color:#9AA5B1"
    if kind == "chg":
        return "color:#D7263D;font-weight:600" if v > 0 else ("color:#1F5FBF;font-weight:600" if v < 0 else "")
    return "color:#D7263D" if v < 0 else ""


def pct_txt(v):
    if v is None or pd.isna(v):
        return "<span class='note'>–</span>"
    cls = "up" if v > 0 else ("down" if v < 0 else "")
    arrow = "▲" if v > 0 else ("▼" if v < 0 else "")
    return f"<span class='{cls}'>{arrow} {abs(v):.1f}%</span>"


def peers_page():
    st.markdown(f"<div class='eyebrow'>(주)아이엠피 · 기준일 {ASOF} · 단위 억원</div>", unsafe_allow_html=True)
    st.title("동종업계 매출·손익 비교")
    st.caption("공공조달 방송·음향장비(PA·전관방송) 제조사 기준. 상장사는 공시, 비상장사는 신용평가사 재무 자료를 사용했습니다.")
    view = (BASE / "peers_view.html").read_text(encoding="utf-8")
    view = view.replace("/*PEERS*/", json.dumps(PEERS, ensure_ascii=False))
    components.html(view, height=1720, scrolling=True)
    st.markdown("<div class='src'>출처 · " + "".join(
        f"<a href='{html.escape(u)}' target='_blank'>{html.escape(n)} ↗</a>" for n, u in PEERS["sources"]) + "</div>",
        unsafe_allow_html=True)


# ------------------------------------------------------------------ 대표님 주요대시보드
CERTS = [
    ("직접생산확인", "2024.6", "2년", "2026.6 전후", "재발급 확인"),
    ("녹색인증(Class D)", "2023.6", "3년", "2026.6 전후", "연장 확인"),
    ("NEP 신제품인증", "2023.9", "3년", "2026.9 전후", "연장 확인"),
    ("우수제품 지정", "2024.1", "3년(+최대 3년)", "2027.1 전후", "연장 신청 준비"),
    ("이노비즈", "2019.1", "3년 주기", "증서 확인", "재확인 주기 점검"),
    ("여성기업 확인", "2014.9", "유효기간 확인", "증서 확인", "공공구매 실적 근거"),
]


def dashboard():
    st.markdown(f"<div class='eyebrow'>(주)아이엠피 · 기준일 {ASOF}</div>", unsafe_allow_html=True)
    st.title("대표님 주요대시보드")
    st.caption("세법·조달 제도·정부지원·업계 실적 중 꼭 보셔야 할 것만 모았습니다. 자세한 내용은 왼쪽 메뉴에서 확인하세요.")

    df = peers_frame()
    imp = df[df["회사"] == "아이엠피"].set_index("연도")
    r, p = imp.loc["2023"], imp.loc["2022"]
    im = df[(df["회사"] == "인터엠")].set_index("연도").loc["2025"]
    k = st.columns(4)
    k[0].markdown(f"<div class='kpi'><div class='k'>당사 매출 (2023)</div><div class='v'>{r['매출액']:,.1f}<span class='note'> 억원</span></div>"
                  f"<div class='d'>전년比 {pct_txt(r['매출 증감률'])}</div></div>", unsafe_allow_html=True)
    k[1].markdown(f"<div class='kpi'><div class='k'>당사 영업이익 (2023)</div><div class='v'>{r['영업이익']:,.1f}<span class='note'> 억원</span></div>"
                  f"<div class='d'>전년比 {pct_txt((r['영업이익']/p['영업이익']-1)*100)}</div></div>", unsafe_allow_html=True)
    k[2].markdown(f"<div class='kpi'><div class='k'>당사 영업이익률 (2023)</div><div class='v'>{r['영업이익률']:.1f}%</div>"
                  f"<div class='d'>전년 {p['영업이익률']:.1f}% · 2020년 {imp.loc['2020','영업이익률']:.1f}%</div></div>", unsafe_allow_html=True)
    k[3].markdown(f"<div class='kpi'><div class='k'>인터엠 영업이익률 (FY2025)</div><div class='v'>{im['영업이익률']:.1f}%</div>"
                  f"<div class='d'>매출 {im['매출액']:,.0f}억 · 임대수익 포함</div></div>", unsafe_allow_html=True)
    st.write("")

    st.markdown("<div class='todo'><h4>이번 달 꼭 보실 것</h4><ol>"
                "<li><b>인증 만료</b> — 직접생산확인·녹색인증·NEP가 2026년 중 만료 추정. 끊기면 수의계약·우선구매 실적이 바로 멈춥니다(아래 표).</li>"
                "<li><b>우수제품 연장</b> — 2024.1 지정분 2027.1 전후 만료. 연장 심사에 수출실적이 반영됩니다.</li>"
                "<li><b>법인세율 인상 확정</b> — 2026 사업연도부터 전 구간 +1%p(과표 2억 이하 10%, 2억~200억 20%).</li>"
                "<li><b>세금 감면 판단</b> — 양주(수도권) 제조업은 소기업이면 특별세액감면 20%, 중기업이면 0%. 소기업 해당 여부에 따라 투자·R&D 공제 전략이 달라집니다.</li>"
                "<li><b>가업승계</b> — 국회 심사 중인 개편안이 확정되면 가업상속공제 경영기간 요건이 10년→30년. 업력 19년인 당사는 대상에서 빠질 수 있어 12월 결과 확인 필요.</li>"
                "<li><b>정부지원</b> — 2027.1 수출바우처·해외규격인증(CE·UL) 공고, 경기도 육성자금(2.9%) 신성장·수출형 특화자금.</li>"
                "</ol></div>", unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.subheader("보유 인증 만료 관리")
        st.dataframe(pd.DataFrame(CERTS, columns=["인증", "취득", "유효기간", "추정 만료", "조치"]),
                     hide_index=True, width="stretch")
        st.caption("회사 연혁의 취득 시점에 일반 유효기간을 대입한 추정치입니다. 정확한 날짜는 각 증서로 확인하세요.")
    with c2:
        st.subheader("동종업계 위치")
        d = df[df["회사"].isin(SERIES_COLORS.keys())].sort_values("연도").groupby("회사").tail(1)
        d = d.assign(라벨=d["회사"] + " (" + d["연도"] + ")")
        scale = alt.Scale(domain=list(SERIES_COLORS.keys()), range=list(SERIES_COLORS.values()))
        ch = alt.Chart(d).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=22).encode(
            y=alt.Y("라벨:N", sort="-x", title=None),
            x=alt.X("매출액:Q", title="최근 확보 연도 매출액(억원)", axis=alt.Axis(grid=True, gridOpacity=.35)),
            color=alt.Color("회사:N", scale=scale, legend=None),
            tooltip=["회사", "연도", alt.Tooltip("매출액:Q", format=",.1f"), alt.Tooltip("영업이익률:Q", format=".1f")])
        txt = ch.mark_text(align="left", dx=4, color="#16202A").encode(text=alt.Text("매출액:Q", format=",.0f"))
        st.altair_chart((ch + txt).properties(height=170), width="stretch")
        st.caption("인터엠은 9월 결산(FY2025), 아이엠피는 2023년이 최근 확보 연도입니다.")

    st.subheader("우선 확인 항목")
    urgent = [i for i in TAX + SUP if is_urgent(i)]
    for it in urgent:
        card(it, "tax" if it in TAX else "support")


# ------------------------------------------------------------------ 회사 기본정보
def company():
    st.markdown(f"<div class='eyebrow'>(주)아이엠피 · 기준일 {ASOF}</div>", unsafe_allow_html=True)
    st.title("회사 기본정보")
    info = [("회사명", "(주)아이엠피 / IMP Co., Ltd."), ("대표이사", "정혜영 · 조순구"), ("설립", "2007년 (업력 약 19년)"),
            ("사업자등록번호", "127-86-05997"), ("본사·공장", "경기도 양주시 광적면 백은로 263 (수도권 성장관리권역)"),
            ("서울 사옥", "서울 도봉구 도봉로 719 인터엠빌딩 2층"), ("업태", "제조업 · 건설업 · 도매업 · 서비스업"),
            ("업종", "기타 음향기기 제조업 / 정보통신공사업 / 소프트웨어개발공급"),
            ("주요 제품", "네트워크 방송장치 · 프로오디오 스피커 · 디지털 무선마이크 · 전관방송 시스템"),
            ("조달", "나라장터 등록 399종 · 납품 3,518건+ · 총액규격 342종 · MAS 실적평가 최우수 14분기 연속"),
            ("R&D", "기업부설연구소(2011) · 등록 특허 28건(국내 27·해외 1)")]
    st.dataframe(pd.DataFrame(info, columns=["항목", "내용"]), hide_index=True, width="stretch")
    st.subheader("보유 인증")
    certs = ["우수조달물품", "MAS 다수공급자계약", "품질보증조달물품", "직접생산확인", "이노비즈", "여성기업", "NEP 신제품",
             "NET 신기술", "녹색인증", "G-PASS", "K마크", "KS", "GS", "ISO 9001", "ISO 14001", "ISO 45001", "CE",
             "스마트공장 수준확인", "정보통신공사업 등록"]
    st.markdown("<div class='certs'>" + "".join(f"<span class='cert'>{c}</span>" for c in certs) + "</div>",
                unsafe_allow_html=True)
    st.caption("출처: 회사 홈페이지 회사소개·연혁 (impav.com)")


# ------------------------------------------------------------------ 라우팅
if not check_login():
    st.stop()

MENU = ["대표님 주요대시보드", "세법·관계법령", "정부지원", "동종업계 비교", "회사 기본정보"]
qp = st.query_params.get("menu")
default = MENU.index(qp) if qp in MENU else 0
with st.sidebar:
    st.markdown("<div class='eyebrow'>(주)아이엠피</div>", unsafe_allow_html=True)
    st.markdown("### 재무·세무 포털")
    menu = st.radio("메뉴", MENU, index=default, label_visibility="collapsed")
    st.divider()
    st.markdown(f"<span class='asof'>기준일 {ASOF}</span>", unsafe_allow_html=True)
    if st.button("로그아웃", width="stretch"):
        st.session_state.clear()
        st.rerun()

if menu == "대표님 주요대시보드":
    dashboard()
elif menu == "세법·관계법령":
    tracker("tax", TAX, "세법·관계법령",
            "음향·방송장비 제조, 정보통신공사, 공공조달 납품, 수출 구조에 걸리는 세법과 관계법령입니다.",
            ["2026 사업연도 예상 법인세를 <b>인상 세율(10·20·22·25%)</b>로 다시 계산하고 최저한세(7%) 확인",
             "매출 기준 <b>소기업 여부</b> 판정 → 특별세액감면(수도권 소기업 20%)과 통합투자세액공제 중 유리한 쪽 선택",
             "R&D 세액공제: 연구전담요원 <b>겸직 정리·연구노트</b> 보완, 필요 시 2027.3.31까지 국세청 사전심사",
             "<b>직접생산확인(2024.6 취득, 2년)</b> 재발급 여부 즉시 확인 — MAS 1단계 직접구매 자격과 연결",
             "<b>우수제품(2024.1 지정)</b> 연장 신청 시기 확인",
             "12월 국회 확정 시 <b>가업상속공제 30년 요건</b>·중소기업 감면 점감구조 반영"],
            "2026년 세제개편안(8.3 발표)은 국회 기획재정위원회 심사 중이며 통상 12월 초 확정됩니다. '입법예고·미확정' 항목은 바뀔 수 있습니다.")
elif menu == "정부지원":
    tracker("support", SUP, "정부지원",
            "당사가 신청할 수 있는 고용·세제·R&D·조달·수출·정책자금 지원입니다. 음향·방송장비 제조업은 제외 업종이 아닙니다.",
            ["<b>인증 만료 점검</b>: 직접생산·녹색인증·NEP·우수제품 추정 만료 — 증서로 날짜 확정",
             "<b>2027년 1월</b> 수출바우처·해외규격인증(CE·UL) 1차 공고 대비 — 인증 필요 모델·전시회 목록 정리",
             "경기도 육성자금 <b>신성장혁신기업·수출형기업</b> 특화자금(2.9%), 공장 증설 시 시설자금",
             "스마트공장 <b>수준확인서(2023)</b> 기반 고도화 지원 신청",
             "청년 채용 계획이 있으면 <b>채용 전</b> 청년일자리도약장려금 참여 신청",
             "빔 스티어링 스피커 등 신제품은 <b>조달청 혁신제품</b> 지정으로 판로 추가"],
            "금액·일정은 각 공고문으로 최종 확인하세요.")
elif menu == "동종업계 비교":
    peers_page()
else:
    company()
