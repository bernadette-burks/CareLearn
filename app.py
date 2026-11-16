from __future__ import annotations

import csv
import io
import json
import os
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8765"))

# Fictional, de-identified teaching data. No patient information is persisted.
SAMPLES = [
    {"id": "E-1001", "staff": "Nurse A", "patient_ref": "SYN-001", "chart_status": "closed", "category": "common_typo", "risk": "low", "description": "Repeated misspelling of 'crackles' in a respiratory assessment.", "confirmed": True},
    {"id": "E-1002", "staff": "Nurse A", "patient_ref": "SYN-002", "chart_status": "closed", "category": "common_typo", "risk": "low", "description": "Repeated misspelling of 'crackles' in a respiratory assessment.", "confirmed": True},
    {"id": "E-1003", "staff": "Nurse A", "patient_ref": "SYN-003", "chart_status": "closed", "category": "common_typo", "risk": "low", "description": "Repeated misspelling of 'crackles' in a respiratory assessment.", "confirmed": True},
    {"id": "E-2001", "staff": "Nurse B", "patient_ref": "SYN-004", "chart_status": "closed", "category": "vital_unit_mismatch", "risk": "medium", "description": "Temperature value and documented unit appear inconsistent.", "confirmed": True},
    {"id": "E-3001", "staff": "Nurse C", "patient_ref": "SYN-005", "chart_status": "closed", "category": "critical_vital_mismatch", "risk": "high", "description": "Critical vital sign value requires immediate clinical review.", "confirmed": True},
    {"id": "E-4001", "staff": "Nurse D", "patient_ref": "SYN-006", "chart_status": "open", "category": "narrative_mismatch", "risk": "medium", "description": "Draft note and structured result may not agree.", "confirmed": True},
]

STATE = {"events": [dict(x) for x in SAMPLES], "analyses": [], "audit": [], "disputes": [], "thresholds": {"low": 3, "medium": 2, "high": 1}, "training_data": "Built-in synthetic sample", "last_result": None}
LOCK = threading.RLock()

PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CareLearn · Agent workspace</title>
<style>
:root{--ink:#142b4d;--muted:#5f7189;--line:#d7e2f2;--paper:#f1f5fb;--white:#fff;--teal:#2878f0;--teal-dark:#1553b4;--blue:#eaf2ff;--red:#c7354a;--amber:#94600c;--green:#215fbd;--shadow:0 5px 20px rgba(22,54,67,.045)}*{box-sizing:border-box}html,body{height:100%;margin:0}body{background:var(--paper);color:var(--ink);font:14px/1.45 Inter,"Aptos",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:-.01em}header{height:68px;background:#122b55;color:#fff;display:flex;align-items:center;gap:12px;padding:0 max(20px,calc((100vw - 1480px)/2))}.brand-mark{position:relative;width:37px;height:37px;display:grid;place-items:center;border:1px solid #42659b;background:#1b3768;border-radius:12px;color:#77b2ff}.heart-mark{position:absolute;right:-3px;bottom:-2px;width:13px;height:13px;color:#ff4f68;filter:drop-shadow(0 1px 1px #132b53)}header h1{font-size:19px;line-height:1.1;margin:0;font-weight:720;letter-spacing:-.03em}header p{font-size:12px;margin:4px 0 0;color:#b8cdd1}.head-tag{margin-left:auto;border:1px solid #44626b;color:#cee1e3;border-radius:20px;padding:5px 10px;font-size:11px}.shell{height:calc(100vh - 68px);max-width:1600px;margin:auto;padding:12px 18px 14px;display:grid;grid-template-columns:minmax(0,1.7fr) minmax(390px,.95fr);gap:14px;overflow:hidden}.left-pane,.right-pane{min-height:0;display:flex;flex-direction:column;gap:9px}.left-pane{display:grid;grid-template-rows:auto auto minmax(130px,1fr) minmax(128px,.9fr)}.notice{flex:none;display:flex;align-items:center;gap:10px;background:#eaf2ff;border:1px solid #cfddf7;border-radius:10px;padding:9px 12px;color:#294b78;font-size:12px}.notice svg{flex:none;color:var(--teal)}.notice b{color:#153d78}.setup-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;flex:none}.card{background:var(--white);border:1px solid var(--line);border-radius:12px;padding:13px 14px;box-shadow:var(--shadow);min-width:0}.card-head{display:flex;align-items:center;gap:9px;margin:0 0 8px}.card h2{margin:0;font-size:14px;font-weight:720;letter-spacing:-.015em}.step-icon{width:27px;height:27px;display:grid;place-items:center;background:#eaf2ff;border-radius:8px;color:var(--teal);flex:none}.step-icon svg{width:15px;height:15px}.step-label{color:var(--teal);font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.desc{font-size:11.5px;color:var(--muted);margin:0 0 9px;line-height:1.4}.row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}button,.button{display:inline-flex;align-items:center;justify-content:center;gap:6px;background:var(--teal);border:0;border-radius:7px;color:white;padding:7px 10px;font:inherit;font-size:11.5px;font-weight:690;cursor:pointer;white-space:nowrap}button svg{width:14px;height:14px}button:hover{background:var(--teal-dark)}button.secondary{background:#edf3ff;color:#234575;border:1px solid #d6e2f8}button.secondary:hover{background:#e1ebfb}select,input,textarea{min-width:0;border:1px solid #cbd9de;border-radius:7px;padding:7px 9px;background:white;color:var(--ink);font:inherit;font-size:11.5px}select{flex:1}input[type=file]{width:100%;font-size:10px;padding:5px}.csv-area{border-top:1px solid #edf1f2;margin-top:9px;padding-top:8px}.muted,.hint{color:var(--muted)}.hint{font-size:10.5px}details{margin-top:6px}summary{cursor:pointer}.pill{display:inline-flex;align-items:center;border-radius:20px;padding:2px 7px;font-size:10px;font-weight:750;background:#edf1f2}.low{color:var(--green);background:#e8f0ff}.medium{color:var(--amber);background:#fff2d8}.high{color:var(--red);background:#fae8e7}.events-card{flex:initial;min-height:0;display:flex;flex-direction:column;padding:12px 13px}.events-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:7px;flex:none}.events-title h2{font-size:13px}.count{font-size:10px;color:var(--muted);background:#f0f5f6;border-radius:20px;padding:3px 8px}.tablewrap{overflow:auto;min-height:0;flex:1}table{width:100%;border-collapse:collapse;font-size:11px}th,td{text-align:left;border-bottom:1px solid #edf1f2;padding:6px 7px;vertical-align:middle}th{position:sticky;top:0;background:#f7f9fa;color:#71828a;font-size:9px;text-transform:uppercase;letter-spacing:.06em;z-index:1}td.desc-col{max-width:220px;color:#526772}td button{padding:4px 7px;font-size:10px}.right-pane{overflow:hidden;padding:0;display:flex;align-items:center;justify-content:center;background:#e9effa;border:1px solid #d6e1f2;border-radius:15px;padding:18px}.result-card{flex:none;background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 14px;box-shadow:var(--shadow)}.result-card h2{font-size:14px;margin:0 0 8px}.actions{display:flex;gap:7px;margin-bottom:9px}.summary{font-size:12px;padding:9px 10px;border-radius:8px;background:#f1f6ff;color:#405b7e}.summary p{margin:4px 0}.summary .status{font-size:12px;font-weight:750}.status.ok{color:var(--green)}.status.err{color:var(--red)}.summary-meta{font-size:10px;color:var(--muted)}.trace-card{flex:none;min-height:0;height:100%;overflow:auto;padding:10px 12px}.trace-card p{font-size:10.5px;margin:4px 0 8px}.trace-list{margin:0;padding:0;list-style:none;display:grid;gap:5px}.trace-list li{display:grid;grid-template-columns:24px 1fr;gap:7px;align-items:start;font-size:11px}.trace-num{display:grid;place-items:center;width:21px;height:21px;background:#eaf2ff;color:#2469cd;border-radius:7px;font-weight:750;font-size:10px}.trace-list b{font-size:10.5px;color:#274854}.trace-list span{color:#647983}.trace-list .trace-copy{padding-top:1px}.trace-empty{font-size:11px;color:var(--muted);padding:7px;background:#f2f6fc;border-radius:8px}.bottom-grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr) minmax(0,1fr);gap:9px;min-height:0;overflow:hidden}.mini-card{min-height:0;height:100%;max-height:none;overflow:auto;padding:11px 12px}.mini-card h2{font-size:12px;margin:0 0 7px}.mini-card p{font-size:10px;margin:4px 0}.mini-card table{font-size:10px}.mini-card ol{padding-left:16px;margin:4px 0}.mini-card li{font-size:10px;padding:2px 0}.empty{color:var(--muted);font-size:11px;padding:8px;background:#f7f9fa;border-radius:7px}.mono{font:9px ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-word}.danger{color:var(--red)}details p{margin:6px 0 0}.decision-detail{font-size:10px;margin-top:5px}.decision-detail p{margin:4px 0}.toast{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);padding:8px 12px;background:#173941;color:white;border-radius:8px;font-size:11px;box-shadow:var(--shadow);display:none}.toast.show{display:block}@media(max-width:1100px) and (min-width:881px){.shell{grid-template-columns:minmax(0,1.5fr) minmax(330px,1fr);padding:10px;gap:10px}.left-pane{grid-template-rows:auto auto minmax(120px,1fr) minmax(120px,.9fr)}.setup-grid{gap:7px}.demo-scene{transform:scale(1.2);width:83.3%;height:83.3%}.desc{font-size:10.5px}.card{padding:11px}.tablewrap table{font-size:10px}}@media(max-width:880px){html,body{height:auto;min-height:100%}header{height:62px;padding:0 14px}.head-tag{font-size:9px}.shell{height:auto;min-height:calc(100vh - 62px);display:flex;flex-direction:column;overflow:visible;padding:10px}.left-pane{display:flex}.right-pane{min-height:340px}.bottom-grid{grid-template-columns:1fr}.trace-card{min-height:140px}.mini-card{min-height:100px;height:auto}.demo-player{max-height:none;aspect-ratio:1.58}.demo-scene{transform:scale(1.2);width:83.3%;height:83.3%}.left-pane,.right-pane{overflow:visible}.setup-grid{grid-template-columns:1fr}.events-card{min-height:260px;max-height:360px}.right-pane{padding:0}.bottom-grid{grid-template-columns:1fr}.tablewrap{overflow:auto}.notice{align-items:flex-start}}

.demo-card{flex:none;width:100%;max-width:650px;padding:16px;border-color:#d5e1f4}.demo-scene{transform:scale(1.3);transform-origin:top left;width:77%;height:77%}.demo-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.demo-title h2{font-size:13px;margin:0}.demo-tag{font-size:9px;color:#617784;background:#eef3f5;border-radius:20px;padding:4px 8px}.demo-player{width:100%;height:auto;aspect-ratio:1.58;max-height:min(58vh,500px);position:relative;overflow:hidden;border-radius:10px;background:linear-gradient(135deg,#dce8e9,#c9d8dc);padding:9px 15px 13px}.demo-screen{height:100%;position:relative;overflow:hidden;border:5px solid #18272d;border-bottom-width:8px;border-radius:9px 9px 5px 5px;background:#edf2f5}.demo-scene{position:absolute;inset:0}.nurse-scene{animation:nurseScene 20s linear infinite}.supervisor-scene{opacity:0;animation:supervisorScene 20s linear infinite}.demo-browser{height:15px;background:#17335f;color:#e5edff;display:flex;align-items:center;gap:4px;padding:0 7px;font-size:7px}.demo-browser i{width:5px;height:5px;border-radius:50%;background:#91aaaf}.demo-top{height:20px;background:#2878f0;color:white;display:flex;align-items:center;justify-content:space-between;padding:0 8px;font-size:8px;font-weight:700}.demo-top small{font-size:6px;font-weight:500}.brand-in-sim{display:flex;align-items:center;gap:4px;color:#fff;font-size:8px;font-weight:800}.brand-in-sim svg{width:15px;height:15px;flex:none}.demo-layout{height:calc(100% - 35px);display:grid;grid-template-columns:22% 78%;font-size:7px;color:#243d49}.demo-nav{background:#f7f9fa;border-right:1px solid #d1dce0;padding:6px;line-height:2.1}.demo-nav b{display:block;color:#2878f0}.demo-content{position:relative;padding:6px 8px;overflow:hidden}.demo-patient{display:flex;justify-content:space-between;border-bottom:1px solid #d5e0e3;padding-bottom:4px;margin-bottom:4px}.demo-patient strong{font-size:8px}.demo-label{font-size:6px;color:#60747e}.demo-vitals{display:flex;gap:4px;margin:4px 0}.demo-vitals span{background:#f3f7f8;border:1px solid #dde6e9;border-radius:3px;padding:3px 4px}.demo-vitals b{font-size:8px}.demo-note{height:36px;border:1px solid #bfd2da;border-radius:4px;background:white;margin-top:4px;padding:4px;font-size:7px}.demo-note small{font-size:6px;color:#627985}.demo-error{color:#a83b36;font-weight:800;animation:typedPulse 1.2s step-end infinite}.low-entry{animation:lowEntry 20s linear infinite}.high-entry{opacity:0;animation:highEntry 20s linear infinite}.nurse-high-alert{width:72%;animation:nurseHighPopup 20s linear infinite;border-left:3px solid #c43f39}.demo-alert{position:absolute;right:5px;bottom:6px;width:68%;display:flex;gap:6px;background:white;border-radius:6px;padding:7px;box-shadow:0 4px 14px #132d3b48;z-index:3;font-size:7px;line-height:1.35;opacity:0}.low-alert{animation:lowPopup 20s linear infinite;border-left:3px solid #2878f0;background:linear-gradient(120deg,#fff 0%,#f4f8ff 100%)}.high-alert{animation:highPopup 20s linear infinite;border-left:3px solid #c43f39}.demo-alert b{font-size:8px;color:#213e49}.demo-alert small{font-size:7px;color:#5c727e}.tip-brain{width:27px;height:27px;display:grid;place-items:center;flex:none;border-radius:9px;background:#eaf2ff;color:#2878f0}.tip-brain svg{width:22px;height:22px}.demo-alert .alert-mark{width:17px;height:17px;display:grid;place-items:center;flex:none;border-radius:50%;background:#e8f0ff;color:#2166cf;font-weight:900}.high-alert .alert-mark{background:#fae8e7;color:#b93834}.supervisor-scene .demo-top{background:#173b75}.supervisor-scene .demo-nav b{color:#2878f0}.super-row{display:flex;justify-content:space-between;border:1px solid #e2e8eb;background:white;border-radius:4px;padding:5px;margin-top:4px;font-size:7px}.urgent{color:#ad3532;font-weight:800}.review-btn{display:inline-block;background:#a93531;color:white;padding:3px 5px;border-radius:3px;font-size:6px;margin-top:4px}.demo-stage{position:absolute;left:18px;bottom:3px;z-index:5;font-size:7px;font-weight:800;color:#3f5c65}.stage-nurse{animation:nurseScene 20s linear infinite}.stage-supervisor{opacity:0;animation:supervisorScene 20s linear infinite}.demo-controls{display:flex;align-items:center;gap:7px;margin-top:6px}.demo-controls button{padding:5px 8px;font-size:10px}.demo-controls span{margin-left:auto;font-size:9px;color:#617784}.demo-player.paused .demo-scene,.demo-player.paused .demo-alert,.demo-player.paused .demo-error,.demo-player.paused .low-entry,.demo-player.paused .high-entry{animation-play-state:paused!important}@keyframes nurseScene{0%,43%{opacity:1}49%,100%{opacity:0}}@keyframes supervisorScene{0%,47%{opacity:0}54%,100%{opacity:1}}@keyframes lowPopup{0%,11%{opacity:0;transform:translateY(5px)}15%,32%{opacity:1;transform:translateY(0)}38%,100%{opacity:0;transform:translateY(4px)}}@keyframes highPopup{0%,62%{opacity:0;transform:translateY(5px)}68%,92%{opacity:1;transform:translateY(0)}100%{opacity:0}}@keyframes typedPulse{50%{opacity:.45}}@keyframes lowEntry{0%,34%{opacity:1}39%,100%{opacity:0}}@keyframes highEntry{0%,35%{opacity:0}39%,44%{opacity:1}48%,100%{opacity:0}}@keyframes nurseHighPopup{0%,37%{opacity:0;transform:translateY(5px)}40%,44%{opacity:1;transform:translateY(0)}48%,100%{opacity:0}}@media(max-height:760px) and (min-width:881px){.demo-player{height:178px}}

/* Let the demonstration own the full right-hand column. */
.right-pane{padding:12px!important;align-items:stretch!important;justify-content:stretch!important}
.right-pane .demo-card{width:100%;max-width:none;height:100%;min-height:0;display:flex;flex:1;flex-direction:column;justify-content:center;gap:12px;padding:20px;background:#fff;overflow:hidden}
.right-pane .demo-title{flex:none;margin:0}
.right-pane .demo-player{flex:1;min-height:0;width:100%;height:auto;max-height:none;aspect-ratio:auto;padding:12px 18px 19px;display:block}
.right-pane .demo-screen{width:100%;height:100%;max-height:none;aspect-ratio:auto}
@media(max-width:880px){.right-pane{padding:10px!important}.right-pane .demo-card{height:auto;min-height:460px;flex:none;padding:15px}.right-pane .demo-player{height:300px;min-height:300px;flex:none}}
</style></head><body><header><div class="brand-mark"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a4 4 0 0 0-7 2.7A4.5 4.5 0 0 0 4 14a4 4 0 0 0 5.5 5.7A3.5 3.5 0 0 0 12 21z"/><path d="M12 3a4 4 0 0 1 7 2.7A4.5 4.5 0 0 1 20 14a4 4 0 0 1-5.5 5.7A3.5 3.5 0 0 1 12 21zM8 8c2 0 2 2 4 2s2-2 4-2M8 15c2 0 2-2 4-2s2 2 4 2M12 3v18"/></svg><svg class="heart-mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21s-7-4.4-9-8.7C1.4 8.5 3.2 5 6.7 5c2.1 0 3.4 1.2 4.3 2.4C11.9 6.2 13.2 5 15.3 5 18.8 5 20.6 8.5 19 12.3 17 16.6 12 21 12 21z"/></svg></div><div><h1>CareLearn</h1><p>Risk-based documentation learning agent</p></div><span class="head-tag">CLASSROOM PROTOTYPE</span></header>
<main class="shell"><div class="left-pane">
<div class="notice"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg><span><b>Synthetic data only.</b> Not for PHI, patient care, or personnel evaluation. Runs locally; state is held in memory.</span></div>
<div class="setup-grid"><section class="card"><div class="card-head"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16M4 12h16M4 19h9"/><circle cx="18" cy="19" r="2"/></svg></span><div><span class="step-label">Step 1</span><h2>Choose or import data</h2></div></div><p class="desc">Load a fictional scenario or import labeled examples to demonstrate adaptation.</p><div class="row"><select id="sample"><option value="all">All synthetic examples</option><option value="low">Low risk · repeated typo</option><option value="medium">Medium risk · unit mismatch</option><option value="high">High risk · critical vital</option><option value="open">Open chart · held</option></select><button onclick="loadSample()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 17v3h14v-3"/></svg>Load</button></div><div class="csv-area"><div class="hint" style="margin-bottom:4px"><b>Adapt with labeled CSV</b> · staff, category, risk, description, chart_status, confirmed</div><div class="row"><input id="csv" type="file" accept=".csv,text/csv"><button class="secondary" onclick="importCsv()">Import CSV</button></div><details><summary class="hint">CSV and FHIR notes</summary><p class="hint">Use synthetic or de-identified examples. Epic sandbox test patients are for integration testing. This app does not connect to Epic or learn from unlabelled FHIR resources.</p><p class="hint">Import calibrates recurrence thresholds; this is not clinical ML training.</p></details></div></section>
<section class="card"><div class="card-head"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v14H4zM8 9l2 2-2 2m5 0h3"/></svg></span><div><span class="step-label">Step 2</span><h2>Plan and review</h2></div></div><p class="desc">Run the rule-based plan. Open charts are held; high-risk signals pause for a human.</p><div class="row"><button onclick="analyze()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 5 12 7-12 7z"/></svg>Run analysis</button><button class="secondary" onclick="resetApp()">Reset demo</button></div><div id="summary" class="summary" style="margin-top:9px">No analysis yet.</div></section></div>
<section class="card events-card"><div class="events-title"><div class="card-head" style="margin:0"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></svg></span><h2>Current synthetic events</h2></div><span id="event-count" class="count">0 events</span></div><div id="events" class="tablewrap"></div></section>
<div class="bottom-grid"><section class="card trace-card"><div class="card-head"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h10M4 18h7"/><circle cx="18" cy="12" r="2"/><circle cx="15" cy="18" r="2"/></svg></span><h2>Reasoning trace & tool use</h2></div><p class="muted">Visible policy steps and tool calls, not hidden model reasoning.</p><div id="trace" class="trace-empty">Run analysis to view checks and routing.</div></section><section class="card mini-card"><div class="card-head"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4m0 10v4M3 12h4m10 0h4M5.6 5.6l2.8 2.8m7.2 7.2 2.8 2.8m0-12.8-2.8 2.8m-7.2 7.2-2.8 2.8"/><circle cx="12" cy="12" r="4"/></svg></span><h2>Adaptation feedback</h2></div><div id="disputes" class="empty">No disputes yet.</div></section><section class="card mini-card"><div class="card-head"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h4"/></svg></span><h2>Audit log</h2></div><div id="audit" class="empty">No actions recorded.</div></section></div></div><div class="right-pane"><section class="card demo-card"><div class="demo-title"><div class="card-head" style="margin:0"><span class="step-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="13" rx="2"/><path d="M8 21h8m-4-3v3"/></svg></span><h2>Agent in the EHR · visual demo</h2></div><span class="demo-tag">EPIC-STYLE · SIMULATED · SILENT</span></div><div class="demo-player" id="demo-player"><div class="demo-screen">
<div class="demo-scene nurse-scene"><div class="demo-browser"><i></i><i></i><i></i> Epic-style EHR · CareLearn demo</div><div class="demo-top"><span class="brand-in-sim"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a4 4 0 0 0-7 2.7A4.5 4.5 0 0 0 4 14a4 4 0 0 0 5.5 5.7A3.5 3.5 0 0 0 12 21zM12 3a4 4 0 0 1 7 2.7A4.5 4.5 0 0 1 20 14a4 4 0 0 1-5.5 5.7A3.5 3.5 0 0 1 12 21zM12 3v18M8 8c2 0 2 2 4 2s2-2 4-2"/><path d="M17.7 17.9s-2.2-1.4-2.8-2.8c-.5-1.2.1-2.3 1.2-2.3.7 0 1.1.4 1.4.8.3-.4.7-.8 1.4-.8 1.1 0 1.7 1.1 1.2 2.3-.6 1.4-2.4 2.8-2.4 2.8z" fill="#ff526b" stroke="none"/></svg>CareLearn</span><small>NURSE VIEW · SIMULATED</small></div><div class="demo-layout"><aside class="demo-nav"><b>Workspace</b>Patient list<br>Encounters<br>Chart review<br>Orders<br>Results</aside><div class="demo-content"><div class="demo-patient"><span><strong>DEMO-014 · Test Patient</strong><br><span class="demo-label">Encounter · 10:42 AM · Closed</span></span><span class="demo-label">Nurse A</span></div><span class="demo-label">RECENT OBSERVATIONS</span><div class="demo-vitals"><span>BP <b>124/78</b></span><span>HR <b>78</b></span><span>SpO₂ <b>97%</b></span><span>Temp <b>37.0°C</b></span></div><span class="demo-label">RESPIRATORY ASSESSMENT</span><div class="demo-note"><span class="low-entry">Breath sounds: <b class="demo-error">crackels</b><br><small>Entry saved · signed chart detected</small></span><span class="high-entry">SpO₂ recorded: <b class="urgent">6%</b><br><small>Second synthetic example · signed chart</small></span></div><div class="demo-alert low-alert"><span class="tip-brain"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a4 4 0 0 0-7 2.7A4.5 4.5 0 0 0 4 14a4 4 0 0 0 5.5 5.7A3.5 3.5 0 0 0 12 21zM12 3a4 4 0 0 1 7 2.7A4.5 4.5 0 0 1 20 14a4 4 0 0 1-5.5 5.7A3.5 3.5 0 0 1 12 21zM12 3v18M8 8c2 0 2 2 4 2s2-2 4-2"/><circle cx="9" cy="12" r=".6" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r=".6" fill="currentColor" stroke="none"/><path d="M9 15c1.7 1.8 4.3 1.8 6 0"/></svg></span><span><b>Quick Tip! · 1 minute</b><br><small>Looks like “crackels” may need an extra “c.” A one-minute refresher can help — you’ve got this!</small></span></div><div class="demo-alert nurse-high-alert"><span class="alert-mark">!</span><span><b>High-risk discrepancy</b><br><small>Automation paused. Supervisor review is being requested.</small></span></div></div></div></div>
<div class="demo-scene supervisor-scene"><div class="demo-browser"><i></i><i></i><i></i> Epic-style EHR · CareLearn demo</div><div class="demo-top"><span class="brand-in-sim"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a4 4 0 0 0-7 2.7A4.5 4.5 0 0 0 4 14a4 4 0 0 0 5.5 5.7A3.5 3.5 0 0 0 12 21zM12 3a4 4 0 0 1 7 2.7A4.5 4.5 0 0 1 20 14a4 4 0 0 1-5.5 5.7A3.5 3.5 0 0 1 12 21zM12 3v18M8 8c2 0 2 2 4 2s2-2 4-2"/><path d="M17.7 17.9s-2.2-1.4-2.8-2.8c-.5-1.2.1-2.3 1.2-2.3.7 0 1.1.4 1.4.8.3-.4.7-.8 1.4-.8 1.1 0 1.7 1.1 1.2 2.3-.6 1.4-2.4 2.8-2.4 2.8z" fill="#ff526b" stroke="none"/></svg>CareLearn</span><small>SUPERVISOR VIEW · SIMULATED</small></div><div class="demo-layout"><aside class="demo-nav"><b>Supervisor desk</b>Team overview<br>Open reviews<br>Audit history<br>Training status</aside><div class="demo-content"><div class="demo-patient"><span><strong>Safety review queue</strong><br><span class="demo-label">Human-in-the-loop checkpoint</span></span><span class="pill high">URGENT</span></div><div class="super-row"><span>DEMO-014 · Nurse A<br><span class="demo-label">Vital-sign entry needs review</span></span><span class="urgent">NEW</span></div><div class="super-row"><span>Risk category<br><b class="urgent">High · immediate review</b></span><span>!</span></div><div class="super-row"><span>Recorded value<br><b>SpO₂ 6% · synthetic example</b></span><span class="demo-label">Closed chart</span></div><span class="review-btn">Open review · human decision required</span><div class="demo-alert high-alert"><span class="alert-mark">!</span><span><b>Supervisor action required</b><br><small>High-risk vital discrepancy detected. Automation paused pending human review.</small></span></div></div></div></div>
</div><span class="demo-stage stage-nurse">NURSE VIEW · LOW-RISK QUICK TIP</span><span class="demo-stage stage-supervisor">SUPERVISOR VIEW · HIGH-RISK HITL ALERT</span></div><div class="demo-controls"><button class="secondary" id="pause-demo" onclick="toggleDemo()">Ⅱ Pause</button><button class="secondary" onclick="replayDemo()">↻ Replay</button><span>20-second loop · no audio</span></div></section></div></main><div id="toast" class="toast"></div>
<script>
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d=await r.json();if(!r.ok)throw new Error(d.error||'Request failed');return d}
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function toast(msg){let el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2400)}
function toggleDemo(){let p=document.getElementById('demo-player'),b=document.getElementById('pause-demo'),paused=p.classList.toggle('paused');b.textContent=paused?'▶ Resume':'Ⅱ Pause'}
function replayDemo(){let p=document.getElementById('demo-player'),b=document.getElementById('pause-demo');p.classList.remove('paused');b.textContent='Ⅱ Pause';p.querySelectorAll('.demo-scene,.demo-alert,.demo-error,.low-entry,.high-entry,.stage-nurse,.stage-supervisor').forEach(e=>{e.style.animation='none';void e.offsetHeight;e.style.animation=''})}
async function refresh(){let s=await api('/state');document.getElementById('event-count').textContent=`${s.events.length} event${s.events.length===1?'':'s'}`;document.getElementById('events').innerHTML=s.events.length?`<table><thead><tr><th>ID</th><th>Staff</th><th>Status</th><th>Category</th><th>Risk</th><th>Description</th><th>Feedback</th></tr></thead><tbody>${s.events.map(e=>`<tr><td>${esc(e.id)}</td><td>${esc(e.staff)}</td><td>${esc(e.chart_status)}</td><td>${esc(e.category)}</td><td><span class="pill ${esc(e.risk)}">${esc(e.risk)}</span></td><td class="desc-col">${esc(e.description)}</td><td>${e.disputed?'<span class="muted">Disputed</span>':`<button class="secondary" onclick="dispute('${esc(e.id)}')">Dispute</button>`}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">No events loaded.</div>';
document.getElementById('summary').innerHTML=s.last_result?`<span class="status ${s.last_result.outcome==='Supervisor review required'?'err':'ok'}">${esc(s.last_result.outcome)}</span><p>${esc(s.last_result.message)}</p><span class="summary-meta">Thresholds: low ${s.thresholds.low} · medium ${s.thresholds.medium} · high ${s.thresholds.high} | ${esc(s.training_data)}</span>`:'No analysis yet. Choose a scenario, then run the plan.';
document.getElementById('trace').innerHTML=s.last_result?`<ol class="trace-list">${s.last_result.steps.map((x,i)=>`<li><span class="trace-num">${i+1}</span><div class="trace-copy"><b>${esc(x.tool)}</b><br><span>${esc(x.result)}</span></div></li>`).join('')}</ol><details class="decision-detail"><summary>Decision summary</summary><p>${esc(s.last_result.rationale)}</p></details>`:'<div class="trace-empty">Run analysis to view checks and routing.</div>';
document.getElementById('disputes').innerHTML=s.disputes.length?`<table><thead><tr><th>Event</th><th>Reason / effect</th></tr></thead><tbody>${s.disputes.map(d=>`<tr><td>${esc(d.id)}</td><td>${esc(d.reason)}<br><span class="muted">${esc(d.effect)}</span></td></tr>`).join('')}</tbody></table>`:'<div class="empty">No disputes yet.</div>';
document.getElementById('audit').innerHTML=s.audit.length?`<ol>${s.audit.slice().reverse().map(a=>`<li><span class="mono">${esc(a.time.slice(11,19))}</span> — ${esc(a.action)}</li>`).join('')}</ol>`:'<div class="empty">No actions recorded.</div>'}
async function loadSample(){try{await api('/scenario',{scenario:document.getElementById('sample').value});await refresh();toast('Scenario loaded')}catch(e){toast(e.message)}}
async function analyze(){try{await api('/analyze',{});await refresh();toast('Analysis complete')}catch(e){toast(e.message)}}
async function dispute(id){let reason=prompt('Why might this be a false positive? (Use a fictional explanation)');if(reason===null)return;try{await api('/dispute',{id,reason});await refresh();toast('Feedback recorded and thresholds recalibrated')}catch(e){toast(e.message)}}
async function importCsv(){let f=document.getElementById('csv').files[0];if(!f){toast('Choose a CSV file first');return}try{let text=await f.text();await api('/import',{text,filename:f.name});await refresh();toast('CSV imported and thresholds recalibrated')}catch(e){toast(e.message)}}
async function resetApp(){try{await api('/reset',{});await refresh();toast('Demo reset')}catch(e){toast(e.message)}}
refresh();
</script></body></html>'''


def audit(action: str) -> None:
    STATE["audit"].append({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": action})


def recalibrate() -> None:
    # Use confirmed labeled examples to set a recurrence trigger by risk class.
    confirmed = [e for e in STATE["events"] if e.get("confirmed") and not e.get("disputed")]
    counts: dict[str, Counter] = defaultdict(Counter)
    for event in confirmed:
        if event["chart_status"] == "closed":
            counts[event["risk"]][(event["staff"], event["category"])] += 1
    for risk, base in (("low", 3), ("medium", 2), ("high", 1)):
        observed = [n for n in counts[risk].values() if n > 0]
        # Keep high-risk escalation at one event; smaller samples never relax safeguards.
        STATE["thresholds"][risk] = 1 if risk == "high" else min(base, max(1, min(observed, default=base)))


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    required = {"staff", "category", "risk", "description", "chart_status", "confirmed"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV headers must include: staff, category, risk, description, chart_status, confirmed")
    out = []
    for i, row in enumerate(reader, 1):
        risk = row.get("risk", "").strip().lower()
        status = row.get("chart_status", "").strip().lower()
        if risk not in {"low", "medium", "high"}:
            raise ValueError(f"Row {i}: risk must be low, medium, or high")
        if status not in {"closed", "signed", "open", "draft"}:
            raise ValueError(f"Row {i}: chart_status must be closed, signed, open, or draft")
        if not row.get("staff", "").strip() or not row.get("category", "").strip():
            raise ValueError(f"Row {i}: staff and category are required")
        out.append({"id": f"CSV-{i:03}", "staff": row["staff"].strip(), "patient_ref": f"SYN-CSV-{i:03}", "chart_status": status, "category": row["category"].strip(), "risk": risk, "description": row.get("description", "").strip(), "confirmed": row.get("confirmed", "").strip().lower() in {"1", "true", "yes", "y"}})
    if not out:
        raise ValueError("CSV contains no data rows")
    return out


def run_agent() -> dict:
    steps = []
    steps.append({"tool": "chart_eligibility_check", "result": "Only signed/closed events are eligible; open and draft charts are held."})
    eligible = [e for e in STATE["events"] if e["chart_status"] in {"closed", "signed"} and not e.get("disputed")]
    held = len(STATE["events"]) - len(eligible)
    steps.append({"tool": "event_filter", "result": f"Accepted {len(eligible)} eligible event(s); held {held} open/draft or disputed event(s)."})
    if not eligible:
        result = {"outcome": "No eligible events", "message": "Nothing was evaluated. Close/sign charts or load eligible synthetic examples.", "steps": steps, "rationale": "The chart eligibility gate prevented analysis."}
        STATE["last_result"] = result
        return result
    # Risk ordering makes a single high-risk signal sufficient for a human checkpoint.
    rank = {"low": 1, "medium": 2, "high": 3}
    highest = max(eligible, key=lambda e: rank[e["risk"]])
    steps.append({"tool": "risk_classifier", "result": f"Highest observed category is {highest['risk']} ({highest['category']}); rule-based label is taken from the annotated demo event."})
    group = [e for e in eligible if e["staff"] == highest["staff"] and e["category"] == highest["category"]]
    count = len(group)
    steps.append({"tool": "pattern_memory_lookup", "result": f"Found {count} eligible occurrence(s) for this staff/category combination."})
    threshold = STATE["thresholds"][highest["risk"]]
    steps.append({"tool": "threshold_policy", "result": f"Current {highest['risk']} threshold is {threshold}; high-risk signals always require human review."})
    if highest["risk"] == "high" or (highest["risk"] == "medium" and count >= threshold):
        outcome = "Supervisor review required"
        message = "A medium/high risk trigger met policy. The agent pauses automation and routes the case to a human reviewer. No training or clinical action is issued automatically."
        steps.append({"tool": "supervisor_escalation", "result": "Escalation queued in the local demo audit log; a real notification channel is not connected."})
    elif highest["risk"] == "low" and count >= threshold:
        outcome = "Targeted micro-training recommended"
        message = "The repeated low-risk pattern met its threshold. A short learning item is recommended; a supervisor can review the suggestion."
        steps.append({"tool": "training_catalog_lookup", "result": "Matched common_typo to a fictional 1-minute terminology refresher."})
    else:
        outcome = "Continue monitoring"
        message = "No eligible threshold was reached. The event remains in the synthetic pattern log for later review."
    rationale = f"Eligible chart gate → {highest['risk']} risk → {count} matching occurrence(s) vs threshold {threshold} → {outcome}. This transparent policy trace shows decisions, not private model reasoning."
    result = {"outcome": outcome, "message": message, "steps": steps, "rationale": rationale}
    STATE["last_result"] = result
    audit(f"Analysis: {outcome}; evaluated {len(eligible)} eligible synthetic event(s).")
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2_000_000:
            raise ValueError("Request too large (2 MB maximum)")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            raw = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/state":
            with LOCK:
                self.send_json({k: STATE[k] for k in ("events", "analyses", "audit", "disputes", "thresholds", "training_data", "last_result")})
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_body()
            with LOCK:
                if path == "/scenario":
                    scenario = body.get("scenario", "all")
                    mapping = {"all": SAMPLES, "low": SAMPLES[:3], "medium": [SAMPLES[3]], "high": [SAMPLES[4]], "open": [SAMPLES[5]]}
                    if scenario not in mapping:
                        raise ValueError("Unknown scenario")
                    STATE["events"] = [dict(e) for e in mapping[scenario]]
                    STATE["disputes"] = []
                    STATE["last_result"] = None
                    STATE["training_data"] = "Built-in synthetic sample"
                    recalibrate()
                    audit(f"Loaded {scenario} synthetic scenario.")
                    self.send_json({"ok": True})
                elif path == "/import":
                    events = parse_csv(body.get("text", ""))
                    STATE["events"] = events
                    STATE["disputes"] = []
                    STATE["last_result"] = None
                    STATE["training_data"] = "Imported labeled CSV (in-memory only)"
                    recalibrate()
                    audit(f"Imported {len(events)} labeled synthetic/de-identified CSV row(s); recalibrated thresholds.")
                    self.send_json({"ok": True, "count": len(events)})
                elif path == "/analyze":
                    self.send_json(run_agent())
                elif path == "/dispute":
                    event = next((e for e in STATE["events"] if e["id"] == body.get("id")), None)
                    if not event:
                        raise ValueError("Event not found")
                    reason = str(body.get("reason", "")).strip()[:500]
                    if not reason:
                        raise ValueError("Add a short fictional reason for the dispute")
                    event["disputed"] = True
                    STATE["disputes"].append({"id": event["id"], "reason": reason, "effect": "Excluded from active counts and calibration; retained in demo dispute/audit view."})
                    recalibrate()
                    STATE["last_result"] = None
                    audit(f"Disputed event {event['id']}; excluded it from active analysis and recalibrated thresholds.")
                    self.send_json({"ok": True})
                elif path == "/reset":
                    STATE.update({"events": [dict(x) for x in SAMPLES], "analyses": [], "audit": [], "disputes": [], "thresholds": {"low": 3, "medium": 2, "high": 1}, "training_data": "Built-in synthetic sample", "last_result": None})
                    audit("Reset in-memory demo state.")
                    self.send_json({"ok": True})
                else:
                    self.send_json({"error": "Not found"}, 404)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"CareLearn running at {url}\nSynthetic/de-identified data only. Press Ctrl+C to stop.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CareLearn.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
