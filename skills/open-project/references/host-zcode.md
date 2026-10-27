# ZCode host adapter — 保留既有政策

本檔只記 ZCode 適配，唔建立 Codex adapter，唔改 host runtime、model mapping、provider 清單、global rules、installed cache 或 hooks。觀察資料要寫當前 capture time／source；歷史數字唔係永久事實。

## 能力與身份

| 項目 | 工作契約 |
|---|---|
| 原生只手動觸發 enforcement | **UNKNOWN**；description／command 係指令層 advisory，唔證明 host 已強制 |
| 執行入口 | 用戶明確調用 open-project／`/open-project`／要求按本流程；一般新 project 唔自動觸發 |
| command 參數 | `commands/open-project.md` 保留 `$ARGUMENTS` 原文轉交 |
| agent 呼叫 | ZCode `Agent` tool，使用 `subagent_type`；只填實際可用 bare／namespaced role |
| session 輔助 | `ReadSessionContext`（RSC）；按實際可用工具與參數使用，摘要標 summary-only |
| DB 候選 | `Path.home() / ".zcode" / "cli" / "db" / "db.sqlite"`；存在唔代表授權或 schema 固定 |
| Plugin | 保留 `.zcode-plugin/plugin.json`、commands、skills、agents 等 ZCode 結構 |
| 已安裝位置 | 由 host／環境核實；可能涉及 `~/.zcode/skills`、`~/.agents/skills`、plugin cache；存在不等於 loaded |

記 requested role、child/session ID、observed role、實際工具與證據。role 同名／title 類似不證明載入同一定義；definition 不可見就 UNKNOWN。唔假設只可 bare name 或一定 namespaced。

## AP-17：現有模型政策不變

專屬 agent frontmatter 必須 line 1，`name`／`description`／`tools` 有效，**必須明寫用戶確認嘅有效 `model: <provider/model>` 字串**；唔留空、唔寫 `inherit`。保留既有觀察：專屬 agent 空值／inherit 可能靜默使用 provider 清單第一個；一般 subagent 先跟後台 default。因此 Phase 4 用已確認模型字串起完整草稿，未有只問該缺口，唔憑空配置。

模型問題已 **RESOLVED**；本修訂唔將舊問題變成 mapping、runtime 或 provider workaround 工程。不新增模型偏好、不改原有政策；loaded／observed 未實測仍標 UNKNOWN。checker 只辨識受支援 frontmatter；quoted scalar 與 bare scalar按同一語義讀取，unsupported YAML 會產生 gate ERROR、blocked ready；語法／host 能力未知另標 UNKNOWN，唔用 regex 猜綠。

agent 草稿 YAML 開頭第一行就係 `---`，不強加 DRAFT banner。用 packet draft 身份表達草稿；只宣告適用 normalization transform。

## Session discovery recipe

優先使用已核實、已授權而足以滿足全系統 inventory／全文搜尋嘅現有能力。RSC 可供後續深讀；如果只提供 topic／handoff summary，唔假設有 global discovery。必要時用既有 Python／SQLite 標準庫，唔另起 MCP、常駐服務、永久索引。

```text
python <SKILL_ROOT>/scripts/discover-sessions.py --help
```

按腳本當前 help 明傳 source／queries／output；操作必須 read-only。來源、schema 與欄位先核實，唔套未知 schema SQL。來源範圍係全部已授權可讀 sessions，metadata／可見 content 搜尋先於 directory／title 排序；**不設 directory/title 作第一層 WHERE**。用戶排除／權限拒絕照記，唔繞過。

1. 列 sources、schema、location、授權、T0/T1、query version。全 metadata inventory 包含主／子／可讀 archive；用 deterministic keyset 分頁。同來源 session ID 去重；跨 source 同 ID 仍保留 source＋revision/hash。
2. IDs 係 opaque，唔假設 `sess_` 或任何前綴。session／message／part 原始 ID 都保留。
3. 全可見 user／assistant text 用項目別名、repo、特徵詞、路徑、檔名、URL 做 query 組；JSON part 解碼後識別文字與來源 field。tool／summary另標，hidden reasoning 不可當原文證據。參數化 SQL；literal %／_ escape；唔以首 N hits 冒充完整。
4. `parent_id` 已驗證先 ancestors／descendants closure；parent／title 類似只係候選線索。fork 未驗證唔推斷。候選含 direct／probable／parent-child-context／mention/copied-context／rejected-with-reason。
5. directory／title 只作後段分類／排序；copied context可保留有用 continuation，唔當真歸屬亦唔一刀切丟棄。
6. WAL-aware URI `mode=ro`，`query_only=ON`，首讀建立 T0，短 read transaction 完 discovery／必要匯出即釋放。唔用 immutable 漏讀 WAL；唔等 LLM／用戶，唔長期保留 reader 令 WAL 累積。
7. 新 connection／後續深讀係新快照，另記 hash／時間；中斷唔冒充同 snapshot。可靠 time_updated 未證實前不宣稱增量完整，併發 delta 列未知／限制。
8. full／partial／summary-only／unread 每來源標範圍及 source-version refs；RSC 只回摘要＝summary-only。subagent 可讀性按實際結果，不將猜測當 host 限制。

coverage 至少記：metadata total、eligible/scanned/skipped/error parts、matched parts/messages/distinct sessions、parent closure、candidate classifications、confirmed/uncertain/rejected、深讀 tags、missing sources、query 組、命令、T0/T1、source version/hash、併發／中斷限制。唔輸出整庫私人內容，只呈交相關證據與可重跑方法。

## 檔案／執行／發布

從 authoring source 讀 raw baseline，唔修改 installed projection。腳本位於 `<PLUGIN_ROOT>/skills/open-project/scripts/`，PROJECT_ROOT 另傳；驗證不同 cwd 仍可執行。host config／重啟／plugin 安裝／push 只有既有明確授權先做。

ZCode package 保留原 `.zcode-plugin` metadata，license 從實際來源核實。package 內容與 source 對帳；PACKAGED、INSTALLED、LOAD VERIFIED 分開。fresh session 載入未實測＝UNKNOWN；不將 package JSON 合法當載入證明。

PowerShell REST 用 `curl.exe`，process 列表用 `tasklist /FO CSV`；長腳本用檔案避免 quoting。CLI 命令逐行呈現，唔用 `status | doctor | verify` 假裝可選項。doctor／verify／deploy／push 按用途與授權決定 N/A／NOT_RUN，唔無條件執行。
