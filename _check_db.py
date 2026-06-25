import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

print("=== Database check ===")
from app.db import list_all_plans, list_sessions, load_messages
plans = list_all_plans()
print("list_all_plans() returned", len(plans), "records")
if plans:
    for p in plans[:3]:
        sid = p.get("session_id", "?")
        title = p.get("title", "?")
        print("  session:", sid, "title:", title)

sessions = list_sessions()
print("list_sessions() returned", len(sessions), "records")
if sessions:
    for s in sessions[:3]:
        sid = s.get("session_id", "?")
        msgs = load_messages(sid)
        print("  session:", sid, "messages:", len(msgs))

print("=== render_plan_list test ===")
from app.gradio_app import _render_plan_list
html = _render_plan_list()
print("HTML length:", len(html))
print("Contains items:", "plan-" in html or "暂无计划" in html)
