"""Prominent recommendation + SC/VSC caveat callout."""

from __future__ import annotations

import html

import streamlit as st

from apps.theme import show_technical
from aris.recommend import Recommendation, RecommendationResult
from aris.ui_text import format_callout_delta, format_race_clock, recommendation_caveat


def _caveat_from(rec: Recommendation | None) -> str | None:
    if rec is None:
        return None
    return recommendation_caveat(rec.narration_context, rec.evidence or "")


def render_recommendation_callout(
    rec: Recommendation | None,
    *,
    title: str = "ARIS recommends",
    extra_caveat: str | None = None,
    empty_body: str | None = None,
) -> None:
    """The product: the decision, visually first. Not a buried expander."""
    if rec is None:
        body = empty_body or (
            "ARIS speaks when a pit window, tyre threshold, or Safety Car hits."
        )
        st.markdown(
            f'<div class="aris-empty"><strong>{html.escape(title)}</strong><br>'
            f"{body}</div>",
            unsafe_allow_html=True,
        )
        return

    caveat = extra_caveat or _caveat_from(rec)
    headline = html.escape(rec.label)
    delta_text = html.escape(format_callout_delta(rec.delta_vs_stay_out_s))
    st.markdown(
        f"""
<div class="aris-callout">
  <div class="eyebrow">{html.escape(title)}</div>
  <div class="headline">{headline}</div>
  <div class="delta">{delta_text}</div>
  {f'<div class="aris-caveat">Note: {html.escape(caveat)}</div>' if caveat else ''}
</div>
""",
        unsafe_allow_html=True,
    )
    if show_technical():
        st.caption(
            f"σ {rec.confidence_std_s:.2f}s · P10/P90 Δ "
            f"{rec.p10_delta_s:+.2f}/{rec.p90_delta_s:+.2f}s · "
            f"mean race {format_race_clock(rec.mean_race_time_s)}"
        )
        if rec.evidence:
            with st.expander("Evidence"):
                st.write(rec.evidence)


def render_recommendation_list(result: RecommendationResult) -> None:
    if not result.recommendations:
        render_recommendation_callout(None)
        return
    render_recommendation_callout(result.recommendations[0], title="ARIS recommends")
    rest = result.recommendations[1:]
    if not rest:
        return
    for r in rest:
        delta_short = format_callout_delta(r.delta_vs_stay_out_s, suffix="")
        label = f"#{r.rank} {r.label}  ·  {delta_short}"
        if show_technical():
            with st.expander(label):
                st.write(r.evidence)
                st.write(f"σ {r.confidence_std_s:.2f}s")
        else:
            st.caption(label)
