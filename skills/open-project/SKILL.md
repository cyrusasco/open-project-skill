---
name: open-project
description: "只喺用戶明確調用 open-project、/open-project 或要求按本流程開案／重整／交接時使用。Phase 0–9：意圖、事實、全系統歷史發現、review、完整 PLAN／MD 草稿／JSON／離線 HTML、批准、受控 promote、按評估實作、獨立審核及交接。普通新 project 或一般編程請求唔會自動觸發。"
---

# open-project — 明確調用嘅開案／重整流程

本 skill 只處理用戶明確要求嘅 `new`／`reorg` 任務生命週期。唔因為見到新 folder、repo、普通 coding task 就自動啟動，唔寫全域規則或自動更新 installed cache。文件／對話用繁體中文／粵語；代碼、路徑、commit message 用英文。例子只用 `<PROJECT>` 等 placeholder；讀到嘅項目資料只寫入該項目。

規模 S/M/L 只調整深讀與實作深度，reorg 全域 discovery 不因規模省略，唔刪交付物：S 都要 11 節 PLAN、product specification、所有 planned MD 完整草稿、同源 JSON、離線 HTML 及 gate 報告。CLI／agent／MCP／Plugin 可 N/A；`PACKAGED`、`LOCAL COMPLETE`、`NOT_PUSHED` 均可係合法結果。

共同細節見 [workflow-contract.md](references/workflow-contract.md)，ZCode 能力／路徑見 [host-zcode.md](references/host-zcode.md)。ZCode 原生「只手動觸發」強制能力係 **UNKNOWN**；本 skill 及 checker 只提供 advisory 工作流程，唔聲稱 OS 或 host 已攔住其他 writer。

## 根目錄與執行邊界

- `PLUGIN_ROOT`：authoring repo／package 根，包含 `.zcode-plugin/`、`commands/`、`skills/`。
- `SKILL_ROOT`：`<PLUGIN_ROOT>/skills/open-project`，放本文件、templates、scripts、schemas、references。
- `PROJECT_ROOT`：用戶指定、已解析嘅項目根，與 plugin 根分開；staging 係 `<PROJECT_ROOT>/md-drafts/`。
- 腳本用絕對路徑及明確 project 參數，唔依賴 cwd。唔將 project 檔案寫入 plugin 或已安裝副本。
- 不自動安裝、同步到 cache、改 host config／global rules、重啟 host、部署、push。已有明確授權繼續有效；唔重複要求批准。

## 全程規則

1. 每個動作按實際副作用與現有授權判斷，唔憑命令名推斷；可安全繼續嘅工作照做。未授權／不能安全執行標 `NOT_RUN`＋原因，對應結論 `UNVERIFIED`。
2. read-only 查詢及隔離、可逆、已在任務範圍內嘅工作按授權執行；不為 routine 工作另設批准。涉及 live／發訊息／出網／安裝／部署／push 等按 §11 具體記錄。
3. 數字連可重跑命令／query、來源與快照；未讀唔當否定證據。PASS／FAIL／UNVERIFIED 有證據；N/A 要有理由。
4. UTF-8、無 BOM、LF。時間用 ISO 8601＋offset；觀察時間唔等於來源修改時間，mtime 唔證明作者或因果。
5. 先讀原始來源及記 raw-byte baseline，先至起草；唔准寫完草稿先補 baseline。
6. 完整 packet、`ready`、批准記錄、host enforcement 係不同概念。advisory exit 0 唔等於 ready／ACCEPTED。

## Phase 總覽

| Phase | 目的 | 輸出／閘門 |
|---|---|---|
| 0 意圖／訪談 | 確定明確任務、new/reorg、S/M/L | 已知答案沿用；補缺口及成功準則 |
| 1 事實／基線 | 分清事實、未知及讀取時原檔 | 六類事實＋source refs＋first-read hashes |
| 2 全系統歷史發現 | 全 metadata、全文檢索先於路徑／title 排序 | discovery／coverage＋深讀來源 tags |
| 3 檔案／代碼 review | 原始文件、矛盾、code map、git、secret | 權威順序＋覆蓋範圍及未驗證清單 |
| 4 完整審批包 | 11 節 PLAN＋全 MD＋JSON＋離線 HTML | 全套可過目；缺份＝INCOMPLETE |
| 5 受控 promote | 綁定批准、baseline、draft、expected | dry-run→已授權 apply；逐檔結果 |
| 6 按需實作 | 沿 §6 工具化評估 | 實作或 N/A；適用驗證有證據 |
| 7 ZCode 打包 | package、installed、loaded 分開 | PACKAGED 可交貨；啟用另按授權 |
| 8 獨立審核 | 12 項 required coverage＋severity | 無 P0 唔會自動 ACCEPTED |
| 9 交接 | status、memory、follow-up、repo 狀態 | LOCAL COMPLETE／NOT_PUSHED 清楚 |

## Phase 0 — 意圖／訪談＋規模

目的：確定用戶要本流程處理嘅目標與邊界，唔因任何新 project 自動啟動。

1. 記錄明確調用來源、目標／現有 folder、`new|reorg`、`S|M|L`。
2. new 兩輪，每輪最多 5 個問題；只問未能推斷嘅缺口。第一輪：做乜、邊個用／場景、痛點、產出形態、沿用資產。第二輪：可測成功準則、out-of-scope、平台／時間／預算、授權邊界、交付對象。
3. reorg 快速登記：一句話目標、使用者、成功準則、限制、授權範圍、舊 folder。已有明確答案唔再問。
4. 概述已知方向；破壞性／不可逆操作按具體範圍確認。唔將本階段變成逐步批准儀式。

輸出／閘門：目標、規模、成功準則及缺口清楚，紀錄入 staging。

## Phase 1 — 事實整理＋首次讀取基線

目的：事實與未知分家，先讀原文先起草。

1. 確認 authoring root、package root、installed projection、PROJECT_ROOT；唔由 installed 目錄唔係 Git repo 推論冇 authoring repo。
2. 對每份可能替換／搬移／合併原檔，**第一次 raw-byte 讀取時**記 source ID、resolved path、size、SHA-256、capture time、revision／HEAD；不存在記 `NOT_EXISTS`。另列 git dirty，唔用 DIRTY 代替 hash。
3. 記 file-set inventory；新讀到嘅內容建立新觀察，唔覆寫舊快照去解釋差異。
4. 六類逐項有證據或 UNVERIFIED：量級、資產、workspace／checkout／state／log 路徑、端口／服務、帳號存在與位置、runtime／dependency／binary pins。唔抄 secret 值。
5. 來源記 path／行號或定位範圍、命令輸出、source revision/hash；未知列驗證方法。

輸出／閘門：六類齊、first-read baselines 可追溯；零未知合法，唔設湊數配額。

## Phase 2 — 全系統 session 發現，再分類深讀

目的：先由所有**已授權可讀**來源發現候選，再用 directory/title 作線索排序。禁止用目錄或標題先篩走全文命中。reorg 不論 S/M/L 都先做全 metadata／全文 discovery；S 只減少後續深讀。只有真正無歷史、來源不可用或用戶明確排除時可 N/A，並記原因／coverage。

1. 列來源：已核實 DB／export／archive／host 工具、schema、授權及讀取時間；未能檢查來源標 UNKNOWN。唔假設物理刪除資料仍存在。
2. 全 metadata inventory：含主／子 sessions、parent_id、directory、title、狀態、建立／更新時間；IDs 視為 opaque，唔假設 `sess_` 前綴。以確定性 keyset 分頁、同來源去重。
3. 全文搜尋先於 directory/title：用項目別名、repo、特徵詞、檔名、URL 等版本化 query 組；以可見 user／assistant text 為主，tool／summary 保留來源類型。JSON part 需解碼，hidden reasoning 唔係可用原文。SQL 參數化，literal %/_ 要 escape；唔用 TopN 宣稱完整。
4. 沿已核實 `parent_id` 做 ancestors／descendants closure；parent 相同或 title 相似唔自動等於相關。未證實 fork 標未知。跨來源同 ID 不同 revision/hash 分開保留。
5. 候選分類：direct、probable、parent-child-context、mention/copied-context、rejected-with-reason。copied context 可以保留相關 continuation；唔當確定歸屬。
6. 按證據、directory/title、時間及量級選深讀名單。每來源標 `full|partial|summary-only|unread`＋ref、revision/hash、時間及所讀範圍。ReadSessionContext（RSC）摘要只可 summary-only；full 必須交代全部可見內容範圍。
7. 短 WAL-aware read-only transaction 完成 discovery／必要匯出後即釋放，唔等 LLM／用戶；`mode=ro`＋`query_only`，唔用 immutable 迴避 WAL。每個新 connection／深讀另記快照/hash，不冒充同一 snapshot。
8. coverage 記 metadata、eligible/scanned/skipped/error parts、matched parts/messages/distinct sessions、closure、候選分類、深讀 tags、缺失來源、T0/T1、query 組及命令。併發增量或中斷不宣稱完整；唔將歷史數字當永久全集。

輸出／閘門：痛點及角色統計有原文 ref＋深度 tag；實際 tool/query/scope 寫 PLAN §5，coverage 明確。只輸出任務相關證據，唔傾倒整個私人 DB；access denied 唔繞過，用戶排除範圍照做。


## Phase 3 — 舊檔／代碼 review

目的：由實際原檔分清現況、需求與歷史，建立權威順序。

1. Inventory：size／mtime、first-read hash；大量檔案按目錄摺疊，排除 .git／dependencies 嘅範圍要列明。
2. 實讀原 MD，列矛盾／取代關係／數字對賬，明寫權威順序。唔將舊 bug、臨時 workaround 自動寫成 desired requirement。
3. Code map 六項：stack／lockfile、入口、Run/Test/Build、結構、測試現況、tech debt；非 code 各項 N/A＋理由。實跑先審實際副作用，未跑標 NOT_RUN／UNVERIFIED。
4. Git branch、HEAD、dirty、log-5；非 repo 如實記。已有 repo 按授權讀 GitHub repo／issues／PR／releases。
5. Secret scan 只報 path＋count，唔印值。列 SCANNED、NOT_SCANNED 逐檔原因、findings；例如 size >2MB 跳過要 UNVERIFIED。準備發布檔案有未掃項，整體只可 PARTIAL，零 findings 唔代表 secret-clean。

輸出／閘門：範圍逐項交代、矛盾有原文出處、code map 齊、secret scan 覆蓋清楚。

## Phase 4 — 完整 PLAN／MD／JSON／離線 HTML 審批包

目的：俾用戶過目具體完整結果；本階段只寫 `<PROJECT_ROOT>/md-drafts/`，正式檔仍保留。

1. 以 `schemas/plan.schema.json` 建 `md-drafts/plan-data.json`（schema_version `1.0`）作唯一 packet 資料源。詳見共同契約；必有 project、host、來源、requirements、folder_changes、drafts；工作流程另記 coverage，唔靠 mtime 判一致。
2. 11 節 PLAN 全保留：§1 六類事實；§2 未知；§3 矛盾；§4 痛點；§5 角色／方法／coverage；§6 工具化及開源候選；§7 code map；§8 逐檔 manifest；§9 before/after folder／執行時序；§10 風險；§11 需求追溯＋批准請求。
3. §6 每觸發器評估四項：沿用現有工具、維護成本／owner、錯誤影響、唔做會點。結論＝沿用現有／CLI／subagent／SKILL／MCP／Plugin／N/A。重複 ≥3 只觸發評估，唔強迫自建；首輪 agents ≤3，new 預估 0–1。
4. new 工具鏈：本地已裝工具清單→已授權 gh／GitHub connector／官方來源搜尋→按需求估 agents。候選列 repo、license、last commit、部署方式、適用原因、風險；採用前查 license、secret、依賴。冇搜尋能力標 UNVERIFIED，唔阻塞離線規劃。
5. 每個 planned 正式 MD 都有**完整可讀草稿**及 manifest 一列：id/path/target/template/kind/required、draft SHA-256、首次讀取 baseline、expected output SHA-256、明列 transforms 字串 array；依賴另記。所有 manifest drafts（包括 required:false）都要完整有效；未採用唔列 row，喺工具決策記 N/A。唔准「保留現有…」、一句交差，唔准 HTML 摘要代替 MD。跨目錄文件同樣要列入。
6. **product_specification.DRAFT.md 必交**：requirements ID＋來源、desired behavior、固定可判定 acceptance；observed status／驗證／修復歷史分開放 status、memory、review。reorg 要分清實際現況及用戶想要嘅行為。
7. 非 agent 可有明確第一行 DRAFT marker，只有宣告 `remove_draft_marker`（第一行必須精確係 `<!-- open-project:draft -->`）先移除；agent YAML frontmatter 必須 line 1，唔強制加 marker。唯二轉換係 exact marker removal 及 `normalize_utf8_lf`；時間／路徑／命令／權限／業務規則須起草時寫定，再 hash／審批，唔喺 promote 臨場填。
8. 生成同源 PLAN／HTML，再 gate：
   ```text
   python <SKILL_ROOT>/scripts/render-plan.py <PROJECT_ROOT>
   python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT>
   python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT> --strict
   ```
   renderer 讀 JSON，寫 `md-drafts/PLAN.DRAFT.md`、`md-drafts/PLAN-REPORT.DRAFT.html`；兩者顯示同一 packet digest。唔手改 rendered views，改 JSON 後再 render。
9. HTML 預設零 CDN、完全離線；所有來源字串安全 escape／serialize，顯示完整 MD 草稿及有效相對連結；0、浮點、null、UNVERIFIED 保真，動畫非驗收證據。圖之外保留完整表格，支援 mobile／reduced motion。
10. 呈交 PLAN＋全部 planned MD（含 spec）＋JSON＋HTML＋gate 報告。checker 預設 advisory＋報告尾部 suggestions；strict 係 opt-in。missing required artifact＝INCOMPLETE，唔因 advisory exit 0 宣稱 ready。零風險／零痛點合法，N/A 寫理由。

輸出／閘門：所有 required 草稿、來源、hash、需求及 folder 決策齊；抽查安全數字、三方 digest 一致。先完成具體可審批包，再需要時請用戶批核。

## Phase 5 — 明確批准＋漂移核對＋promote

目的：只 promote 用戶已過目、確定身份嘅內容，原檔受保護。

1. 重跑 gate；專屬 agent 模型按下文 AP-17 現有政策，唔開模型 mapping／provider workaround 工程。
2. 將用戶具體批准寫成**獨立 approval JSON**，綁 plan id/revision/packet digest、每個選定 draft id/target/draft hash/baseline/expected/transforms/effects。已有同範圍明確批准唔重問；approval 係決定證據，唔提供 OS 權限。
3. 預設 dry-run 無寫入；`--apply` 先執行；中斷後同 approval＋同 packet 才可 `--resume`：
   ```text
   python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON>
   python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON> --apply
   python <SKILL_ROOT>/scripts/promote.py <PROJECT_ROOT> --approval <APPROVAL_JSON> --apply --resume
   ```
4. 寫入前逐檔三態：target==expected→no-op；target==baseline（或原定 NOT_EXISTS）→backup／promote；兩者皆非→STOPPED_DRIFTED。不可用新 hash 靜默「修好」approval。選定依賴唔齊就 BLOCKED。
5. 備份係原始 bytes，唔加 banner；`.open-project-promotion/backups/<uuid>/<relative-target>` 保留同名檔完整相對路徑。journal 位於 `.open-project-promotion/journals/`；apply 建內部 `.gitignore` 排除操作記錄／備份，唔將 secret 備份入 Git。
6. 寫同目錄 temp，`os.replace`，記 journal；retry／resume 對帳，唔以合作鎖聲稱阻止外部 writer。只能提供寫前偵測及自身操作協作，唔宣稱全域 CAS。
7. 失敗記 FAILED_RECOVERED／FAILED_UNRECOVERED；復原範圍係 **target file bytes**。備份、journal 及新建空 parent directories 可保留；唔冒稱 filesystem 完全回復。復原失敗要清楚報告。
8. FROZEN 舊 bytes 唔改；新版本與 supersedes 映射放外部 manifest。memory 只 append entry／supersedes／revokes／correction events，唔回頭改舊 row。

輸出／閘門：每檔有 promote/no-op/STOPPED/BLOCKED/FAILED 狀態及證據；內容只做已批確定性 transforms；變更後需重新形成 packet、render、gate 及對應批准。

## Phase 6 — 按 §6 評估實作

1. 只建有用途目錄及已採用工具，唔為過閘門逆向生成 CLI／agent／MCP。
2. **保留 ZCode 現有 AP-17 政策**：專屬 agent 必須 line 1 YAML frontmatter，明寫用戶確認嘅有效 `model: <provider/model>`；唔留空、唔寫 `inherit`。既有觀察係專屬 agent 留空／inherit 會落 provider 清單第一個，一般 subagent 跟後台 default。Phase 4 用已確認 model 字串填完整草稿；未知時問缺口。模型問題已 RESOLVED，本工作唔改模型設定、runtime mapping 或 provider policy。
3. ZCode 用 `Agent` 工具與 `subagent_type` 派任角色；只用實際可用 bare／namespaced role。記 requested role、child/session ID、observed role；loaded definition 不可見就 UNKNOWN，唔由 title 推斷已載入。
4. CLI 只在採用時提供 status／doctor／verify／handover；deploy 無場景就 N/A。命令逐行示範，唔以 shell `|` 當「或」。
5. 採用 SKILL／stdio MCP 才建立；host config／restart 係啟用動作。FROZEN invariant 用有 assert 嘅可重跑檢查及 SHA-256 外部 manifest。
6. secret 用 env／本地檔；實測審實際副作用，輸出證據入 status。doctor／verify 只喺有 CLI 才適用；否則 NOT_APPLICABLE＋理由。

輸出／閘門：適用且已授權嘅驗證有真實證據；各評估結論落地或 N/A。

## Phase 7 — ZCode Plugin 打包

評估採用先打包。保留 `.zcode-plugin/plugin.json`、commands／skills／agents／tools 等 ZCode 結構；package 內使用實體副本及正確相對路徑，唔附 runtime binary、state、secret、大歷史。source／PACKAGED／INSTALLED／LOAD VERIFIED 分開；JSON 合法及內容乾淨可 PACKAGED 交貨。安裝、同步 installed cache、改 config、重啟、新 session loaded 驗證按明確授權另做，唔自行啟用。license 來源必須核實，唔預設改 MIT。

## Phase 8 — 獨立 review

未參與改動嘅 reviewer 唯讀審核；只跑已授權且安全嘅相關驗證，唔改檔／commit。12 項逐項 PASS/FAIL/UNVERIFIED/N/A＋證據：FROZEN、三方數字/digest、required 結構、路徑、secret coverage、適用驗證、git、agent frontmatter／AP-17、SOP/skill/CLI 邏輯、過時宣稱、PLAN/HTML 對賬、已批草稿/實際檔 hash＋transform 對賬。coordinator 抽樣核實 subagent 報告，唔照抄結論。

P0 及 required P1 必修；P2 roadmap。具體書面豁免只記限制或明確改變驗收範圍，唔將未解 required P1 當已通過。**零 P0 只係必要條件**：required coverage 有 UNVERIFIED、未解 required P1、未交草稿／未驗證 assertion，結論唔可 ACCEPTED。用 ACCEPTED／CHANGES REQUIRED／PARTIAL，清楚分 N/A、已批准限制及未知。修復後對受影響範圍覆核。

## Phase 9 — Handover／Repo＋follow-up

更新 status 快照、append memory、新舊 evidence refs、逐項結果與 P0–Pn 下一步（各有 acceptance）。交接寫明 PROJECT_ROOT、canonical packet、批准、promotion journal、可重跑命令及新 session 入口。PLAN JSON 改動後重新 render HTML（AP-15），最終報告指同一 snapshot。

LOCAL COMPLETE／NOT_PUSHED 合法，唔強迫 push 先交貨。已有明確 push 授權先 feature branch、secret coverage／git status 檢查、push，之後 `gh api`／`ls-remote` 驗遠端 tip。副本 SHA-256 對賬。fresh-session loaded／host 原生手動觸發未實測就 UNKNOWN，唔冒稱 PASS。

## 反模式與可重跑驗收

AP-01 frontmatter 唔喺 line1；AP-02 假綠／無 assert；AP-03 crash 未查錯誤報告就歸因；AP-04 可用 API 卻用 UI；AP-05 hardcode secret；AP-06 placeholder 未替換；AP-07 banner 令引用漂移；AP-08 push 無遠端驗證；AP-09 副本不同步；AP-10 tasklist 截斷（用 /FO CSV）；AP-11 argparse dest 撞名；AP-12 無 baseline 宣稱穩定；AP-13 照抄 subagent；AP-14 數字無命令；AP-15 PLAN/HTML 脫鉤；AP-16 草稿缺份／一句交差；**AP-17 專屬 agent model 留空／inherit**；AP-18 規格混入病歷。

唔要求舊 SELFTEST.md／SKILL-REPORT.html 存在先通過；以當前 source revision＋真實可重跑測試命令、exit、輸出及 coverage 作證。執行 repo 當前 unittest suite（按 README 指定入口），涵蓋 global discovery／WAL／opaque IDs、packet 缺件與 quoted YAML、offline renderer／script escaping、approval tamper／drift／no-op／resume／rollback、New-S／Reorg-M／不同 cwd／無 CLI／無 plugin／無 push。fresh-session／browser／host loaded 未驗證分開列，唔由 synthetic tests 推論。
