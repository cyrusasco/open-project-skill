# <PROJECT> — 管理 PLAN

> Canonical：`md-drafts/plan-data.json`，schema_version `1.0`
> plan_id：<PLAN_ID>　revision：<POSITIVE_INTEGER_STRING>
> host：<HOST>　route：<new|reorg>　scale：<S|M|L>
> capture time：<ISO8601_WITH_OFFSET>　packet SHA-256：<PACKET_DIGEST>
> 本檔係 11 節內容指引。實際 PLAN／HTML 由 render-plan.py 同源生成；唔手改 rendered views。
> scope complete、ready、approved、ACCEPTED 分開；advisory exit 0 唔等於通過。

## §1 核實數字／事實與首次讀取快照

六類逐項有事實或 UNVERIFIED，不設最低行數。每數字連產生佢嘅命令／query／snapshot。先 raw-byte 讀取、記 baseline，先起草。

| ID | 類別 | 事實／值 | 狀態 | source ID／版本／定位 | 可重跑命令 |
|---|---|---|---|---|---|
| F1 | 量級 | <files/lines/sessions> | <PASS/UNVERIFIED> | <source ref> | <command> |
| F2 | 資產 | <repo/folder/CLI/plugin/docs> | | | |
| F3 | 路徑 | <workspace/checkout/state/log> | | | |
| F4 | 端口／服務 | <existence/status> | | | |
| F5 | 帳號 | <只記存在／位置，唔記 secret 值> | | | |
| F6 | 版本 pin | <runtime/lockfile/binary hash> | | | |

| source ID | 類型／ref | resolved path／locator | revision/hash | 首讀 size／capture time | 覆蓋／verified |
|---|---|---|---|---|---|
| SRC1 | <file/session/tool/url> | <locator> | <raw SHA-256 or source revision> | <bytes; ISO time> | <scope; verified> |

## §2 未知表（UNVERIFIED）

| ID | 未知／缺失來源 | 原因 | 驗證方法／所需授權 | 影響 required coverage |
|---|---|---|---|---|
| U1 | <unknown> | <reason> | <safe next action> | <yes/no + impact> |

零未知可以記「零發現」，不可由未讀推論唔存在。

## §3 矛盾清單與權威順序

| ID | 衝突原文／來源版本 | 現行權威／理由 | 處理決定 | 受影響 draft／requirement |
|---|---|---|---|---|
| C1 | <file:location + hash or session ref> | <authority> | <decision> | <IDs> |

原檔實讀；臨時 bug／workaround 不自動當 desired requirement。無矛盾記零發現。

## §4 痛點排行

| ID | 痛點 | 可見原文／source-version ref | 深讀 tag／範圍 | 影響 | 對應 §6 |
|---|---|---|---|---|---|
| P1 | <evidence-backed pain> | <quote ≤120 chars + ref> | <full/partial/summary-only/unread> | <impact> | <tool ID> |

冇證據唔湊數；零痛點合法。

## §5 角色統計、發現方法與 coverage

| 角色 ID | 實際角色／分類 | 次數／訊息數 | source ref／parent 關聯 | 判斷或機械工作 | 深讀 tag |
|---|---|---|---|---|---|
| ROLE1 | <role> | <count> | <evidence> | <type> | <tag> |

### 全系統發現口徑

| 欄位 | 實際方法／結果 |
|---|---|
| run／source／schema | <run ID, source IDs, schema, authorized scope> |
| T0／T1 | <ISO times + offset; snapshot/revision/hash> |
| inventory | <全 metadata；主／子／可讀 archive；opaque IDs；keyset 分頁> |
| 全文 query 組 | <versioned aliases/repo/terms/files/URLs; actual tool/SQL + params> |
| 優先順序 | <全 metadata／可見 content BEFORE directory/title 排序> |
| parent closure | <verified parent_id ancestors/descendants; unknown fork> |
| metadata／content coverage | <total; eligible/scanned/skipped/error; reasons> |
| 命中 | <parts/messages/distinct sessions> |
| 候選分類 | <direct/probable/parent-child-context/mention-copied/rejected + reasons> |
| 深讀 | <full/partial/summary-only/unread per source + range> |
| 缺失／併發／中斷 | <sources/delta/reconnect snapshots/limits> |
| 可重跑方法 | <actual command/query/params; SQL only if actually used> |

reorg S/M/L 都先全域 discovery；S 只縮深讀。WAL-aware read-only 短 transaction，discovery／必要匯出完即釋放；唔等 LLM／用戶。新 connection 深讀另記 snapshot。RSC 摘要只可 summary-only。不要用舊 directory/title WHERE 篩走全文候選。

## §6 工具化評估及開源候選

| ID | 觸發器／需求來源 | 沿用現有工具 | 維護成本／owner | 錯誤影響 | 唔做會點 | 結論／理由 |
|---|---|---|---|---|---|---|
| T1 | <requirement/interview/pain ID> | <existing + limitation> | <cost> | <risk> | <impact> | <reuse/CLI/subagent/SKILL/MCP/Plugin/N/A> |

重複 ≥3 係評估觸發器，唔代表必須自建。首輪 agents ≤3；new 預估 0–1。0 agents／不建 MCP／Plugin N/A 合法。

### new 三層工具鏈

本地已裝 SKILL/MCP/CLI/Plugin → 已授權 gh／GitHub connector／官方來源搜尋 → 預估 subagent 需求。每推薦引用訪談／requirement ID。無搜尋能力則 UNVERIFIED，唔阻離線規劃。

| repo | license／來源 | last commit | 部署方式 | 適用原因／需求 ID | 風險／依賴 | 狀態 |
|---|---|---|---|---|---|---|
| <repo> | <verified or unknown> | <time/ref> | <method> | <reason> | <risk> | <candidate/UNVERIFIED> |

採用前核實 license 相容、secret scan 及依賴面；唔自動用 MIT。

## §7 Code map

| 項目 | 現況／證據 |
|---|---|
| Stack／lockfile | <actual source> |
| 入口 | <paths> |
| Run／Test／Build | <command; effects; exit; NOT_RUN reason if unavailable> |
| 結構 | <actual map> |
| 測試現況 | <coverage/limits> |
| Tech debt | <evidence-backed items or zero findings> |

非 code 項目逐項 N/A＋理由，唔為閘門起 CLI。

## §8 完整 MD 草稿 manifest

| draft ID | path | target | template／kind／required | sha256 | baseline_sha256 | expected_sha256 | transforms／depends_on |
|---|---|---|---|---|---|---|---|
| D-SPEC | md-drafts/product_specification.DRAFT.md | product_specification.md | product_specification.template.md／<kind>／true | <draft hash> | <first-read hash or NOT_EXISTS> | <output hash> | <exact declared list> |

每個 planned 正式 MD 一列、完整草稿逐檔呈交（包括 required:false）；未採用項目唔列 draft row、工具決策寫 N/A；**spec 必交**。DIRTY 另列，唔代替 baseline。transforms 係不重複字串 array，只准 remove_draft_marker（第一行精確 `<!-- open-project:draft -->`）及 normalize_utf8_lf；agent YAML line1，不強加 marker。原文搬移不得以「保留現有…」省略。

| draft ID | 解決矛盾／需求 | DoD | 首讀 baseline source ID | 依賴／引用影響 |
|---|---|---|---|---|
| <ID> | <C/R IDs> | <testable completion> | <source ID> | <IDs + impact> |

完整草稿由 renderer 納入 PLAN／HTML 證據視圖。promotion 結果按逐檔記 promoted／no-op／STOPPED_DRIFTED／BLOCKED／FAILED_RECOVERED／FAILED_UNRECOVERED。

## §9 Folder before／after 與執行時序

| ID | before | after | 決定 | 用途／owner | 權威來源 | 引用／依賴影響 |
|---|---|---|---|---|---|---|
| FC1 | <old path or none> | <new path or same> | KEEP/ADD/MOVE/MERGE/ARCHIVE | <purpose; owner> | <source ID> | <refs to update> |

只建採用目錄；FROZEN 舊 bytes 不改，supersedes 關係放外部 manifest；memory 只 append correction events。

| 次序 | Phase | 操作／依賴 | 輸出／驗收 | 授權 |
|---|---|---|---|---|
| 1 | <phase> | <action> | <evidence> | <existing/pending/N/A> |

## §10 風險與限制

| ID | 風險／未知 | 觸發／來源 | 影響 | 緩解／owner | 殘留限制 |
|---|---|---|---|---|---|
| RISK1 | <risk> | <evidence> | <impact> | <action> | <known limit> |

零風險記「未發現」，唔宣稱絕對安全。host 原生手動觸發／loaded definition／fresh session 未實測＝UNKNOWN。合作鎖非全域 CAS；恢復只對 target_file_bytes，journal／backup／空新目錄可能保留。

## §11 需求追溯及批准請求

| requirement ID | 來源 ID／版本 | desired behavior | 固定 acceptance | required | 對應 draft／驗收 |
|---|---|---|---|---|---|
| REQ1 | <explicit request/source> | <desired behavior> | <measurable pass/fail> | true | <draft/test refs> |

observed status／修復過程另放 status、memory、review，唔混入 desired contract。

| ID | 動作／具體 target | effects | 可逆性 | 現有授權證據 | 狀態／缺口 |
|---|---|---|---|---|---|
| A1 | <specific action and target> | <write_file/push/config/install/restart/deploy/network> | <rollback> | <user decision ref> | <approved/pending/NOT_RUN/N/A> |

此表係 approval_requests，唔係腳本可用嘅自我批准。promotion 另存 approval JSON：plan_id、revision、packet_sha256、approved_by、approved_at、actions；逐 action 綁 draft_id、target、draft_sha256、baseline_sha256、expected_sha256、transforms、effects。hash／內容／target 變動需新 packet 及相符批准。approval 唔提供 OS 權限；已有相同範圍明確授權唔重複問。

## 報告尾部建議

<advisory suggestions、scope limits、N/A 理由、剩餘驗證、下一步；唔用建議覆蓋 missing required／UNVERIFIED 狀態。>
