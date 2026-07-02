# ruff: noqa
"""
Family Emergency Drill - FastAPI Web Dashboard
Run: uv run uvicorn app.web_dashboard:dashboard_app --host 127.0.0.1 --port 8090 --reload
Pages:
  GET /         - Home: recent drills + system status
  GET /profile  - Family profile viewer / editor
  GET /history  - Emergency history log
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

dashboard_app = FastAPI(title="Family Emergency Drill Dashboard", version="1.0.0")

BASE_DIR = Path(__file__).parent.parent
HISTORY_FILE = BASE_DIR / "emergency_history.json"
PROFILE_FILE  = BASE_DIR / "family_profile.json"
AUDIT_FILE    = BASE_DIR / "audit_log.json"

def _read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _default_profile():
    return {
        "family_name": "Rahman Family",
        "city": "Karachi",
        "home_address": "House 45-B, Street 3, PECHS, Karachi",
        "primary_contact_name": "Kamran Rahman (Father)",
        "primary_contact_phone": "0300-9876543",
        "secondary_contact_name": "Ayesha Rahman (Mother)",
        "secondary_contact_phone": "0333-1234567",
        "nearest_hospital_name": "Aga Khan University Hospital",
        "nearest_hospital_phone": "021-111-911-911",
    }

STYLE = """<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--accent:#58a6ff;--green:#3fb950;
      --red:#f85149;--orange:#d29922;--text:#e6edf3;--muted:#8b949e}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:15px;line-height:1.6}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
nav{background:var(--card);border-bottom:1px solid var(--border);padding:12px 32px;display:flex;align-items:center;gap:24px}
nav .logo{font-weight:700;font-size:18px;color:var(--text)}
nav .logo span{color:var(--accent)}
nav a{color:var(--muted);font-size:14px;padding:4px 10px;border-radius:6px;transition:background .2s}
nav a:hover,nav a.active{background:#21262d;color:var(--text);text-decoration:none}
.container{max-width:1100px;margin:32px auto;padding:0 24px}
h1{font-size:24px;font-weight:600;margin-bottom:8px}
h2{font-size:18px;font-weight:600;margin-bottom:16px;color:var(--accent)}
.subtitle{color:var(--muted);font-size:14px;margin-bottom:32px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:24px;margin-bottom:20px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 24px}
.stat-num{font-size:32px;font-weight:700;color:var(--accent)}
.stat-label{color:var(--muted);font-size:13px;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:500;padding:8px 12px;border-bottom:1px solid var(--border)}
td{padding:10px 12px;border-bottom:1px solid #21262d}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;text-transform:uppercase}
.badge-critical{background:#3d1a1a;color:#f85149}
.badge-high{background:#2d2009;color:#d29922}
.badge-medium{background:#1a2d1a;color:#3fb950}
.badge-low{background:#152030;color:#58a6ff}
.badge-fire{background:#3d1a1a;color:#f85149}
.badge-gas{background:#2d2009;color:#d29922}
.badge-medical{background:#152030;color:#58a6ff}
.badge-electrical{background:#2a1a3d;color:#bc8cff}
.badge-default{background:#21262d;color:#8b949e}
form label{display:block;color:var(--muted);font-size:13px;margin-bottom:4px;margin-top:16px}
form input[type=text]{width:100%;background:#0d1117;border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px 12px;font-size:14px}
form input[type=text]:focus{outline:none;border-color:var(--accent)}
.btn{display:inline-block;background:var(--accent);color:#0d1117;font-weight:600;padding:9px 20px;border-radius:6px;border:none;cursor:pointer;font-size:14px;margin-top:20px;transition:opacity .2s}
.btn:hover{opacity:.85}
.alert-ok{background:#162316;border:1px solid #3fb950;color:#3fb950;padding:10px 16px;border-radius:6px;margin-bottom:20px;font-size:14px}
.empty{color:var(--muted);text-align:center;padding:40px;font-size:14px}
.ts{color:var(--muted);font-size:12px}
</style>"""

def _nav(active):
    pages = [("/","Home"),("/profile","Profile"),("/history","History")]
    links = ""
    for h,l in pages:
        cls = "active" if h==active else ""
        links += f'<a href="{h}" class="{cls}">{l}</a>'
    return f'<nav><span class="logo">Emergency <span>Drill</span></span>{links}</nav>'

def _sev_badge(s):
    cls = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(s.upper(),"default")
    return f'<span class="badge badge-{cls}">{s}</span>'

def _cat_badge(c):
    cls = {"FIRE":"fire","GAS_LEAK":"gas","MEDICAL":"medical","ELECTRICAL":"electrical"}.get(c.upper(),"default")
    icon = {"FIRE":"Fire","GAS_LEAK":"Gas","MEDICAL":"Medical","ELECTRICAL":"Electric","CHILD_ALONE":"Child","FLOOD":"Flood","EARTHQUAKE":"Quake"}.get(c.upper(),"Alert")
    return f'<span class="badge badge-{cls}">{icon}: {c}</span>'

@dashboard_app.get("/", response_class=HTMLResponse)
async def home():
    history = _read_json(HISTORY_FILE, [])
    audit   = _read_json(AUDIT_FILE, [])
    profile = _read_json(PROFILE_FILE, _default_profile())
    total   = len(history)
    crithigh = sum(1 for e in history if e.get("severity","").upper() in ("CRITICAL","HIGH"))
    cats = {}
    for e in history:
        c = e.get("category","UNKNOWN"); cats[c] = cats.get(c,0)+1
    top_cat = max(cats, key=cats.get) if cats else "None yet"
    recent = list(reversed(history))[:5]
    rows = "".join(
        f"<tr><td>{_cat_badge(e.get('category','?'))}</td><td>{_sev_badge(e.get('severity','?'))}</td><td class='ts'>{e.get('timestamp','')[:19].replace('T',' ')}</td></tr>"
        for e in recent
    ) or "<tr><td colspan='3' class='empty'>No drills yet. Test your agent at <a href='http://127.0.0.1:18081' target='_blank'>localhost:18081</a></td></tr>"
    ai = len([a for a in audit if a.get("severity")=="INFO"])
    aw = len([a for a in audit if a.get("severity")=="WARNING"])
    ac = len([a for a in audit if a.get("severity")=="CRITICAL"])
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Emergency Drill Dashboard</title>{STYLE}</head><body>
{_nav("/")}
<div class="container">
<h1>Emergency Drill Dashboard</h1>
<p class="subtitle">Family: <strong>{profile.get('family_name','?')}</strong> | City: {profile.get('city','?')} | <a href="http://127.0.0.1:18081" target="_blank">Open Playground</a></p>
<div class="grid-3">
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Total Drills Run</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--red)">{crithigh}</div><div class="stat-label">Critical / High Severity</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--green);font-size:20px">{top_cat}</div><div class="stat-label">Most Common Emergency</div></div>
</div>
<div class="card"><h2>Recent Drills</h2>
<table><thead><tr><th>Category</th><th>Severity</th><th>Time</th></tr></thead>
<tbody>{rows}</tbody></table>
<div style="margin-top:12px"><a href="/history">View full history</a></div></div>
<div class="card"><h2>Audit Log Summary</h2>
<div class="grid-3" style="margin-bottom:0">
  <div class="stat"><div class="stat-num" style="color:var(--green)">{ai}</div><div class="stat-label">INFO events</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--orange)">{aw}</div><div class="stat-label">WARNING events</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--red)">{ac}</div><div class="stat-label">CRITICAL events</div></div>
</div></div>
</div></body></html>"""
    return HTMLResponse(html)

@dashboard_app.get("/profile", response_class=HTMLResponse)
async def profile_page(saved: str = ""):
    profile = _read_json(PROFILE_FILE, _default_profile())
    alert = '<div class="alert-ok">Profile saved successfully!</div>' if saved=="1" else ""
    def fi(name, label, val):
        return f'<label>{label}</label><input type="text" name="{name}" value="{val}">'
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Family Profile</title>{STYLE}</head><body>
{_nav("/profile")}
<div class="container">
<h1>Family Profile</h1>
<p class="subtitle">Personalise your emergency plans. Stored locally, never shared.</p>
{alert}
<div class="card"><h2>Edit Profile</h2>
<form method="POST" action="/profile">
{fi("family_name","Family Name",profile.get("family_name",""))}
{fi("city","City",profile.get("city",""))}
{fi("home_address","Home Address",profile.get("home_address",""))}
{fi("primary_contact_name","Primary Contact Name",profile.get("primary_contact_name",""))}
{fi("primary_contact_phone","Primary Contact Phone",profile.get("primary_contact_phone",""))}
{fi("secondary_contact_name","Secondary Contact Name",profile.get("secondary_contact_name",""))}
{fi("secondary_contact_phone","Secondary Contact Phone",profile.get("secondary_contact_phone",""))}
{fi("nearest_hospital_name","Nearest Hospital",profile.get("nearest_hospital_name",""))}
{fi("nearest_hospital_phone","Hospital Phone",profile.get("nearest_hospital_phone",""))}
<button type="submit" class="btn">Save Profile</button>
</form></div></div></body></html>"""
    return HTMLResponse(html)

@dashboard_app.post("/profile")
async def save_profile(
    family_name: str = Form(""), city: str = Form(""),
    home_address: str = Form(""),
    primary_contact_name: str = Form(""), primary_contact_phone: str = Form(""),
    secondary_contact_name: str = Form(""), secondary_contact_phone: str = Form(""),
    nearest_hospital_name: str = Form(""), nearest_hospital_phone: str = Form(""),
):
    _write_json(PROFILE_FILE, {
        "family_name": family_name, "city": city, "home_address": home_address,
        "primary_contact_name": primary_contact_name, "primary_contact_phone": primary_contact_phone,
        "secondary_contact_name": secondary_contact_name, "secondary_contact_phone": secondary_contact_phone,
        "nearest_hospital_name": nearest_hospital_name, "nearest_hospital_phone": nearest_hospital_phone,
    })
    return RedirectResponse(url="/profile?saved=1", status_code=303)

@dashboard_app.get("/history", response_class=HTMLResponse)
async def history_page():
    history = list(reversed(_read_json(HISTORY_FILE, [])))
    rows = "".join(
        f"<tr><td>{i+1}</td><td>{_cat_badge(e.get('category','?'))}</td><td>{_sev_badge(e.get('severity','?'))}</td>"
        f"<td class='ts'>{e.get('profile_id','?')}</td>"
        f"<td class='ts'>{e.get('timestamp','')[:19].replace('T',' ')}</td>"
        f"<td><span class='badge badge-medium'>{e.get('status','?')}</span></td></tr>"
        for i,e in enumerate(history)
    ) or "<tr><td colspan='6' class='empty'>No events logged yet. Run a drill first.</td></tr>"
    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Emergency History</title>{STYLE}</head><body>
{_nav("/history")}
<div class="container">
<h1>Emergency History</h1>
<p class="subtitle">{len(history)} total events logged. PII is never stored here.</p>
<div class="card"><h2>All Events</h2>
<table><thead><tr><th>#</th><th>Category</th><th>Severity</th><th>Profile ID</th><th>Timestamp</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</div></body></html>"""
    return HTMLResponse(html)
