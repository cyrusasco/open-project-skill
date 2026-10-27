# Workflow contract — packet 1.0

本契約適用用戶明確要求嘅 open-project 任務生命週期；唔係常駐全域規則。checker／技能提示只係 advisory；`--strict` 可改變 checker exit，唔提供 host／OS 攔截。既有授權持續有效，勿重複請批。

## 路徑與來源

`PLUGIN_ROOT` 係帶 `skills/` 嘅 package 根（host manifest 位置由 adapter 定義）；`SKILL_ROOT=<PLUGIN_ROOT>/skills/open-project`；`PROJECT_ROOT` 係用戶指定項目。所有腳本明傳 PROJECT_ROOT，唔依賴 cwd。staging 僅 `PROJECT_ROOT/md-drafts/`，source authoring、package、installed、loaded 分開記。

第一次讀取將受影響原檔嘅 raw bytes 時，記 resolved path、size、SHA-256、capture timestamp、revision／HEAD；不存在記 `NOT_EXISTS`。呢個先係 baseline，唔可以起草後重新讀檔取代。git dirty 另記，mtime 不證明作者。檔案／來源改動後建立新 revision、保留舊觀察。

## Canonical packet

`md-drafts/plan-data.json` 係唯一資料源；schema 以 `schemas/plan.schema.json` 為準。JSON schema 及腳本內部語義檢查一齊使用，唔靠散落 regex。必須有以下欄位：

| 欄位 | 契約 |
|---|---|
| schema_version | 字串 `1.0` |
| plan_id | 穩定 plan 身份 |
| revision | 正整數形式嘅數字字串，例如 `1` |
| host | host 識別字串 `zcode` 或 `codex`；能力觀察另放 coverage／facts |
| project | 項目資料，含 `name` |
| route／scale | new 或 reorg；S、M 或 L |
| requirements | ID、來源、desired behavior、可判定 acceptance；唔將 observed status 當需求 |
| sources | 每項有 `id`，可追溯來源快照 |
| facts／unknowns／conflicts／pains／roles | 對應 PLAN §1–§5；零發現用空 array＋原因資料 |
| tools／oss | §6 工具化決策、候選及限制 |
| risks／folder_changes | 風險、before/after、KEEP/ADD/MOVE/MERGE/ARCHIVE、owner、權威及引用影響 |
| drafts | 每個 planned 正式 MD 一列，含必交 product specification |

sources：`kind:file` 必含 path／sha256；外部 `session|url|tool|unknown` 保留 reference/url/locator 等 captured reference。required 外部來源要 `verified:true`＋可定位證據；unknown 唔可 ready。每引用保留 source ID、revision/hash、定位及 capture time；額外版本／時間 metadata 放 source.notes 或相應 facts／coverage，唔加 schema 不允許嘅 source top-level 欄位。unsupported/缺失來源明記，唔借用別個快照。

每個 draft 必須有：

| 欄位 | 意義 |
|---|---|
| id | packet 內唯一身份 |
| path | staging 草稿路徑 |
| target | PROJECT_ROOT 內唯一正式相對路徑 |
| template／kind／required | 模板來源、種類、是否本輪必交 |
| sha256 | 完整草稿 raw-byte SHA-256 |
| baseline_sha256 | 首讀原檔 SHA-256，或 `NOT_EXISTS` |
| expected_sha256 | 對草稿套用宣告 transforms 後嘅完整輸出 hash |
| transforms | 明列確定性轉換；唔默認填任何內容 |
| depends_on | 選用嘅 draft ID 依賴，promote 選擇須包含依賴 |

transforms 係不重複字串 array，例如 `["normalize_utf8_lf"]`；只准 `remove_draft_marker`（第一行必須精確係 `<!-- open-project:draft -->`）及 `normalize_utf8_lf`，唔做模糊刪除。冇 marker 就唔宣告 removal。agent frontmatter 必須 line 1，可只 normalize；唔為草稿身份加一行覆蓋 YAML。路徑、命令、模型、時間、權限、業務規則全部起草時寫定及 hash，唔喺 promote 時填 placeholder。

`product_specification.DRAFT.md` 係 required，S 規模都保留。所有 planned MD 必須完整 wording，唔准「保留現有…」或摘要代替。spec 只放 desired 功能／acceptance／來源；observed、修復、歷史進 status／memory／review。requirements、source、draft、folder 與 approval IDs 要可追溯。

## Render、gate 與判定

```text
python <SKILL_ROOT>/scripts/render-plan.py <PROJECT_ROOT>
python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT>
python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT> --strict
python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT> --json
```

renderer 從 JSON 寫 `md-drafts/PLAN.DRAFT.md` 與 `md-drafts/PLAN-REPORT.DRAFT.html`，兩者顯示 `Packet SHA-256: <digest>`，digest 由 canonical JSON packet 計算。不要手改 views；改 JSON 重新 render。HTML 包全草稿及相對導航、完整表格、安全 escaped／serialized 字串，離線零 CDN；0／null／float／UNVERIFIED 保真。

gate 預設 advisory：顯示 missing／unknown／suggestions（尾部）但可 exit 0；`--strict` 對 required failure／unknown 用非零。可用 `--out PATH` 儲存報告。**exit、ready、required、approved、ACCEPTED 各自分開**：packet 缺件 INCOMPLETE，無 P0 不代表 ACCEPTED。required P1 未處理／無具體書面豁免、required coverage unknown 均不能 ACCEPTED。

## 獨立批准證據

先完成整套具體結果俾用戶過目。批准另存 JSON，唔往 packet 塞自我批准。批准文件只記用戶決定，唔授 OS 權限，唔取代服務憑證或現有授權邊界。

批准頂層**只包含**：
`plan_id`、`revision`、`packet_sha256`、非空 `approved_by`、ISO 8601＋offset `approved_at`、非空 `actions`。

每個 action **只包含**：
`draft_id`、`target`、`draft_sha256`、`baseline_sha256`、`expected_sha256`、`transforms`、`effects:["write_file"]`。

action 必須精確等於所選 packet draft，含所有選定依賴。plan、revision、JSON digest、draft、target、baseline、expected、transform、effects 任一變動均使舊批准失效，需形成新 packet／具體新批准。唔推論同意 PLAN＝同意安裝／host config／restart／push／憑證／部署；先查既有授權，有缺口先問。

## Promote 與恢復

```text
python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON>
python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON> --apply
python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON> --apply --resume
```

預設 read-only dry-run，不建目錄／journal。apply 先寫前核對、位元組備份、同目錄 temp、replace 及 journal；內部 `.gitignore` 排除操作記錄。paths／junction／target uniqueness／dependencies／hash 失配停止，唔將 mismatch 當建議跳過。

target==expected → no-op；target==原 baseline／原定 NOT_EXISTS → 可正常處理；其他 → STOPPED_DRIFTED。中斷只可用同 packet＋同 approval resume；合作鎖不阻外部 writer，唔宣稱 global CAS。

記錄位於 `.open-project-promotion/journals/<hashed-plan-id>-<approval-hash>.json`。唯一備份位於 `.open-project-promotion/backups/<uuid>/<target-relative-path>`；備份原始 bytes 唔加 banner，同名檔唔碰撞，不入 Git。FAILED_RECOVERED／FAILED_UNRECOVERED 嘅 `recovery_scope=target_file_bytes`：恢復目標檔 bytes，備份／journal 留存，新空 parent directories 可能留存。恢復失敗必須顯示，唔冒稱還原完成。

FROZEN 舊 bytes 永遠不改（包括 banner）；新版本＋external manifest 記 supersedes／hash／授權／驗收。memory append 新 entry 及 correction／supersedes／revokes event，舊 row 不改；current 由事件鏈推導。

## 可重跑證據與交接

記 source revision/hash、命令、exit、輸出、覆蓋與未測項，唔以舊 SELFTEST／SKILL-REPORT 代替當前測試。standard-library unittest 使用 synthetic fixtures；host fresh-session、loaded role、browser、live integration 逐項獨立列 coverage。N/A 具體說明；LOCAL COMPLETE／NOT_PUSHED／PACKAGED 可合法交付。source、package、installed、loaded 唔混用；不自行同步 cache／global rules。


所有 manifest drafts，包括 required:false，都必須有效、完整可讀、hash 相符；false 唔容許缺檔／半份。未採用工具唔列 draft row，喺 tools 寫 N/A。選填 packet 欄位包括 graph、code_map、timeline、execution、approval_requests、coverage、suggestions；approval_requests 唔係已批准證據。

## 舊 packet 遷移

v3 packet 1.0 係 breaking contract：舊 Markdown-only／寬鬆 JSON packet 會 INCOMPLETE。保留舊 packet、歷史與 approvals；由已驗證 read-time evidence 及完整 drafts 重建 structured packet。已知 baseline 作明確舊紀錄保留；未知或已漂移來源需要新讀取、新 revision，唔將晚補 hash 冒充首次 baseline。重新 render／gate，取得綁定新內容嘅具體 approval；唔推定舊 approval 自動有效。
