"""Shared ARIS dashboard theme — tokens, CSS, and the technical-detail toggle.

Applied once per page via ``inject_theme()``. Keep this palette small; components
should use these classes instead of inventing new colors.
"""

from __future__ import annotations

import streamlit as st

from aris.ui_text import DISCLAIMER_SHORT, DISCLAIMER_URL

# Limited palette (also mirrored in .streamlit/config.toml).
COLOR_BG = "#0B0D10"
COLOR_SURFACE = "#15191F"
COLOR_SURFACE_2 = "#1C222B"
COLOR_BORDER = "#2A313C"
COLOR_TEXT = "#F3F4F6"
COLOR_MUTED = "#8B93A1"
COLOR_ACCENT = "#E10600"
COLOR_RECOMMEND = "#F5C518"
COLOR_CAVEAT = "#E8A317"
COLOR_OK = "#3DDC97"
SECTOR_PURPLE = "#7C3AED"
SECTOR_GREEN = "#22C55E"
SECTOR_YELLOW = "#CA8A04"

_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, .stCaption {{
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}}
.stApp {{
  background: {COLOR_BG};
  color: {COLOR_TEXT};
}}
h1, h2, h3 {{
  letter-spacing: -0.02em;
  font-weight: 600;
}}
h1 {{ font-size: 1.7rem; }}
h2, .stSubheader {{ font-size: 1.15rem; }}
p, li, .stMarkdown {{ line-height: 1.45; }}

.aris-kicker {{
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: {COLOR_ACCENT};
  margin-bottom: 0.35rem;
}}
.aris-muted {{ color: {COLOR_MUTED}; font-size: 0.92rem; }}
.aris-disclaimer {{
  color: {COLOR_MUTED};
  font-size: 0.78rem;
  line-height: 1.4;
  margin-top: 0.75rem;
}}
.aris-disclaimer a {{ color: {COLOR_TEXT}; }}

.aris-hero {{
  background: {COLOR_SURFACE};
  border: 1px solid {COLOR_BORDER};
  border-left: 4px solid {COLOR_ACCENT};
  border-radius: 6px;
  padding: 1.25rem 1.4rem;
  margin: 0.5rem 0 1.1rem 0;
}}
.aris-hero h1 {{ margin: 0 0 0.4rem 0; font-size: 1.85rem; }}
.aris-stat-row {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin: 1rem 0;
}}
.aris-stat {{
  background: {COLOR_SURFACE};
  border: 1px solid {COLOR_BORDER};
  border-radius: 6px;
  padding: 0.85rem 1rem;
}}
.aris-stat .lbl {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: {COLOR_MUTED};
  margin-bottom: 0.3rem;
}}
.aris-stat .val {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 1.35rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}}
.aris-stat .sub {{
  color: {COLOR_MUTED};
  font-size: 0.78rem;
  margin-top: 0.25rem;
}}
.aris-stat.miss .val {{ color: {COLOR_CAVEAT}; }}
.aris-stat.pass .val {{ color: {COLOR_OK}; }}

.aris-callout {{
  background: {COLOR_SURFACE};
  border: 1px solid {COLOR_RECOMMEND};
  border-left: 6px solid {COLOR_RECOMMEND};
  border-radius: 6px;
  padding: 1rem 1.15rem;
  margin: 0.4rem 0 1rem 0;
}}
.aris-callout .eyebrow {{
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: {COLOR_RECOMMEND};
  margin-bottom: 0.35rem;
}}
.aris-callout .headline {{
  font-size: 1.35rem;
  font-weight: 650;
  line-height: 1.25;
  margin: 0 0 0.45rem 0;
}}
.aris-callout .delta {{
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 1.15rem;
  font-variant-numeric: tabular-nums;
  color: {COLOR_TEXT};
}}
.aris-caveat {{
  background: rgba(232, 163, 23, 0.12);
  border: 1px solid {COLOR_CAVEAT};
  border-radius: 4px;
  color: {COLOR_CAVEAT};
  font-size: 0.88rem;
  font-weight: 500;
  padding: 0.55rem 0.75rem;
  margin: 0.55rem 0 0 0;
}}
.aris-empty {{
  background: {COLOR_SURFACE};
  border: 1px dashed {COLOR_BORDER};
  border-radius: 6px;
  color: {COLOR_MUTED};
  padding: 1rem 1.1rem;
  margin: 0.4rem 0 1rem 0;
}}
.aris-empty strong {{ color: {COLOR_TEXT}; }}

.aris-tower-wrap {{
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 0.4rem 0 0.6rem 0;
}}
.aris-tower {{
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
}}
.aris-tower th {{
  text-align: left;
  color: {COLOR_MUTED};
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-bottom: 1px solid {COLOR_BORDER};
  padding: 0.35rem 0.4rem;
}}
.aris-tower td {{
  padding: 0.28rem 0.4rem;
  border-bottom: 1px solid {COLOR_BORDER};
  color: {COLOR_TEXT};
}}
.aris-tower tr:hover td {{ background: {COLOR_SURFACE_2}; }}
.aris-sec {{
  display: inline-block;
  min-width: 3.4rem;
  text-align: center;
  padding: 1px 6px;
  border-radius: 3px;
}}
.aris-sec.purple {{ background: {SECTOR_PURPLE}; color: #fff; }}
.aris-sec.green {{ background: {SECTOR_GREEN}; color: #052e16; }}
.aris-sec.yellow {{ background: {SECTOR_YELLOW}; color: #1a1400; }}
.aris-sec.none {{ color: {COLOR_MUTED}; }}

.aris-strat-card {{
  background: {COLOR_SURFACE};
  border: 1px solid {COLOR_BORDER};
  border-radius: 6px;
  padding: 0.85rem 0.9rem 0.6rem 0.9rem;
  min-height: 8rem;
}}
.aris-strat-card.recommended {{
  border-color: {COLOR_RECOMMEND};
  box-shadow: inset 3px 0 0 {COLOR_RECOMMEND};
}}
.aris-strat-card .name {{
  font-weight: 650;
  margin-bottom: 0.35rem;
}}
.aris-strat-card .desc {{
  color: {COLOR_MUTED};
  font-size: 0.85rem;
  margin-bottom: 0.55rem;
}}

.aris-nav-card {{
  display: block;
  background: {COLOR_SURFACE};
  border: 1px solid {COLOR_BORDER};
  border-radius: 6px;
  padding: 1.05rem 1.15rem;
  margin: 0.4rem 0 0.8rem 0;
  text-decoration: none;
  color: {COLOR_TEXT};
}}
.aris-nav-card:hover {{ border-color: {COLOR_ACCENT}; }}
.aris-nav-card .go {{
  color: {COLOR_ACCENT};
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-top: 0.55rem;
}}

.aris-live-badge {{
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.2rem 0.5rem;
  border-radius: 3px;
  margin-right: 0.45rem;
}}
.aris-live-badge.live {{ background: {COLOR_ACCENT}; color: #fff; }}
.aris-live-badge.replay {{ background: #2563eb; color: #fff; }}
.aris-live-badge.wait {{ background: {COLOR_SURFACE_2}; color: {COLOR_MUTED}; }}
.aris-tyre {{
  display: inline-block;
  min-width: 1.15rem;
  text-align: center;
  font-weight: 700;
  border-radius: 999px;
  padding: 0 5px;
}}
.aris-tyre.S {{ background: #E10600; color: #fff; }}
.aris-tyre.M {{ background: #F5C518; color: #111; }}
.aris-tyre.H {{ background: #F3F4F6; color: #111; }}
.aris-tyre.I {{ background: #22C55E; color: #052e16; }}
.aris-tyre.W {{ background: #2563eb; color: #fff; }}
.aris-posup {{ color: {COLOR_OK}; }}
.aris-posdn {{ color: {COLOR_ACCENT}; }}
.aris-fl {{ color: {SECTOR_PURPLE}; font-weight: 700; }}

@media (max-width: 768px) {{
  .aris-stat-row {{ grid-template-columns: 1fr; }}
  .aris-hero {{ padding: 1rem; }}
  .aris-callout .headline {{ font-size: 1.15rem; }}
  .aris-tower {{ font-size: 0.72rem; min-width: 460px; }}
}}
"""


_V3_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800;900&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: #070A0E !important;
  color: #E8ECF0 !important;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}
[data-testid="stHeader"], header[data-testid="stHeader"],
#MainMenu, footer, .stDeployButton, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
.block-container { padding: 0.4rem 1rem 1.2rem 1rem !important; max-width: 1400px !important; }
[data-testid="stSidebar"] { background: #0B0E12 !important; border-right: 1px solid #1E2630; }
[data-testid="stSidebar"] * { font-family: "IBM Plex Mono", ui-monospace, monospace !important; }
h1, h2, h3, .aris-display {
  font-family: "Big Shoulders Display", sans-serif !important;
  letter-spacing: -0.02em;
  font-weight: 800 !important;
}
.aris-v3-nav {
  display: flex; align-items: center; gap: 16px;
  padding: 8px 4px 10px 4px;
  border-bottom: 1px solid #1E2630;
  margin-bottom: 10px;
}
.aris-v3-brand {
  font-family: "Big Shoulders Display", sans-serif;
  font-size: 22px; font-weight: 900; letter-spacing: -0.5px; color: #E8ECF0;
}
.aris-v3-head {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 8px 0 10px 0; border-bottom: 1px solid #1E2630; margin-bottom: 8px;
}
.aris-chip {
  display: inline-flex; align-items: center;
  padding: 3px 8px; border-radius: 3px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10px; font-weight: 600; letter-spacing: 0.04em;
  border: 1px solid #1E2630; color: #7A8796;
}
.aris-chip.live { background: #2A1210; color: #E05B4A; border-color: #E05B4A66; }
.aris-chip.replay { background: #0C1E2E; color: #4FA8E0; border-color: #4FA8E060; }
.aris-chip.green { background: #0A1F18; color: #2DD4A0; border-color: #2DD4A060; }
.aris-chip.signal { background: #2E2510; color: #E8A33D; border-color: #E8A33D80; }
.aris-title {
  font-family: "Big Shoulders Display", sans-serif;
  font-weight: 800; font-size: 18px; color: #E8ECF0;
}
.aris-wx {
  display: grid; grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px; padding: 8px 0; border-bottom: 1px solid #1E2630;
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10px;
  margin-bottom: 8px;
}
.aris-wx .lbl { color: #4A5560; letter-spacing: 0.08em; }
.aris-wx .val { color: #E8ECF0; font-weight: 700; margin-top: 2px; }
.aris-wx .val.alert { color: #E8A33D; }
.aris-v3-tower { width: 100%; border-collapse: collapse; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; }
.aris-v3-tower th {
  text-align: left; color: #4A5560; font-size: 9px; font-weight: 500;
  padding: 6px 8px; border-bottom: 1px solid #1E2630;
}
.aris-v3-tower td { padding: 6px 8px; border-bottom: 1px solid #1E263060; color: #E8ECF0; }
.aris-v3-tower tr.focus td { background: #2E2510; }
.aris-v3-tower tr.alt td { background: #131820; }
.aris-v3-tower tr.out { opacity: 0.38; }
.aris-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }
.aris-dot.purple { background: #9B72F0; }
.aris-dot.green { background: #2DD4A0; }
.aris-dot.yellow { background: #E8A33D; }
.aris-dot.grey, .aris-dot.none { background: #7A8796; }
.aris-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 9px; font-weight: 700;
}
.aris-badge.S { color: #E8002D; border: 2px solid #E8002D; }
.aris-badge.M { color: #D4B800; border: 2px solid #D4B800; }
.aris-badge.H { color: #C0C4CC; border: 2px solid #C0C4CC; }
.aris-badge.I { color: #39B54A; border: 2px solid #39B54A; }
.aris-badge.W { color: #0067FF; border: 2px solid #0067FF; }
.aris-fl { color: #9B72F0; font-weight: 500; margin-left: 6px; }
.aris-weekend {
  padding: 14px; background: #0F1318; border: 1px solid #1E2630; border-radius: 6px;
}
.aris-weekend-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px;
}
"""


def inject_v3() -> None:
    """React live-dashboard chrome — same tokens as frontend/src/theme.ts."""
    st.markdown(f"<style>{_V3_CSS}</style>", unsafe_allow_html=True)


def inject_theme(*, show_tech_toggle: bool = True) -> None:
    """Inject CSS once per run and optionally render the technical-detail toggle."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    if show_tech_toggle:
        with st.sidebar:
            if "aris_show_technical" not in st.session_state:
                st.session_state.aris_show_technical = False
            st.toggle(
                "Show technical detail",
                key="aris_show_technical",
                help="MAE numbers, Monte Carlo bands, and model evidence. Off by default.",
            )


def show_technical() -> bool:
    return bool(st.session_state.get("aris_show_technical", False))


def render_disclaimer() -> None:
    st.markdown(
        f'<p class="aris-disclaimer">{DISCLAIMER_SHORT} '
        f'<a href="{DISCLAIMER_URL}" target="_blank" rel="noopener">Full disclaimer</a>.</p>',
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f'<div class="aris-empty"><strong>{title}</strong><br>{body}</div>',
        unsafe_allow_html=True,
    )
