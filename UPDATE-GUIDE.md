# open-project 兩版更新與安裝交接

同一 repo 保留兩個獨立 host 版本。按所用 host 更新來源，唔合併整條 branch，亦唔用另一版覆蓋已運作嘅 harness 設定。

| Host | Branch | Skill revision | Plugin version | 原生整合 |
|---|---|---|---|---|
| ZCode | `main` | `3.0.0` | `0.1.0` | 保留 `.zcode-plugin`、commands、Agent／subagent_type、ReadSessionContext 及既有 model／provider 規則 |
| Codex | `codex-port` | `3.0.0-codex.2` | `0.1.1` | portable plugin、native TOML agents、JSONL adapter、手動叫用 policy |

版本以各 branch 嘅 `VERSION`、`SOURCE.json`、manifest 為準。更新前先比較本地修改，保留原檔／設定及來源記錄；唔自行覆蓋已安裝 cache、全域指令或其他插件。

## 已有共用改進

`main` 已包含 v3 共用修正：packet 1.0 契約、必交 specification／完整草稿、行級 agent 解析、內容 hash／canonical views 核對、全系統 session discovery、數值保真離線 HTML，以及 dry-run／漂移停止／備份／journal／重跑 no-op 嘅 promote。

模型跟用戶／後台設定問題已 RESOLVED。更新唔重新設計模型選擇，亦唔搬另一 harness 嘅 model、agent、工具或 manifest 規則。之後共用修正按檔／功能選擇移植，再分別測試兩版。

## Codex 安裝及手動叫用

只喺 `codex-port` 來源根目錄、你正常有寫入權限嘅 PowerShell 7 使用本機安裝入口（Python 3.11+）：

```powershell
.\scripts\install-plugin.ps1
```

入口使用 Codex 原生 marketplace／plugin 安裝流程；唔直接改 cache 或全域模型。若當前來源未包含此入口，先更新 `codex-port`，或按該 branch README 嘅已核實 CLI 指令安裝。寫入 `config.toml` 被拒絕係安裝失敗，唔可以將打包／舊版載入結果當成功；保留錯誤及現有設定。

Codex 版 `agents/openai.yaml` 已設定 YAML boolean `policy.allow_implicit_invocation: false`。用時喺 Codex 訊息／skill picker 明確選取，以下係 prompt，唔係 PowerShell 命令：

```text
$open-project-codex:open-project new <goal or folder>
$open-project-codex:open-project reorg <project folder>
```

安裝狀態、實際載入名稱／版本、手動及一般任務觸發行為分開驗證。已經開住嘅 session 唔證明已重新載入新版；更新後以新 session／host 支援嘅載入流程核對。單純安裝唔會建立 project folder 或啟動開案流程。

## ZCode 更新及手動叫用

ZCode 只更新 `main`。用 ZCode 自己支援嘅安裝／載入流程，唔照搬 Codex marketplace 指令或 invocation policy 欄位。實際 namespace 以 host 顯示為準，例如：

```text
/open-project new <goal or folder>
/open-project reorg <project folder>
```

ZCode 原生「啟用後仍只手動觸發」尚未實測保證。文件要求明確叫用，唔等於 host 強制；未核實前可於不用時停用此 plugin。先盤點舊 standalone skill／command，避免另一份仍自動觸發或遮住新版本；只處理已選定副本，保留其他設定。

## 新內容、GitNexus 與驗收

- `new` 先列清 project folder 嘅位置／用途；`reorg` 沿用現有 root，再按 PLAN 新增所需目錄。Phase 4 只寫 project 內 `md-drafts/`：JSON、PLAN、全文草稿、spec、離線 HTML；正式目錄／內容按具體批准及漂移檢查落地。
- Codex profile 每份 PLAN 必列 `gitnexus-project-onboarding`，逐個新建／更新 Skill、Plugin 交付物記 graph／catalog 範圍、步驟、驗收、blockers、evidence；G6 擋缺 onboarding 決策／結構不完整，reviewer 另核對產物無漏項及證據內容。呢個 profile 唔搬入 ZCode。
- 現有 onboarding Skill 核實版本仍係 copied-JavaScript fixture MVP，唔係真實專案／Markdown Skill 嘅通用 adapter。缺 reviewed adapter 或 catalog 入口就列 `BLOCKED`；Skill／Plugin 嘅 catalog obligation 唔可以用 N/A 略過，亦唔自動 index 全聊天／shared Skills。
- 計劃齊件唔代表已 onboarding。沿用現有 graph、capability catalog、immutable casebook owner；真實寫入／backend verification 按實際 scope／effects 及既有有效授權執行，唔因 file promote 已批而順帶授權。
- `PACKAGED`、`INSTALLED`、`LOAD_VERIFIED`、`INVOCATION_VERIFIED` 各自有證據；synthetic PASS／CLI exit 0 唔代表全部完成。舊 packet 補新內容後升 revision，重新 render／gate，唔沿用不匹配嘅 approval。

## 可直接交俾 ZCode 嘅更新 prompt

```text
請更新 open-project：來源只用 cyrusasco/open-project-skill 嘅 main。
先記 repo/branch/HEAD、本地差異、已安裝版本／來源同相關檔案 raw hashes；保留本地修改及原有備份，唔直接覆蓋 dirty files。
採用 main 已有共用 v3 修正；唔 merge codex-port，唔搬 Codex agent TOML、JSONL adapter、G6 profile 或 policy 設定。
逐項保護而家有效嘅 ZCode model/provider、agent frontmatter、tools/commands、hooks、global instructions、host config；模型問題已 RESOLVED，唔重新修改。
先建獨立 package，再跑該版本 synthetic tests、gate 負例、renderer 數值／全文視圖及 promote dry-run／no-op／drift 驗證；唔對 live session DB 寫入。
按我已授權範圍，用 ZCode 支援方法更新選定 plugin；任何額外 host config/hook/權限/其他副本變更先列具體內容及需要，唔順帶做。
喺新 session 核對實際 skill/command/agent 載入來源、版本、namespace；測明確叫用同普通無關任務嘅觸發行為。未驗證就標 UNKNOWN，唔寫手動保證。
交付版本／路徑／hash／命令／exit／測試覆蓋、保留設定對照、載入／觸發證據、未完成項及 rollback 方法。唔以打包或舊測試當實機成功。
```
