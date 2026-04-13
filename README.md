# Local AI Agent Framework

使用 Python 建立的本地 AI 助手，學習 Agent 架構的練習專案。

### 1. Application Layer (應用層)

### 2. Orchestration Layer (編排層)

### 3. Context Layer (上下文層)

### 4. Provider Layer (模型層)

統一的 LLM 介面，透過 LiteLLM 支援所有 Provider — 決定「誰來想」。

- `providers/base.py` — `LLM` class (基於 litellm)、`Message`、`Response`
- `providers/registry.py` — `ProviderRegistry`，集中註冊管理所有 LLM

## Project Structure

```
agent/
├── main.py                 # CLI 入口
├── agent.py                # Agent 核心
├── providers/
│   ├── __init__.py
│   ├── base.py             # LLM, Message, Response
│   └── registry.py         # ProviderRegistry
├── requirements.txt
└── README.md
```
