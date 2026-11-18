import os
import io
import json
import time
import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

# --- Seiten-Konfiguration ---
st.set_page_config(page_title="Recall – Active Recall & Spaced Repetition", layout="centered")

# --- Design & CSS: Tiefschwarz mit Ice-Blue Akzenten ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #07090E;
        color: #F1F5F9;
    }

    [data-testid="stSidebar"] {
        background-color: #0B0F17;
        border-right: 1px solid rgba(125, 211, 252, 0.28);
    }

    hr {
        border: none !important;
        border-top: 1px solid rgba(125, 211, 252, 0.35) !important;
        margin: 1rem 0 !important;
    }

    .ar-title {
        font-size: 1.85rem;
        font-weight: 700;
        color: #F8FAFC;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
        border-bottom: 1.5px solid #7DD3FC;
        letter-spacing: 0.02em;
    }

    .ar-subtitle {
        font-size: 1.2rem;
        font-weight: 600;
        color: #E0F2FE;
        margin-top: 0.5rem;
        margin-bottom: 0.6rem;
    }

    /* Karteikarten-Box */
    .flashcard-box {
        background: linear-gradient(145deg, #0E1525 0%, #0A0F1C 100%);
        border: 1.5px solid rgba(125, 211, 252, 0.55);
        border-radius: 14px;
        padding: 1.5rem 1.4rem;
        margin: 0.8rem 0 1rem 0;
        box-shadow: 0 8px 24px rgba(2, 132, 199, 0.12);
    }

    .flashcard-badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #07090E;
        background-color: #7DD3FC;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        margin-bottom: 0.85rem;
    }

    .flashcard-badge-warn {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: #07090E;
        background-color: #FACC15;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        margin-left: 0.4rem;
        margin-bottom: 0.85rem;
    }

    .flashcard-question {
        font-size: 1.22rem;
        font-weight: 600;
        color: #F8FAFC;
        line-height: 1.55;
    }

    .stat-card {
        background-color: #0E131F;
        border: 1px solid rgba(125, 211, 252, 0.25);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        text-align: center;
    }

    .stat-num {
        font-size: 1.55rem;
        font-weight: 700;
        color: #7DD3FC;
    }

    .stat-label {
        font-size: 0.8rem;
        color: #94A3B8;
        margin-top: 0.15rem;
    }

    .stButton > button {
        border: 1px solid rgba(125, 211, 252, 0.45) !important;
        background-color: #0E1525 !important;
        color: #E0F2FE !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        border-color: #7DD3FC !important;
        background-color: #152238 !important;
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
        st.markdown('<div class="ar-title">Zugang geschützt</div>', unsafe_allow_html=True)
        eingabe = st.text_input("Bitte Passwort eingeben:", type="password")
        if st.button("Entsperren", use_container_width=True):
            if eingabe == richtiges_passwort:
                st.session_state.eingeloggt = True
                st.rerun()
            else:
                st.error("Falsches Passwort.")
        st.stop()

passwort_pruefen()

# --- Datenbank-Verbindung (Neon PostgreSQL mit Auto-Wakeup Retry) ---
def get_db_url():
    try:
        url = st.secrets["DATABASE_URL"].strip()
    except Exception:
        url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def get_connection():
    db_url = get_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL fehlt in den Streamlit Secrets.")
    last_err = None
    for _ in range(3):
        try:
            return psycopg2.connect(db_url, connect_timeout=15)
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise last_err

@st.cache_resource
def init_db():
    conn = get_connection()
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
                    uploaded_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
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
                    next_review TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        conn.commit()
    finally:
        conn.close()
    return True

try:
    init_db()
except Exception as e:
    st.error(f"Datenbank-Verbindung fehlgeschlagen: {e}")
    st.info("Prüfe in Streamlit unter **Settings → Secrets**, ob `DATABASE_URL` korrekt eingetragen ist.")
    st.stop()

# --- Gemini API Initialisierung (automatische Modellwahl gegen 404/429) ---
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
        0 if "lite" in x.lower() else (1 if "flash" in x.lower() else 2),
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

# --- Text-Extraktion aus PDF, DOCX, TXT, MD ---
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

# --- Active-Recall Kartengenerator ---
def generiere_karteikarten(text_inhalt, anzahl, aufgabentypen):
    gekuerzter_text = text_inhalt[:28000]
    typen_beschreibung = {
        "Klassisch": "Klassische Verständnis- und Definitionsfragen (präzise Frage auf der Vorderseite, strukturierte Kernantwort auf der Rückseite).",
        "Lückentext": "Lückentext (Cloze Deletion): Ein wichtiger fachlicher Merksatz auf der Vorderseite, bei dem 1–2 zentrale Schlüsselbegriffe durch '[...]' ersetzt wurden; auf der Rückseite der vollständige Satz mit den eingesetzten Begriffen.",
        "Multiple Choice": "Multiple Choice: Eine anspruchsvolle Frage auf der Vorderseite sowie genau 4 plausible Antwortmöglichkeiten im Feld 'options' (als Liste von 4 Strings, ohne Buchstaben-Präfix wie A/B/C/D). Im Feld 'answer' steht exakt der Wortlaut der einen richtigen Option.",
        "Transfer": "Transfer- & Anwendungsfrage: Ein konkretes Fallbeispiel oder eine 'Was passiert, wenn...'-Problemstellung auf der Vorderseite und die fachlich begründete Lösung auf der Rückseite."
    }
    gewaehlte_beschreibungen = "\n".join(
        f"- {t}: {typen_beschreibung[t]}" for t in aufgabentypen if t in typen_beschreibung
    )

    prompt = (
        f"Du bist ein Experte für evidenzbasiertes Lernen (Active Recall & Spaced Repetition).\n"
        f"Erstelle auf Basis des folgenden Lernmaterials genau {anzahl} hochwertige, prüfungsrelevante Karteikarten.\n"
        f"Verteile die Karten möglichst gleichmäßig auf diese Aufgabentypen:\n{gewaehlte_beschreibungen}\n\n"
        "Wichtige Regeln:\n"
        "1. Keine trivialen Ja/Nein-Fragen; jede Karte soll aktives Abrufen fördern.\n"
        "2. Formuliere klar, präzise und auf Deutsch (oder in der Sprache des Dokuments, falls Fachbegriffe/Englisch).\n"
        "3. Antworte AUSSCHLIESSLICH mit einem gültigen JSON-Array (ohne Markdown-Codeblock ```json).\n"
        "Jedes Objekt im Array muss exakt diese Felder besitzen:\n"
        '{"card_type": "Klassisch|Lückentext|Multiple Choice|Transfer", '
        '"question": "Vorderseite der Karte", '
        '"options": ["Option 1", "Option 2", "Option 3", "Option 4"], '
        '"answer": "Richtige Antwort", '
        '"explanation": "Kurze Eselsbrücke, Kontext oder Begründung (1–2 Sätze)"}\n'
        "Hinweis: Bei allen Typen außer 'Multiple Choice' muss 'options' eine leere Liste [] sein.\n\n"
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
    for k in karten:
        if not k.get("question") or not k.get("answer"):
            continue
        ctype = k.get("card_type", "Klassisch")
        if ctype not in ("Klassisch", "Lückentext", "Multiple Choice", "Transfer"):
            ctype = "Klassisch"
        opts = k.get("options") if ctype == "Multiple Choice" else []
        if not isinstance(opts, list):
            opts = []
        bereinigt.append({
            "card_type": ctype,
            "question": str(k["question"]).strip(),
            "options": [str(o).strip() for o in opts],
            "answer": str(k["answer"]).strip(),
            "explanation": str(k.get("explanation", "")).strip(),
        })
    return bereinigt

# --- Spaced Repetition Algorithmus (Anki SM-2 Logik) ---
def berechne_sm2(ease_factor, interval_days, repetitions, lapses, bewertung):
    ef = float(ease_factor)
    interval = int(interval_days)
    reps = int(repetitions)
    lapses = int(lapses)

    if bewertung == 1:
        # Falsch beantwortet -> Zurücksetzen & in derselben Sitzung erneut abfragen
        reps = 0
        interval = 0
        lapses += 1
        ef = max(1.3, ef - 0.20)
        next_delta = datetime.timedelta(minutes=1)
    elif bewertung == 2:
        # Schwer
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
        # Gut (klassisches SM-2)
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(interval + 1, round(interval * ef))
        reps += 1
        next_delta = datetime.timedelta(days=interval)
    else:
        # Leicht
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

# --- Datenbank-Hilfsfunktionen ---
def lade_ordner():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    f.id,
                    f.name,
                    COUNT(DISTINCT d.id) AS doc_count,
                    COUNT(DISTINCT c.id) AS total_cards,
                    COUNT(DISTINCT CASE WHEN c.next_review <= NOW() THEN c.id END) AS due_cards,
                    COUNT(DISTINCT CASE WHEN c.lapses > 0 THEN c.id END) AS weak_cards
                FROM folders f
                LEFT JOIN documents d ON d.folder_id = f.id
                LEFT JOIN cards c ON c.folder_id = f.id
                GROUP BY f.id, f.name
                ORDER BY f.name ASC;
            """)
            return cur.fetchall()
    finally:
        conn.close()

def erstelle_ordner(name):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO folders (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id;",
                (name.strip(),)
            )
            res = cur.fetchone()
        conn.commit()
        return res is not None
    finally:
        conn.close()

def loesche_ordner(folder_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM folders WHERE id = %s;", (folder_id,))
        conn.commit()
    finally:
        conn.close()

def lade_dokumente_fuer_ordner(folder_id):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.filename, d.char_count, d.uploaded_at, COUNT(c.id) AS card_count
                FROM documents d
                LEFT JOIN cards c ON c.document_id = d.id
                WHERE d.folder_id = %s
                GROUP BY d.id
                ORDER BY d.uploaded_at DESC;
            """, (folder_id,))
            return cur.fetchall()
    finally:
        conn.close()

def speichere_dokument_und_karten(folder_id, filename, char_count, karten_liste):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (folder_id, filename, char_count) VALUES (%s, %s, %s) RETURNING id;",
                (folder_id, filename, char_count)
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
    finally:
        conn.close()

def lade_lernkarten(folder_id=None, modus="due"):
    conn = get_connection()
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
            return cur.fetchall()
    finally:
        conn.close()

def aktualisiere_karte_sm2(card_id, ef, interval, reps, lapses, next_review):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cards
                SET ease_factor = %s,
                    interval_days = %s,
                    repetitions = %s,
                    lapses = %s,
                    next_review = %s
                WHERE id = %s;
                """,
                (ef, interval, reps, lapses, next_review, card_id)
            )
        conn.commit()
    finally:
        conn.close()

def loesche_karte(card_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cards WHERE id = %s;", (card_id,))
        conn.commit()
    finally:
        conn.close()

# --- Session State für aktive Lernsitzung ---
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

# --- Hauptüberschrift & Status-Übersicht ---
st.markdown('<div class="ar-title">Active Recall & Spaced Repetition</div>', unsafe_allow_html=True)

ordner_liste = lade_ordner()
gesamt_karten = sum(o["total_cards"] for o in ordner_liste)
gesamt_faellig = sum(o["due_cards"] for o in ordner_liste)
gesamt_schwach = sum(o["weak_cards"] for o in ordner_liste)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_faellig}</div><div class="stat-label">Heute fällig</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_schwach}</div><div class="stat-label">Fehler-Stapel</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{gesamt_karten}</div><div class="stat-label">Karten gesamt</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="stat-card"><div class="stat-num">{len(ordner_liste)}</div><div class="stat-label">Ordner</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

tab_lernen, tab_upload, tab_ordner = st.tabs([
    "🎯 Lernen (Spaced Repetition)",
    "📄 Dokumente & Kartengenerator",
    "📁 Ordner & Kartenverwaltung"
])

# ==============================================================================
# TAB 1: LERNEN (SPACED REPETITION)
# ==============================================================================
with tab_lernen:
    col_f, col_m = st.columns([2, 2])
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

    if st.button("▶ Lernsitzung starten / neu laden", use_container_width=True):
        karten = lade_lernkarten(folder_id=gewaehlter_ordner_id, modus=gewaehlter_modus)
        st.session_state.study_queue = list(karten)
        st.session_state.study_show_answer = False
        st.session_state.study_done_count = 0
        st.session_state.study_initial_total = len(karten)
        st.session_state.study_label = f"{gewaehlter_ordner_label} · {gewaehlter_modus_label}"
        st.rerun()

    st.markdown("---")

    if st.session_state.study_queue:
        aktuelle_karte = st.session_state.study_queue[0]
        rest = len(st.session_state.study_queue)
        erledigt = st.session_state.study_done_count
        gesamt_sitzung = max(1, erledigt + rest)

        st.progress(erledigt / gesamt_sitzung, text=f"Fortschritt: {erledigt} abgeschlossen · {rest} verbleibend")

        warn_badge = ""
        if aktuelle_karte.get("lapses", 0) > 0:
            warn_badge = f'<span class="flashcard-badge-warn">Wiederholung ({aktuelle_karte["lapses"]}× falsch)</span>'

        frage_html = aktuelle_karte["question"].replace("\n", "<br>")
        st.markdown(
            f"""
            <div class="flashcard-box">
                <span class="flashcard-badge">{aktuelle_karte['folder_name']} · {aktuelle_karte['card_type']}</span>
                {warn_badge}
                <div class="flashcard-question">{frage_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Interaktive Multiple-Choice-Auswahl vor dem Aufdecken
        mc_options = []
        if aktuelle_karte["card_type"] == "Multiple Choice":
            try:
                mc_options = json.loads(aktuelle_karte.get("options_json") or "[]")
            except Exception:
                mc_options = []

        gewaehlte_mc = None
        if mc_options:
            gewaehlte_mc = st.radio(
                "Wähle deine Antwort:",
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

            antwort_html = aktuelle_karte["answer"].replace("\n", "<br>")
            erklaerung = aktuelle_karte.get("explanation", "").strip()
            erklaerung_html = f"<br><br><span style='color:#7DD3FC;font-size:0.95rem;'>💡 {erklaerung}</span>" if erklaerung else ""

            st.markdown(
                f"""
                <div class="flashcard-box" style="border-color:#7DD3FC;">
                    <div style="font-size:0.78rem;color:#7DD3FC;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.4rem;">Lösung</div>
                    <div style="font-size:1.1rem;color:#F8FAFC;line-height:1.6;">{antwort_html}{erklaerung_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption("Wie gut konntest du die Antwort abrufen?")
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
                aktualisiere_karte_sm2(aktuelle_karte["id"], ef, iv, reps, lapses, next_rev)

                fertige_karte = st.session_state.study_queue.pop(0)
                if gewaehlte_bewertung == 1:
                    # Falsch -> Karte bleibt in der aktuellen Sitzung und kommt nach 2 Karten wieder
                    fertige_karte["ease_factor"] = ef
                    fertige_karte["interval_days"] = iv
                    fertige_karte["repetitions"] = reps
                    fertige_karte["lapses"] = lapses
                    einfuege_pos = min(2, len(st.session_state.study_queue))
                    st.session_state.study_queue.insert(einfuege_pos, fertige_karte)
                else:
                    st.session_state.study_done_count += 1

                st.session_state.study_show_answer = False
                st.rerun()

    else:
        if st.session_state.study_initial_total > 0 and st.session_state.study_done_count > 0:
            st.success(f"Stark! Alle {st.session_state.study_done_count} Karten dieser Sitzung abgeschlossen.")
        elif gesamt_karten == 0:
            st.info("Du hast noch keine Karteikarten erstellt. Lege unter **Dokumente & Kartengenerator** deinen ersten Ordner an und lade ein Skript hoch.")
        else:
            st.info("Klicke oben auf **Lernsitzung starten**, um deine fälligen Karten abzurufen.")

# ==============================================================================
# TAB 2: DOKUMENTE HOCHLADEN & KARTEIKARTEN GENERIEREN
# ==============================================================================
with tab_upload:
    st.markdown('<div class="ar-subtitle">1. Zielordner auswählen oder neu anlegen</div>', unsafe_allow_html=True)

    col_new1, col_new2 = st.columns([3, 1])
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

    ordner_liste = lade_ordner()
    if not ordner_liste:
        st.warning("Bitte lege zuerst oben einen Ordner an, in dem deine Dokumente und Karten gespeichert werden.")
    else:
        ziel_ordner_map = {o["name"]: o["id"] for o in ordner_liste}
        ziel_ordner_name = st.selectbox("Zielordner für deine Dokumente", list(ziel_ordner_map.keys()))
        ziel_ordner_id = ziel_ordner_map[ziel_ordner_name]

        st.markdown('<div class="ar-subtitle">2. Dokumente hochladen & Active-Recall-Karten erstellen</div>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Dokumente auswählen (PDF, DOCX, TXT, MD – auch mehrere gleichzeitig)",
            type=["pdf", "docx", "txt", "md"],
            accept_multiple_files=True
        )

        col_opt1, col_opt2 = st.columns([1, 2])
        karten_pro_dok = col_opt1.slider("Karten pro Dokument", min_value=3, max_value=25, value=8)
        gewaehlte_typen = col_opt2.multiselect(
            "Aufgabentypen (Active Recall)",
            ["Klassisch", "Lückentext", "Multiple Choice", "Transfer"],
            default=["Klassisch", "Lückentext", "Multiple Choice", "Transfer"]
        )

        if st.button("⚡ Karteikarten aus Dokumenten generieren", use_container_width=True):
            if not uploaded_files:
                st.warning("Bitte lade zuerst mindestens eine Datei hoch.")
            elif not gewaehlte_typen:
                st.warning("Bitte wähle mindestens einen Aufgabentyp aus.")
            else:
                gesamt_erstellt = 0
                for datei in uploaded_files:
                    with st.spinner(f"Lese '{datei.name}' aus und erstelle Active-Recall-Karten..."):
                        try:
                            text = extrahiere_text_aus_datei(datei)
                            if len(text) < 40:
                                st.warning(f"In '{datei.name}' konnte kaum Text gefunden werden (evtl. reiner Bild-Scan).")
                                continue
                            neue_karten = generiere_karteikarten(text, karten_pro_dok, gewaehlte_typen)
                            speichere_dokument_und_karten(ziel_ordner_id, datei.name, len(text), neue_karten)
                            gesamt_erstellt += len(neue_karten)
                        except Exception as e:
                            st.error(f"Fehler bei '{datei.name}': {e}")

                if gesamt_erstellt > 0:
                    st.success(f"{gesamt_erstellt} Karteikarten wurden erfolgreich im Ordner **{ziel_ordner_name}** gespeichert!")
                    time.sleep(1)
                    st.rerun()

# ==============================================================================
# TAB 3: ORDNER- & KARTENVERWALTUNG
# ==============================================================================
with tab_ordner:
    if not ordner_liste:
        st.info("Noch keine Ordner vorhanden.")
    else:
        verw_ordner_map = {f"{o['name']} ({o['total_cards']} Karten · {o['doc_count']} Dokumente)": o for o in ordner_liste}
        auswahl_label = st.selectbox("Ordner inspizieren", list(verw_ordner_map.keys()))
        akt_ordner = verw_ordner_map[auswahl_label]

        st.markdown('<div class="ar-subtitle">Hinterlegte Dokumente in diesem Ordner</div>', unsafe_allow_html=True)
        doks = lade_dokumente_fuer_ordner(akt_ordner["id"])
        if doks:
            for d in doks:
                datum_str = d["uploaded_at"].astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")
                st.markdown(f"- **{d['filename']}** ({d['card_count']} Karten · hochgeladen am {datum_str})")
        else:
            st.caption("In diesem Ordner wurden noch keine Dokumente hochgeladen.")

        st.markdown("---")

        st.markdown('<div class="ar-subtitle">Enthaltene Karteikarten & Spaced-Repetition-Status</div>', unsafe_allow_html=True)
        alle_karten_ordner = lade_lernkarten(folder_id=akt_ordner["id"], modus="all")
        if alle_karten_ordner:
            jetzt_utc = datetime.datetime.now(datetime.timezone.utc)
            for k in alle_karten_ordner:
                faellig = k["next_review"] <= jetzt_utc
                status_txt = "Jetzt fällig" if faellig else f"Fällig am {k['next_review'].astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y')}"
                fehler_txt = f" · {k['lapses']}× falsch" if k["lapses"] > 0 else ""
                with st.expander(f"[{k['card_type']}] {k['question'][:85]} ({status_txt}{fehler_txt})"):
                    st.markdown(f"**Frage:** {k['question']}")
                    st.markdown(f"**Antwort:** {k['answer']}")
                    if k.get("explanation"):
                        st.caption(f"Erklärung: {k['explanation']}")
                    st.caption(f"Intervall: {k['interval_days']} Tage · Leichtigkeit: {k['ease_factor']:.2f}")
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