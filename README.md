# 🎮 renpy-mcp — Ren'Py AI 原生开发助手

**语言 / Languages:** **简体中文** | [English](./README.en.md)

一个 MCP（Model Context Protocol）服务器，让 AI Agent（Cursor、Claude 等）成为 Ren'Py 视觉小说的**原生开发助手**——读代码、写代码、查官方文档、自动修复、编译验证，全流程闭环。

基于 [FastMCP](https://github.com/jlowin/fastmcp) 构建，内置 Ren'Py 中文官方文档（23 页 / 580KB），跨平台支持 Windows / macOS / Linux。

> ⭐ **如果这个项目帮到你，欢迎去仓库点个 Star 支持一下～**
> 👉 [https://gitee.com/gdouage/renpy-mcp](https://gitee.com/gdouage/renpy-mcp)
> 你的一颗星，是个人开发者继续更新的最大动力 ❤️

| | |
|---|---|
| 仓库 | [gitee.com/gdouage/renpy-mcp](https://gitee.com/gdouage/renpy-mcp) |
| 协议 | [MIT](./LICENSE) |
| 作者 | abbuibuibui |
| 联系 | [3244940576@qq.com](mailto:3244940576@qq.com) |
| 文档来源 | [doc.renpy.cn](https://doc.renpy.cn/zh-CN/) |

---

## 📌 项目介绍

Ren'Py 没有内置编辑器，开发者手动写 `.rpy` 文本文件再点「启动项目」测试。这个 MCP 让 AI 直接理解 Ren'Py 项目结构——不用你手动贴报错，AI 自己就能读代码、查文档、改代码、编译验证、自动修 bug。

| 能力 | 说明 |
|------|------|
| 读代码 | 列出全部 label / 读取指定 label 脚本 / 盘点角色立绘 screen 声明 / 查找 jump-call 调用关系 |
| 查文档 | 内置 23 页 Ren'Py 中文官方文档，关键词搜索返回相关段落，离线可用 |
| 写代码 | 往任意 .rpy 文件注入代码（8 种定位模式），自动建文件，保留 BOM |
| 编译验证 | 编译 + lint 一次跑完，返回结构化错误（文件名 + 行号 + 消息） |
| 自动修复 | 检测并修复 5 类常见问题：`return True/False`、缺 `from` 子句、BOM 不一致、漏标签、陈旧存档 |
| 存档管理 | 列出 / 清除 / 清除陈旧存档（修复 `Could not find return label` 报错） |
| 素材管理 | 拷贝图片 / 字体 / 音频到项目，获取图片尺寸算立绘定位 |
| 跨平台 | Windows / macOS / Linux 全支持，SDK 路径自动探测 |

**核心流程：**

```text
查文档(search_docs) → 读代码(list_labels) → 写代码(exec_rpy) → 编译验证(check_project) → 自动修复(auto_fix)
```

---

## 🏗️ 项目架构

```text
┌──────────────────────────────────────────────┐
│              AI Agent (Cursor / Claude)        │
│                  通过 MCP 协议调用               │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              renpy-mcp Server                  │
│              (FastMCP, 15 个工具)               │
├──────────┬──────────┬──────────┬──────────────┤
│  读代码   │  写代码   │  验证修复  │   文档知识库   │
│ (4 tools)│ (1 tool) │ (5 tools)│  (2 tools)  │
├──────────┴──────────┴──────────┴──────────────┤
│                  底层能力                       │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 正则解析 │  │ 文件读写  │  │ subprocess    │  │
│  │ .rpy文件 │  │ BOM安全  │  │ 调用Ren'Py SDK │  │
│  └─────────┘  └──────────┘  └───────────────┘  │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│           Ren'Py SDK (renpy.py)               │
│     compile · lint · 项目文件 (.rpy/.rpyc)     │
└──────────────────────────────────────────────┘
```

**目录结构：**

```text
renpy-mcp/
├── src/renpy_mcp/
│   ├── server.py              # MCP 服务入口 + 工具注册
│   ├── project.py             # 标签解析：list_labels / read_script / find_references / list_definitions
│   ├── executor.py            # 代码注入：exec_rpy（8种定位 + CJK字体）
│   ├── build.py               # 编译验证：compile / lint / check_project / manage_saves
│   ├── fixer.py               # 自动修复：auto_fix（5类修复器）
│   ├── assets.py              # 素材管理：copy_asset / get_image_size
│   ├── docs_search.py         # 文档搜索：search_docs / list_doc_pages
│   ├── config.py              # SDK 路径配置（跨平台自动探测）
│   └── docs/                  # 内置官方文档（23页，580KB）
│       ├── quickstart.txt     # 快速入门
│       ├── screens.txt        # 界面语言（77KB）
│       ├── screen_actions.txt # 界面行为（60KB）
│       ├── transforms.txt     # 变换和ATL（43KB）
│       ├── gui.txt            # GUI定制化（44KB）
│       └── ...                # 共23个文档页面
├── AI_GUIDE.md                # AI Agent 操作规范
├── CHANGELOG.md               # 变更日志
├── pyproject.toml             # 包配置
├── LICENSE                    # MIT 协议
├── README.md                  # 中文（默认，Gitee 首页展示）
└── README.en.md               # English
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 协议 | MCP (Model Context Protocol) |
| 框架 | FastMCP |
| 语言 | Python 3.12+ |
| 文档解析 | Python 标准库 html.parser |
| 图片处理 | Pillow |
| 构建系统 | setuptools |
| SDK 调用 | subprocess 调用 Ren'Py SDK |

---

## 🚀 快速开始

### 1. 环境要求

- Python **3.12+**
- Ren'Py SDK **8.0+**（用于编译和 lint）
- 支持 MCP 的 AI 客户端（Cursor、Claude Desktop 等）

### 2. 获取代码

```bash
git clone https://gitee.com/gdouage/renpy-mcp.git
cd renpy-mcp
```

### 3. 安装

```bash
# 创建虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .

# macOS / Linux
.venv/bin/pip install -e .
```

### 4. 配置 MCP 客户端

#### Cursor

添加到 `~/.cursor/mcp.json`（不存在则创建）：

```json
{
  "mcpServers": {
    "renpy-mcp": {
      "command": "D:/absolute/path/to/renpy-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "renpy_mcp.server"],
      "env": {
        "PYTHONPATH": "D:/absolute/path/to/renpy-mcp/src",
        "RENPY_SDK_PATH": "D:/absolute/path/to/renpy-sdk"
      }
    }
  }
}
```

#### Claude Desktop

添加到 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "renpy-mcp": {
      "command": "/absolute/path/to/renpy-mcp/.venv/bin/python",
      "args": ["-m", "renpy_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/renpy-mcp/src",
        "RENPY_SDK_PATH": "/absolute/path/to/renpy-sdk"
      }
    }
  }
}
```

> **注意：** macOS / Linux 用 `bin/python` 替代 `Scripts/python.exe`。
> 设置 `RENPY_SDK_PATH` 指向你的 Ren'Py SDK 目录（如 `renpy-8.5.3-sdk`）。未设置时服务器会自动扫描常见路径。

### 5. 重启客户端 🎬

重启 Cursor / Claude Desktop，MCP 服务自动启动。AI 现在可以直接操作你的 Ren'Py 项目。

---

## 📡 15 个工具一览

### 读代码（4 个）

| 工具 | 功能 |
|------|------|
| `list_labels` | 列出全项目所有 label（可选 rich 模式：参数、jump 目标、call 目标、返回值） |
| `read_script` | 读取指定 label 的完整代码块（BOM 安全） |
| `find_references` | 查找全项目中对某 label/screen 的所有 jump/call 引用 |
| `list_definitions` | 盘点所有角色、立绘、transform、screen、default、define 声明 |

### 写代码（1 个）

| 工具 | 功能 |
|------|------|
| `exec_rpy` | 往任意 .rpy 文件注入代码（8 种定位：end/top/inside/after/before/replace/replace_all/自动建文件） |

### 编译验证（3 个）

| 工具 | 功能 |
|------|------|
| `compile_project` | 编译 .rpy → .rpyc，抓语法错误（可强制清缓存） |
| `lint_project` | 跑 Ren'Py lint 静态分析（查未定义变量、不可达代码等） |
| `check_project` | 一次跑完编译 + lint（编译不过则跳过 lint） |

### 自动修复（2 个）

| 工具 | 功能 |
|------|------|
| `auto_fix` | 自动检测并修复 5 类问题，修复后重新编译验证 |
| `list_fixers` | 列出所有可用修复器 |

**auto_fix 支持的 5 类修复：**

| 修复器 | 类型 | 做什么 |
|--------|------|--------|
| `return_values` | 改代码 | `return True/False` → `$ _label_result = True/False` + `return` |
| `missing_from` | 改代码 | `call xxx` → `call xxx from _call_xxx_N` |
| `bom_normalize` | 改代码 | 有 CJK 内容的文件加 BOM，没 CJK 的去 BOM |
| `missing_labels` | 只报告 | 检测 jump/call 到不存在的 label |
| `stale_saves` | 只报告 | 检测 `_reload-*`/`_tracesave-*` 残留存档 |

### 存档管理（1 个）

| 工具 | 功能 |
|------|------|
| `manage_saves` | list（列出存档）/ clear（全删）/ clear_stale（清陈旧存档） |

### 素材管理（2 个）

| 工具 | 功能 |
|------|------|
| `copy_asset` | 拷贝图片/字体/音频到项目（自动补 `game/` 前缀） |
| `get_image_size` | 获取图片尺寸（算立绘定位 transform 用） |

### 文档搜索（2 个）

| 工具 | 功能 |
|------|------|
| `search_docs` | 搜索内置 Ren'Py 中文官方文档（23 页），返回相关段落 |
| `list_doc_pages` | 列出所有可用文档页面 |

---

## 📝 典型工作流

### 场景 1：接手陌生项目

```text
list_labels(rich=True)    → 看全项目结构和跳转关系
list_definitions()         → 看有哪些角色/立绘/screen
read_script("start")      → 读入口标签代码
find_references("chapter_01") → 看谁调用了这个标签
```

### 场景 2：写新功能

```text
search_docs("Movie")      → 查官方文档怎么播放视频
exec_rpy(...)              → 根据文档写正确的代码
check_project(force=True)  → 编译 + lint 验证
```

### 场景 3：遇到报错自动修复

```text
auto_fix()                 → 自动检测并修复 5 类常见问题
manage_saves("clear_stale") → 清掉导致崩溃的陈旧存档
```

### 场景 4：重构前检查影响范围

```text
find_references("arrow_round")  → 看谁调了它（12 处）
find_references("chapter_03")   → 没人调 = 死代码
find_references("typo_label")   → defined=False = 有 jump 指向不存在的标签
```

---

## 💡 设计说明

- **文档离线可用**：23 页官方文档打包在 `src/renpy_mcp/docs/`，不需要网络
- **BOM 安全**：所有文件读写使用 `utf-8-sig`，不会漏掉第一行的 label
- **CJK 字体可选**：`exec_rpy` 的 `auto_cjk_font` 默认关闭，不静默改 gui.rpy
- **SDK 自动探测**：未设 `RENPY_SDK_PATH` 时自动扫描常见路径，按修改时间取最新
- **修改类修复器保留 BOM**：写入时检测原文件是否有 BOM，有则保留
- **只读检查器不改代码**：`missing_labels` 和 `stale_saves` 只报告不修改

---

## 💬 反馈与贡献

如果这个项目对你有帮助，拜托：

1. ⭐ 去仓库点个 **Star**：[renpy-mcp](https://gitee.com/gdouage/renpy-mcp)
2. 🐛 遇到问题提 [Issue](https://gitee.com/gdouage/renpy-mcp/issues)
3. ✉️ 想交流可发邮件：[3244940576@qq.com](mailto:3244940576@qq.com)（作者：abbuibuibui）

也欢迎提交 Pull Request（请先说明改动目的与测试方式）～

---

## 📄 许可证

本项目基于 [MIT License](./LICENSE) 开源。

```text
Copyright (c) 2026 abbuibuibui
```
