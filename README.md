# PlannerAI - 学习计划生成智能体 (Learning Plan Agent)

PlannerAI 是一个基于大语言模型（LLM）的智能代理，旨在通过自然语言对话帮助用户生成、管理和调整结构化的学习计划。

本项目采用了现代化的架构，集成了基于图的智能体编排系统，并提供了一个优雅简洁的 Web 交互界面。

## 🌟 核心特性

- **自然语言输入**：只需告诉 PlannerAI 你的目标（如：“我想在未来三个月备考雅思，每天晚上学习两小时”），它就能自动解析你的需求。
- **智能意图与实体提取**：系统内置工具能精准提取**学习目标**、**可用时长**和**薄弱模块**，若信息不足会主动追问。
- **现代化 UI 界面**：采用毛玻璃材质与微动画设计的流畅聊天界面，左侧面板自动保留历史计划记录。
- **前后端一体化**：只需启动一次服务，FastAPI 会作为稳定宿主挂载原生的 Gradio 前端页面。
- **多轮对话与计划局部调整**：支持在已有计划的基础上进行微调，而不是每次都全盘重建。
- **本地计划存储**：自带 SQLite 数据库持久化存储所有会话对话和计划内容，支持数据回溯与导出。

## 🛠️ 技术栈

- **后端核心**: Python 3.10+
- **服务入口**: FastAPI (用于提供 Web 服务挂载与健康检查)
- **Agent 编排**: LangChain & LangGraph (构建 ReAct 机制的 Agent)
- **大模型接口**: DeepSeek / OpenAI API 兼容接口
- **前端交互**: Gradio 5+ (使用自定义 CSS 打造精美组件)
- **本地存储**: SQLite3

## 🚀 如何运行

### 1. 安装依赖

请确保你已经安装了 Python 3.10 或更高版本。在项目根目录下运行以下命令安装所需依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

项目默认使用 **DeepSeek** 大模型服务，请参考 `.env.example`，在根目录下创建一个 `.env` 文件，并填写你的 API Key。

```env
DEEPSEEK_API_KEY=你的_deepseek_api_key_在这里
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```
*(注：如果不使用 DeepSeek，你可以取消注释并使用 OpenAI 兼容配置)*

### 3. 启动应用

本项目已将前端 UI（Gradio）无缝集成到 FastAPI 后端中。只需要运行以下命令即可启动完整的应用：

```bash
uvicorn main:app --reload --port 8000
```

启动成功后，在浏览器中打开：
👉 **http://127.0.0.1:8000** （即可直接访问 PlannerAI 交互界面）

## 📁 核心目录结构

```text
PlannerAI/
├── main.py                  # 服务入口 (FastAPI 应用及挂载的 Gradio 前端)
├── app/                     # 核心应用逻辑
│   ├── agents/              # 智能体编排层 (LangGraph Agent, 计划生成逻辑)
│   ├── mcp/                 # MCP 工具箱 (包含意图提取、计划校验等原子工具)
│   ├── db.py                # SQLite 数据持久化层
│   ├── llm.py               # 大模型连接层
│   └── gradio_app.py        # 前端交互界面与样式定义
├── requirements.txt         # Python 依赖项
└── .env                     # 本地环境变量 (不提交至代码库)
```

## 🧠 计划生成逻辑解析

1. **工具调用 (Tool Usage)**: 
   Agent 在收到输入后，会自主决定调用提取时长的工具（`tool_extract_duration`）和分析可用时间的工具（`tool_parse_availability`）。
2. **逻辑编排**:
   - 当提取到充足的要素后，Agent 会调用 `tool_generate_plan` 生成结构化的 JSON 数据。
   - 如果遇到信息缺失（例如没提学习周期），Agent 会发起补充提问。
3. **前端渲染**:
   前端 `gradio_app.py` 中的异步生成器会捕获 `plan_sync` 事件，实时更新左侧边栏并允许用户将最新计划导出为 Markdown。

## 📝 许可证

MIT License
