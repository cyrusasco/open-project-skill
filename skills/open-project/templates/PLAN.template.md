# <PROJECT> — 管理 PLAN（草稿）

> 日期：YYYY-MM-DD HH:MM（當地時區）　路線：<new|reorg>　規模：<S|M|L>　狀態：<草稿｜已批>
> 本檔草稿寫入 `md-drafts/PLAN.DRAFT.md`；批准後 promote 做 `PLAN.md`（唯一權威）。
> `PLAN-REPORT.html` 係佢嘅視圖（同 `plan-data.json` 同源）；`md-drafts/*.DRAFT.md` 係各 MD 交付物草稿。
> 章節唔准刪，無內容寫「（暫無）」。**閘門係範圍制：做完指定範圍即可；零發現合法（明記「零發現」）；未查標 UNVERIFIED——唔准為湊數作嘢（見 skill 全域規則）。**

---

## §1 核實數字快照（每行連命令——冇命令唔准入表，AP-14）

> 涵蓋 Phase 1 六類，每類有事實或 UNVERIFIED；唔設最低行數。

| # | 類別 | 項目 | 值 | 來源命令（可重跑，唯讀優先） |
|---|---|---|---|---|
| 1 | 量級 | <檔數/行數/session 數> | <值> | <命令> |
| 2 | 資產 | <repo/folder/CLI/plugin> | | |
| 3 | 路徑 | <workspace/checkout/state> | | |
| 4 | 端口/服務 | <port→process> | | |
| 5 | 帳號 | <只記存在+位置，唔抄值> | | |
| 6 | 版本 pin | <runtime/dependency/binary hash> | | |

## §2 未知表（UNVERIFIED）

| 項目 | 點解查唔到 | 建議驗證方法 | 所需批准？ |
|---|---|---|---|

## §3 矛盾清單（reorg；零發現＝合法，明記）

| # | 矛盾 | 兩邊講法（檔案:行／原句節錄） | 邊個新／邊個啱 | 處理 |
|---|---|---|---|---|

## §4 痛點排行（reorg；零痛點＝合法，明記）

| # | 痛點 | 次數 | 出處（session ref＋日期＋原句 ≤120 字＋**深度 tag**） | 影響 | 對應方案（連去 §6 行號） |
|---|---|---|---|---|---|

## §5 角色重複統計（reorg；無 subagent 史＝「（暫無）」）

| 角色（bucket） | 次數 | 訊息數 | 出處 ref | 判斷型/機械型 | 深度 tag |
|---|---|---|---|---|---|

> **方法口徑（必填——記實際用嘅嘢）**：tool＝<平台 session 工具／用戶匯出／唯讀 SQL（邊條）>；scope＝<邊啲 session、時間範圍>；深度＝<每個來源 full/partial/summary-only/unread>。真係用咗 SQL 先貼 SQL。

## §6 工具化評估表（每個觸發器一行；結論 N/A 係合法最佳答案）

> **評估四條（每行必答）**：①沿用現有工具得唔得（邊個、點解唔夠）②自建維護成本（邊個維護、幾耐更新）③錯咗嘅風險影響 ④唔做會點。
> **結論合法值**：沿用現有／起 CLI／起 subagent／起 SKILL／自建 MCP／打包 Plugin／唔起（N/A）。
> 冷卻規則：首輪 agent ≤3。

| # | 觸發器（重複 ≥3／儀式／對接外部／要分發） | 證據（§4/§5 行號 or 訪談答案編號） | 評估①②③④ | 結論 | 理由 |
|---|---|---|---|---|---|
| T1 | | | | | |

### 開源候選表（new route 三層之②；gh 首選，已授權 connector 亦可；零工具→整表標 UNVERIFIED 留空，唔阻塞規劃）

| repo | license | last commit | star | 部署方式 | 點解啱 | 風險 | 狀態 |
|---|---|---|---|---|---|---|---|
| | | | | | | | <UNVERIFIED（無 gh）｜候選｜採用前待查> |

> 採用前必查：license 相容＋secret scan（R3 狀態制）＋依賴面。

## §7 Code map（六項；非 code 每項「（暫無）」）

| 項 | 內容 |
|---|---|
| Stack | |
| 入口 | |
| Run／Test／Build（實跑結果；有副作用嘅標 NOT_RUN+UNVERIFIED） | |
| 結構 | |
| 測試現況 | |
| 明顯 tech debt | |

## §8 草稿 manifest（逐檔；原檔狀態＝Phase 5 baseline）

| 草稿檔 | 對應模板 | 修邊條矛盾（§3 #） | DoD（點算完成） | 正式目標路徑 | 原檔狀態（sha256／NOT_EXISTS／DIRTY） |
|---|---|---|---|---|---|
| md-drafts/<name>.DRAFT.md | <template> | | | <PROJECT>/<name>.md | <sha256…／NOT_EXISTS／DIRTY> |

> promote 結果欄（Phase 5 填）：promote ／ STOPPED_DRIFTED（新 hash）／ FAILED_RECOVERED。

## §9 執行時序

| # | Phase | 時間 | 產出 |
|---|---|---|---|

## §10 風險（按發現填；零風險記「未發現」）

| # | 風險 | 機會 | 影響 | 緩解 |
|---|---|---|---|---|

## §11 批准請求表（PLAN 批核＝批准內容方向；啟用動作執行前逐類再確認）

| # | 動作 | target（具體檔/repo/host） | 副作用（寫檔/push/重啟/安裝/憑證/部署/出網） | 可逆性 | 狀態 |
|---|---|---|---|---|---|
| A1 | | | | | <待批／已批／NOT_RUN（原因）> |

## 逐檔草稿（跟喺下面，完整 wording——禁一句交差 AP-16；md-drafts/ 每份草稿對應 §8 一行）

（正文草稿放 `md-drafts/<name>.DRAFT.md`；§8 manifest 係索引。）
