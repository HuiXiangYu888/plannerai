"""
PlannerAI - 学习计划生成 Agent 交互界面
类 ChatGPT 对话体验，支持流式输出、工具调用可视化、计划状态管理
"""
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr

from app.agents.graph_agent import run_agent_stream
from app.agents.study_planner import generate_study_plan
from app.db import (
    clear_session_data,
    create_session,
    delete_session,
    list_all_plans,
    load_messages,
    load_plan,
    rename_plan,
    save_messages,
    save_plan,
)


# ============================================================================
# 自定义 CSS - 类 ChatGPT 风格
# ============================================================================
CUSTOM_CSS = """
/* ===== 现代化布局修复与界面美化 ===== */
body {
    background-color: #f3f4f6 !important;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* 让 Gradio 主容器更好地适应屏幕 */
.gradio-container {
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    background: #ffffff !important;
    border: none !important;
    height: 100vh !important;
}

/* 隐藏通信按钮 */
#_load_plan_btn, #_del_plan_btn, #_rename_plan_btn, #_export_all_btn {
    display: none !important;
}

/* 主行容器 */
#main-row {
    height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
    flex-wrap: nowrap !important;
}

/* ===== 左侧边栏 ===== */
.sidebar-col {
    background: rgba(249, 250, 251, 0.7) !important;
    border-right: 1px solid rgba(229, 231, 235, 0.5) !important;
    height: 100vh !important;
    min-width: 260px !important;
    max-width: 320px !important;
    position: relative !important;
}

/* 侧边栏标题 */
#sidebar-title {
    padding: 20px !important;
    border-bottom: 1px solid rgba(229, 231, 235, 0.5) !important;
}
#sidebar-title h3 {
    color: #111827 !important;
    font-size: 18px !important;
    font-weight: 700 !important;
    margin: 0 !important;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* 新建计划按钮 */
#new-plan-btn button {
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
    color: #374151 !important;
    font-weight: 600 !important;
    padding: 12px !important;
    margin: 16px !important;
    width: calc(100% - 32px) !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
#new-plan-btn button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05) !important;
    border-color: #d1d5db !important;
}

/* 计划列表包裹层 */
.plan-list-wrapper {
    overflow-y: auto !important;
    height: calc(100vh - 220px) !important;
}

/* 计划列表容器 */
#plan_list_container {
    flex: 1 !important;
    overflow-y: auto !important;
    padding: 0 12px !important;
}

/* 隐藏真实的文件下载组件 */
#export-file {
    display: none !important;
}

/* 计划列表项 */
.plan-item {
    background: transparent !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    margin-bottom: 4px !important;
    cursor: pointer !important;
    border: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
}
.plan-item:hover {
    background: #f3f4f6 !important;
    box-shadow: none !important;
}
.plan-item-active {
    background: #e5e7eb !important;
    box-shadow: none !important;
}

/* 更多菜单 */
.more-menu-wrapper {
    position: relative !important;
}
.more-btn {
    background: none !important;
    border: none !important;
    cursor: pointer !important;
    color: #6b7280 !important;
    font-weight: bold !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 4px 8px !important;
    border-radius: 4px !important;
}
.more-btn:hover {
    background: rgba(0,0,0,0.05) !important;
    color: #111827 !important;
}
.more-menu {
    display: none !important;
    position: absolute !important;
    right: 0 !important;
    top: 100% !important;
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    z-index: 1000 !important;
    min-width: 100px !important;
    overflow: hidden !important;
}
.more-menu.show {
    display: block !important;
}
.menu-item {
    padding: 8px 12px !important;
    font-size: 13px !important;
    cursor: pointer !important;
    color: #374151 !important;
}
.menu-item:hover {
    background: #f3f4f6 !important;
}
.menu-item.danger {
    color: #ef4444 !important;
}
.menu-item.danger:hover {
    background: #fef2f2 !important;
}

/* ===== 右侧聊天区 ===== */
.chat-col {
    background: #ffffff !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}

#chat-area {
    flex: 1 !important;
    overflow-y: auto !important;
    padding: 20px !important;
}

/* 消息气泡动画 */
.message {
    border-radius: 16px !important;
    padding: 14px 20px !important;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.02) !important;
    animation: fadeIn 0.3s ease-out forwards;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* 工具调用折叠区域 */
details {
    background: #f9fafb !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    border: 1px solid #e5e7eb !important;
    transition: all 0.3s ease !important;
}
details:hover {
    border-color: #d1d5db !important;
}

/* 输入区域 */
#input-area {
    padding: 16px 24px !important;
    background: rgba(255, 255, 255, 0.9) !important;
    border-top: 1px solid #e5e7eb !important;
    backdrop-filter: blur(10px) !important;
}

#input-area textarea {
    border-radius: 14px !important;
    border: 1px solid #d1d5db !important;
    padding: 12px 16px !important;
    transition: all 0.3s ease !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
}
#input-area textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
}

/* 发送按钮 */
#send-btn button {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    border: none !important;
    border-radius: 12px !important;
    color: white !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2) !important;
}
#send-btn button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 15px rgba(37, 99, 235, 0.3) !important;
}

/* 导出按钮 */
#export-btn-container {
    padding: 16px !important;
    border-top: 1px solid rgba(229, 231, 235, 0.5) !important;
    background: rgba(249, 250, 251, 0.9) !important;
    position: absolute !important;
    bottom: 0 !important;
    left: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
#export-btn button {
    background: #f3f4f6 !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
    color: #4b5563 !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}
#export-btn button:hover {
    background: #e5e7eb !important;
    color: #1f2937 !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05) !important;
}
"""

# ============================================================================
# 计划列表交互 JS（通过 launch(js=...) 注入页面）
# ============================================================================
JS_PLAN_SCRIPT = """
function() {
    // 简化后的 JS 脚本，不再暴力修改 DOM 布局，交由 Gradio 原生支持
    window.activeMenu = null;
    window.closeAllMenus = function() {
        document.querySelectorAll('.more-menu').forEach(function(m) { m.classList.remove('show'); });
        window.activeMenu = null;
    };
    
    window.toggleMoreMenu = function(e, sid) {
        e.stopPropagation();
        var menu = document.getElementById('menu-' + sid);
        if (window.activeMenu && window.activeMenu !== menu) window.activeMenu.classList.remove('show');
        if (menu) {
            menu.classList.toggle('show');
            window.activeMenu = menu.classList.contains('show') ? menu : null;
        }
    };

    function setInputValue(containerId, value) {
        var container = document.getElementById(containerId);
        if (!container) return;
        var input = container.querySelector('textarea, input');
        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    window.selectPlan = function(sid) {
        window.closeAllMenus();
        document.querySelectorAll('.plan-item').forEach(function(item) {
            item.classList.remove('plan-item-active');
        });
        var activeItem = document.getElementById('plan-' + sid);
        if (activeItem) {
            activeItem.classList.add('plan-item-active');
        }
        setInputValue('_cur_plan_sid', sid);
        setTimeout(function() { 
            var b = document.getElementById('_load_plan_btn'); 
            if (b) b.click(); 
        }, 50);
    };

    window.deletePlan = function(sid) {
        window.closeAllMenus();
        if (!confirm('确定删除该计划及其对话记录？')) return;
        setInputValue('_cur_plan_sid', sid);
        setTimeout(function() { 
            var b = document.getElementById('_del_plan_btn'); 
            if (b) b.click(); 
        }, 50);
    };

    window.renamePlan = function(sid, currentTitle) {
        window.closeAllMenus();
        var item = document.getElementById('plan-' + sid);
        if (!item) return;
        var titleSpan = item.querySelector('.plan-title');
        if (!titleSpan) return;
        
        var input = document.createElement('input');
        input.type = 'text'; 
        input.value = currentTitle;
        input.style.cssText = 'flex:1;font-size:14px;background:#fff;border:1px solid #3b82f6;border-radius:6px;color:#111827;padding:4px 8px;outline:none;box-shadow: 0 0 0 2px rgba(59,130,246,0.2);';
        
        titleSpan.style.display = 'none';
        var timeSpan = item.querySelector('.plan-time');
        if (timeSpan) timeSpan.style.display = 'none';
        
        item.insertBefore(input, item.querySelector('.more-menu-wrapper'));
        input.focus(); 
        input.select();
        
        input.addEventListener('click', function(e) { e.stopPropagation(); });
        input.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        input.addEventListener('mouseup', function(e) { e.stopPropagation(); });
        
        function finishRename() {
            var newTitle = input.value.trim();
            if (newTitle && newTitle !== currentTitle) {
                setInputValue('_cur_plan_sid', sid);
                setInputValue('_rename_title', newTitle);
                setTimeout(function() { 
                    var b = document.getElementById('_rename_plan_btn'); 
                    if (b) b.click(); 
                }, 50);
            } else { 
                titleSpan.style.display = ''; 
                if (timeSpan) timeSpan.style.display = ''; 
                input.remove(); 
            }
        }
        input.addEventListener('blur', finishRename);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            else if (e.key === 'Escape') { input.value = currentTitle; input.blur(); }
        });
    };

    document.addEventListener('click', function(e) { 
        if (!e.target.closest('.more-menu-wrapper')) { 
            window.closeAllMenus(); 
        } 
    });
}
"""


# ============================================================================
# 工具函数
# ============================================================================
def _normalize_messages(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out

    for item in raw:
        if isinstance(item, dict) and "role" in item and "content" in item:
            out.append({"role": str(item["role"]), "content": str(item["content"])})
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            out.append({"role": "user", "content": str(item[0])})
            out.append({"role": "assistant", "content": str(item[1])})
            continue
        out.append({"role": "assistant", "content": str(item)})
    return out


def _plan_to_markdown(plan: dict[str, Any]) -> str:
    """将计划 JSON 转换为漂亮的 Markdown 表格"""
    if not isinstance(plan, dict) or not plan:
        return "### 📋 当前计划\n\n暂无计划。请在右侧发送消息开始生成。"

    title = plan.get("title") or "学习计划"
    status = plan.get("status") or "unknown"
    goal = plan.get("goal_summary") or "-"
    horizon = plan.get("horizon_days")
    horizon_text = f"{horizon} 天" if isinstance(horizon, int) else "-"

    capacity = plan.get("capacity") or {}
    weekly = capacity.get("weekly_minutes", 0)
    total = capacity.get("estimated_total_minutes", 0)

    # 状态图标
    status_icon = {"ok": "✅", "warning": "⚠️", "need_more_info": "❓"}.get(status, "❓")

    lines = [
        "### 📋 当前计划",
        "",
        f"#### {title}",
        "",
        "| 字段 | 值 |",
        "|:---|:---|",
        f"| **状态** | {status_icon} {status} |",
        f"| **目标** | {goal} |",
        f"| **周期** | {horizon_text} |",
        f"| **周可用时长** | {weekly} 分钟 |",
        f"| **预估总时长** | {total} 分钟 |",
    ]

    phases = plan.get("phases") or []
    if phases:
        lines.extend(["", "#### 📅 阶段安排", "", "| 阶段 | 时间范围 | 重点 |", "|:---|:---|:---|"])
        for phase in phases:
            lines.append(
                f"| {phase.get('phase', '-')} | {phase.get('range', '-')} | {phase.get('focus', '-')} |"
            )

    pending = plan.get("clarification_needed") or []
    if pending:
        lines.extend(["", "#### ⚠️ 待补充信息", ""])
        for item in pending:
            lines.append(f"- {item}")

    return "\n".join(lines)


def _render_plan_list(current_sid: str = "") -> str:
    """渲染左侧计划列表 HTML（含内联 CSS/JS）"""
    plans = list_all_plans()
    items_html = ""
    if not plans:
        items_html = '<div style="text-align:center;color:#8e8e93;padding:24px;font-size:14px;">暂无计划</div>'
    else:
        for p in plans:
            sid = p["session_id"]
            title = p["title"]
            updated = p["updated_at"][:16].replace("T", " ")
            is_active = "plan-item-active" if sid == current_sid else ""
            # 转义标题中的特殊字符
            safe_title = title.replace("'", "\\'").replace('"', '&quot;')
            items_html += (
                f'<div class="plan-item {is_active}" id="plan-{sid}" data-sid="{sid}" onclick="selectPlan(\'{sid}\')" '
                f'style="display:flex!important;align-items:center!important;height:44px!important;'
                f'min-height:44px!important;max-height:44px!important;box-sizing:border-box!important;'
                f'padding:0 12px!important;margin-bottom:2px!important;overflow:visible!important;'
                f'line-height:44px!important;position:relative!important;cursor:pointer!important;'
                f'border-radius:8px!important;font-size:14px!important;">'
                f'<span class="plan-title" style="flex:1;font-size:14px!important;line-height:44px!important;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{title}</span>'
                f'<span class="plan-time" style="font-size:11px!important;line-height:44px!important;color:#8e8e93;margin-right:8px;white-space:nowrap;">{updated}</span>'
                f'<div class="more-menu-wrapper" onclick="event.stopPropagation();" onmousedown="event.stopPropagation();">'
                f'<button class="more-btn" onclick="toggleMoreMenu(event, \'{sid}\')" style="font-size:16px!important;line-height:1!important;">...</button>'
                f'<div class="more-menu" id="menu-{sid}">'
                f'<div class="menu-item" onclick="renamePlan(\'{sid}\', \'{safe_title}\')">✏️ 重命名</div>'
                f'<div class="menu-item danger" onclick="deletePlan(\'{sid}\')">🗑️ 删除</div>'
                f'</div>'
                f'</div>'
                f'</div>'
            )

    return (
        '<style>'
        '#plan-list-box{padding:4px 8px!important;margin:0!important;}'
        '#plan-list-box > *{margin-bottom:2px!important;}'
        '</style>'
        f'<div id="plan-list-box">{items_html}</div>'
    )


# ============================================================================
# 核心交互逻辑
# ============================================================================
import uuid

def new_plan(current_sid: str):
    """新建计划：清理空记录，并在需要时复用当前空记录或创建全新会话"""
    # 1. 查找并清理所有空记录（无消息，且无任何有效计划数据）
    plans = list_all_plans()
    for p in plans:
        sid = p["session_id"]
        if sid == "default":
            continue
        msgs = load_messages(sid)
        plan = load_plan(sid)
        if not msgs and (not plan or plan == {}):
            delete_session(sid)
            
    # 2. 如果当前的活跃会话（current_sid）本身就是一个空会话，直接复用它，不再生成新记录
    if current_sid and current_sid != "default":
        msgs = load_messages(current_sid)
        plan = load_plan(current_sid)
        if not msgs and (not plan or plan == {}):
            create_session(current_sid) # 确保存在
            return (
                [],
                [],
                {},
                _render_plan_list(current_sid),
                current_sid,
            )

    # 3. 否则，生成新的 session_id
    new_sid = str(uuid.uuid4())[:8]
    create_session(new_sid)

    empty_messages: list[dict[str, str]] = []
    empty_plan: dict[str, Any] = {}
    return (
        empty_messages,
        empty_messages,
        empty_plan,
        _render_plan_list(new_sid),
        new_sid,  # 返回新的 session_id
    )


def load_from_local(session_id: str):
    """从 SQLite 数据库加载"""
    messages = load_messages(session_id)
    plan = load_plan(session_id)
    return messages, messages, plan, _plan_to_markdown(plan)


def delete_records(session_id: str):
    """删除当前会话的对话和计划记录"""
    clear_session_data(session_id)
    empty_messages: list[dict[str, str]] = []
    empty_plan: dict[str, Any] = {}
    return (
        empty_messages,
        empty_messages,
        empty_plan,
        _plan_to_markdown(empty_plan),
        "🗑️ 已删除记录",
    )


def _load_plan_action(current_sid: str):
    """加载指定计划的对话和详情（只返回3个值，避免不必要的侧边栏重绘）"""
    msgs = load_messages(current_sid)
    plan = load_plan(current_sid)
    return msgs, msgs, plan


def _delete_plan_action(current_sid: str, session_id: str, messages_state: list, plan_state: dict):
    """删除指定计划（从数据库彻底删除），如果删的是当前计划则清空右侧（返回4个值）"""
    if not current_sid:
        # 如果 current_sid 为空，不做任何操作
        return (
            messages_state,
            messages_state,
            plan_state,
            _render_plan_list(session_id),
        )
    
    # 真正删除会话记录
    delete_session(current_sid)
    
    if current_sid == session_id:
        empty_msgs: list[dict[str, str]] = []
        empty_plan: dict[str, Any] = {}
        return (
            empty_msgs,
            empty_msgs,
            empty_plan,
            _render_plan_list(""),
        )
    else:
        return (
            messages_state,
            messages_state,
            plan_state,
            _render_plan_list(session_id),
        )


def _rename_plan_action(current_sid: str, new_title: str) -> str:
    """重命名指定计划（返回刷新后的列表 HTML）"""
    if not current_sid or not new_title:
        return _render_plan_list(current_sid)
    rename_plan(current_sid, new_title)
    return _render_plan_list(current_sid)


async def send_message(
    user_text: str,
    session_id: str,
    current_plan_sid: str,
    messages_state: list[dict[str, str]],
    plan_state: dict[str, Any],
):
    """Send a message and stream the response. Returns separate clean (storage) and visual (display) messages."""
    text = (user_text or "").strip()
    if not text:
        yield (messages_state, messages_state, plan_state, gr.skip(), current_plan_sid, "")
        return

    base_messages = list(messages_state or [])

    # clean_messages: stored in DB, used as agent context (no HTML tool bubbles)
    clean_messages = list(base_messages)
    clean_messages.append({"role": "user", "content": text})

    # visual_messages: displayed in chatbot (may include HTML tool bubbles)
    visual_messages = list(clean_messages)

    target_sid = current_plan_sid if current_plan_sid else session_id
    tool_bubbles: list[str] = []
    full_reply = ""
    error_reply = ""
    synced_plan: dict[str, Any] | None = None
    has_error = False

    # Initial placeholder (visual only, don't pollute clean state)
    pending = list(visual_messages)
    pending.append({"role": "assistant", "content": "正在生成计划..."})
    yield (pending, clean_messages, plan_state, gr.skip(), current_plan_sid, "")

    try:
        async for event in run_agent_stream(
            user_text=text,
            session_id=target_sid,
            messages_state=base_messages,
            plan_state=plan_state or {},
        ):
            event_type = event.get("type")

            if event_type == "tool_call":
                name = event.get("tool_name", "unknown")
                args = event.get("tool_args", "")
                tool_bubbles.append(
                    f"<details><summary>🔧 正在调用: {name}</summary><pre>{args}</pre></details>"
                )
                current_visual = list(visual_messages)
                current_visual.append({"role": "assistant", "content": "\n\n".join(tool_bubbles)})
                yield (current_visual, clean_messages, plan_state, gr.skip(), current_plan_sid, "")

            elif event_type == "token":
                full_reply += event.get("text", "")
                current_visual = list(visual_messages)
                content = ""
                if tool_bubbles:
                    content = "\n\n".join(tool_bubbles) + "\n\n"
                content += full_reply
                current_visual.append({"role": "assistant", "content": content})
                yield (current_visual, clean_messages, plan_state, gr.skip(), current_plan_sid, "")

            elif event_type == "plan_sync":
                synced_plan = event.get("plan")

            elif event_type == "error":
                has_error = True
                error_text = event.get("error", "未知错误")
                try:
                    fallback_plan = generate_study_plan(text)
                except Exception:
                    fallback_plan = {"found": False}
                if fallback_plan.get("found"):
                    synced_plan = fallback_plan
                error_reply = _local_plan_reply(fallback_plan, error_text)
                current_visual = list(visual_messages)
                current_visual.append({"role": "assistant", "content": error_reply})
                yield (current_visual, clean_messages, plan_state, gr.skip(), current_plan_sid, "")

    except Exception as exc:
        has_error = True
        try:
            fallback_plan = generate_study_plan(text)
        except Exception:
            fallback_plan = {"found": False}
        final_plan = fallback_plan if fallback_plan.get("found") else (plan_state or {})
        error_reply = _local_plan_reply(fallback_plan, str(exc))

        # clean messages for storage
        final_clean = list(clean_messages)
        final_clean.append({"role": "assistant", "content": error_reply})

        # visual messages for display
        final_visual = list(visual_messages)
        final_visual.append({"role": "assistant", "content": error_reply})

        save_messages(target_sid, final_clean)
        save_plan(target_sid, final_plan)
        new_current_sid = current_plan_sid or target_sid
        yield (
            final_visual,
            final_clean,
            final_plan,
            _render_plan_list(new_current_sid),
            new_current_sid,
            "",
        )
        return

    # ── Build final plan ──
    final_plan = plan_state or {}
    if synced_plan:
        existing_title = final_plan.get("title", "")
        new_title = synced_plan.get("title", "")
        generic_titles = {"学习计划", "学习", "", None}
        if existing_title and (not new_title or new_title in generic_titles):
            synced_plan["title"] = existing_title
        final_plan = synced_plan
    elif full_reply and not has_error:
        try:
            new_plan = generate_study_plan(text)
            if new_plan.get("found"):
                existing_title = final_plan.get("title", "")
                new_title = new_plan.get("title", "")
                generic_titles = {"学习计划", "学习", "", None}
                if existing_title and (not new_title or new_title in generic_titles):
                    new_plan["title"] = existing_title
                final_plan = new_plan
        except Exception:
            pass

    # ── Build final messages ──
    # Clean messages: for DB storage and agent state (no tool HTML)
    final_clean = list(clean_messages)
    if full_reply:
        final_clean.append({"role": "assistant", "content": full_reply})
    elif error_reply:
        final_clean.append({"role": "assistant", "content": error_reply})
    else:
        fallback = generate_study_plan(text)
        if fallback.get("found"):
            final_plan = fallback
        final_clean.append({"role": "assistant", "content": _local_plan_reply(fallback)})

    # Visual messages: for chatbot display (may include tool HTML)
    final_visual = list(visual_messages)
    if full_reply:
        content = ""
        if tool_bubbles:
            content = "\n\n".join(tool_bubbles) + "\n\n"
        content += full_reply
        final_visual.append({"role": "assistant", "content": content})
    elif error_reply:
        final_visual.append({"role": "assistant", "content": error_reply})
    elif tool_bubbles and not has_error:
        final_visual.append({"role": "assistant", "content": "\n\n".join(tool_bubbles)})
    else:
        fallback = generate_study_plan(text)
        if fallback.get("found"):
            final_plan = fallback
        final_visual.append({"role": "assistant", "content": _local_plan_reply(fallback)})

    save_messages(target_sid, final_clean)
    save_plan(target_sid, final_plan)
    new_current_sid = current_plan_sid or target_sid

    yield (
        final_visual,
        final_clean,
        final_plan,
        _render_plan_list(new_current_sid),
        new_current_sid,
        "",
    )


def _local_plan_reply(plan: dict[str, Any], error_text: str | None = None) -> str:
    """Build a deterministic reply when the LLM stream is unavailable or silent."""
    if plan.get("found"):
        prefix = "模型服务暂时不稳定，我先根据本地规则生成一版可执行计划："
        if error_text:
            prefix = f"模型服务暂时不稳定（{error_text}），我先根据本地规则生成一版可执行计划："
        return f"{prefix}\n\n{_plan_to_markdown(plan)}"

    msg = "我已经收到你的需求，但还缺少一些关键信息：学习周期、每天/每周可用时间，以及薄弱模块。"
    if error_text:
        msg = f"模型服务暂时不稳定（{error_text}）。\n\n{msg}"
    return msg

def _export_plan(plan_state: dict[str, Any]) -> str | None:
    """导出计划为 Markdown 文件"""
    if not plan_state or not plan_state.get("found"):
        return None
    md = _plan_to_markdown(plan_state)
    title = str(plan_state.get("title") or "学习计划")
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", title).strip(" ._")
    safe_title = (safe_title[:40] or "study_plan") + "_"
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix=safe_title, delete=False, encoding="utf-8"
        )
        tmp.write(md)
        tmp.close()
        return tmp.name
    except (OSError, IOError) as e:
        return None


def _export_all_plans() -> str | None:
    """导出所有计划为单个 Markdown 文件"""
    plans = list_all_plans()
    if not plans:
        return None
    md_lines = ["# 🌟 PlannerAI 所有学习计划\n"]
    for p in plans:
        sid = p["session_id"]
        plan_data = load_plan(sid)
        title = p["title"]
        md_lines.append(f"## {title}\n")
        md_lines.append(_plan_to_markdown(plan_data))
        md_lines.append("\n---\n")
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="all_study_plans_", delete=False, encoding="utf-8"
        )
        tmp.write("\n".join(md_lines))
        tmp.close()
        return tmp.name
    except (OSError, IOError):
        return None


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="PlannerAI 学习计划 Agent", css=CUSTOM_CSS, fill_height=True, fill_width=True) as demo:
        # 状态管理（启动时不加载旧数据，避免残留历史记录）
        messages_state = gr.State([])
        plan_state = gr.State({})

        with gr.Row(elem_id="main-row"):
            # ================================================================
            # 左侧边栏
            # ================================================================
            with gr.Column(elem_classes=["sidebar-col"], elem_id="sidebar-col"):
                gr.HTML("<h3 style='color:#1a1a2e;margin:0;'> PlannerAI</h3>", elem_id="sidebar-title")
                new_plan_btn = gr.Button("＋ 新建计划", elem_id="new-plan-btn")
                plan_list_html = gr.HTML(
                    value=_render_plan_list(""),
                    elem_id="plan_list_container",
                    elem_classes=["plan-list-wrapper"],
                )
                with gr.Column(elem_id="export-btn-container"):
                    export_btn = gr.Button("📥 一键导出全部计划", elem_id="export-btn")
                    export_file = gr.File(label="", elem_id="export-file", interactive=False)


            # ================================================================
            # 右侧聊天区
            # ================================================================
            with gr.Column(elem_classes=["chat-col"]):
                chatbot = gr.Chatbot(
                    elem_id="chat-area",
                    avatar_images=(None, None),
                    layout="bubble",
                    allow_tags=True,
                    type="messages",
                )

                with gr.Row(elem_id="input-area"):
                    user_input = gr.Textbox(
                        placeholder="输入你的学习需求，按 Enter 发送...",
                        scale=8,
                        show_label=False,
                        container=False,
                    )
                    send_btn = gr.Button("➤ 发送", elem_id="send-btn")

        # 隐藏组件：用于 JS ↔ Gradio 通信
        # 注意：必须 visible=True + CSS 隐藏，因为 visible=False 不会渲染到 DOM
        current_plan_sid = gr.Textbox(value="", elem_id="_cur_plan_sid", label="_cur_plan_sid")
        load_plan_btn = gr.Button("", elem_id="_load_plan_btn")
        del_plan_btn = gr.Button("", elem_id="_del_plan_btn")
        rename_title_input = gr.Textbox(value="", elem_id="_rename_title", label="_rename_title")
        rename_plan_btn = gr.Button("", elem_id="_rename_plan_btn")

        # 隐藏 session_id
        session_id = gr.Textbox(value="default", visible=False)

        # ================================================================
        # 事件绑定
        # ================================================================

        # 新建计划
        new_plan_btn.click(
            fn=new_plan,
            inputs=[current_plan_sid],
            outputs=[chatbot, messages_state, plan_state, plan_list_html, current_plan_sid],
        )

        # 隐藏按钮：加载选中计划
        load_plan_btn.click(
            fn=_load_plan_action,
            inputs=[current_plan_sid],
            outputs=[chatbot, messages_state, plan_state],
            queue=True,
        )

        # 隐藏按钮：删除计划
        del_plan_btn.click(
            fn=_delete_plan_action,
            inputs=[current_plan_sid, session_id, messages_state, plan_state],
            outputs=[chatbot, messages_state, plan_state, plan_list_html],
            queue=True,
        )

        # 隐藏按钮：重命名计划
        rename_plan_btn.click(
            fn=_rename_plan_action,
            inputs=[current_plan_sid, rename_title_input],
            outputs=[plan_list_html],
            queue=True,
        )

        # 导出全部计划
        export_btn.click(
            fn=_export_all_plans,
            inputs=[],
            outputs=[export_file],
        ).then(
            fn=None, inputs=None, outputs=None, js="() => { setTimeout(() => { const a = document.querySelector('#export-file a'); if(a) a.click(); }, 500); }"
        )

        # 发送按钮和回车发送
        send_btn.click(
            fn=send_message,
            inputs=[user_input, session_id, current_plan_sid, messages_state, plan_state],
            outputs=[chatbot, messages_state, plan_state, plan_list_html, current_plan_sid, user_input],
        )

        user_input.submit(
            fn=send_message,
            inputs=[user_input, session_id, current_plan_sid, messages_state, plan_state],
            outputs=[chatbot, messages_state, plan_state, plan_list_html, current_plan_sid, user_input],
        )

        demo.load(None, js=JS_PLAN_SCRIPT)

    return demo


if __name__ == "__main__":
    build_demo().launch(server_name="0.0.0.0", server_port=9000, show_error=True)
