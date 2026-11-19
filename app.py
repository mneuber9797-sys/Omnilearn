import os
import io
import re
import html
import json
import time
import queue
import threading
import urllib.parse
import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

# --- Seiten-Konfiguration: Großzügiges Wide-Layout ---
st.set_page_config(page_title="OmniLearn", layout="wide")

BERLIN_TZ = ZoneInfo("Europe/Berlin")
DAILY_GOAL_TARGET = 30
DAILY_GOAL_BONUS_XP = 25

# --- Freischaltbare Maus-Symbole (alle 5 Level) ---
CURSOR_MILESTONES = [
    {
        "level": 0,
        "name": "Standard-Mauszeiger",
        "short": "Standard",
        "hot_x": 4,
        "hot_y": 4,
        "svg": None,
    },
    {
        "level": 5,
        "name": "Litschi",
        "short": "Litschi",
        "hot_x": 16,
        "hot_y": 16,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <ellipse cx="16" cy="17.5" rx="10.8" ry="11.5" fill="#E11D48" stroke="#07090E" stroke-width="2"/>
          <ellipse cx="16" cy="17.5" rx="8.2" ry="9" fill="none" stroke="#FB7185" stroke-width="1.2" stroke-dasharray="2 2"/>
          <circle cx="12.5" cy="13.5" r="1.2" fill="#FDA4AF"/><circle cx="19.5" cy="14" r="1.2" fill="#FDA4AF"/>
          <circle cx="14" cy="21" r="1.2" fill="#FDA4AF"/><circle cx="19.5" cy="20.5" r="1.2" fill="#FDA4AF"/>
          <path d="M16 6 C17 2.5, 22 2.5, 23 5.5 C20 6.5, 18 6.5, 16 6 Z" fill="#22C55E" stroke="#07090E" stroke-width="1.2"/>
        </svg>""",
    },
    {
        "level": 10,
        "name": "Panzer",
        "short": "Panzer",
        "hot_x": 4,
        "hot_y": 14,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <rect x="2.5" y="12.5" width="11.5" height="3.6" rx="1.6" fill="#94A3B8" stroke="#07090E" stroke-width="1.5"/>
          <rect x="11" y="9.5" width="12.5" height="7.2" rx="2.5" fill="#4D7C0F" stroke="#07090E" stroke-width="1.6"/>
          <rect x="6" y="16" width="21.5" height="8.5" rx="4.2" fill="#365314" stroke="#07090E" stroke-width="1.8"/>
          <circle cx="10.5" cy="20.2" r="1.6" fill="#A3E635"/><circle cx="16.8" cy="20.2" r="1.6" fill="#A3E635"/><circle cx="23" cy="20.2" r="1.6" fill="#A3E635"/>
        </svg>""",
    },
    {
        "level": 15,
        "name": "Goldbarren",
        "short": "Goldbarren",
        "hot_x": 16,
        "hot_y": 16,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <polygon points="8,9.5 24,9.5 29.5,23.5 2.5,23.5" fill="#F59E0B" stroke="#07090E" stroke-width="1.8" stroke-linejoin="round"/>
          <polygon points="10,11.5 22,11.5 25.5,20.5 6.5,20.5" fill="#FDE047"/>
          <line x1="11" y1="13.8" x2="21" y2="13.8" stroke="#FEF9C3" stroke-width="1.8" stroke-linecap="round"/>
        </svg>""",
    },
    {
        "level": 20,
        "name": "Blauer Schleim",
        "short": "Blauer Schleim",
        "hot_x": 16,
        "hot_y": 16,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <path d="M16 3.5 C16 3.5, 28 14, 28 21.2 C28 26.8, 22.6 29.2, 16 29.2 C9.4 29.2, 4 26.8, 4 21.2 C4 14, 16 3.5, 16 3.5 Z" fill="#0EA5E9" stroke="#07090E" stroke-width="1.8"/>
          <ellipse cx="11" cy="15" rx="2.2" ry="3.5" transform="rotate(-25 11 15)" fill="#BAE6FD"/>
          <circle cx="12.5" cy="21" r="1.9" fill="#FFFFFF"/><circle cx="19.5" cy="21" r="1.9" fill="#FFFFFF"/>
          <circle cx="12.5" cy="21" r="0.95" fill="#07090E"/><circle cx="19.5" cy="21" r="0.95" fill="#07090E"/>
          <path d="M12.5 24.6 Q16 27 19.5 24.6" fill="none" stroke="#07090E" stroke-width="1.5" stroke-linecap="round"/>
        </svg>""",
    },
    {
        "level": 25,
        "name": "Schneeflocke",
        "short": "Schneeflocke",
        "hot_x": 16,
        "hot_y": 16,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <g stroke="#07090E" stroke-width="3.8" stroke-linecap="round">
            <line x1="16" y1="3" x2="16" y2="29"/><line x1="4.7" y1="9.5" x2="27.3" y2="22.5"/><line x1="27.3" y1="9.5" x2="4.7" y2="22.5"/>
          </g>
          <g stroke="#7DD3FC" stroke-width="2.2" stroke-linecap="round">
            <line x1="16" y1="3" x2="16" y2="29"/><line x1="4.7" y1="9.5" x2="27.3" y2="22.5"/><line x1="27.3" y1="9.5" x2="4.7" y2="22.5"/>
            <polyline points="13,6 16,9 19,6" fill="none"/><polyline points="13,26 16,23 19,26" fill="none"/>
          </g>
          <circle cx="16" cy="16" r="2.6" fill="#E0F2FE"/>
        </svg>""",
    },
    {
        "level": 30,
        "name": "Affenkopf",
        "short": "Affenkopf",
        "hot_x": 16,
        "hot_y": 16,
        "svg": """<svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="32" height="32" viewBox="0 0 32 32">
          <circle cx="6.2" cy="16" r="4.2" fill="#92400E" stroke="#07090E" stroke-width="1.6"/>
          <circle cx="25.8" cy="16" r="4.2" fill="#92400E" stroke="#07090E" stroke-width="1.6"/>
          <circle cx="16" cy="16" r="10.5" fill="#78350F" stroke="#07090E" stroke-width="1.8"/>
          <ellipse cx="16" cy="18.6" rx="7.2" ry="5.5" fill="#FDE68A"/>
          <circle cx="13" cy="13.5" r="1.6" fill="#FFFFFF"/><circle cx="19" cy="13.5" r="1.6" fill="#FFFFFF"/>
          <circle cx="13" cy="13.5" r="0.85" fill="#07090E"/><circle cx="19" cy="13.5" r="0.85" fill="#07090E"/>
          <path d="M13 20.2 Q16 22.6 19 20.2" fill="none" stroke="#07090E" stroke-width="1.5" stroke-linecap="round"/>
        </svg>""",
    },
]

def svg_zu_data_uri(svg_str: str) -> str:
    encoded = urllib.parse.quote(svg_str.strip(), safe="")
    return f"data:image/svg+xml,{encoded}"

def ermittle_aktiven_cursor(level: int, selected_cursor_level: int) -> dict:
    freigeschaltet = [c for c in CURSOR_MILESTONES if c["level"] <= level]
    if selected_cursor_level == -1:
        return freigeschaltet[-1]
    for c in freigeschaltet:
        if c["level"] == selected_cursor_level:
            return c
    return freigeschaltet[-1]

# --- Level-Mathematik ---
def xp_fuer_naechstes_level(level: int) -> int:
    return 100 + (max(1, int(level)) - 1) * 50

# --- Sichere Text- & HTML-Formatierung ---
def formatiere_kartentext_html(rohtext: str, ist_lueckentext: bool = False) -> str:
    bereinigt = html.escape(str(rohtext or "").strip())
    if ist_lueckentext:
        bereinigt = re.sub(
            r"(\[\.{2,}\]|_{3,})",
            '<span class="cloze-blank">________</span>',
            bereinigt,
        )
    bereinigt = bereinigt.replace("\r\n", "\n").replace("\n", "<br>")
    return bereinigt

# --- Anki-Kartenstatus-Klassifikation ---
def klassifiziere_karte_anki(karte: dict) -> str:
    reps = int(karte.get("repetitions", 0))
    iv = int(karte.get("interval_days", 0))
    lapses = int(karte.get("lapses", 0))
    sc = int(karte.get("success_count", 0))

    if reps == 0 and lapses == 0 and sc == 0:
        return "neu"
    if lapses >= 2 or (lapses >= 1 and reps == 0):
        return "kritisch"
    if reps >= 2 and iv >= 6:
        return "gut"
    return "wackelig"

def baue_themen_fortschritt_html(ordner_row: dict) -> str:
    total = int(ordner_row.get("total_cards", 0))
    due = int(ordner_row.get("due_cards", 0))
    gut = int(ordner_row.get("gut_cards", 0))
    wackelig = int(ordner_row.get("wackelig_cards", 0))
    kritisch = int(ordner_row.get("kritisch_cards", 0))
    neu = int(ordner_row.get("neu_cards", 0))

    if total > 0:
        p_gut = round((gut / total) * 100, 1)
        p_wackelig = round((wackelig / total) * 100, 1)
        p_kritisch = round((kritisch / total) * 100, 1)
        p_neu = max(0.0, round(100.0 - p_gut - p_wackelig - p_kritisch, 1))
        mastery_pct = round((gut / total) * 100)
    else:
        p_gut = p_wackelig = p_kritisch = 0.0
        p_neu = 100.0
        mastery_pct = 0

    due_badge = (
        f'<span class="topic-due-badge">{due} fällig</span>'
        if due > 0 else '<span class="topic-done-badge">Alles erledigt</span>'
    )
    name_esc = html.escape(str(ordner_row["name"]))

    return (
        f'<div class="topic-card">'
        f'<div class="topic-top-row">'
        f'<div class="topic-name">{name_esc}</div>'
        f'<div class="topic-right-meta"><span class="topic-pct">{mastery_pct}% gefestigt</span>{due_badge}</div>'
        f'</div>'
        f'<div class="anki-bar-track">'
        f'<div class="anki-seg-gut" style="width:{p_gut}%;"></div>'
        f'<div class="anki-seg-wackelig" style="width:{p_wackelig}%;"></div>'
        f'<div class="anki-seg-kritisch" style="width:{p_kritisch}%;"></div>'
        f'<div class="anki-seg-neu" style="width:{p_neu}%;"></div>'
        f'</div>'
        f'<div class="anki-legend-row">'
        f'<span><i class="dot-gut"></i><b>{gut}</b> gut gelernt</span>'
        f'<span><i class="dot-wackelig"></i><b>{wackelig}</b> wackelig</span>'
        f'<span><i class="dot-kritisch"></i><b>{kritisch}</b> öfter falsch</span>'
        f'<span><i class="dot-neu"></i><b>{neu}</b> ungelernt</span>'
        f'</div>'
        f'</div>'
    )

# --- Basis-Design & Plastisches CSS ---
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at 50% -10%, #0F1A2E 0%, #07090E 55%, #05070B 100%);
        color: #F1F5F9;
    }

    .block-container {
        max-width: 1180px !important;
        padding-top: 2rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 2.4rem !important;
        padding-right: 2.4rem !important;
    }

    [data-testid="stSidebar"] {
        background-color: #090D16;
        border-right: 1px solid rgba(125, 211, 252, 0.22);
    }

    hr {
        border: none !important;
        border-top: 1px solid rgba(125, 211, 252, 0.22) !important;
        margin: 1.35rem 0 !important;
    }

    .omni-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 0.9rem;
        margin-bottom: 1.2rem;
        border-bottom: 1.5px solid rgba(125, 211, 252, 0.45);
    }

    .omni-brand {
        font-size: 2.25rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #FFFFFF 0%, #E0F2FE 55%, #7DD3FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
    }

    .omni-tagline {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 0.2rem;
        letter-spacing: 0.03em;
    }

    .ar-subtitle {
        font-size: 1.22rem;
        font-weight: 600;
        color: #E0F2FE;
        margin-top: 0.6rem;
        margin-bottom: 0.75rem;
    }

    .section-kicker {
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #7DD3FC;
        margin-bottom: 0.55rem;
    }

    .sculpt-panel {
        background: linear-gradient(165deg, #11192B 0%, #0A0F1A 100%);
        border: 1px solid rgba(125, 211, 252, 0.26);
        border-radius: 16px;
        padding: 1.25rem 1.45rem;
        box-shadow:
            0 14px 30px rgba(0, 0, 0, 0.52),
            inset 0 1px 0 rgba(255, 255, 255, 0.09);
        height: 100%;
    }

    .panel-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.65rem;
    }

    .level-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        background: linear-gradient(135deg, #38BDF8 0%, #7DD3FC 100%);
        color: #060911;
        font-weight: 800;
        font-size: 0.92rem;
        padding: 0.28rem 0.8rem;
        border-radius: 999px;
        box-shadow: 0 4px 14px rgba(125, 211, 252, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.65);
    }

    .xp-meta {
        font-size: 0.88rem;
        color: #CBD5E1;
        font-weight: 600;
    }

    .progress-track {
        width: 100%;
        height: 11px;
        background: #060911;
        border-radius: 999px;
        border: 1px solid rgba(125, 211, 252, 0.22);
        box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.75);
        overflow: hidden;
        margin: 0.55rem 0 0.75rem 0;
    }

    .progress-fill-ice {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #0284C7 0%, #38BDF8 55%, #BAE6FD 100%);
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.55);
        transition: width 0.25s ease;
    }

    .progress-fill-quest {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #0EA5E9 0%, #7DD3FC 100%);
        box-shadow: 0 0 12px rgba(125, 211, 252, 0.45);
        transition: width 0.25s ease;
    }

    .panel-footer-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem;
        font-size: 0.82rem;
        color: #94A3B8;
    }

    .streak-chip {
        display: inline-block;
        padding: 0.18rem 0.6rem;
        border-radius: 7px;
        background: rgba(125, 211, 252, 0.12);
        border: 1px solid rgba(125, 211, 252, 0.3);
        color: #E0F2FE;
        font-weight: 600;
    }

    .streak-chip-hot {
        display: inline-block;
        padding: 0.18rem 0.6rem;
        border-radius: 7px;
        background: rgba(250, 204, 21, 0.16);
        border: 1px solid rgba(250, 204, 21, 0.45);
        color: #FDE047;
        font-weight: 700;
    }

    .day-dots {
        display: inline-flex;
        gap: 5px;
        align-items: center;
    }

    .day-dot {
        width: 11px;
        height: 11px;
        border-radius: 50%;
        background: #070A12;
        border: 1px solid rgba(125, 211, 252, 0.3);
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.8);
    }

    .day-dot-active {
        background: linear-gradient(135deg, #7DD3FC 0%, #38BDF8 100%);
        border-color: #E0F2FE;
        box-shadow: 0 0 8px rgba(125, 211, 252, 0.65);
    }

    .stat-card {
        background: linear-gradient(165deg, #101727 0%, #090D16 100%);
        border: 1px solid rgba(125, 211, 252, 0.24);
        border-radius: 16px;
        padding: 1.15rem 1rem;
        text-align: center;
        box-shadow:
            0 12px 26px rgba(0, 0, 0, 0.48),
            inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }

    .stat-num {
        font-size: 2rem;
        font-weight: 800;
        color: #7DD3FC;
        line-height: 1.15;
        text-shadow: 0 2px 14px rgba(125, 211, 252, 0.22);
    }

    .stat-label {
        font-size: 0.85rem;
        font-weight: 500;
        color: #94A3B8;
        margin-top: 0.25rem;
        letter-spacing: 0.02em;
    }

    .topic-card {
        background: linear-gradient(165deg, #101829 0%, #090D16 100%);
        border: 1px solid rgba(125, 211, 252, 0.24);
        border-radius: 15px;
        padding: 1.05rem 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow:
            0 10px 24px rgba(0, 0, 0, 0.46),
            inset 0 1px 0 rgba(255, 255, 255, 0.07);
    }

    .topic-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.55rem;
    }

    .topic-name {
        font-size: 1.03rem;
        font-weight: 700;
        color: #F8FAFC;
    }

    .topic-right-meta {
        display: flex;
        align-items: center;
        gap: 0.55rem;
    }

    .topic-pct {
        font-size: 0.84rem;
        font-weight: 700;
        color: #7DD3FC;
    }

    .topic-due-badge {
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.16rem 0.55rem;
        border-radius: 999px;
        background: rgba(125, 211, 252, 0.14);
        border: 1px solid rgba(125, 211, 252, 0.35);
        color: #E0F2FE;
    }

    .topic-done-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.16rem 0.55rem;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.12);
        border: 1px solid rgba(148, 163, 184, 0.25);
        color: #94A3B8;
    }

    .anki-bar-track {
        display: flex;
        width: 100%;
        height: 11px;
        background: #060911;
        border-radius: 999px;
        border: 1px solid rgba(125, 211, 252, 0.2);
        box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.8);
        overflow: hidden;
        margin-bottom: 0.6rem;
    }

    .anki-seg-gut {
        height: 100%;
        background: linear-gradient(90deg, #0284C7 0%, #38BDF8 65%, #7DD3FC 100%);
        transition: width 0.25s ease;
    }

    .anki-seg-wackelig {
        height: 100%;
        background: linear-gradient(90deg, #EAB308 0%, #FACC15 100%);
        transition: width 0.25s ease;
    }

    .anki-seg-kritisch {
        height: 100%;
        background: linear-gradient(90deg, #DC2626 0%, #F87171 100%);
        transition: width 0.25s ease;
    }

    .anki-seg-neu {
        height: 100%;
        background: #172033;
        transition: width 0.25s ease;
    }

    .anki-legend-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.85rem;
        font-size: 0.8rem;
        color: #94A3B8;
    }

    .anki-legend-row b {
        color: #E2E8F0;
    }

    .dot-gut, .dot-wackelig, .dot-kritisch, .dot-neu {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 5px;
        vertical-align: middle;
    }
    .dot-gut { background: #38BDF8; box-shadow: 0 0 6px rgba(56, 189, 248, 0.6); }
    .dot-wackelig { background: #FACC15; }
    .dot-kritisch { background: #F87171; }
    .dot-neu { background: #334155; border: 1px solid #64748B; }

    /* Fokussierte Lern-Fortschrittsleiste oben */
    .focus-progress-wrap {
        margin-bottom: 0.35rem;
    }
    .focus-progress-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.84rem;
        color: #94A3B8;
        font-weight: 600;
        margin-bottom: 0.35rem;
    }

    .flashcard-box {
        background: linear-gradient(160deg, #11192C 0%, #0A0F1B 100%);
        border: 1.5px solid rgba(125, 211, 252, 0.48);
        border-radius: 18px;
        padding: 2.15rem 2.15rem;
        margin: 0.85rem 0 1.25rem 0;
        box-shadow:
            0 18px 38px rgba(0, 0, 0, 0.58),
            0 0 0 1px rgba(125, 211, 252, 0.08),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    .flashcard-meta {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1.15rem;
    }

    .flashcard-badge {
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #060911;
        background: linear-gradient(135deg, #7DD3FC 0%, #38BDF8 100%);
        padding: 0.26rem 0.72rem;
        border-radius: 7px;
        box-shadow: 0 3px 10px rgba(56, 189, 248, 0.25);
    }

    .flashcard-badge-xp {
        display: inline-block;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: #BAE6FD;
        background: rgba(125, 211, 252, 0.12);
        border: 1px solid rgba(125, 211, 252, 0.35);
        padding: 0.23rem 0.65rem;
        border-radius: 7px;
    }

    .flashcard-badge-warn {
        display: inline-block;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: #07090E;
        background-color: #FACC15;
        padding: 0.25rem 0.68rem;
        border-radius: 7px;
    }

    .flashcard-question {
        font-size: 1.38rem;
        font-weight: 500;
        color: #F8FAFC;
        line-height: 1.65;
        letter-spacing: 0.005em;
    }

    .flashcard-answer-label {
        font-size: 0.78rem;
        color: #7DD3FC;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }

    .flashcard-answer-body {
        font-size: 1.18rem;
        font-weight: 400;
        color: #F8FAFC;
        line-height: 1.65;
    }

    .flashcard-explanation {
        margin-top: 1rem;
        padding-top: 0.85rem;
        border-top: 1px solid rgba(125, 211, 252, 0.2);
        color: #BAE6FD;
        font-size: 0.96rem;
        line-height: 1.55;
    }

    .cloze-blank {
        display: inline-block;
        min-width: 96px;
        padding: 0 0.55rem;
        margin: 0 0.2rem;
        border-bottom: 2.5px solid #7DD3FC;
        background: rgba(125, 211, 252, 0.12);
        border-radius: 5px 5px 0 0;
        color: #7DD3FC;
        font-weight: 700;
        text-align: center;
        letter-spacing: 0.08em;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 0.6rem;
        margin-top: 0.4rem;
        margin-bottom: 0.8rem;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        background: linear-gradient(165deg, #101829 0%, #0A0F1A 100%) !important;
        border: 1px solid rgba(125, 211, 252, 0.3) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.05rem !important;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.38) !important;
        transition: border-color 0.12s ease !important;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
        border-color: #7DD3FC !important;
    }

    .xp-banner {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.14) 0%, rgba(15, 23, 42, 0.88) 100%);
        border: 1px solid rgba(125, 211, 252, 0.42);
        border-radius: 11px;
        padding: 0.55rem 0.95rem;
        margin-bottom: 0.7rem;
        color: #E0F2FE;
        font-size: 0.88rem;
        font-weight: 600;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.6rem;
        background: #0A0F1A;
        padding: 0.4rem;
        border-radius: 14px;
        border: 1px solid rgba(125, 211, 252, 0.2);
        box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.55);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 0.65rem 1.2rem !important;
        font-weight: 600 !important;
        font-size: 0.96rem !important;
        color: #94A3B8 !important;
        border: none !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(160deg, #162238 0%, #0F172A 100%) !important;
        color: #E0F2FE !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(125, 211, 252, 0.35) !important;
    }

    .stButton > button {
        background: linear-gradient(180deg, #152036 0%, #0D1424 100%) !important;
        border: 1px solid rgba(125, 211, 252, 0.42) !important;
        color: #E0F2FE !important;
        border-radius: 12px !important;
        padding: 0.62rem 1.1rem !important;
        font-weight: 600 !important;
        box-shadow:
            0 6px 16px rgba(0, 0, 0, 0.42),
            inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
        transition: border-color 0.12s ease, background 0.12s ease !important;
    }
    .stButton > button:hover {
        border-color: #7DD3FC !important;
        background: linear-gradient(180deg, #1B2A47 0%, #111B30 100%) !important;
        color: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Passwort-Abfrage ---
def passwort_pruefen():
    try:
        richtiges_passwort = st.secrets["APP_PASSWORD"]
    except Exception:
        richtiges_passwort = "1234"

    if "eingeloggt" not in st.session_state:
        st.session_state.eingeloggt = False

    if not st.session_state.eingeloggt:
        st.markdown(
            '<div class="omni-header"><div><div class="omni-brand">OmniLearn</div><div class="omni-tagline">Active Recall & Spaced Repetition</div></div></div>',
            unsafe_allow_html=True,
        )
        col_l, _ = st.columns([1.2, 1])
        with col_l:
            eingabe = st.text_input("Zugangspasswort:", type="password", placeholder="Passwort eingeben...")
            if st.button("Entsperren", use_container_width=True):
                if eingabe == richtiges_passwort:
                    st.session_state.eingeloggt = True
                    st.rerun()
                else:
                    st.error("Falsches Passwort.")
        st.stop()

passwort_pruefen()

# --- Persistenter Connection-Pool & Asynchroner FIFO-Hintergrund-Writer ---
def get_db_url():
    try:
        url = st.secrets["DATABASE_URL"].strip()
    except Exception:
        url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@st.cache_resource
def get_db_pool():
    db_url = get_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL fehlt in den Streamlit Secrets.")
    return pool.ThreadedConnectionPool(minconn=1, maxconn=6, dsn=db_url, connect_timeout=15)

def get_connection():
    p = get_db_pool()
    last_err = None
    for _ in range(3):
        conn = None
        try:
            conn = p.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return conn
        except Exception as e:
            last_err = e
            if conn is not None:
                try:
                    p.putconn(conn, close=True)
                except Exception:
                    pass
            time.sleep(0.4)
    raise last_err

def release_connection(conn, broken: bool = False):
    if conn is None:
        return
    try:
        get_db_pool().putconn(conn, close=broken)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

@st.cache_resource
def get_bg_db_queue():
    q = queue.Queue()

    def _worker():
        while True:
            task = q.get()
            conn = None
            broken = False
            try:
                conn = get_connection()
                with conn.cursor() as cur:
                    for sql, params in task:
                        cur.execute(sql, params)
                conn.commit()
            except Exception:
                broken = True
                if conn is not None:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            finally:
                release_connection(conn, broken=broken)
                q.task_done()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return q

def enqueue_db_writes(statements: list):
    get_bg_db_queue().put(statements)

@st.cache_resource
def init_db():
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    char_count INTEGER DEFAULT 0,
                    content_text TEXT DEFAULT '',
                    uploaded_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_text TEXT DEFAULT '';")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id SERIAL PRIMARY KEY,
                    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                    card_type TEXT NOT NULL DEFAULT 'Klassisch',
                    question TEXT NOT NULL,
                    options_json TEXT DEFAULT '[]',
                    answer TEXT NOT NULL,
                    explanation TEXT DEFAULT '',
                    ease_factor REAL NOT NULL DEFAULT 2.5,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    lapses INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    next_review TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0;")
            cur.execute("UPDATE cards SET success_count = repetitions WHERE success_count = 0 AND repetitions > 0;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    level INTEGER NOT NULL DEFAULT 1,
                    xp_in_level INTEGER NOT NULL DEFAULT 0,
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    answer_streak INTEGER NOT NULL DEFAULT 0,
                    best_answer_streak INTEGER NOT NULL DEFAULT 0,
                    daily_cards_done INTEGER NOT NULL DEFAULT 0,
                    daily_quest_claimed BOOLEAN NOT NULL DEFAULT FALSE,
                    stats_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    daily_quest_streak INTEGER NOT NULL DEFAULT 0,
                    last_quest_completed_date DATE,
                    selected_cursor_level INTEGER NOT NULL DEFAULT -1,
                    bonus_10_start TIMESTAMPTZ,
                    bonus_20_start TIMESTAMPTZ
                );
            """)
            cur.execute("ALTER TABLE user_progress ADD COLUMN IF NOT EXISTS bonus_10_start TIMESTAMPTZ;")
            cur.execute("ALTER TABLE user_progress ADD COLUMN IF NOT EXISTS bonus_20_start TIMESTAMPTZ;")

            cur.execute("""
                INSERT INTO user_progress (id, level, xp_in_level, total_xp, stats_date)
                VALUES (1, 1, 0, 0, CURRENT_DATE)
                ON CONFLICT (id) DO NOTHING;
            """)
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)
    return True

try:
    init_db()
except Exception as e:
    st.error(f"Datenbank-Verbindung fehlgeschlagen: {e}")
    st.info("Prüfe in Streamlit unter **Settings → Secrets**, ob `DATABASE_URL` korrekt eingetragen ist.")
    st.stop()

# --- Fortschritt, XP, Quests & Cursor-Logik ---
def lade_user_progress_aus_db() -> dict:
    heute_berlin = datetime.datetime.now(BERLIN_TZ).date()
    gestern_berlin = heute_berlin - datetime.timedelta(days=1)

    conn = get_connection()
    broken = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM user_progress WHERE id = 1;")
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO user_progress (id, level, xp_in_level, total_xp, stats_date) VALUES (1, 1, 0, 0, %s) RETURNING *;",
                    (heute_berlin,)
                )
                row = cur.fetchone()

            needs_update = False
            stats_date = row["stats_date"]
            daily_cards_done = row["daily_cards_done"]
            daily_quest_claimed = row["daily_quest_claimed"]
            daily_quest_streak = row["daily_quest_streak"]
            last_completed = row["last_quest_completed_date"]

            if stats_date != heute_berlin:
                daily_cards_done = 0
                daily_quest_claimed = False
                stats_date = heute_berlin
                needs_update = True

            if daily_quest_streak > 0 and (last_completed is None or last_completed < gestern_berlin):
                daily_quest_streak = 0
                needs_update = True

            if needs_update:
                cur.execute(
                    """
                    UPDATE user_progress
                    SET daily_cards_done = %s,
                        daily_quest_claimed = %s,
                        stats_date = %s,
                        daily_quest_streak = %s,
                        bonus_10_start = NULL,
                        bonus_20_start = NULL
                    WHERE id = 1
                    RETURNING *;
                    """,
                    (daily_cards_done, daily_quest_claimed, stats_date, daily_quest_streak)
                )
                row = cur.fetchone()
        conn.commit()
        return dict(row)
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def hole_user_progress_schnell() -> dict:
    heute_berlin = datetime.datetime.now(BERLIN_TZ).date()
    if "cached_user_progress" not in st.session_state:
        st.session_state.cached_user_progress = lade_user_progress_aus_db()
    elif st.session_state.cached_user_progress.get("stats_date") != heute_berlin:
        st.session_state.cached_user_progress = lade_user_progress_aus_db()
    return st.session_state.cached_user_progress

def lade_ordner_aus_db() -> list:
    conn = get_connection()
    broken = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    f.id,
                    f.name,
                    COUNT(DISTINCT d.id) AS doc_count,
                    COUNT(DISTINCT c.id) AS total_cards,
                    COUNT(DISTINCT CASE WHEN c.next_review <= NOW() THEN c.id END) AS due_cards,
                    COUNT(DISTINCT CASE WHEN c.lapses > 0 THEN c.id END) AS weak_cards,
                    COUNT(DISTINCT CASE
                        WHEN c.id IS NOT NULL
                         AND c.repetitions = 0
                         AND c.lapses = 0
                         AND COALESCE(c.success_count, 0) = 0
                        THEN c.id
                    END) AS neu_cards,
                    COUNT(DISTINCT CASE
                        WHEN c.id IS NOT NULL
                         AND (c.lapses >= 2 OR (c.lapses >= 1 AND c.repetitions = 0))
                        THEN c.id
                    END) AS kritisch_cards,
                    COUNT(DISTINCT CASE
                        WHEN c.id IS NOT NULL
                         AND NOT (c.lapses >= 2 OR (c.lapses >= 1 AND c.repetitions = 0))
                         AND c.repetitions >= 2
                         AND c.interval_days >= 6
                        THEN c.id
                    END) AS gut_cards,
                    COUNT(DISTINCT CASE
                        WHEN c.id IS NOT NULL
                         AND NOT (c.repetitions = 0 AND c.lapses = 0 AND COALESCE(c.success_count, 0) = 0)
                         AND NOT (c.lapses >= 2 OR (c.lapses >= 1 AND c.repetitions = 0))
                         AND NOT (c.repetitions >= 2 AND c.interval_days >= 6)
                        THEN c.id
                    END) AS wackelig_cards
                FROM folders f
                LEFT JOIN documents d ON d.folder_id = f.id
                LEFT JOIN cards c ON c.folder_id = f.id
                GROUP BY f.id, f.name
                ORDER BY f.name ASC;
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def hole_ordner_schnell(force_refresh: bool = False) -> list:
    if force_refresh or "cached_ordner_liste" not in st.session_state:
        st.session_state.cached_ordner_liste = lade_ordner_aus_db()
    return st.session_state.cached_ordner_liste

def invalidiere_ordner_cache():
    if "cached_ordner_liste" in st.session_state:
        del st.session_state["cached_ordner_liste"]

def verarbeite_bewertung_sofort(
    aktuelle_karte: dict,
    ef: float,
    iv: int,
    reps: int,
    lapses: int,
    next_rev: datetime.datetime,
    neuer_success_count: int,
    erfolgreich: bool,
    war_erste_loesung: bool,
) -> str:
    heute_berlin = datetime.datetime.now(BERLIN_TZ).date()
    gestern_berlin = heute_berlin - datetime.timedelta(days=1)
    jetzt_utc = datetime.datetime.now(datetime.timezone.utc)

    alter_status = klassifiziere_karte_anki(aktuelle_karte)
    war_faellig = (aktuelle_karte["next_review"] <= jetzt_utc)

    aktuelle_karte["ease_factor"] = ef
    aktuelle_karte["interval_days"] = iv
    aktuelle_karte["repetitions"] = reps
    aktuelle_karte["lapses"] = lapses
    aktuelle_karte["next_review"] = next_rev
    aktuelle_karte["success_count"] = neuer_success_count

    neuer_status = klassifiziere_karte_anki(aktuelle_karte)
    ist_jetzt_faellig = (next_rev <= jetzt_utc)

    for o in hole_ordner_schnell():
        if o["id"] == aktuelle_karte["folder_id"]:
            if war_faellig and not ist_jetzt_faellig:
                o["due_cards"] = max(0, int(o["due_cards"]) - 1)
            if alter_status != neuer_status:
                o[f"{alter_status}_cards"] = max(0, int(o[f"{alter_status}_cards"]) - 1)
                o[f"{neuer_status}_cards"] = int(o[f"{neuer_status}_cards"]) + 1
            break

    prog = hole_user_progress_schnell()
    level = int(prog["level"])
    xp_in_level = int(prog["xp_in_level"])
    total_xp = int(prog["total_xp"])
    answer_streak = int(prog["answer_streak"])
    best_answer_streak = int(prog["best_answer_streak"])
    daily_cards_done = int(prog["daily_cards_done"])
    daily_quest_claimed = bool(prog["daily_quest_claimed"])
    daily_quest_streak = int(prog["daily_quest_streak"])
    last_completed = prog["last_quest_completed_date"]
    selected_cursor_level = int(prog["selected_cursor_level"])
    bonus_10_start = prog.get("bonus_10_start")
    bonus_20_start = prog.get("bonus_20_start")

    ereignisse = []
    xp_gewinn = 0
    streak_bonus = 0

    if not erfolgreich:
        answer_streak = 0
        ereignisse.append("Antwort-Serie gerissen · Karte kommt gleich nochmal.")
    else:
        basis_xp = 2 if war_erste_loesung else 1
        answer_streak += 1
        best_answer_streak = max(best_answer_streak, answer_streak)

        if answer_streak >= 10:
            if bonus_10_start is None:
                bonus_10_start = jetzt_utc
                ereignisse.append("🔥 10er-Serie! +1 XP Multiplikator für 30 Min. aktiv!")
                streak_bonus = 1
            elif (jetzt_utc - bonus_10_start).total_seconds() < 1800:
                streak_bonus = 1

        if answer_streak >= 20:
            if bonus_20_start is None:
                bonus_20_start = jetzt_utc
                ereignisse.append("⚡ 20er-Serie! +2 XP Multiplikator für 30 Min. aktiv!")
                streak_bonus = 2
            elif (jetzt_utc - bonus_20_start).total_seconds() < 1800:
                streak_bonus = 2

        xp_gewinn += basis_xp + streak_bonus
        details = [f"+{basis_xp} XP ({'Erst-Erfolg' if war_erste_loesung else 'Wiederholung'})"]
        if streak_bonus > 0:
            details.append(f"+{streak_bonus} XP ({answer_streak}er-Serie)")
        ereignisse.append(" · ".join(details))

        daily_cards_done += 1
        extra_level_ups = 0

        if daily_cards_done >= DAILY_GOAL_TARGET and not daily_quest_claimed:
            daily_quest_claimed = True
            xp_gewinn += DAILY_GOAL_BONUS_XP
            ereignisse.append(f"🎯 Tagesziel ({DAILY_GOAL_TARGET}/{DAILY_GOAL_TARGET}) erfüllt: +{DAILY_GOAL_BONUS_XP} XP Extra!")

            if last_completed == gestern_berlin:
                daily_quest_streak += 1
            elif last_completed == heute_berlin:
                pass
            else:
                daily_quest_streak = 1
            last_completed = heute_berlin

            if daily_quest_streak > 0 and daily_quest_streak % 7 == 0:
                extra_level_ups += 1
                ereignisse.append(f"🔥 {daily_quest_streak} Tage in Folge! Vollständiges Level-Up!")

        old_level = level
        xp_in_level += xp_gewinn
        total_xp += xp_gewinn

        while xp_in_level >= xp_fuer_naechstes_level(level):
            xp_in_level -= xp_fuer_naechstes_level(level)
            level += 1

        level += extra_level_ups

        if level > old_level:
            ereignisse.append(f"⬆️ Level-Up erreicht: Jetzt Level {level}!")
            neu_freigeschaltet = [
                c for c in CURSOR_MILESTONES
                if c["level"] > 0 and old_level < c["level"] <= level
            ]
            if neu_freigeschaltet:
                neues_symbol = neu_freigeschaltet[-1]
                selected_cursor_level = -1
                ereignisse.append(f"✨ Neues Maus-Symbol freigeschaltet: {neues_symbol['name']}!")

    prog.update({
        "level": level,
        "xp_in_level": xp_in_level,
        "total_xp": total_xp,
        "answer_streak": answer_streak,
        "best_answer_streak": best_answer_streak,
        "daily_cards_done": daily_cards_done,
        "daily_quest_claimed": daily_quest_claimed,
        "stats_date": heute_berlin,
        "daily_quest_streak": daily_quest_streak,
        "last_quest_completed_date": last_completed,
        "selected_cursor_level": selected_cursor_level,
        "bonus_10_start": bonus_10_start,
        "bonus_20_start": bonus_20_start,
    })

    enqueue_db_writes([
        (
            """
            UPDATE cards
            SET ease_factor = %s,
                interval_days = %s,
                repetitions = %s,
                lapses = %s,
                next_review = %s,
                success_count = %s
            WHERE id = %s;
            """,
            (ef, iv, reps, lapses, next_rev, neuer_success_count, aktuelle_karte["id"]),
        ),
        (
            """
            UPDATE user_progress
            SET level = %s,
                xp_in_level = %s,
                total_xp = %s,
                answer_streak = %s,
                best_answer_streak = %s,
                daily_cards_done = %s,
                daily_quest_claimed = %s,
                stats_date = %s,
                daily_quest_streak = %s,
                last_quest_completed_date = %s,
                selected_cursor_level = %s,
                bonus_10_start = %s,
                bonus_20_start = %s
            WHERE id = 1;
            """,
            (
                level,
                xp_in_level,
                total_xp,
                answer_streak,
                best_answer_streak,
                daily_cards_done,
                daily_quest_claimed,
                heute_berlin,
                daily_quest_streak,
                last_completed,
                selected_cursor_level,
                bonus_10_start,
                bonus_20_start,
            ),
        ),
    ])

    return "  |  ".join(ereignisse)

def setze_ausgewaehlten_cursor(cursor_level: int):
    prog = hole_user_progress_schnell()
    prog["selected_cursor_level"] = cursor_level
    enqueue_db_writes([
        ("UPDATE user_progress SET selected_cursor_level = %s WHERE id = 1;", (cursor_level,))
    ])

# --- Benutzer-Fortschritt laden & freigeschaltetes Maus-Symbol anwenden ---
user_prog = hole_user_progress_schnell()
aktuelles_level = int(user_prog["level"])
aktiver_cursor = ermittle_aktiven_cursor(aktuelles_level, int(user_prog["selected_cursor_level"]))

if aktiver_cursor["svg"]:
    cursor_uri = svg_zu_data_uri(aktiver_cursor["svg"])
    hx, hy = aktiver_cursor["hot_x"], aktiver_cursor["hot_y"]
    st.markdown(
        f'<style>html, body, .stApp, .stApp * {{ cursor: url("{cursor_uri}") {hx} {hy}, auto !important; }}</style>',
        unsafe_allow_html=True,
    )

# --- Gemini API Initialisierung ---
@st.cache_resource
def init_gemini():
    try:
        api_key = st.secrets["GEMINI_API_KEY"].strip()
    except Exception:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        return []

    genai.configure(api_key=api_key, transport="rest")
    verfuegbare_modelle = []
    try:
        for m in genai.list_models():
            if 'generateContent' in getattr(m, 'supported_generation_methods', []):
                name = m.name
                n_low = name.lower()
                if "gemini" in n_low and not any(x in n_low for x in ["image", "audio", "tts", "robotics", "computer", "embedding", "aqa"]):
                    verfuegbare_modelle.append(name)
    except Exception:
        pass

    verfuegbare_modelle.sort(key=lambda x: (
        0 if ("flash" in x.lower() and "lite" not in x.lower()) else (1 if "lite" in x.lower() else 2),
        x
    ))
    return verfuegbare_modelle

verfuegbare_modelle = init_gemini()
if "aktives_modell" not in st.session_state and verfuegbare_modelle:
    st.session_state.aktives_modell = verfuegbare_modelle[0]

def gemini_fragen(prompt, timeout=90):
    if not verfuegbare_modelle:
        raise RuntimeError("GEMINI_API_KEY fehlt in den Secrets oder es wurden keine Modelle gefunden.")
    letzter_fehler = None
    aktiv = st.session_state.get("aktives_modell", verfuegbare_modelle[0])
    kandidaten = [aktiv] + [m for m in verfuegbare_modelle if m != aktiv]

    for modell_name in kandidaten:
        try:
            aktuelles_modell = genai.GenerativeModel(modell_name)
            antwort = aktuelles_modell.generate_content(prompt, request_options={"timeout": timeout})
            st.session_state.aktives_modell = modell_name
            return antwort.text
        except Exception as e:
            letzter_fehler = e
            continue
    raise letzter_fehler

# --- Text-Extraktion ---
def extrahiere_text_aus_datei(uploaded_file):
    name = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw_bytes))
        seiten = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(seiten).strip()
    elif name.endswith(".docx"):
        doc = Document(io.BytesIO(raw_bytes))
        absaetze = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                absaetze.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(absaetze).strip()
    else:
        for enc in ("utf-8", "latin-1"):
            try:
                return raw_bytes.decode(enc).strip()
            except Exception:
                continue
        return ""

# --- Kartengenerator ---
def generiere_karteikarten(text_inhalt, anzahl, aufgabentypen):
    gekuerzter_text = text_inhalt[:28000]
    typen_beschreibung = {
        "Lückentext": (
            "Lückentext: Formuliere auf der Vorderseite ('question') einen wichtigen, prüfungsrelevanten Merksatz oder Zusammenhang, "
            "bei dem 1 bis 2 zentrale Fachbegriffe durch '______' ersetzt wurden. "
            "Schreibe in 'answer' die gesuchten Begriffe sowie den vollständigen Satz. 'options' ist []."
        ),
        "Problemstellung": (
            "Problemstellung: Formuliere auf der Vorderseite ('question') ein kurzes, konkretes Fallbeispiel, eine Mini-Aufgabe "
            "oder eine 'Was passiert, wenn...'-Problemstellung, die der Lernende aktiv durchdenken und lösen muss. "
            "Schreibe in 'answer' die klare Lösung mit Schritt-für-Schritt-Begründung. 'options' ist []."
        ),
        "Multiple Choice": (
            "Multiple Choice: Formuliere auf der Vorderseite ('question') eine präzise Verständnis- oder Anwendungsfrage "
            "(liste die Antwortmöglichkeiten NICHT im Text von 'question' auf!). "
            "Fülle das Array 'options' mit EXAKT 4 plausiblen, kurzen Antwortoptionen (ohne Buchstaben wie A/B/C/D davor). "
            "Schreibe in 'answer' exakt den identischen Wortlaut der einen richtigen Option aus 'options'."
        ),
        "Klassisch": (
            "Klassisch: Formuliere auf der Vorderseite ('question') eine gezielte offene Verständnis- oder Erklärungsfrage "
            "und in 'answer' eine klare, strukturierte Musterantwort. 'options' ist []."
        ),
    }

    gewaehlte_liste = [t for t in aufgabentypen if t in typen_beschreibung]
    if not gewaehlte_liste:
        gewaehlte_liste = ["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"]

    karten_fahrplan = "\n".join(
        f"- Karte {i + 1}: Pflicht-Typ '{gewaehlte_liste[i % len(gewaehlte_liste)]}'"
        for i in range(anzahl)
    )
    gewaehlte_beschreibungen = "\n".join(
        f"* {t}: {typen_beschreibung[t]}" for t in gewaehlte_liste
    )

    prompt = (
        f"Du bist ein Experte für evidenzbasiertes Lernen (Active Recall & Spaced Repetition).\n"
        f"Erstelle auf Basis des folgenden Lernmaterials genau {anzahl} hochwertige, abwechslungsreiche Lernaufgaben.\n\n"
        f"VERBINDLICHER AUFGABEN-FAHRPLAN (halte dich exakt an den vorgegebenen Typ je Karte):\n{karten_fahrplan}\n\n"
        f"FORMAT-REGELN JE TYP:\n{gewaehlte_beschreibungen}\n\n"
        "Allgemeine Qualitätsregeln:\n"
        "1. Keine trivialen Ja/Nein-Fragen. Jede Aufgabe soll echtes Nachdenken und aktives Abrufen auslösen.\n"
        "2. Schreibe alle Fragen, Lückentexte und Problemstellungen als normalen, gut lesbaren Fließtext (ohne Code-Blöcke).\n"
        "3. Bei 'Multiple Choice' MÜSSEN im Feld 'options' immer genau 4 verschiedene Antwortmöglichkeiten stehen!\n"
        "4. Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Array (ohne ```json).\n\n"
        f"LERNMATERIAL:\n{gekuerzter_text}"
    )

    rohtext = gemini_fragen(prompt, timeout=90).strip()
    if rohtext.startswith("```"):
        rohtext = rohtext.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start_idx = rohtext.find("[")
    end_idx = rohtext.rfind("]")
    if start_idx != -1 and end_idx != -1:
        rohtext = rohtext[start_idx:end_idx + 1]

    karten = json.loads(rohtext)
    bereinigt = []
    for idx, k in enumerate(karten):
        if not k.get("question") or not k.get("answer"):
            continue
        erwarteter_typ = gewaehlte_liste[idx % len(gewaehlte_liste)]
        ctype = str(k.get("card_type", erwarteter_typ)).strip()
        if ctype == "Transfer":
            ctype = "Problemstellung"
        if ctype not in ("Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"):
            ctype = erwarteter_typ

        raw_opts = k.get("options") if ctype == "Multiple Choice" else []
        opts = []
        if isinstance(raw_opts, list):
            for o in raw_opts:
                clean_o = re.sub(r"^[A-Da-d1-4][\)\.\:]\s*", "", str(o).strip())
                if clean_o:
                    opts.append(clean_o)

        ans_clean = re.sub(r"^[A-Da-d1-4][\)\.\:]\s*", "", str(k["answer"]).strip())

        if ctype == "Multiple Choice" and len(opts) < 2:
            ctype = "Klassisch"
            opts = []
        elif ctype == "Multiple Choice":
            opts = opts[:4]
            if ans_clean not in opts and opts:
                match = next((o for o in opts if ans_clean.lower() in o.lower() or o.lower() in ans_clean.lower()), None)
                if match:
                    ans_clean = match
                else:
                    opts[0] = ans_clean

        bereinigt.append({
            "card_type": ctype,
            "question": str(k["question"]).strip(),
            "options": opts,
            "answer": ans_clean,
            "explanation": str(k.get("explanation", "")).strip(),
        })
    return bereinigt

# --- Spaced Repetition Algorithmus ---
def berechne_sm2(ease_factor, interval_days, repetitions, lapses, bewertung):
    ef = float(ease_factor)
    interval = int(interval_days)
    reps = int(repetitions)
    lapses = int(lapses)

    if bewertung == 1:
        reps = 0
        interval = 0
        lapses += 1
        ef = max(1.3, ef - 0.20)
        next_delta = datetime.timedelta(minutes=1)
    elif bewertung == 2:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = max(interval + 1, round(interval * 1.2))
        reps += 1
        ef = max(1.3, ef - 0.15)
        next_delta = datetime.timedelta(days=interval)
    elif bewertung == 3:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(interval + 1, round(interval * ef))
        reps += 1
        next_delta = datetime.timedelta(days=interval)
    else:
        if reps == 0:
            interval = 4
        elif reps == 1:
            interval = 8
        else:
            interval = max(interval + 2, round(interval * ef * 1.3))
        reps += 1
        ef = min(3.2, ef + 0.15)
        next_delta = datetime.timedelta(days=interval)

    next_review = datetime.datetime.now(datetime.timezone.utc) + next_delta
    return ef, interval, reps, lapses, next_review

def formatiere_intervall_vorschau(ease_factor, interval_days, repetitions, lapses, bewertung):
    _, iv, _, _, _ = berechne_sm2(ease_factor, interval_days, repetitions, lapses, bewertung)
    if iv == 0:
        return "Sofort wieder"
    elif iv == 1:
        return "1 Tag"
    else:
        return f"{iv} Tage"

# --- Datenbank-Verwaltungs-Befehle ---
def erstelle_ordner(name):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO folders (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id;",
                (name.strip(),)
            )
            res = cur.fetchone()
        conn.commit()
        invalidiere_ordner_cache()
        return res is not None
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def loesche_ordner(folder_id):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM folders WHERE id = %s;", (folder_id,))
        conn.commit()
        invalidiere_ordner_cache()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def lade_dokumente_fuer_ordner(folder_id):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.filename, d.char_count, COALESCE(d.content_text, '') AS content_text, d.uploaded_at, COUNT(c.id) AS card_count
                FROM documents d
                LEFT JOIN cards c ON c.document_id = d.id
                WHERE d.folder_id = %s
                GROUP BY d.id
                ORDER BY d.uploaded_at DESC;
            """, (folder_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def speichere_dokument_und_karten(folder_id, filename, char_count, karten_liste, content_text=""):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (folder_id, filename, char_count, content_text) VALUES (%s, %s, %s, %s) RETURNING id;",
                (folder_id, filename, char_count, content_text[:40000])
            )
            doc_id = cur.fetchone()[0]
            for k in karten_liste:
                cur.execute(
                    """
                    INSERT INTO cards (folder_id, document_id, card_type, question, options_json, answer, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        folder_id,
                        doc_id,
                        k["card_type"],
                        k["question"],
                        json.dumps(k.get("options", []), ensure_ascii=False),
                        k["answer"],
                        k.get("explanation", "")
                    )
                )
        conn.commit()
        invalidiere_ordner_cache()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def fuege_karten_zu_dokument_hinzu(folder_id, doc_id, karten_liste):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            for k in karten_liste:
                cur.execute(
                    """
                    INSERT INTO cards (folder_id, document_id, card_type, question, options_json, answer, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        folder_id,
                        doc_id,
                        k["card_type"],
                        k["question"],
                        json.dumps(k.get("options", []), ensure_ascii=False),
                        k["answer"],
                        k.get("explanation", "")
                    )
                )
        conn.commit()
        invalidiere_ordner_cache()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def lade_lernkarten(folder_id=None, modus="due"):
    get_bg_db_queue().join()
    conn = get_connection()
    broken = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            bedingungen = []
            params = []
            if folder_id is not None:
                bedingungen.append("c.folder_id = %s")
                params.append(folder_id)
            if modus == "due":
                bedingungen.append("c.next_review <= NOW()")
            elif modus == "weak":
                bedingungen.append("c.lapses > 0")

            where_clause = ("WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
            query = f"""
                SELECT c.*, f.name AS folder_name
                FROM cards c
                JOIN folders f ON f.id = c.folder_id
                {where_clause}
                ORDER BY
                    CASE WHEN c.lapses > 0 THEN 0 ELSE 1 END,
                    c.next_review ASC,
                    c.id ASC;
            """
            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def loesche_karte(card_id):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cards WHERE id = %s;", (card_id,))
        conn.commit()
        invalidiere_ordner_cache()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

# --- Session State ---
if "study_queue" not in st.session_state:
    st.session_state.study_queue = []
if "study_show_answer" not in st.session_state:
    st.session_state.study_show_answer = False
if "study_done_count" not in st.session_state:
    st.session_state.study_done_count = 0
if "study_initial_total" not in st.session_state:
    st.session_state.study_initial_total = 0
if "study_label" not in st.session_state:
    st.session_state.study_label = ""
if "last_xp_event" not in st.session_state:
    st.session_state.last_xp_event = None

now_utc = datetime.datetime.now(datetime.timezone.utc)
answer_streak = int(user_prog["answer_streak"])
b10_start = user_prog.get("bonus_10_start")
b20_start = user_prog.get("bonus_20_start")

# ==============================================================================
# ANSICHT 1: FOKUS-LERNMODUS (WENN EINE SITZUNG LÄUFT -> NUR DIE FRAGE OBEN)
# ==============================================================================
if st.session_state.study_queue:
    aktuelle_karte = st.session_state.study_queue[0]
    rest = len(st.session_state.study_queue)
    erledigt = st.session_state.study_done_count
    gesamt_sitzung = max(1, erledigt + rest)
    fortschritt_pct = min(100, round((erledigt / gesamt_sitzung) * 100))

    col_prog, col_exit = st.columns([5.2, 1.1])
    with col_prog:
        st.markdown(
            f'<div class="focus-progress-wrap">'
            f'<div class="focus-progress-meta">'
            f'<span>Fortschritt: {erledigt} abgeschlossen · {rest} verbleibend</span>'
            f'<span>Level {aktuelles_level} · Serie {answer_streak}</span>'
            f'</div>'
            f'<div class="progress-track" style="margin:0;">'
            f'<div class="progress-fill-ice" style="width:{fortschritt_pct}%;"></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_exit:
        if st.button("✕ Beenden", key="exit_study_mode", use_container_width=True):
            st.session_state.study_queue = []
            st.session_state.study_show_answer = False
            st.rerun()

    if st.session_state.last_xp_event:
        st.markdown(f'<div class="xp-banner">{html.escape(st.session_state.last_xp_event)}</div>', unsafe_allow_html=True)

    war_neu = (int(aktuelle_karte.get("success_count", 0)) == 0)
    sim_streak = answer_streak + 1
    aktueller_streak_bonus = 0
    if sim_streak >= 10:
        if b10_start is None or (now_utc - b10_start).total_seconds() < 1800:
            aktueller_streak_bonus = 1
    if sim_streak >= 20:
        if b20_start is None or (now_utc - b20_start).total_seconds() < 1800:
            aktueller_streak_bonus = 2

    moegliche_xp = (2 if war_neu else 1) + aktueller_streak_bonus

    anzeige_typ = "Problemstellung" if aktuelle_karte["card_type"] == "Transfer" else aktuelle_karte["card_type"]
    folder_esc = html.escape(str(aktuelle_karte["folder_name"]))
    typ_esc = html.escape(str(anzeige_typ))

    badges_html = (
        f'<span class="flashcard-badge">{folder_esc} · {typ_esc}</span>'
        f'<span class="flashcard-badge-xp">+{moegliche_xp} XP bei Erfolg</span>'
    )
    if aktuelle_karte.get("lapses", 0) > 0:
        badges_html += f'<span class="flashcard-badge-warn">Wiederholung ({aktuelle_karte["lapses"]}× falsch)</span>'

    ist_lueckentext = (anzeige_typ == "Lückentext")
    frage_html = formatiere_kartentext_html(aktuelle_karte["question"], ist_lueckentext=ist_lueckentext)

    st.markdown(
        f'<div class="flashcard-box">'
        f'<div class="flashcard-meta">{badges_html}</div>'
        f'<div class="flashcard-question">{frage_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    mc_options = []
    if aktuelle_karte["card_type"] == "Multiple Choice":
        try:
            mc_options = json.loads(aktuelle_karte.get("options_json") or "[]")
        except Exception:
            mc_options = []

    gewaehlte_mc = None
    if mc_options:
        gewaehlte_mc = st.radio(
            "Wähle eine der 4 Antwortoptionen:",
            mc_options,
            key=f"mc_radio_{aktuelle_karte['id']}_{erledigt}"
        )

    if not st.session_state.study_show_answer:
        if st.button("Antwort aufdecken", use_container_width=True):
            st.session_state.study_show_answer = True
            st.rerun()
    else:
        if mc_options and gewaehlte_mc is not None:
            if gewaehlte_mc.strip().lower() == aktuelle_karte["answer"].strip().lower():
                st.success("Richtig ausgewählt!")
            else:
                st.error(f"Deine Auswahl: **{gewaehlte_mc}** — das war leider nicht richtig.")

        antwort_html = formatiere_kartentext_html(aktuelle_karte["answer"], ist_lueckentext=False)
        erklaerung = str(aktuelle_karte.get("explanation") or "").strip()
        erklaerung_block = (
            f'<div class="flashcard-explanation">💡 {formatiere_kartentext_html(erklaerung)}</div>'
            if erklaerung else ""
        )

        st.markdown(
            f'<div class="flashcard-box" style="border-color:#7DD3FC;">'
            f'<div class="flashcard-answer-label">Lösung</div>'
            f'<div class="flashcard-answer-body">{antwort_html}</div>'
            f'{erklaerung_block}'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.caption("Wie gut konntest du die Aufgabe lösen?")
        b1, b2, b3, b4 = st.columns(4)

        p1 = formatiere_intervall_vorschau(aktuelle_karte["ease_factor"], aktuelle_karte["interval_days"], aktuelle_karte["repetitions"], aktuelle_karte["lapses"], 1)
        p2 = formatiere_intervall_vorschau(aktuelle_karte["ease_factor"], aktuelle_karte["interval_days"], aktuelle_karte["repetitions"], aktuelle_karte["lapses"], 2)
        p3 = formatiere_intervall_vorschau(aktuelle_karte["ease_factor"], aktuelle_karte["interval_days"], aktuelle_karte["repetitions"], aktuelle_karte["lapses"], 3)
        p4 = formatiere_intervall_vorschau(aktuelle_karte["ease_factor"], aktuelle_karte["interval_days"], aktuelle_karte["repetitions"], aktuelle_karte["lapses"], 4)

        gewaehlte_bewertung = None
        if b1.button(f"❌ Nochmal\n({p1})", use_container_width=True):
            gewaehlte_bewertung = 1
        if b2.button(f"🟠 Schwer\n({p2})", use_container_width=True):
            gewaehlte_bewertung = 2
        if b3.button(f"🔵 Gut\n({p3})", use_container_width=True):
            gewaehlte_bewertung = 3
        if b4.button(f"🟢 Leicht\n({p4})", use_container_width=True):
            gewaehlte_bewertung = 4

        if gewaehlte_bewertung is not None:
            ef, iv, reps, lapses, next_rev = berechne_sm2(
                aktuelle_karte["ease_factor"],
                aktuelle_karte["interval_days"],
                aktuelle_karte["repetitions"],
                aktuelle_karte["lapses"],
                gewaehlte_bewertung,
            )

            erfolgreich = (gewaehlte_bewertung in (2, 3, 4))
            alter_success_count = int(aktuelle_karte.get("success_count", 0))
            war_erste_loesung = (erfolgreich and alter_success_count == 0)
            neuer_success_count = alter_success_count + (1 if erfolgreich else 0)

            fertige_karte = st.session_state.study_queue.pop(0)

            st.session_state.last_xp_event = verarbeite_bewertung_sofort(
                aktuelle_karte=fertige_karte,
                ef=ef,
                iv=iv,
                reps=reps,
                lapses=lapses,
                next_rev=next_rev,
                neuer_success_count=neuer_success_count,
                erfolgreich=erfolgreich,
                war_erste_loesung=war_erste_loesung,
            )

            if gewaehlte_bewertung == 1:
                einfuege_pos = min(2, len(st.session_state.study_queue))
                st.session_state.study_queue.insert(einfuege_pos, fertige_karte)
            else:
                st.session_state.study_done_count += 1

            st.session_state.study_show_answer = False
            st.rerun()

# ==============================================================================
# ANSICHT 2: GESAMTÜBERSICHT & VERWALTUNG (WENN GERADE NICHT GELERNT WIRD)
# ==============================================================================
else:
    col_brand, col_cursor_btn = st.columns([4.5, 1.5])
    with col_brand:
        st.markdown(
            '<div class="omni-header" style="border-bottom:none;margin-bottom:0;padding-bottom:0;"><div><div class="omni-brand">OmniLearn</div><div class="omni-tagline">Active Recall & Spaced Repetition</div></div></div>',
            unsafe_allow_html=True,
        )

    with col_cursor_btn:
        st.markdown('<div style="height:0.35rem;"></div>', unsafe_allow_html=True)
        with st.popover(f"🖱️ Maus: {aktiver_cursor['short']}", use_container_width=True):
            st.markdown("**Freigeschaltete Maus-Symbole**")
            st.caption("Alle 5 Level schaltest du ein neues Symbol für deinen Mauszeiger frei.")
            for item in CURSOR_MILESTONES:
                freigeschaltet = aktuelles_level >= item["level"]
                if item["svg"]:
                    uri = svg_zu_data_uri(item["svg"])
                    icon_html = f'<img src="{uri}" width="20" height="20" style="vertical-align:middle;margin-right:6px;"/>'
                else:
                    icon_html = "↖️ "

                status = "Freigeschaltet" if freigeschaltet else f"Ab Level {item['level']}"
                label_row = f'{icon_html}<b>{item["name"]}</b> — <span style="color:#94A3B8;font-size:0.82rem;">{status}</span>'
                st.markdown(label_row, unsafe_allow_html=True)

                if freigeschaltet:
                    ist_aktiv = (aktiver_cursor["level"] == item["level"])
                    btn_txt = "✓ Aktiv" if ist_aktiv else "Auswählen"
                    if st.button(btn_txt, key=f"cur_sel_{item['level']}", disabled=ist_aktiv, use_container_width=True):
                        setze_ausgewaehlten_cursor(item["level"])
                        st.rerun()

    st.markdown('<hr style="margin-top:0.6rem;margin-bottom:1.1rem;">', unsafe_allow_html=True)

    # --- Level- & Tagesquest-Karten ---
    xp_im_lvl = int(user_prog["xp_in_level"])
    xp_ziel_lvl = xp_fuer_naechstes_level(aktuelles_level)
    lvl_prozent = min(100, round((xp_im_lvl / max(1, xp_ziel_lvl)) * 100))

    bonus_val = 0
    time_left = 0

    if b20_start and (now_utc - b20_start).total_seconds() < 1800:
        bonus_val = 2
        time_left = int(30 - (now_utc - b20_start).total_seconds() // 60)
    elif b10_start and (now_utc - b10_start).total_seconds() < 1800:
        bonus_val = 1
        time_left = int(30 - (now_utc - b10_start).total_seconds() // 60)

    if bonus_val == 2:
        streak_html = f'<span class="streak-chip-hot">⚡ {answer_streak}er-Serie (+2 XP / {time_left} Min)</span>'
    elif bonus_val == 1:
        streak_html = f'<span class="streak-chip-hot">⚡ {answer_streak}er-Serie (+1 XP / {time_left} Min)</span>'
    else:
        b10_used = b10_start is not None and (now_utc - b10_start).total_seconds() >= 1800
        b20_used = b20_start is not None and (now_utc - b20_start).total_seconds() >= 1800
        if answer_streak >= 20 and b20_used:
            streak_html = f'<span class="streak-chip">Serie: {answer_streak} (Tages-Boosts verbraucht)</span>'
        elif answer_streak >= 10 and b10_used and not b20_start:
            streak_html = f'<span class="streak-chip">Serie: {answer_streak} (Boost 2 ab Serie 20)</span>'
        else:
            streak_html = f'<span class="streak-chip">Serie: {answer_streak} richtig in Folge</span>'

    naechster_cursor = next((c for c in CURSOR_MILESTONES if c["level"] > aktuelles_level), None)
    cursor_vorschau_txt = (
        f"Nächstes Maus-Symbol ab Lv. {naechster_cursor['level']}: {naechster_cursor['name']}"
        if naechster_cursor else "Alle Maus-Symbole freigeschaltet"
    )

    daily_done = int(user_prog["daily_cards_done"])
    daily_pct = min(100, round((daily_done / DAILY_GOAL_TARGET) * 100))
    daily_claimed = bool(user_prog["daily_quest_claimed"])
    quest_streak = int(user_prog["daily_quest_streak"])
    tage_im_zyklus = quest_streak % 7 if (quest_streak % 7 != 0 or quest_streak == 0) else 7

    dots_html = "".join(
        f'<span class="day-dot {"day-dot-active" if i < tage_im_zyklus else ""}"></span>'
        for i in range(7)
    )
    quest_status_txt = (
        f"Tagesziel erfüllt (+{DAILY_GOAL_BONUS_XP} XP erhalten)"
        if daily_claimed else f"Noch {max(0, DAILY_GOAL_TARGET - daily_done)} Karten bis +{DAILY_GOAL_BONUS_XP} XP"
    )

    col_lvl, col_quest = st.columns(2)
    with col_lvl:
        st.markdown(
            f'<div class="sculpt-panel">'
            f'<div class="panel-top-row"><span class="level-pill">Level {aktuelles_level}</span><span class="xp-meta">{xp_im_lvl} / {xp_ziel_lvl} XP</span></div>'
            f'<div class="progress-track"><div class="progress-fill-ice" style="width:{lvl_prozent}%;"></div></div>'
            f'<div class="panel-footer-row">{streak_html}<span>{cursor_vorschau_txt}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_quest:
        st.markdown(
            f'<div class="sculpt-panel">'
            f'<div class="panel-top-row"><span style="font-weight:700;color:#F8FAFC;font-size:0.98rem;">Tagesziel: {min(daily_done, DAILY_GOAL_TARGET)} / {DAILY_GOAL_TARGET} Karten</span><span class="xp-meta">{quest_status_txt}</span></div>'
            f'<div class="progress-track"><div class="progress-fill-quest" style="width:{daily_pct}%;"></div></div>'
            f'<div class="panel-footer-row"><span>7-Tage-Quest (Volles Level-Up): <b>{quest_streak}</b> Tage</span><span class="day-dots">{dots_html}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:0.95rem;"></div>', unsafe_allow_html=True)

    # --- Status-Kacheln ---
    ordner_liste = hole_ordner_schnell()
    gesamt_karten = sum(o["total_cards"] for o in ordner_liste)
    gesamt_faellig = sum(o["due_cards"] for o in ordner_liste)
    gesamt_schwach = sum(o["kritisch_cards"] for o in ordner_liste)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_faellig}</div><div class="stat-label">Heute fällig</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_schwach}</div><div class="stat-label">Kritisch / Öfter falsch</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_karten}</div><div class="stat-label">Karten gesamt</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><div class="stat-num">{len(ordner_liste)}</div><div class="stat-label">Themen-Ordner</div></div>', unsafe_allow_html=True)

    # --- Themen-Fortschritt ---
    if ordner_liste:
        st.markdown('<div style="height:1.1rem;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">Themen-Fortschritt (Anki-Status)</div>', unsafe_allow_html=True)
        for idx in range(0, len(ordner_liste), 2):
            t_cols = st.columns(2)
            with t_cols[0]:
                st.markdown(baue_themen_fortschritt_html(ordner_liste[idx]), unsafe_allow_html=True)
            if idx + 1 < len(ordner_liste):
                with t_cols[1]:
                    st.markdown(baue_themen_fortschritt_html(ordner_liste[idx + 1]), unsafe_allow_html=True)

    st.markdown('<div style="height:1.05rem;"></div>', unsafe_allow_html=True)

    tab_lernen, tab_upload, tab_ordner = st.tabs([
        "🎯 Lernen (Spaced Repetition)",
        "📄 Dokumente & Kartengenerator",
        "📁 Ordner & Kartenverwaltung"
    ])

    # ==========================================================================
    # TAB 1: LERNEN STARTEN
    # ==========================================================================
    with tab_lernen:
        if st.session_state.study_initial_total > 0 and st.session_state.study_done_count > 0:
            st.success(f"Stark! Alle {st.session_state.study_done_count} Karten der letzten Sitzung abgeschlossen.")
            if st.session_state.last_xp_event:
                st.markdown(f'<div class="xp-banner">{html.escape(st.session_state.last_xp_event)}</div>', unsafe_allow_html=True)

        col_f, col_m, col_btn = st.columns([2.2, 2.2, 1.4])
        ordner_optionen = {"Alle Ordner": None}
        for o in ordner_liste:
            ordner_optionen[f"{o['name']} ({o['due_cards']} fällig)"] = o["id"]

        gewaehlter_ordner_label = col_f.selectbox("Lernbereich wählen", list(ordner_optionen.keys()))
        gewaehlter_ordner_id = ordner_optionen[gewaehlter_ordner_label]

        modus_optionen = {
            "Fällige Karten (Spaced Repetition)": "due",
            "Nur bisher falsche Karten (Fehler-Training)": "weak",
            "Alle Karten im Stapel durchgehen": "all"
        }
        gewaehlter_modus_label = col_m.selectbox("Lernmodus", list(modus_optionen.keys()))
        gewaehlter_modus = modus_optionen[gewaehlter_modus_label]

        with col_btn:
            st.markdown('<div style="height:1.72rem;"></div>', unsafe_allow_html=True)
            if st.button("▶ Sitzung starten", use_container_width=True):
                hole_ordner_schnell(force_refresh=True)
                karten = lade_lernkarten(folder_id=gewaehlter_ordner_id, modus=gewaehlter_modus)
                st.session_state.study_queue = list(karten)
                st.session_state.study_show_answer = False
                st.session_state.study_done_count = 0
                st.session_state.study_initial_total = len(karten)
                st.session_state.study_label = f"{gewaehlter_ordner_label} · {gewaehlter_modus_label}"
                st.session_state.last_xp_event = None
                if not karten:
                    st.warning("Für diese Auswahl sind aktuell keine Karten fällig.")
                else:
                    st.rerun()

        if gesamt_karten == 0:
            st.info("Du hast noch keine Karteikarten erstellt. Lege unter **Dokumente & Kartengenerator** deinen ersten Ordner an und lade ein Skript hoch.")

    # ==========================================================================
    # TAB 2: DOKUMENTE HOCHLADEN & KARTEIKARTEN GENERIEREN
    # ==========================================================================
    with tab_upload:
        st.markdown('<div class="ar-subtitle">1. Zielordner auswählen oder neu anlegen</div>', unsafe_allow_html=True)

        col_new1, col_new2 = st.columns([3.5, 1])
        neuer_ordner_name = col_new1.text_input("Neuen Ordner anlegen", label_visibility="collapsed", placeholder="Neuen Ordnernamen eingeben (z. B. Makroökonomie, BGB AT)...")
        if col_new2.button("➕ Ordner erstellen", use_container_width=True):
            if neuer_ordner_name.strip():
                if erstelle_ordner(neuer_ordner_name):
                    st.success(f"Ordner **{neuer_ordner_name.strip()}** erstellt!")
                    st.rerun()
                else:
                    st.warning("Dieser Ordner existiert bereits.")
            else:
                st.warning("Bitte gib einen Ordnernamen ein.")

        ordner_liste = hole_ordner_schnell()
        if not ordner_liste:
            st.warning("Bitte lege zuerst oben einen Ordner an, in dem deine Dokumente und Karten gespeichert werden.")
        else:
            ziel_ordner_map = {o["name"]: o["id"] for o in ordner_liste}
            ziel_ordner_name = st.selectbox("Zielordner für deine Dokumente", list(ziel_ordner_map.keys()))
            ziel_ordner_id = ziel_ordner_map[ziel_ordner_name]

            st.markdown('<div class="ar-subtitle">2. Dokumente hochladen & abwechslungsreiche Lernkarten erstellen</div>', unsafe_allow_html=True)
            uploaded_files = st.file_uploader(
                "Dokumente auswählen (PDF, DOCX, TXT, MD – auch mehrere gleichzeitig)",
                type=["pdf", "docx", "txt", "md"],
                accept_multiple_files=True
            )

            col_opt1, col_opt2 = st.columns([1, 2])
            karten_pro_dok = col_opt1.slider("Karten pro Dokument", min_value=4, max_value=24, value=8)
            gewaehlte_typen = col_opt2.multiselect(
                "Aufgaben-Mix (werden abwechselnd generiert)",
                ["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"],
                default=["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"]
            )

            if st.button("⚡ Abwechslungsreiche Lernkarten generieren", use_container_width=True):
                if not uploaded_files:
                    st.warning("Bitte lade zuerst mindestens eine Datei hoch.")
                elif not gewaehlte_typen:
                    st.warning("Bitte wähle mindestens einen Aufgabentyp aus.")
                else:
                    gesamt_erstellt = 0
                    for datei in uploaded_files:
                        with st.spinner(f"Lese '{datei.name}' aus und erstelle Lückentexte, Problemstellungen & Multiple-Choice-Fragen..."):
                            try:
                                text = extrahiere_text_aus_datei(datei)
                                if len(text) < 40:
                                    st.warning(f"In '{datei.name}' konnte kaum Text gefunden werden (evtl. reiner Bild-Scan).")
                                    continue
                                neue_karten = generiere_karteikarten(text, karten_pro_dok, gewaehlte_typen)
                                speichere_dokument_und_karten(ziel_ordner_id, datei.name, len(text), neue_karten, content_text=text)
                                gesamt_erstellt += len(neue_karten)
                            except Exception as e:
                                st.error(f"Fehler bei '{datei.name}': {e}")

                    if gesamt_erstellt > 0:
                        st.success(f"{gesamt_erstellt} abwechslungsreiche Lernkarten wurden im Ordner **{ziel_ordner_name}** gespeichert!")
                        st.rerun()

    # ==========================================================================
    # TAB 3: ORDNER- & KARTENVERWALTUNG
    # ==========================================================================
    with tab_ordner:
        if not ordner_liste:
            st.info("Noch keine Ordner vorhanden.")
        else:
            verw_ordner_map = {f"{o['name']} ({o['total_cards']} Karten · {o['doc_count']} Dokumente)": o for o in ordner_liste}
            auswahl_label = st.selectbox("Ordner inspizieren", list(verw_ordner_map.keys()))
            akt_ordner = verw_ordner_map[auswahl_label]

            st.markdown(baue_themen_fortschritt_html(akt_ordner), unsafe_allow_html=True)

            st.markdown('<div class="ar-subtitle">Hinterlegte Dokumente in diesem Ordner</div>', unsafe_allow_html=True)
            doks = lade_dokumente_fuer_ordner(akt_ordner["id"])
            if doks:
                for d in doks:
                    datum_str = d["uploaded_at"].astimezone(BERLIN_TZ).strftime("%d.%m.%Y %H:%M")
                    col_doc1, col_doc2 = st.columns([3.5, 1.5])
                    with col_doc1:
                        st.markdown(f"- **{d['filename']}** ({d['card_count']} Karten · hochgeladen am {datum_str})")
                    with col_doc2:
                        if d.get("content_text") and len(d["content_text"]) >= 40:
                            if st.button("➕ 8 neue Mix-Karten", key=f"regen_doc_{d['id']}", use_container_width=True):
                                with st.spinner("Generiere neuen Aufgaben-Mix..."):
                                    neue = generiere_karteikarten(
                                        d["content_text"],
                                        8,
                                        ["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"]
                                    )
                                    fuege_karten_zu_dokument_hinzu(akt_ordner["id"], d["id"], neue)
                                    st.rerun()
            else:
                st.caption("In diesem Ordner wurden noch keine Dokumente hochgeladen.")

            st.markdown("---")

            st.markdown('<div class="ar-subtitle">Enthaltene Karteikarten & Spaced-Repetition-Status</div>', unsafe_allow_html=True)
            status_filter = st.radio(
                "Nach Anki-Status filtern:",
                [
                    "Alle Karten",
                    "🔵 Gut gelernt",
                    "🟡 Wackelig",
                    "🔴 Kritisch / Öfter falsch",
                    "⚫ Ungelernt",
                ],
                horizontal=True,
            )

            filter_map = {
                "🔵 Gut gelernt": "gut",
                "🟡 Wackelig": "wackelig",
                "🔴 Kritisch / Öfter falsch": "kritisch",
                "⚫ Ungelernt": "neu",
            }
            badge_map = {
                "gut": "🔵 Gut gelernt",
                "wackelig": "🟡 Wackelig",
                "kritisch": "🔴 Kritisch",
                "neu": "⚫ Ungelernt",
            }

            alle_karten_ordner = lade_lernkarten(folder_id=akt_ordner["id"], modus="all")
            if alle_karten_ordner:
                jetzt_utc = datetime.datetime.now(datetime.timezone.utc)
                gefilterte_karten = [
                    k for k in alle_karten_ordner
                    if status_filter == "Alle Karten" or klassifiziere_karte_anki(k) == filter_map[status_filter]
                ]
                if not gefilterte_karten:
                    st.caption("Keine Karten in dieser Kategorie vorhanden.")
                for k in gefilterte_karten:
                    anki_kat = klassifiziere_karte_anki(k)
                    faellig = k["next_review"] <= jetzt_utc
                    status_txt = "Jetzt fällig" if faellig else f"Fällig am {k['next_review'].astimezone(BERLIN_TZ).strftime('%d.%m.%Y')}"
                    fehler_txt = f" · {k['lapses']}× falsch" if k["lapses"] > 0 else ""
                    typ_label = "Problemstellung" if k["card_type"] == "Transfer" else k["card_type"]
                    with st.expander(f"{badge_map[anki_kat]} · [{typ_label}] {k['question'][:80]} ({status_txt}{fehler_txt})"):
                        st.markdown(f"**Frage:** {k['question']}")
                        if typ_label == "Multiple Choice" and k.get("options_json"):
                            try:
                                opts_prev = json.loads(k["options_json"])
                                if opts_prev:
                                    st.markdown("**Optionen:** " + " · ".join(opts_prev))
                            except Exception:
                                pass
                        st.markdown(f"**Antwort:** {k['answer']}")
                        if k.get("explanation"):
                            st.caption(f"Erklärung: {k['explanation']}")
                        st.caption(f"Intervall: {k['interval_days']} Tage · Wiederholungen: {k['repetitions']} · Leichtigkeit: {k['ease_factor']:.2f}")
                        if st.button("Karte löschen", key=f"del_card_{k['id']}"):
                            loesche_karte(k["id"])
                            st.rerun()
            else:
                st.caption("Noch keine Karteikarten in diesem Ordner.")

            st.markdown("---")
            with st.expander("Gefahrenzone: Gesamten Ordner löschen"):
                st.warning(f"Dadurch werden der Ordner **{akt_ordner['name']}** sowie alle darin enthaltenen Dokumente und Karteikarten unwiderruflich gelöscht.")
                if st.button(f"Ordner '{akt_ordner['name']}' endgültig löschen", key=f"del_folder_{akt_ordner['id']}"):
                    loesche_ordner(akt_ordner["id"])
                    st.rerun()
