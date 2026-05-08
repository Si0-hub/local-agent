# Local AI Agent Framework

使用 Python 建立的本地 AI 助手，學習 Agent 架構的練習專案。

---

## 架構分層

### 1. Application Layer（應用層）

負責與使用者直接互動的最外層。啟動時讓使用者選擇或建立專案與 session，接著進入互動式 CLI 循環接收輸入。每一筆輸入都會先判斷意圖，再決定走哪條執行路徑，最終將結果渲染回終端。也負責 session 的切換、清除等管理指令（`/new`、`/sessions`、`/switch`、`/clear`）。

### 2. Orchestration Layer（編排層）

負責把使用者意圖轉化為可靠的執行行動。首先自動分類輸入為「詢問（INQUIRY）」或「指令（DIRECTIVE）」：詢問直接進對話流；指令則啟動三階段編排——

- **Planner**：將任務拆解成有序的步驟清單
- **Executor**：逐步執行每個步驟，內嵌 ReAct loop，讓 LLM 可在執行中動態呼叫工具
- **Verifier**：執行完畢後驗證結果是否真正達成目標，失敗則觸發重試

三階段設計的目的是將「想怎麼做」、「實際去做」、「確認做到了」三件事拆開，讓每個角色只需專注自己的職責，提高可靠度。

### 3. Context Layer（上下文層）

負責控制每次送入 LLM 的訊息內容。對話歷史會隨著輪數增加不斷累積，若不加管理會超出模型的 context window 或浪費 token。這一層做兩件事：一是動態組裝訊息，根據 token 預算決定納入多少歷史；二是當歷史超過一定量（預設 30 條）時，自動將最舊的一半壓縮成摘要，以純文字保留語意但釋放空間。

### 4. Provider Layer（模型層）

統一的 LLM 介面，透過 LiteLLM 支援所有 Provider（Ollama、OpenAI、Anthropic 等）而無需改動上層程式碼。上層只需指定模型名稱與訊息，這一層負責實際發送請求、解析回應，以及管理多個 LLM 實例的註冊與取用。預設使用本地 Ollama 模型，可在設定中切換。

### 5. Tools Layer（工具層）

定義 Agent 可以呼叫的外部能力，與 LLM 的 function calling 介接。目前實作了一組檔案系統工具（讀取、寫入、搜尋、列目錄等），讓 Agent 能直接操作本地檔案。工具以統一的格式註冊，LLM 可在 ReAct loop 中自由選擇呼叫哪個工具、帶入什麼參數，並根據回傳結果決定下一步。

---

## 執行流程

```
使用者輸入
    │
    ├─ INQUIRY（詢問）─→ ReAct loop
    │                    LLM 思考 → 工具呼叫（視需要）→ 再思考，最多 10 次
    │
    └─ DIRECTIVE（指令）─→ Planner → Executor（ReAct）→ Verifier
                                                          └─ 未達成 → 重試
```

---

## 對話記憶持久化

每個專案的所有 session 存放於 `.agent/projects/<project-hash>/`，包含完整對話歷史（JSONL 格式）、壓縮後的長期摘要，以及系統提示詞，重啟後可無縫接續上次對話。

---

## 快速開始

```bash
pip install -r requirements.txt
python main.py
```

預設使用 Ollama 本地模型（`qwen3:1.7b`），也可在 `providers/registry.py` 切換為 OpenAI 或 Anthropic。
