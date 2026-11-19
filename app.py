import os, io, re, html, json, time, queue, random, threading, urllib.parse, datetime
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="OmniLearn", layout="wide")
BERLIN_TZ = ZoneInfo("Europe/Berlin")
DAILY_GOAL_TARGET, DAILY_GOAL_BONUS_XP = 30, 25

CURSOR_MILESTONES = [
    {"level": 0, "name": "Standard-Mauszeiger", "short": "Standard", "hx": 4, "hy": 4, "svg": None},
    {"level": 5, "name": "Litschi", "short": "Litschi", "hx": 16, "hy": 16,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><ellipse cx="16" cy="17.5" rx="10.8" ry="11.5" fill="#E11D48" stroke="#07090E" stroke-width="2"/><circle cx="12.5" cy="13.5" r="1.2" fill="#FDA4AF"/><circle cx="19.5" cy="14" r="1.2" fill="#FDA4AF"/><circle cx="15" cy="21" r="1.2" fill="#FDA4AF"/><path d="M16 6 C17 2.5,22 2.5,23 5.5 C20 6.5,18 6.5,16 6 Z" fill="#22C55E" stroke="#07090E" stroke-width="1.2"/></svg>'},
    {"level": 10, "name": "Panzer", "short": "Panzer", "hx": 4, "hy": 14,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><rect x="2.5" y="12.5" width="11.5" height="3.6" rx="1.6" fill="#94A3B8" stroke="#07090E" stroke-width="1.5"/><rect x="11" y="9.5" width="12.5" height="7.2" rx="2.5" fill="#4D7C0F" stroke="#07090E" stroke-width="1.6"/><rect x="6" y="16" width="21.5" height="8.5" rx="4.2" fill="#365314" stroke="#07090E" stroke-width="1.8"/><circle cx="10.5" cy="20.2" r="1.6" fill="#A3E635"/><circle cx="16.8" cy="20.2" r="1.6" fill="#A3E635"/><circle cx="23" cy="20.2" r="1.6" fill="#A3E635"/></svg>'},
    {"level": 15, "name": "Goldbarren", "short": "Goldbarren", "hx": 16, "hy": 16,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><polygon points="8,9.5 24,9.5 29.5,23.5 2.5,23.5" fill="#F59E0B" stroke="#07090E" stroke-width="1.8"/><polygon points="10,11.5 22,11.5 25.5,20.5 6.5,20.5" fill="#FDE047"/></svg>'},
    {"level": 20, "name": "Blauer Schleim", "short": "Blauer Schleim", "hx": 16, "hy": 16,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="M16 3.5 C16 3.5,28 14,28 21.2 C28 26.8,22.6 29.2,16 29.2 C9.4 29.2,4 26.8,4 21.2 C4 14,16 3.5,16 3.5 Z" fill="#0EA5E9" stroke="#07090E" stroke-width="1.8"/><circle cx="12.5" cy="21" r="1.9" fill="#FFF"/><circle cx="19.5" cy="21" r="1.9" fill="#FFF"/><circle cx="12.5" cy="21" r="0.95" fill="#07090E"/><circle cx="19.5" cy="21" r="0.95" fill="#07090E"/></svg>'},
    {"level": 25, "name": "Schneeflocke", "short": "Schneeflocke", "hx": 16, "hy": 16,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><g stroke="#7DD3FC" stroke-width="2.4" stroke-linecap="round"><line x1="16" y1="3" x2="16" y2="29"/><line x1="4.7" y1="9.5" x2="27.3" y2="22.5"/><line x1="27.3" y1="9.5" x2="4.7" y2="22.5"/></g><circle cx="16" cy="16" r="2.6" fill="#E0F2FE"/></svg>'},
    {"level": 30, "name": "Affenkopf", "short": "Affenkopf", "hx": 16, "hy": 16,
     "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><circle cx="6.2" cy="16" r="4.2" fill="#92400E" stroke="#07090E" stroke-width="1.6"/><circle cx="25.8" cy="16" r="4.2" fill="#92400E" stroke="#07090E" stroke-width="1.6"/><circle cx="16" cy="16" r="10.5" fill="#78350F" stroke="#07090E" stroke-width="1.8"/><ellipse cx="16" cy="18.6" rx="7.2" ry="5.5" fill="#FDE68A"/><circle cx="13" cy="13.5" r="1.5" fill="#FFF"/><circle cx="19" cy="13.5" r="1.5" fill="#FFF"/></svg>'},
]

def render_dragon_stage(total_meat: int, dragon_event: str, activity_mode: str, anim_seq: int):
    payload = json.dumps({"meat": int(total_meat), "event": dragon_event, "mode": activity_mode, "seq": int(anim_seq)})
    html_stage = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      *{{box-sizing:border-box;margin:0;padding:0}}
      body{{background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#F8FAFC;overflow:hidden}}
      .shell{{background:linear-gradient(180deg,#0D1525 0%,#070B14 100%);border:1.5px solid rgba(125,211,252,.42);border-radius:18px;padding:11px 15px 13px;box-shadow:0 14px 30px rgba(0,0,0,.52)}}
      .hud{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:9px}}
      .hl,.ctrls{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
      .badge{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;padding:4px 11px;border-radius:999px;background:linear-gradient(135deg,#38BDF8,#7DD3FC);color:#060911}}
      .sub{{font-size:12px;color:#94A3B8;font-weight:600}}
      .meat{{background:#060911;border:1px solid rgba(125,211,252,.3);padding:4px 11px;border-radius:999px;font-size:12px;font-weight:700;color:#FDE68A}}
      .btn{{background:#11192B;border:1px solid rgba(125,211,252,.3);color:#CBD5E1;font-size:11.5px;font-weight:600;padding:4px 9px;border-radius:8px;cursor:pointer}}
      .btn.active{{background:rgba(56,189,248,.22);border-color:#7DD3FC;color:#FFF}}
      canvas{{width:100%;height:218px;display:block;border-radius:12px;border:1px solid rgba(125,211,252,.22);image-rendering:pixelated}}
    </style></head><body><div class="shell"><div class="hud"><div class="hl">
      <span class="badge">🐉 Hoher Drache</span><span class="sub">Ankylosaurus-T-Rex-Hybrid</span>
      <div class="meat">🍖 {int(total_meat)} Fleisch</div></div><div class="ctrls">
      <button class="btn" id="bSleep" onclick="setM('sleep')">💤 Schlafen</button>
      <button class="btn" id="bFly" onclick="setM('fly')">🪽 Fliegen</button>
      <button class="btn" id="bRock" onclick="setM('fight_rock')">🪨 Stein-Kampf</button>
    </div></div><canvas id="c" width="760" height="218"></canvas></div><script>
      const D={payload},cv=document.getElementById("c"),ctx=cv.getContext("2d");ctx.imageSmoothingEnabled=false;
      let mode=D.mode,evT=(D.event==="feed_meat"||D.event==="burn_tree")?2.1:0,SC=4.5;
      function setM(m){{mode=m;["Sleep","Fly","Rock"].forEach(k=>document.getElementById("b"+k).className="btn"+((k==="Sleep"&&m==="sleep")||(k==="Fly"&&m==="fly")||(k==="Rock"&&m==="fight_rock")?" active":""));}}setM(mode);
      const px=(bx,by,ox,oy,w,h,col)=>{{ctx.fillStyle=col;ctx.fillRect(Math.round(bx+ox*SC),Math.round(by+oy*SC),Math.ceil(w*SC),Math.ceil(h*SC));}};
      function bg(t,angry){{
        ctx.fillStyle=angry?"#190B12":"#08101E";ctx.fillRect(0,0,760,218);
        ctx.fillStyle=angry?"#FCA5A5":"#E0F2FE";for(let i=0;i<22;i++)ctx.fillRect((i*37+19)%745,(i*19+11)%88,i%4?2:3,i%4?2:3);
        ctx.fillStyle=angry?"#261018":"#0F1A2E";ctx.beginPath();ctx.moveTo(0,162);ctx.lineTo(130,90);ctx.lineTo(260,152);ctx.lineTo(400,78);ctx.lineTo(550,148);ctx.lineTo(680,88);ctx.lineTo(760,152);ctx.lineTo(760,168);ctx.lineTo(0,168);ctx.fill();
        ctx.fillStyle="#0E172A";ctx.fillRect(0,162,760,56);ctx.fillStyle=angry?"#EF4444":"#38BDF8";ctx.fillRect(0,162,760,2);
      }}
      function boulder(x,y,sx,flash){{
        x+=sx;ctx.fillStyle=flash?"#7DD3FC":"#334155";ctx.fillRect(x,y+18,70,36);
        ctx.fillStyle=flash?"#E0F2FE":"#475569";ctx.fillRect(x+6,y+6,58,42);ctx.fillRect(x+14,y,42,10);
        ctx.fillStyle="#0F172A";ctx.fillRect(x+22,y+15,4,14);ctx.fillRect(x+44,y+19,4,12);
      }}
      function steak(x,y){{ctx.fillStyle="#7F1D1D";ctx.fillRect(x,y,26,16);ctx.fillStyle="#EF4444";ctx.fillRect(x+2,y+2,22,12);ctx.fillStyle="#FEF9C3";ctx.fillRect(x+13,y+6,6,5);}}
      function tree(x,gy,st,t){{
        ctx.fillStyle=st>=2?"#1C1917":"#78350F";ctx.fillRect(x+24,gy-50,18,50);
        if(st===0){{ctx.fillStyle="#166534";ctx.fillRect(x+6,gy-94,54,46);ctx.fillStyle="#22C55E";ctx.fillRect(x+14,gy-88,36,24);}}
        else if(st===1){{const f=Math.sin(t*.7)*5;ctx.fillStyle="#DC2626";ctx.fillRect(x+2,gy-92+f,62,44);ctx.fillStyle="#F97316";ctx.fillRect(x+8,gy-98-f,50,36);ctx.fillStyle="#FACC15";ctx.fillRect(x+16,gy-90+f,34,24);}}
        else{{ctx.fillStyle="#1C1917";ctx.fillRect(x+12,gy-66,8,18);ctx.fillRect(x+44,gy-62,8,16);ctx.fillRect(x+28,gy-74,8,24);ctx.fillStyle="rgba(148,163,184,.55)";ctx.fillRect(x+26,gy-84-(t*2)%26,10,8);}}
      }}
      function dragon(cx,gy,t,st,swing,open,angry){{
        const p=(ox,oy,w,h,c)=>px(cx,gy,ox,oy,w,h,c),eye=angry?"#EF4444":"#38BDF8";
        if(st==="sleep"){{
          const b=Math.sin(t*.1)>0?0:1;
          p(-16,-12+b,28,12-b,"#0F172A");p(-14,-14+b,24,4,"#0284C7");p(-11,-16+b,3,2,"#FACC15");p(-4,-16+b,3,2,"#FACC15");p(2,-16+b,3,2,"#FACC15");
          p(-9,-11+b,16,6,"#1E293B");p(-24,-6,10,5,"#0F172A");p(-31,-8,8,7,"#FDE047");
          p(12,-11+b,14,11-b,"#0F172A");p(15,-8+b,6,2,"#38BDF8");p(21,-4,5,2,"#FFF");
          const z=Math.floor(t/15)%3;ctx.fillStyle="#E0F2FE";ctx.font="bold 15px monospace";ctx.fillText("z",cx+25*SC,gy-(14+z*3)*SC);ctx.fillText("Z",cx+29*SC,gy-(19+z*3)*SC);return;
        }}
        const bob=st==="fly"?Math.round(Math.sin(t*.16)*2.5):(Math.sin(t*.14)>0?0:1),wf=st==="fly"?Math.round(Math.sin(t*.35)*6):Math.round(Math.sin(t*.14)*2);
        p(-12,-26+bob+wf,20,10,"#1E293B");p(-14,-28+bob+wf,22,2,"#38BDF8");
        const ty=swing?-8:0,tx=swing?4:0;
        p(-19+tx,-11+bob+ty*.4,10,6,"#0F172A");p(-27+tx,-10+bob+ty*.7,9,5,"#0284C7");p(-36+tx,-13+bob+ty,10,9,"#FDE047");p(-38+tx,-11+bob+ty,2,5,"#FACC15");
        p(-6,-8+bob,6,7,"#0284C7");p(-1,-9+bob,7,8,"#0F172A");p(-7,-2+bob,8,2,"#FACC15");p(-2,-2+bob,9,2,"#FACC15");
        p(-10,-18+bob,20,12,"#0F172A");p(-6,-15+bob,14,8,"#E0F2FE");p(-11,-20+bob,19,4,"#0284C7");
        p(-10,-23+bob,3,3,"#FACC15");p(-5,-23+bob,3,3,"#FACC15");p(0,-23+bob,3,3,"#FACC15");p(5,-22+bob,3,2,"#FACC15");
        p(9,-14+bob,5,3,"#0F172A");p(13,-13+bob,2,3,"#FACC15");
        p(-7,-23+bob-wf,19,9,"#1E293B");p(-9,-25+bob-wf,21,2,"#38BDF8");
        p(7,-27+bob,15,11,"#0F172A");p(12,-27+bob,11,7,"#0F172A");p(12,-25+bob,3,3,eye);p(6,-30+bob,4,3,"#FACC15");p(3,-32+bob,4,3,"#FACC15");
        p(14,-20+bob,2,2,"#FFF");p(18,-20+bob,2,2,"#FFF");p(21,-20+bob,2,2,"#FFF");
        p(11,-18+bob+(open?4:0),11,3,"#0284C7");
      }}
      function fire(sx,sy,ex,ey,t){{
        for(let i=0;i<=16;i++){{const k=i/16,fx=sx+(ex-sx)*k,sp=6+k*26,fy=sy+(ey-sy)*k+Math.sin(t*.9+i)*(4+k*7);
          ctx.fillStyle="#DC2626";ctx.fillRect(fx-4,fy-sp*.6,15,sp*1.2);ctx.fillStyle="#F97316";ctx.fillRect(fx,fy-sp*.4,11,sp*.8);ctx.fillStyle="#FACC15";ctx.fillRect(fx+2,fy-sp*.2,7,sp*.4);}}
      }}
      let t0=performance.now();
      function loop(now){{
        const el=(now-t0)/1000,tk=Math.floor(el*20);
        if(D.event==="feed_meat"&&evT>0){{
          const r=Math.max(0,evT-el),pr=1-r/2.1;bg(tk,false);dragon(310,162,tk,"stand",false,pr>.3&&pr<.85,false);
          if(pr<.6)steak(550-pr*245,70+Math.sin(pr*Math.PI)*-30+pr*20);
          else{{ctx.fillStyle="#FDE047";ctx.font="bold 16px monospace";ctx.fillText("+1 🍖 Lecker!",385,56-(pr-.6)*32);}}
          if(r<=0)evT=0;requestAnimationFrame(loop);return;
        }}
        if(D.event==="burn_tree"&&evT>0){{
          const r=Math.max(0,evT-el),pr=1-r/2.1,bl=pr>=.15&&pr<=.72;
          ctx.save();if(bl)ctx.translate(Math.sin(tk*1.9)*3,0);bg(tk,true);
          tree(540,162,pr<.25?0:(pr<.78?1:2),tk);dragon(270,162,tk,"stand",bl,bl,true);
          if(bl)fire(368,82,560,92,tk);
          ctx.fillStyle="#FCA5A5";ctx.font="bold 15px monospace";ctx.fillText("🔥 Vor Wut einen Baum abgefackelt!",230,32);
          ctx.restore();if(r<=0)evT=0;requestAnimationFrame(loop);return;
        }}
        bg(tk,false);
        if(mode==="sleep")dragon(345,162,tk,"sleep",false,false,false);
        else if(mode==="fly"){{
          const fx=365+Math.sin(el*1.1)*185,fy=102+Math.cos(el*2.2)*12;
          ctx.fillStyle="rgba(2,132,199,.25)";ctx.fillRect(fx-42,165,84,6);dragon(fx,fy,tk,"fly",false,false,false);
        }}else{{
          const cy=(el*1.35)%2,st=cy>.55&&cy<.95,lx=cy<.7?cy*66:(1.4-cy)*44;
          boulder(515,108,st?Math.sin(tk*1.8)*5:0,st);dragon(325+Math.max(0,lx),162,tk,"fight",st,st,false);
        }}
        requestAnimationFrame(loop);
      }}requestAnimationFrame(loop);
    </script></body></html>"""
    components.html(html_stage, height=270, scrolling=False)

def svg_uri(s): return "data:image/svg+xml," + urllib.parse.quote(s.strip(), safe="")
def get_cursor(lvl, sel):
    ok = [c for c in CURSOR_MILESTONES if c["level"] <= lvl]
    return ok[-1] if sel == -1 else next((c for c in ok if c["level"] == sel), ok[-1])
def xp_next(lvl): return 100 + (max(1, int(lvl)) - 1) * 50

def fmt_card_html(txt, cloze=False):
    s = html.escape(str(txt or "").strip())
    if cloze:
        s = re.sub(r"(\[\.{2,}\]|_{3,})", '<span class="cloze-blank">________</span>', s)
    return s.replace("\r\n", "\n").replace("\n", "<br>")

def anki_cat(k):
    r, iv, lp, sc = int(k.get("repetitions") or 0), int(k.get("interval_days") or 0), int(k.get("lapses") or 0), int(k.get("success_count") or 0)
    if r == 0 and lp == 0 and sc == 0: return "neu"
    if lp >= 2 or (lp >= 1 and r == 0): return "kritisch"
    if r >= 2 and iv >= 6: return "gut"
    return "wackelig"

def topic_bar_html(o):
    tot, due = int(o.get("total_cards") or 0), int(o.get("due_cards") or 0)
    g, w, kr, n = int(o.get("gut_cards") or 0), int(o.get("wackelig_cards") or 0), int(o.get("kritisch_cards") or 0), int(o.get("neu_cards") or 0)
    if tot > 0:
        pg, pw, pk = round(g/tot*100, 1), round(w/tot*100, 1), round(kr/tot*100, 1)
        pn, pct = max(0.0, round(100 - pg - pw - pk, 1)), round(g/tot*100)
    else:
        pg = pw = pk = 0.0; pn, pct = 100.0, 0
    badge = f'<span class="topic-due-badge">{due} fällig</span>' if due > 0 else '<span class="topic-done-badge">Alles erledigt</span>'
    return (f'<div class="topic-card"><div class="topic-top-row"><div class="topic-name">{html.escape(str(o["name"]))}</div>'
            f'<div class="topic-right-meta"><span class="topic-pct">{pct}% gefestigt</span>{badge}</div></div>'
            f'<div class="anki-bar-track"><div class="anki-seg-gut" style="width:{pg}%;"></div><div class="anki-seg-wackelig" style="width:{pw}%;"></div>'
            f'<div class="anki-seg-kritisch" style="width:{pk}%;"></div><div class="anki-seg-neu" style="width:{pn}%;"></div></div>'
            f'<div class="anki-legend-row"><span><i class="dot-gut"></i><b>{g}</b> gut gelernt</span><span><i class="dot-wackelig"></i><b>{w}</b> wackelig</span>'
            f'<span><i class="dot-kritisch"></i><b>{kr}</b> öfter falsch</span><span><i class="dot-neu"></i><b>{n}</b> ungelernt</span></div></div>')

st.markdown("""<style>
.stApp{background:radial-gradient(circle at 50% -10%,#0F1A2E 0%,#07090E 55%,#05070B 100%);color:#F1F5F9}
.block-container{max-width:1180px!important;padding:2.1rem 2.3rem 3.2rem!important}
hr{border:none!important;border-top:1px solid rgba(125,211,252,.22)!important;margin:1.25rem 0!important}
.omni-header{display:flex;align-items:center;justify-content:space-between;padding-bottom:.8rem;margin-bottom:1rem}
.omni-brand{font-size:2.2rem;font-weight:800;letter-spacing:-.02em;background:linear-gradient(135deg,#FFF 0%,#E0F2FE 55%,#7DD3FC 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.1}
.omni-tagline{font-size:.86rem;color:#94A3B8;margin-top:.2rem}
.ar-subtitle{font-size:1.18rem;font-weight:600;color:#E0F2FE;margin:.6rem 0 .7rem}
.section-kicker{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#7DD3FC;margin-bottom:.5rem}
.sculpt-panel{background:linear-gradient(165deg,#11192B,#0A0F1A);border:1px solid rgba(125,211,252,.26);border-radius:16px;padding:1.15rem 1.35rem;box-shadow:0 14px 30px rgba(0,0,0,.52),inset 0 1px 0 rgba(255,255,255,.09);height:100%}
.panel-top-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem}
.level-pill{background:linear-gradient(135deg,#38BDF8,#7DD3FC);color:#060911;font-weight:800;font-size:.9rem;padding:.25rem .78rem;border-radius:999px}
.xp-meta{font-size:.86rem;color:#CBD5E1;font-weight:600}
.progress-track{width:100%;height:11px;background:#060911;border-radius:999px;border:1px solid rgba(125,211,252,.22);overflow:hidden;margin:.5rem 0 .7rem}
.progress-fill-ice{height:100%;border-radius:999px;background:linear-gradient(90deg,#0284C7,#38BDF8 55%,#BAE6FD)}
.progress-fill-quest{height:100%;border-radius:999px;background:linear-gradient(90deg,#0EA5E9,#7DD3FC)}
.panel-footer-row{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem;font-size:.82rem;color:#94A3B8}
.streak-chip{padding:.18rem .6rem;border-radius:7px;background:rgba(125,211,252,.12);border:1px solid rgba(125,211,252,.3);color:#E0F2FE;font-weight:600}
.streak-chip-hot{padding:.18rem .6rem;border-radius:7px;background:rgba(250,204,21,.16);border:1px solid rgba(250,204,21,.45);color:#FDE047;font-weight:700}
.day-dots{display:inline-flex;gap:5px;align-items:center}
.day-dot{width:11px;height:11px;border-radius:50%;background:#070A12;border:1px solid rgba(125,211,252,.3)}
.day-dot-active{background:linear-gradient(135deg,#7DD3FC,#38BDF8);border-color:#E0F2FE;box-shadow:0 0 8px rgba(125,211,252,.65)}
.stat-card{background:linear-gradient(165deg,#101727,#090D16);border:1px solid rgba(125,211,252,.24);border-radius:16px;padding:1.1rem .9rem;text-align:center;box-shadow:0 12px 26px rgba(0,0,0,.48),inset 0 1px 0 rgba(255,255,255,.08)}
.stat-num{font-size:1.95rem;font-weight:800;color:#7DD3FC;line-height:1.15}
.stat-label{font-size:.84rem;color:#94A3B8;margin-top:.25rem}
.topic-card{background:linear-gradient(165deg,#101829,#090D16);border:1px solid rgba(125,211,252,.24);border-radius:15px;padding:1rem 1.2rem;margin-bottom:.7rem;box-shadow:0 10px 24px rgba(0,0,0,.46)}
.topic-top-row{display:flex;justify-content:space-between;align-items:center;gap:.6rem;margin-bottom:.5rem}
.topic-name{font-size:1.02rem;font-weight:700;color:#F8FAFC}
.topic-right-meta{display:flex;align-items:center;gap:.5rem}
.topic-pct{font-size:.83rem;font-weight:700;color:#7DD3FC}
.topic-due-badge{font-size:.74rem;font-weight:700;padding:.15rem .52rem;border-radius:999px;background:rgba(125,211,252,.14);border:1px solid rgba(125,211,252,.35);color:#E0F2FE}
.topic-done-badge{font-size:.74rem;padding:.15rem .52rem;border-radius:999px;background:rgba(148,163,184,.12);color:#94A3B8}
.anki-bar-track{display:flex;width:100%;height:10px;background:#060911;border-radius:999px;border:1px solid rgba(125,211,252,.2);overflow:hidden;margin-bottom:.55rem}
.anki-seg-gut{height:100%;background:linear-gradient(90deg,#0284C7,#38BDF8 65%,#7DD3FC)}
.anki-seg-wackelig{height:100%;background:linear-gradient(90deg,#EAB308,#FACC15)}
.anki-seg-kritisch{height:100%;background:linear-gradient(90deg,#DC2626,#F87171)}
.anki-seg-neu{height:100%;background:#172033}
.anki-legend-row{display:flex;flex-wrap:wrap;gap:.8rem;font-size:.79rem;color:#94A3B8}
.anki-legend-row b{color:#E2E8F0}
.dot-gut,.dot-wackelig,.dot-kritisch,.dot-neu{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:middle}
.dot-gut{background:#38BDF8}.dot-wackelig{background:#FACC15}.dot-kritisch{background:#F87171}.dot-neu{background:#334155;border:1px solid #64748B}
.flashcard-box{background:linear-gradient(160deg,#11192C,#0A0F1B);border:1.5px solid rgba(125,211,252,.48);border-radius:18px;padding:1.6rem 1.8rem;margin:.6rem 0 1.05rem;box-shadow:0 18px 38px rgba(0,0,0,.58),inset 0 1px 0 rgba(255,255,255,.1);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.flashcard-meta{display:flex;flex-wrap:wrap;align-items:center;gap:.45rem;margin-bottom:.95rem}
.flashcard-badge{font-size:.76rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#060911;background:linear-gradient(135deg,#7DD3FC,#38BDF8);padding:.24rem .68rem;border-radius:7px}
.flashcard-badge-xp{font-size:.75rem;font-weight:700;color:#BAE6FD;background:rgba(125,211,252,.12);border:1px solid rgba(125,211,252,.35);padding:.22rem .62rem;border-radius:7px}
.flashcard-badge-warn{font-size:.75rem;font-weight:700;color:#07090E;background:#FACC15;padding:.24rem .64rem;border-radius:7px}
.flashcard-question{font-size:1.28rem;font-weight:500;color:#F8FAFC;line-height:1.6}
.flashcard-answer-label{font-size:.76rem;color:#7DD3FC;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.45rem;font-weight:700}
.flashcard-answer-body{font-size:1.12rem;color:#F8FAFC;line-height:1.6}
.flashcard-explanation{margin-top:.9rem;padding-top:.8rem;border-top:1px solid rgba(125,211,252,.2);color:#BAE6FD;font-size:.95rem}
.cloze-blank{display:inline-block;min-width:92px;padding:0 .5rem;margin:0 .2rem;border-bottom:2.5px solid #7DD3FC;background:rgba(125,211,252,.12);border-radius:5px 5px 0 0;color:#7DD3FC;font-weight:700;text-align:center}
div[data-testid="stRadio"]>div[role="radiogroup"]{gap:.55rem;margin:.35rem 0 .75rem}
div[data-testid="stRadio"]>div[role="radiogroup"]>label{background:linear-gradient(165deg,#101829,#0A0F1A)!important;border:1px solid rgba(125,211,252,.3)!important;border-radius:12px!important;padding:.7rem 1rem!important}
div[data-testid="stRadio"]>div[role="radiogroup"]>label:hover{border-color:#7DD3FC!important}
.xp-banner{background:linear-gradient(135deg,rgba(14,165,233,.16),rgba(15,23,42,.92));border:1px solid rgba(125,211,252,.5);border-radius:12px;padding:.68rem 1.05rem;margin-bottom:.8rem;color:#E0F2FE;font-size:.92rem;font-weight:600}
.stTabs [data-baseweb="tab-list"]{gap:.55rem;background:#0A0F1A;padding:.38rem;border-radius:14px;border:1px solid rgba(125,211,252,.2)}
.stTabs [data-baseweb="tab"]{border-radius:10px!important;padding:.6rem 1.15rem!important;font-weight:600!important;color:#94A3B8!important}
.stTabs [aria-selected="true"]{background:linear-gradient(160deg,#162238,#0F172A)!important;color:#E0F2FE!important}
.stButton>button{background:linear-gradient(180deg,#152036,#0D1424)!important;border:1px solid rgba(125,211,252,.42)!important;color:#E0F2FE!important;border-radius:12px!important;padding:.6rem 1.05rem!important;font-weight:600!important;box-shadow:0 6px 16px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.1)!important}
.stButton>button:hover{border-color:#7DD3FC!important;background:linear-gradient(180deg,#1B2A47,#111B30)!important;color:#FFF!important}
</style>""", unsafe_allow_html=True)

def check_password():
    try: pw = st.secrets["APP_PASSWORD"]
    except Exception: pw = "1234"
    if not st.session_state.get("eingeloggt"):
        st.markdown('<div class="omni-header"><div><div class="omni-brand">OmniLearn</div><div class="omni-tagline">Active Recall & Spaced Repetition</div></div></div>', unsafe_allow_html=True)
        c1, _ = st.columns([1.2, 1])
        with c1:
            inp = st.text_input("Zugangspasswort:", type="password", placeholder="Passwort eingeben...")
            if st.button("Entsperren", use_container_width=True):
                if inp == pw:
                    st.session_state.eingeloggt = True
                    st.rerun()
                else:
                    st.error("Falsches Passwort.")
        st.stop()

check_password()

def get_db_url():
    try: u = st.secrets["DATABASE_URL"].strip()
    except Exception: u = os.environ.get("DATABASE_URL", "").strip()
    return u.replace("postgres://", "postgresql://", 1) if u.startswith("postgres://") else u

@st.cache_resource
def get_db_pool():
    u = get_db_url()
    if not u: raise RuntimeError("DATABASE_URL fehlt in den Streamlit Secrets.")
    return pool.ThreadedConnectionPool(minconn=1, maxconn=6, dsn=u, connect_timeout=15)

def get_conn():
    p, err = get_db_pool(), None
    for _ in range(3):
        c = None
        try:
            c = p.getconn()
            with c.cursor() as cur: cur.execute("SELECT 1;")
            return c
        except Exception as e:
            err = e
            if c:
                try: p.putconn(c, close=True)
                except Exception: pass
            time.sleep(0.4)
    raise err

def put_conn(c, broken=False):
    if c:
        try: get_db_pool().putconn(c, close=broken)
        except Exception:
            try: c.close()
            except Exception: pass

@st.cache_resource
def get_bg_queue():
    q = queue.Queue()
    def _worker():
        while True:
            task = q.get()
            c, brk = None, False
            try:
                c = get_conn()
                with c.cursor() as cur:
                    for sql, params in task: cur.execute(sql, params)
                c.commit()
            except Exception:
                brk = True
                if c:
                    try: c.rollback()
                    except Exception: pass
            finally:
                put_conn(c, brk)
                q.task_done()
    threading.Thread(target=_worker, daemon=True).start()
    return q

def enqueue_writes(stmts): get_bg_queue().put(stmts)

@st.cache_resource
def init_db():
    c, brk = get_conn(), False
    try:
        with c.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS folders (id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ DEFAULT NOW());")
            cur.execute("CREATE TABLE IF NOT EXISTS documents (id SERIAL PRIMARY KEY, folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE, filename TEXT NOT NULL, char_count INTEGER DEFAULT 0, content_text TEXT DEFAULT '', uploaded_at TIMESTAMPTZ DEFAULT NOW());")
            cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_text TEXT DEFAULT '';")
            cur.execute("""CREATE TABLE IF NOT EXISTS cards (
                id SERIAL PRIMARY KEY, folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL, card_type TEXT NOT NULL DEFAULT 'Klassisch',
                question TEXT NOT NULL, options_json TEXT DEFAULT '[]', answer TEXT NOT NULL, explanation TEXT DEFAULT '',
                ease_factor REAL NOT NULL DEFAULT 2.5, interval_days INTEGER NOT NULL DEFAULT 0, repetitions INTEGER NOT NULL DEFAULT 0,
                lapses INTEGER NOT NULL DEFAULT 0, success_count INTEGER NOT NULL DEFAULT 0,
                next_review TIMESTAMPTZ NOT NULL DEFAULT NOW(), created_at TIMESTAMPTZ DEFAULT NOW());""")
            cur.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS success_count INTEGER NOT NULL DEFAULT 0;")
            cur.execute("UPDATE cards SET success_count = repetitions WHERE success_count = 0 AND repetitions > 0;")
            cur.execute("""CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY DEFAULT 1, level INTEGER NOT NULL DEFAULT 1, xp_in_level INTEGER NOT NULL DEFAULT 0,
                total_xp INTEGER NOT NULL DEFAULT 0, answer_streak INTEGER NOT NULL DEFAULT 0, best_answer_streak INTEGER NOT NULL DEFAULT 0,
                daily_cards_done INTEGER NOT NULL DEFAULT 0, daily_quest_claimed BOOLEAN NOT NULL DEFAULT FALSE,
                stats_date DATE NOT NULL DEFAULT CURRENT_DATE, daily_quest_streak INTEGER NOT NULL DEFAULT 0,
                last_quest_completed_date DATE, selected_cursor_level INTEGER NOT NULL DEFAULT -1,
                bonus_10_start TIMESTAMPTZ, bonus_20_start TIMESTAMPTZ, dragon_meat INTEGER NOT NULL DEFAULT 0);""")
            for col_sql in [
                "ALTER TABLE user_progress ADD COLUMN IF NOT EXISTS bonus_10_start TIMESTAMPTZ;",
                "ALTER TABLE user_progress ADD COLUMN IF NOT EXISTS bonus_20_start TIMESTAMPTZ;",
                "ALTER TABLE user_progress ADD COLUMN IF NOT EXISTS dragon_meat INTEGER NOT NULL DEFAULT 0;",
            ]:
                cur.execute(col_sql)
            cur.execute("INSERT INTO user_progress (id, level, xp_in_level, total_xp, stats_date, dragon_meat) VALUES (1, 1, 0, 0, CURRENT_DATE, 0) ON CONFLICT (id) DO NOTHING;")
        c.commit()
    except Exception:
        brk = True; raise
    finally:
        put_conn(c, brk)
    return True

try:
    init_db()
except Exception as e:
    st.error(f"Datenbank-Verbindung fehlgeschlagen: {e}")
    st.stop()

def load_progress_db():
    today = datetime.datetime.now(BERLIN_TZ).date()
    yesterday = today - datetime.timedelta(days=1)
    c, brk = get_conn(), False
    try:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM user_progress WHERE id = 1;")
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO user_progress (id, level, xp_in_level, total_xp, stats_date, dragon_meat) VALUES (1, 1, 0, 0, %s, 0) RETURNING *;", (today,))
                row = cur.fetchone()
            upd = False
            sd, d_done, d_clm, q_str, last_c = row["stats_date"], int(row.get("daily_cards_done") or 0), bool(row.get("daily_quest_claimed")), int(row.get("daily_quest_streak") or 0), row.get("last_quest_completed_date")
            if sd != today:
                d_done, d_clm, sd, upd = 0, False, today, True
            if q_str > 0 and (last_c is None or last_c < yesterday):
                q_str, upd = 0, True
            if upd:
                cur.execute("UPDATE user_progress SET daily_cards_done=%s, daily_quest_claimed=%s, stats_date=%s, daily_quest_streak=%s, bonus_10_start=NULL, bonus_20_start=NULL WHERE id=1 RETURNING *;", (d_done, d_clm, sd, q_str))
                row = cur.fetchone()
        c.commit()
        return dict(row)
    except Exception:
        brk = True; raise
    finally:
        put_conn(c, brk)

def get_progress():
    today = datetime.datetime.now(BERLIN_TZ).date()
    if "cached_user_progress" not in st.session_state or st.session_state.cached_user_progress.get("stats_date") != today:
        st.session_state.cached_user_progress = load_progress_db()
    return st.session_state.cached_user_progress

def load_folders_db():
    c, brk = get_conn(), False
    try:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT f.id, f.name, COUNT(DISTINCT d.id) AS doc_count, COUNT(DISTINCT c.id) AS total_cards,
                    COUNT(DISTINCT CASE WHEN c.next_review <= NOW() THEN c.id END) AS due_cards,
                    COUNT(DISTINCT CASE WHEN c.id IS NOT NULL AND c.repetitions=0 AND c.lapses=0 AND COALESCE(c.success_count,0)=0 THEN c.id END) AS neu_cards,
                    COUNT(DISTINCT CASE WHEN c.id IS NOT NULL AND (c.lapses>=2 OR (c.lapses>=1 AND c.repetitions=0)) THEN c.id END) AS kritisch_cards,
                    COUNT(DISTINCT CASE WHEN c.id IS NOT NULL AND NOT (c.lapses>=2 OR (c.lapses>=1 AND c.repetitions=0)) AND c.repetitions>=2 AND c.interval_days>=6 THEN c.id END) AS gut_cards,
                    COUNT(DISTINCT CASE WHEN c.id IS NOT NULL AND NOT (c.repetitions=0 AND c.lapses=0 AND COALESCE(c.success_count,0)=0) AND NOT (c.lapses>=2 OR (c.lapses>=1 AND c.repetitions=0)) AND NOT (c.repetitions>=2 AND c.interval_days>=6) THEN c.id END) AS wackelig_cards
                FROM folders f LEFT JOIN documents d ON d.folder_id=f.id LEFT JOIN cards c ON c.folder_id=f.id
                GROUP BY f.id, f.name ORDER BY f.name ASC;""")
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        brk = True; raise
    finally:
        put_conn(c, brk)

def get_folders(force=False):
    if force or "cached_ordner_liste" not in st.session_state:
        st.session_state.cached_ordner_liste = load_folders_db()
    return st.session_state.cached_ordner_liste

def inv_folders():
    st.session_state.pop("cached_ordner_liste", None)

def process_rating_instant(card, rated, ef, iv, reps, lapses, next_rev, new_sc, ok, first_ok):
    today = datetime.datetime.now(BERLIN_TZ).date()
    yesterday = today - datetime.timedelta(days=1)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    old_st = anki_cat(card)
    was_due = card["next_review"] <= now_utc
    card.update({"ease_factor": ef, "interval_days": iv, "repetitions": reps, "lapses": lapses, "next_review": next_rev, "success_count": new_sc})
    new_st = anki_cat(card)

    for o in get_folders():
        if o["id"] == card["folder_id"]:
            if was_due and not (next_rev <= now_utc):
                o["due_cards"] = max(0, int(o.get("due_cards") or 0) - 1)
            if old_st != new_st:
                o[f"{old_st}_cards"] = max(0, int(o.get(f"{old_st}_cards") or 0) - 1)
                o[f"{new_st}_cards"] = int(o.get(f"{new_st}_cards") or 0) + 1
            break

    p = get_progress()
    lvl, xp_lvl, tot_xp = int(p.get("level") or 1), int(p.get("xp_in_level") or 0), int(p.get("total_xp") or 0)
    a_str, best_str = int(p.get("answer_streak") or 0), int(p.get("best_answer_streak") or 0)
    d_done, d_clm, q_str = int(p.get("daily_cards_done") or 0), bool(p.get("daily_quest_claimed")), int(p.get("daily_quest_streak") or 0)
    last_c = p.get("last_quest_completed_date")
    sel_cur = int(p["selected_cursor_level"]) if p.get("selected_cursor_level") is not None else -1
    b10, b20 = p.get("bonus_10_start"), p.get("bonus_20_start")
    meat = int(p.get("dragon_meat") or 0)

    ev = []
    st.session_state.dragon_anim_seq += 1
    if ok:
        meat += 1
        st.session_state.dragon_event = "feed_meat"
        ev.append(f"🍖 +1 Fleisch für deinen Drachen ({meat} gesamt)")
    else:
        st.session_state.dragon_event = "burn_tree"
        ev.append("🔥 Dein Drache fackelt vor Wut einen Baum ab!")

    # Streak steigt NUR bei "Gut" (3) oder "Leicht" (4). Bei "Schwer" (2) bleibt sie stehen, bei "Nochmal" (1) reißt sie.
    if rated == 1:
        a_str = 0
        ev.append("Antwort-Serie gerissen · Karte kommt gleich nochmal")
    else:
        base = 2 if first_ok else 1
        sb = 0
        if rated in (3, 4):
            a_str += 1
            best_str = max(best_str, a_str)
            if a_str >= 10:
                if b10 is None:
                    b10 = now_utc; sb = 1; ev.append("🔥 10er-Serie! +1 XP Multiplikator (30 Min.) aktiv!")
                elif (now_utc - b10).total_seconds() < 1800:
                    sb = 1
            if a_str >= 20:
                if b20 is None:
                    b20 = now_utc; sb = 2; ev.append("⚡ 20er-Serie! +2 XP Multiplikator (30 Min.) aktiv!")
                elif (now_utc - b20).total_seconds() < 1800:
                    sb = 2
        else:
            ev.append(f"Serie pausiert bei {a_str} („Schwer“)")

        gain = base + sb
        ev.append(f"+{base} XP" + (f" · +{sb} XP Serie" if sb > 0 else ""))
        d_done += 1
        extra_lvl = 0
        if d_done >= DAILY_GOAL_TARGET and not d_clm:
            d_clm = True; gain += DAILY_GOAL_BONUS_XP
            ev.append(f"🎯 Tagesziel ({DAILY_GOAL_TARGET}/{DAILY_GOAL_TARGET}) erfüllt: +{DAILY_GOAL_BONUS_XP} XP Extra!")
            q_str = (q_str + 1) if last_c == yesterday else (q_str if last_c == today else 1)
            last_c = today
            if q_str > 0 and q_str % 7 == 0:
                extra_lvl += 1; ev.append(f"🔥 {q_str} Tage in Folge! Vollständiges Level-Up!")

        old_lvl = lvl
        xp_lvl += gain; tot_xp += gain
        while xp_lvl >= xp_next(lvl):
            xp_lvl -= xp_next(lvl); lvl += 1
        lvl += extra_lvl
        if lvl > old_lvl:
            ev.append(f"⬆️ Level-Up erreicht: Jetzt Level {lvl}!")
            unlocked = [c for c in CURSOR_MILESTONES if c["level"] > 0 and old_lvl < c["level"] <= lvl]
            if unlocked:
                sel_cur = -1; ev.append(f"✨ Neues Maus-Symbol freigeschaltet: {unlocked[-1]['name']}!")

    p.update({"level": lvl, "xp_in_level": xp_lvl, "total_xp": tot_xp, "answer_streak": a_str, "best_answer_streak": best_str,
              "daily_cards_done": d_done, "daily_quest_claimed": d_clm, "stats_date": today, "daily_quest_streak": q_str,
              "last_quest_completed_date": last_c, "selected_cursor_level": sel_cur, "bonus_10_start": b10, "bonus_20_start": b20, "dragon_meat": meat})

    enqueue_writes([
        ("UPDATE cards SET ease_factor=%s, interval_days=%s, repetitions=%s, lapses=%s, next_review=%s, success_count=%s WHERE id=%s;",
         (ef, iv, reps, lapses, next_rev, new_sc, card["id"])),
        ("UPDATE user_progress SET level=%s, xp_in_level=%s, total_xp=%s, answer_streak=%s, best_answer_streak=%s, daily_cards_done=%s, daily_quest_claimed=%s, stats_date=%s, daily_quest_streak=%s, last_quest_completed_date=%s, selected_cursor_level=%s, bonus_10_start=%s, bonus_20_start=%s, dragon_meat=%s WHERE id=1;",
         (lvl, xp_lvl, tot_xp, a_str, best_str, d_done, d_clm, today, q_str, last_c, sel_cur, b10, b20, meat)),
    ])
    return "  |  ".join(ev)

user_prog = get_progress()
cur_lvl = int(user_prog.get("level") or 1)
sel_cur = int(user_prog["selected_cursor_level"]) if user_prog.get("selected_cursor_level") is not None else -1
active_cur = get_cursor(cur_lvl, sel_cur)
if active_cur["svg"]:
    st.markdown(f'<style>html,body,.stApp,.stApp *{{cursor:url("{svg_uri(active_cur["svg"])}") {active_cur["hx"]} {active_cur["hy"]},auto!important}}</style>', unsafe_allow_html=True)

@st.cache_resource
def init_gemini():
    try: key = st.secrets["GEMINI_API_KEY"].strip()
    except Exception: key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key: return []
    genai.configure(api_key=key, transport="rest")
    mods = []
    try:
        for m in genai.list_models():
            if "generateContent" in getattr(m, "supported_generation_methods", []):
                nl = m.name.lower()
                if "gemini" in nl and not any(x in nl for x in ["image", "audio", "tts", "robotics", "computer", "embedding", "aqa"]):
                    mods.append(m.name)
    except Exception: pass
    mods.sort(key=lambda x: (0 if ("flash" in x.lower() and "lite" not in x.lower()) else 1, x))
    return mods

gemini_models = init_gemini()

def ask_gemini(prompt):
    if not gemini_models: raise RuntimeError("GEMINI_API_KEY fehlt in den Secrets.")
    last_e = None
    for mn in gemini_models:
        try:
            return genai.GenerativeModel(mn).generate_content(prompt, request_options={"timeout": 90}).text
        except Exception as e:
            last_e = e
    raise last_e

def extract_text(f):
    nm, raw = f.name.lower(), f.read()
    if nm.endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages).strip()
    if nm.endswith(".docx"):
        doc = Document(io.BytesIO(raw))
        out = [p.text for p in doc.paragraphs if p.text.strip()]
        for tb in doc.tables:
            for r in tb.rows: out.append(" | ".join(c.text.strip() for c in r.cells))
        return "\n".join(out).strip()
    for enc in ("utf-8", "latin-1"):
        try: return raw.decode(enc).strip()
        except Exception: pass
    return ""

def generate_cards(text, count, types):
    t_desc = {
        "Lückentext": "Lückentext: Ein prüfungsrelevanter Merksatz in 'question', bei dem 1-2 Fachbegriffe durch '______' ersetzt sind; in 'answer' die Begriffe + voller Satz; 'options'=[].",
        "Problemstellung": "Problemstellung: Ein kurzes Fallbeispiel oder 'Was passiert, wenn...'-Szenario in 'question'; in 'answer' die begründete Lösung; 'options'=[].",
        "Multiple Choice": "Multiple Choice: Präzise Frage in 'question' (Optionen NICHT in question schreiben!); 'options' = Liste mit EXAKT 4 kurzen Antwortoptionen ohne A/B/C/D; 'answer' = exakter Wortlaut der einen richtigen Option.",
        "Klassisch": "Klassisch: Offene Verständnisfrage in 'question'; strukturierte Musterantwort in 'answer'; 'options'=[].",
    }
    chosen = [t for t in types if t in t_desc] or list(t_desc.keys())
    plan = "\n".join(f"- Karte {i+1}: '{chosen[i % len(chosen)]}'" for i in range(count))
    prompt = (f"Erstelle auf Basis des Lernmaterials genau {count} abwechslungsreiche Active-Recall-Karten.\n"
              f"FAHRPLAN:\n{plan}\n\nREGELN:\n" + "\n".join(t_desc[t] for t in chosen) +
              '\nAntworte NUR als JSON-Array: [{"card_type":"...","question":"...","options":[],"answer":"...","explanation":"..."}]\n\nMATERIAL:\n' + text[:28000])
    raw = ask_gemini(prompt).strip()
    if raw.startswith("```"): raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    s, e = raw.find("["), raw.rfind("]")
    if s != -1 and e != -1: raw = raw[s:e+1]
    res = []
    for idx, k in enumerate(json.loads(raw)):
        if not k.get("question") or not k.get("answer"): continue
        exp_t = chosen[idx % len(chosen)]
        ct = str(k.get("card_type", exp_t)).strip()
        if ct == "Transfer": ct = "Problemstellung"
        if ct not in t_desc: ct = exp_t
        opts = [re.sub(r"^[A-Da-d1-4][\)\.\:]\s*", "", str(o).strip()) for o in (k.get("options") or []) if str(o).strip()] if ct == "Multiple Choice" else []
        ans = re.sub(r"^[A-Da-d1-4][\)\.\:]\s*", "", str(k["answer"]).strip())
        if ct == "Multiple Choice":
            if len(opts) < 2: ct, opts = "Klassisch", []
            else:
                opts = opts[:4]
                if ans not in opts:
                    m = next((o for o in opts if ans.lower() in o.lower() or o.lower() in ans.lower()), None)
                    if m: ans = m
                    else: opts[0] = ans
        res.append({"card_type": ct, "question": str(k["question"]).strip(), "options": opts, "answer": ans, "explanation": str(k.get("explanation", "")).strip()})
    return res

def sm2(ef, iv, reps, lapses, rating):
    ef, iv, reps, lapses = float(ef), int(iv), int(reps), int(lapses)
    if rating == 1:
        return max(1.3, ef - 0.2), 0, 0, lapses + 1, datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=1)
    if rating == 2:
        iv = 1 if reps == 0 else (3 if reps == 1 else max(iv + 1, round(iv * 1.2)))
        ef = max(1.3, ef - 0.15)
    elif rating == 3:
        iv = 1 if reps == 0 else (6 if reps == 1 else max(iv + 1, round(iv * ef)))
    else:
        iv = 4 if reps == 0 else (8 if reps == 1 else max(iv + 2, round(iv * ef * 1.3)))
        ef = min(3.2, ef + 0.15)
    return ef, iv, reps + 1, lapses, datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=iv)

def iv_label(ef, iv, reps, lapses, rating):
    _, d, _, _, _ = sm2(ef, iv, reps, lapses, rating)
    return "Sofort wieder" if d == 0 else ("1 Tag" if d == 1 else f"{d} Tage")

def create_folder(name):
    c, brk = get_conn(), False
    try:
        with c.cursor() as cur:
            cur.execute("INSERT INTO folders (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id;", (name.strip(),))
            ok = cur.fetchone() is not None
        c.commit(); inv_folders(); return ok
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

def delete_folder(fid):
    c, brk = get_conn(), False
    try:
        with c.cursor() as cur: cur.execute("DELETE FROM folders WHERE id=%s;", (fid,))
        c.commit(); inv_folders()
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

def load_docs(fid):
    c, brk = get_conn(), False
    try:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT d.id, d.filename, COALESCE(d.content_text,'') AS content_text, d.uploaded_at, COUNT(c.id) AS card_count FROM documents d LEFT JOIN cards c ON c.document_id=d.id WHERE d.folder_id=%s GROUP BY d.id ORDER BY d.uploaded_at DESC;", (fid,))
            return [dict(r) for r in cur.fetchall()]
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

def save_doc_and_cards(fid, fn, chars, cards, txt=""):
    c, brk = get_conn(), False
    try:
        with c.cursor() as cur:
            cur.execute("INSERT INTO documents (folder_id, filename, char_count, content_text) VALUES (%s,%s,%s,%s) RETURNING id;", (fid, fn, chars, txt[:40000]))
            did = cur.fetchone()[0]
            for k in cards:
                cur.execute("INSERT INTO cards (folder_id, document_id, card_type, question, options_json, answer, explanation) VALUES (%s,%s,%s,%s,%s,%s,%s);",
                            (fid, did, k["card_type"], k["question"], json.dumps(k.get("options", []), ensure_ascii=False), k["answer"], k.get("explanation", "")))
        c.commit(); inv_folders()
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

def load_cards(fid=None, mode="due"):
    get_bg_queue().join()
    c, brk = get_conn(), False
    try:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            w, p = [], []
            if fid is not None: w.append("c.folder_id=%s"); p.append(fid)
            if mode == "due": w.append("c.next_review <= NOW()")
            elif mode == "weak": w.append("c.lapses > 0")
            wc = ("WHERE " + " AND ".join(w)) if w else ""
            cur.execute(f"SELECT c.*, f.name AS folder_name FROM cards c JOIN folders f ON f.id=c.folder_id {wc} ORDER BY CASE WHEN c.lapses>0 THEN 0 ELSE 1 END, c.next_review ASC, c.id ASC;", tuple(p))
            return [dict(r) for r in cur.fetchall()]
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

def delete_card(cid):
    c, brk = get_conn(), False
    try:
        with c.cursor() as cur: cur.execute("DELETE FROM cards WHERE id=%s;", (cid,))
        c.commit(); inv_folders()
    except Exception: brk = True; raise
    finally: put_conn(c, brk)

for k, v in [("study_queue", []), ("study_show_answer", False), ("study_done_count", 0), ("study_initial_total", 0), ("last_xp_event", None), ("session_notice", None), ("dragon_event", "none"), ("dragon_anim_seq", 0)]:
    st.session_state.setdefault(k, v)
st.session_state.setdefault("dragon_activity", random.choice(["sleep", "fly", "fight_rock"]))

# --- Header & Maus-Auswahl ---
cb, cc = st.columns([4.5, 1.5])
with cb:
    st.markdown('<div class="omni-header"><div><div class="omni-brand">OmniLearn</div><div class="omni-tagline">Active Recall & Spaced Repetition</div></div></div>', unsafe_allow_html=True)
with cc:
    st.markdown('<div style="height:.35rem"></div>', unsafe_allow_html=True)
    with st.popover(f"🖱️ Maus: {active_cur['short']}", use_container_width=True):
        st.markdown("**Freigeschaltete Maus-Symbole**")
        for it in CURSOR_MILESTONES:
            ok = cur_lvl >= it["level"]
            ico = f'<img src="{svg_uri(it["svg"])}" width="18" height="18" style="vertical-align:middle;margin-right:6px"/>' if it["svg"] else "↖️ "
            st_txt = "Freigeschaltet" if ok else f"Ab Level {it['level']}"
            st.markdown(f'{ico}<b>{it["name"]}</b> — <span style="color:#94A3B8;font-size:.82rem">{st_txt}</span>', unsafe_allow_html=True)
            if ok:
                act = active_cur["level"] == it["level"]
                if st.button("✓ Aktiv" if act else "Auswählen", key=f"cs_{it['level']}", disabled=act, use_container_width=True):
                    user_prog["selected_cursor_level"] = it["level"]
                    enqueue_writes([("UPDATE user_progress SET selected_cursor_level=%s WHERE id=1;", (it["level"],))])
                    st.rerun()

# --- Level & Tagesquest ---
xp_l, xp_z = int(user_prog.get("xp_in_level") or 0), xp_next(cur_lvl)
lvl_pct = min(100, round(xp_l / max(1, xp_z) * 100))
a_str = int(user_prog.get("answer_streak") or 0)
now_utc = datetime.datetime.now(datetime.timezone.utc)
b10, b20 = user_prog.get("bonus_10_start"), user_prog.get("bonus_20_start")

if b20 and (now_utc - b20).total_seconds() < 1800:
    st_chip = f'<span class="streak-chip-hot">⚡ {a_str}er-Serie (+2 XP / {int(30-(now_utc-b20).total_seconds()//60)} Min)</span>'
elif b10 and (now_utc - b10).total_seconds() < 1800:
    st_chip = f'<span class="streak-chip-hot">⚡ {a_str}er-Serie (+1 XP / {int(30-(now_utc-b10).total_seconds()//60)} Min)</span>'
else:
    st_chip = f'<span class="streak-chip">Serie: {a_str} Gut/Leicht in Folge</span>'

nxt_cur = next((c for c in CURSOR_MILESTONES if c["level"] > cur_lvl), None)
cur_hint = f"Nächstes Maus-Symbol ab Lv. {nxt_cur['level']}: {nxt_cur['name']}" if nxt_cur else "Alle Maus-Symbole freigeschaltet"

d_done, d_clm, q_str = int(user_prog.get("daily_cards_done") or 0), bool(user_prog.get("daily_quest_claimed")), int(user_prog.get("daily_quest_streak") or 0)
d_pct = min(100, round(d_done / DAILY_GOAL_TARGET * 100))
cyc = q_str % 7 if (q_str % 7 != 0 or q_str == 0) else 7
dots = "".join(f'<span class="day-dot {"day-dot-active" if i < cyc else ""}"></span>' for i in range(7))
q_txt = f"Tagesziel erfüllt (+{DAILY_GOAL_BONUS_XP} XP)" if d_clm else f"Noch {max(0, DAILY_GOAL_TARGET - d_done)} Karten bis +{DAILY_GOAL_BONUS_XP} XP"

cl, cq = st.columns(2)
with cl:
    st.markdown(f'<div class="sculpt-panel"><div class="panel-top-row"><span class="level-pill">Level {cur_lvl}</span><span class="xp-meta">{xp_l} / {xp_z} XP</span></div><div class="progress-track"><div class="progress-fill-ice" style="width:{lvl_pct}%"></div></div><div class="panel-footer-row">{st_chip}<span>{cur_hint}</span></div></div>', unsafe_allow_html=True)
with cq:
    st.markdown(f'<div class="sculpt-panel"><div class="panel-top-row"><span style="font-weight:700;color:#F8FAFC">Tagesziel: {min(d_done, DAILY_GOAL_TARGET)} / {DAILY_GOAL_TARGET} Karten</span><span class="xp-meta">{q_txt}</span></div><div class="progress-track"><div class="progress-fill-quest" style="width:{d_pct}%"></div></div><div class="panel-footer-row"><span>7-Tage-Quest (Volles Level-Up): <b>{q_str}</b> Tage</span><span class="day-dots">{dots}</span></div></div>', unsafe_allow_html=True)

st.markdown('<div style="height:.85rem"></div>', unsafe_allow_html=True)

folders = get_folders()
tot_cards = sum(int(o.get("total_cards") or 0) for o in folders)
tot_due = sum(int(o.get("due_cards") or 0) for o in folders)
tot_meat = int(user_prog.get("dragon_meat") or 0)

s1, s2, s3, s4 = st.columns(4)
s1.markdown(f'<div class="stat-card"><div class="stat-num">{tot_due}</div><div class="stat-label">Heute fällig</div></div>', unsafe_allow_html=True)
s2.markdown(f'<div class="stat-card"><div class="stat-num">🍖 {tot_meat}</div><div class="stat-label">Drachen-Fleisch</div></div>', unsafe_allow_html=True)
s3.markdown(f'<div class="stat-card"><div class="stat-num">{tot_cards}</div><div class="stat-label">Karten gesamt</div></div>', unsafe_allow_html=True)
s4.markdown(f'<div class="stat-card"><div class="stat-num">{len(folders)}</div><div class="stat-label">Themen-Ordner</div></div>', unsafe_allow_html=True)

if folders:
    st.markdown('<div style="height:.95rem"></div><div class="section-kicker">Themen-Fortschritt (Anki-Status)</div>', unsafe_allow_html=True)
    for i in range(0, len(folders), 2):
        tc = st.columns(2)
        tc[0].markdown(topic_bar_html(folders[i]), unsafe_allow_html=True)
        if i + 1 < len(folders): tc[1].markdown(topic_bar_html(folders[i + 1]), unsafe_allow_html=True)

st.markdown('<div style="height:.9rem"></div>', unsafe_allow_html=True)
t_learn, t_up, t_mgr = st.tabs(["🎯 Lernen (Spaced Repetition)", "📄 Dokumente & Kartengenerator", "📁 Ordner & Kartenverwaltung"])

with t_learn:
    render_dragon_stage(tot_meat, st.session_state.dragon_event, st.session_state.dragon_activity, st.session_state.dragon_anim_seq)
    if st.session_state.last_xp_event:
        st.markdown(f'<div class="xp-banner">{html.escape(st.session_state.last_xp_event)}</div>', unsafe_allow_html=True)
    if st.session_state.session_notice:
        st.info(st.session_state.session_notice)

    cf, cm, cb_start = st.columns([2.2, 2.2, 1.4])
    f_opts = {f"Alle Ordner ({tot_cards} Karten · {tot_due} fällig)": None}
    for o in folders:
        f_opts[f"{o['name']} ({o['total_cards']} Karten · {o['due_cards']} fällig)"] = o["id"]
    sel_f = cf.selectbox("Lernbereich wählen", list(f_opts.keys()))

    m_opts = {
        "Fällige Karten (Spaced Repetition)": "due",
        "Freies Lernen (alle Karten im Ordner)": "all",
        "Nur bisher falsche Karten (Fehler-Training)": "weak",
    }
    sel_m = cm.selectbox("Lernmodus", list(m_opts.keys()))
    with cb_start:
        st.markdown('<div style="height:1.72rem"></div>', unsafe_allow_html=True)
        if st.button("▶ Sitzung starten", use_container_width=True):
            get_folders(force=True)
            chosen_fid = f_opts[sel_f]
            chosen_mode = m_opts[sel_m]
            ks = load_cards(chosen_fid, chosen_mode)
            notice = None
            if not ks and chosen_mode == "due":
                ks = load_cards(chosen_fid, "all")
                if ks:
                    notice = f"Aktuell sind keine Karten fällig – freie Übungsrunde mit allen {len(ks)} Karten gestartet!"
            elif not ks and chosen_mode == "weak":
                notice = "In diesem Bereich gibt es aktuell keine falsch beantworteten Karten. Wähle 'Freies Lernen', um alle Karten durchzugehen."
            elif not ks:
                notice = "In diesem Ordner sind noch keine Karteikarten vorhanden."

            st.session_state.update({
                "study_queue": list(ks),
                "study_show_answer": False,
                "study_done_count": 0,
                "study_initial_total": len(ks),
                "last_xp_event": None,
                "session_notice": notice,
                "dragon_event": "none",
                "dragon_activity": random.choice(["sleep", "fly", "fight_rock"]),
            })
            st.rerun()

    st.markdown("---")
    if st.session_state.study_queue:
        card = st.session_state.study_queue[0]
        rest, done = len(st.session_state.study_queue), st.session_state.study_done_count
        st.progress(done / max(1, done + rest), text=f"Fortschritt: {done} abgeschlossen · {rest} verbleibend")

        is_new = int(card.get("success_count") or 0) == 0
        sim_s = a_str + 1
        sb_prev = 2 if (sim_s >= 20 and (b20 is None or (now_utc - b20).total_seconds() < 1800)) else (1 if (sim_s >= 10 and (b10 is None or (now_utc - b10).total_seconds() < 1800)) else 0)
        disp_t = "Problemstellung" if card["card_type"] == "Transfer" else card["card_type"]
        badges = f'<span class="flashcard-badge">{html.escape(str(card["folder_name"]))} · {html.escape(disp_t)}</span><span class="flashcard-badge-xp">+{(2 if is_new else 1) + sb_prev} XP · +1 🍖 bei Erfolg</span>'
        if int(card.get("lapses") or 0) > 0:
            badges += f'<span class="flashcard-badge-warn">Wiederholung ({card["lapses"]}× falsch)</span>'
        st.markdown(f'<div class="flashcard-box"><div class="flashcard-meta">{badges}</div><div class="flashcard-question">{fmt_card_html(card["question"], disp_t=="Lückentext")}</div></div>', unsafe_allow_html=True)

        mc_opts = []
        if card["card_type"] == "Multiple Choice":
            try: mc_opts = json.loads(card.get("options_json") or "[]")
            except Exception: mc_opts = []
        picked = st.radio("Wähle eine der 4 Antwortoptionen:", mc_opts, key=f"mc_{card['id']}_{done}") if mc_opts else None

        if not st.session_state.study_show_answer:
            if st.button("Antwort aufdecken", use_container_width=True):
                st.session_state.study_show_answer = True; st.session_state.dragon_event = "none"; st.session_state.session_notice = None; st.rerun()
        else:
            if mc_opts and picked is not None:
                if picked.strip().lower() == card["answer"].strip().lower(): st.success("Richtig ausgewählt!")
                else: st.error(f"Deine Auswahl: **{picked}** — leider nicht richtig.")
            expl = str(card.get("explanation") or "").strip()
            expl_h = f'<div class="flashcard-explanation">💡 {fmt_card_html(expl)}</div>' if expl else ""
            st.markdown(f'<div class="flashcard-box" style="border-color:#7DD3FC"><div class="flashcard-answer-label">Lösung</div><div class="flashcard-answer-body">{fmt_card_html(card["answer"])}</div>{expl_h}</div>', unsafe_allow_html=True)

            st.caption("Wie gut konntest du die Aufgabe lösen?")
            b1, b2, b3, b4 = st.columns(4)
            rated = None
            if b1.button(f"❌ Nochmal · 🔥 Baum\n({iv_label(card['ease_factor'], card['interval_days'], card['repetitions'], card['lapses'], 1)})", use_container_width=True): rated = 1
            if b2.button(f"🟠 Schwer · +1 🍖\n({iv_label(card['ease_factor'], card['interval_days'], card['repetitions'], card['lapses'], 2)})", use_container_width=True): rated = 2
            if b3.button(f"🔵 Gut · +1 🍖 · +Serie\n({iv_label(card['ease_factor'], card['interval_days'], card['repetitions'], card['lapses'], 3)})", use_container_width=True): rated = 3
            if b4.button(f"🟢 Leicht · +1 🍖 · +Serie\n({iv_label(card['ease_factor'], card['interval_days'], card['repetitions'], card['lapses'], 4)})", use_container_width=True): rated = 4

            if rated is not None:
                ef, iv, reps, lapses, nrev = sm2(card["ease_factor"], card["interval_days"], card["repetitions"], card["lapses"], rated)
                ok = rated in (2, 3, 4)
                old_sc = int(card.get("success_count") or 0)
                finished = st.session_state.study_queue.pop(0)
                if random.random() < 0.35:
                    st.session_state.dragon_activity = random.choice(["sleep", "fly", "fight_rock"])
                st.session_state.last_xp_event = process_rating_instant(finished, rated, ef, iv, reps, lapses, nrev, old_sc + (1 if ok else 0), ok, ok and old_sc == 0)
                st.session_state.session_notice = None
                if rated == 1: st.session_state.study_queue.insert(min(2, len(st.session_state.study_queue)), finished)
                else: st.session_state.study_done_count += 1
                st.session_state.study_show_answer = False
                st.rerun()
    else:
        if st.session_state.study_initial_total > 0 and st.session_state.study_done_count > 0:
            st.success(f"Stark! Alle {st.session_state.study_done_count} Karten dieser Sitzung abgeschlossen.")
        elif tot_cards == 0:
            st.info("Erstelle unter **Dokumente & Kartengenerator** deinen ersten Ordner und lade ein Skript hoch.")
        else:
            st.info("Wähle oben deinen Ordner und klicke auf **▶ Sitzung starten** (auch nicht-fällige Ordner starten direkt als freie Übungsrunde).")

with t_up:
    st.markdown('<div class="ar-subtitle">1. Zielordner auswählen oder neu anlegen</div>', unsafe_allow_html=True)
    cn1, cn2 = st.columns([3.5, 1])
    new_fn = cn1.text_input("Ordner", label_visibility="collapsed", placeholder="Neuen Ordnernamen eingeben (z. B. Makroökonomie, BGB AT)...")
    if cn2.button("➕ Ordner erstellen", use_container_width=True):
        if new_fn.strip():
            if create_folder(new_fn): st.success(f"Ordner **{new_fn.strip()}** erstellt!"); st.rerun()
            else: st.warning("Dieser Ordner existiert bereits.")
    folders = get_folders()
    if folders:
        fmap = {o["name"]: o["id"] for o in folders}
        z_name = st.selectbox("Zielordner", list(fmap.keys()))
        st.markdown('<div class="ar-subtitle">2. Dokumente hochladen & Lernkarten erstellen</div>', unsafe_allow_html=True)
        ups = st.file_uploader("Dokumente (PDF, DOCX, TXT, MD)", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True)
        co1, co2 = st.columns([1, 2])
        k_cnt = co1.slider("Karten pro Dokument", 4, 24, 8)
        k_typs = co2.multiselect("Aufgaben-Mix", ["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"], default=["Lückentext", "Problemstellung", "Multiple Choice", "Klassisch"])
        if st.button("⚡ Abwechslungsreiche Lernkarten generieren", use_container_width=True):
            if ups and k_typs:
                tot_new = 0
                for f in ups:
                    with st.spinner(f"Erstelle Karten aus '{f.name}'..."):
                        try:
                            tx = extract_text(f)
                            if len(tx) < 40: st.warning(f"Kaum Text in '{f.name}'."); continue
                            nc = generate_cards(tx, k_cnt, k_typs)
                            save_doc_and_cards(fmap[z_name], f.name, len(tx), nc, tx)
                            tot_new += len(nc)
                        except Exception as e: st.error(f"Fehler bei '{f.name}': {e}")
                if tot_new > 0: st.success(f"{tot_new} Karten in **{z_name}** gespeichert!"); st.rerun()

with t_mgr:
    if not folders:
        st.info("Noch keine Ordner vorhanden.")
    else:
        vmap = {f"{o['name']} ({o['total_cards']} Karten · {o['doc_count']} Dokumente)": o for o in folders}
        cur_o = vmap[st.selectbox("Ordner inspizieren", list(vmap.keys()))]
        st.markdown(topic_bar_html(cur_o), unsafe_allow_html=True)
        st.markdown('<div class="ar-subtitle">Dokumente</div>', unsafe_allow_html=True)
        for d in load_docs(cur_o["id"]):
            st.markdown(f"- **{d['filename']}** ({d['card_count']} Karten · {d['uploaded_at'].astimezone(BERLIN_TZ).strftime('%d.%m.%Y %H:%M')})")
        st.markdown("---")
        st.markdown('<div class="ar-subtitle">Karteikarten & Anki-Status</div>', unsafe_allow_html=True)
        flt = st.radio("Filter:", ["Alle", "🔵 Gut gelernt", "🟡 Wackelig", "🔴 Kritisch", "⚫ Ungelernt"], horizontal=True)
        f_key = {"🔵 Gut gelernt": "gut", "🟡 Wackelig": "wackelig", "🔴 Kritisch": "kritisch", "⚫ Ungelernt": "neu"}
        b_lbl = {"gut": "🔵 Gut", "wackelig": "🟡 Wackelig", "kritisch": "🔴 Kritisch", "neu": "⚫ Neu"}
        now_u = datetime.datetime.now(datetime.timezone.utc)
        for k in load_cards(cur_o["id"], "all"):
            kat = anki_cat(k)
            if flt != "Alle" and kat != f_key[flt]: continue
            st_t = "Jetzt fällig" if k["next_review"] <= now_u else f"Fällig {k['next_review'].astimezone(BERLIN_TZ).strftime('%d.%m.%Y')}"
            with st.expander(f"{b_lbl[kat]} · [{k['card_type']}] {k['question'][:78]} ({st_t})"):
                st.markdown(f"**Frage:** {k['question']}\n\n**Antwort:** {k['answer']}")
                if k.get("explanation"): st.caption(f"Erklärung: {k['explanation']}")
                if st.button("Karte löschen", key=f"dk_{k['id']}"): delete_card(k["id"]); st.rerun()
        st.markdown("---")
        with st.expander("Gefahrenzone: Ordner löschen"):
            if st.button(f"Ordner '{cur_o['name']}' endgültig löschen", key=f"df_{cur_o['id']}"):
                delete_folder(cur_o["id"]); st.rerun()
