---
name: open-project
description: "按 project 規模縮放嘅開工／重整流程：訪談／意圖 → 事實整理 → 舊 session 深讀（範圍制＋深度標記）→ 舊檔＋代碼 review → 管理 PLAN＋逐檔完整草稿（md-drafts staging）＋離線 HTML 證據視圖 → 老闆批 → 逐檔漂移核對 → promote（原檔保護）→ 按評估實作（SKILL/MCP/CLI/Plugin/agent，N/A 合法）→ 獨立 review → handover。任何新 project 開工、舊 project 重整、交接前先用呢個 skill。"
---

# open-project — 開新 project／重整舊 project 嘅端到端流程

> **定位**：按 project 規模縮放——細嘢行輕量，大嘢行全套；重型產物（MCP／plugin／多 agent）一律經工具化評估，評估話唔起就唔起，N/A 由頭 valid 到收尾。
> **適用**：`new`（全新 project）／`reorg`（舊 project 重整、交接）。兩條路線行同一套 Phase 0–9，分別喺深度。
> **核心交付物**：Phase 4 三件套——PLAN 草稿＋逐檔 MD 草稿（md-drafts/ staging）＋離線 HTML 證據視圖；老闆過目批准，先可以郁正式檔案。
> **語言**：文件同對話用繁體中文／粵語；代碼、路徑、commit message 用英文。
> **零項目例子聲明**：本 skill 完全通用。所有例子一律 placeholder（`<PROJECT>`、`<REPO>`、`<CLI>`、`<PORT>`）；執行時讀到嘅項目事實只准寫入該 project 自己嘅文件，永遠唔准寫入本 skill。

---

## 快速入口

| 路線 | 幾時用 | 行法 |
|---|---|---|
| `new` | 全新 project，無舊 session／舊檔 | 0→1→（2 跳過；3 只做 inventory＋secret scan）→4→5→6→（7 視評估）→8→9 |
| `reorg` | 舊 project 重整、混亂、要交接 | 0→1→2→3→4→5→6→7→8→9 全做 |

**規模判定（Phase 0 產出）**

| 規模 | 定義 | Phase 2/3 深度 | Phase 6/7 |
|---|---|---|---|
| S | 一次性、個人實驗 | 2 跳過；3 只 inventory＋secret scan | 通常 N/A；有需要先單命令 |
| M | 會持續維護 | 2 做 prioritized 深讀；3 全做 | 按評估表結論 |
| L | 重整、交接、派俾其他人 | 2/3 全做＋完整紀錄 | 按評估表結論（plugin 常見） |

**Phase 總覽**

| Phase | 名 | 一句話目的 | 關鍵輸出 | 閘門（全部範圍制：做完指定範圍即可過；零發現合法；未讀標 UNVERIFIED） |
|---|---|---|---|---|
| 0 | 意圖／訪談＋規模 | 講清想要乜、幾大規模 | 路線＋規模＋（new）訪談紀錄 | 意向＋規模確認 |
| 1 | 資料整理 | 事實與未知分家 | 事實表＋未知表 | 六類逐項有事實或 UNVERIFIED |
| 2 | 舊 session 深讀 | 痛點＋角色統計（帶深度標記） | 痛點表＋角色統計（連方法口徑） | 深讀名單每個來源有深度 tag |
| 3 | 舊檔＋代碼 review | 檔案／矛盾／code map／git／secret | inventory＋權威順序＋矛盾＋code map | 範圍清單做完；secret scan 有跑 |
| 4 | PLAN＋草稿＋HTML | 出俾老闆批嘅三件套（staging） | PLAN.DRAFT＋md-drafts/*.DRAFT.md＋plan-data.json＋HTML | substance 清單＋老闆批 §11＋過目草稿 |
| 5 | 漂移核對＋promote | 逐檔核對→逐字 promote（原檔保護） | 正式 MD＋位元組備份＋archive 映射 | 逐檔核對過；promote diff 符白名單 |
| 6 | 實作 | 照 §6 評估結論落地（N/A 合法） | agents／CLI／SKILL／MCP＋manifest＋invariant | 適用且已授權嘅驗證全綠 |
| 7 | Plugin 打包 | 評估話打包先做 | PACKAGED→（批准後）INSTALLED | JSON 合法；狀態如實記錄 |
| 8 | 獨立 review | 唯讀 12 項 PASS/FAIL/UNVERIFIED | REVIEW_REPORT.md | 0 P0 |
| 9 | Handover／Repo | 收工固化＋經批准嘅啟用動作 | status＋memory＋handoff＋（批准後）push | LOCAL COMPLETE 交代清楚 |

---

## 命名／語言規則

1. placeholder：`<PROJECT>`／`<REPO>`／`<PLUGIN>`／`<CLI>`。
2. 項目事實只寫入項目文件；唔准寫入本 skill。
3. 時間戳 `YYYY-MM-DD HH:MM`（當地時區）。
4. 全部文件 UTF-8、無 BOM、LF。
5. 統計口徑連方法記錄（見 R1）。
6. **可複現規則（AP-14）**：任何寫入 PLAN／status 嘅數字必須連產生佢嘅命令。

## 執行安全規則（全域——任何 Phase、任何命令、任何動作，執行前先行）

1. 每個命令／動作執行前先審：**副作用**（寫檔？寫 DB？發訊息？起服務？出網？）＋**授權**（§11 批准請求表批咗未）。
2. 唔安全或未批→標 **NOT_RUN**（記原因＋所需批准），其餘工作照做，**唔准阻塞成個流程**。
3. Phase 3 嘅實跑 test、Phase 5 嘅漂移核對、Phase 8 reviewer 嘅重跑——一律受本規則約束：**只重跑安全且相關嘅唯讀核對命令**；有寫入／出網副作用嘅 test 標 NOT_RUN＋結果 UNVERIFIED（搵安全替代或列入批准請求表）。
4. 「命令名睇落安全」唔算審查——要睇佢實際做咩。

---

## Phase 0 — 意圖／訪談＋規模判定

**目的**：定路線、定規模、（new）訪談清楚方向。本 phase 唔出計劃、唔攞細節批核。

**步驟**：
1. 判路線：有舊 folder／舊 session→`reorg`；冇→`new`。
2. 判規模 S/M/L（表見上；拿捏唔到就問用戶一句）。
3. `reorg`：意圖登記五樣——一句話、使用者、成功準則、限制、批核邊界；記低舊 folder 路徑。
4. `new` 訪談制——兩輪，每輪 ≤5 條，每輪答完用三句覆述俾用戶確認先入下一輪：
   - 第一輪（定方向）：①想做咩（逼用戶講到一句話）②比邊個用、咩場景 ③解決咩痛 ④產出形態（app／script／GAS／sheet／ops／內容／其他）⑤有咩現有資產要沿用（repo、帳號、工具）。
   - 第二輪（定邊界）：①成功準則點量（要可測）②明確唔做咩 ③平台／時間／預算限制 ④邊啲操作要先批准 ⑤成品交俾邊個（自己／朋友／上線）。
   - 只問推斷唔到嘅嘢；環境有 office-hours／spec 類 skill 可借，但本 skill 自帶以上問題集。
5. 破壞性操作（刪檔／覆寫／push --force／碰 live 服務）一律先確認後執行。

**輸出**：路線＋規模＋（new）訪談紀錄（寫入 staging）。
**閘門**：用戶確認意向＋規模即入 Phase 1。

---

## Phase 1 — 資料整理

**目的**：事實與未知分家；之後每個 phase 引用。

**指定範圍（六類，逐類要有嘢或者 UNVERIFIED）**：量級（檔數／行數／session 數）｜資產（repo／folder／CLI／plugin／docs）｜路徑（workspace／checkout／state／log）｜端口／服務｜帳號（只記存在＋位置，唔准抄值）｜版本 pin（runtime／dependency／binary hash）。

**步驟**：①每項事實連出處（檔案:行／命令輸出／session ref）②查唔到嘅入未知表標 UNVERIFIED＋驗證方法③無出處降級 UNVERIFIED。

**閘門**：六類逐項有事實或 UNVERIFIED；抽查 3 項講得出出處。零未知＝合法（記「零發現」）。

---

## Phase 2 — 舊 session 深讀（reorg；S 規模跳過，M 規模做 prioritized）

**目的**：由歷史抽痛點＋角色重複統計——用證據，唔用湊數。

**三步流程**：
1. **Inventory**：列清單——id／title／日期／量級。只搵同 project match（directory／title keyword）嘅 session。
2. **Prioritize**：按相關度（match 精確度＞時間新＞量級大）揀**深讀名單**；唔係全部一次過讀晒。名單記入 PLAN。
3. **Deep-read**（名單內）：追重要決策、矛盾講法、痛點原句、subagent 角色。

**方法記錄（邊個工具就記邊個）**：記**實際用嘅 tool／query／scope／depth**——用咗平台 session 工具就記工具同參數；用咗用戶匯出就記匯出檔；**真係用咗 SQL 先記 SQL**（R1 只係其中一種實作 recipe）。

**深度標記（每個引用嘅來源必帶）**：`full`（全文讀過）／`partial`（讀咗揀選段）／`summary-only`（淨係攞到摘要）／`unread`（未讀）＋ref（session id／匯出路徑）＋日期＋（有就附）hash。

**私隱界（唔准越）**：①只掃同 project match 嘅 session；②唔准全表傾倒成個 DB；③唔准掃其他私人 session；④access denied→標 unread，唔准繞過；⑤用戶要求排除嘅範圍即刻排除並記錄。

**痛點抽取**：四類——重複手動流程／最花時間／用戶逐字要求（原文引用 ≤120 字）／最後仍靠人手。有證據先列；零痛點＝合法。

**角色統計**：subagent 按 parent 鏈＋title bucket 分類；每行：角色／次數／訊息數／出處／判斷型定機械型。**統計口徑（實際方法＋範圍）必須原文記入 PLAN §5**。

**閘門**：深讀名單每個來源有深度 tag；引用嘅痛點全部有 ref；口徑記錄入 PLAN。零痛點＝合法（明記）。

---

## Phase 3 — 舊檔＋代碼 review（reorg 全做；new 只做①⑥）

**步驟**：
1. 檔案 inventory（R2：大小／mtime；>50 檔按目錄摺疊）。
2. 矛盾掃描：讀 `*.md`（按權威優先順序揀讀）——邊份取代邊份／講法衝突／數字對賬→**權威順序表**（自訂但必須寫明）。
3. Code map 六項：stack（lockfile 實讀）／入口／Run·Test·Build（**先過全域執行安全規則**：安全先實跑，有寫入／出網副作用嘅 test 標 NOT_RUN＋UNVERIFIED）／結構／測試現況／tech debt。非 code project 每項「（暫無）」。
4. Git 狀態（R4：branch／HEAD／dirty／log-5；唔係 repo 都記——本身係 finding）。
5. GitHub review（有 repo 先做）：`gh repo view`／`issue list`／`pr list`／`release list`。
6. Secret scan（R3）：只報路徑＋次數，任何情況唔准印值。

**閘門**：範圍清單逐項做完；矛盾每條有檔案出處；code map 六項齊（或「（暫無）」）；secret scan 有跑（零命中＝合法，見 R3 狀態制）；權威順序無歧義。

---

## Phase 4 — PLAN＋草稿＋HTML（★核心；全部寫入 staging `md-drafts/`，唔掂正式檔）

**步驟**：
1. 建 staging `md-drafts/`。
2. 寫 `PLAN.DRAFT.md`（模板：`PLAN.template.md`）§1–§11：
   - §1 核實數字快照：每行連命令；涵蓋 Phase 1 六類（每類有事實或 UNVERIFIED——唔設最低行數）。
   - §2 未知表。§3 矛盾清單。§4 痛點排行（全量搬入，有 ref＋深度 tag）。§5 角色統計＋方法口徑。
   - §6 **工具化評估表**：每行＝觸發器（重複 ≥3／session 儀式／要對接外部系統／要分發俾其他人）＋**評估四條**（①沿用現有工具得唔得、邊個、點解唔夠 ②自建維護成本（邊個維護、幾耐更新）③錯咗嘅風險影響 ④唔做會點）＋結論。**結論合法值**：沿用現有／起 CLI／起 subagent／起 SKILL／自建 MCP／打包 Plugin／唔起（N/A）。重複 ≥3 只代表「值得評估」，唔代表必須起；**0 agent、唔建 MCP、Plugin=N/A 可以係最好答案**（明寫理由）。冷卻：首輪 agent ≤3。
     - `new` route §6＝三層工具鏈：①本地掃描（環境已裝 SKILL／MCP server／CLI／Plugin 清單→按訪談答案推薦）②**GitHub 開源掃描**：gh 首選（`gh search repos`）；**已授權嘅 GitHub connector／官方資料來源同樣可以**；**完全冇工具→開源候選表標 UNVERIFIED 留空，唔阻塞離線規劃**——PLAN 照出，掃描變成批准後補充項。候選表：repo／license／last commit／部署方式／點解啱／風險；採用前必查 license 相容＋secret scan＋依賴面。③subagent 預估（由項目形態推，標「預估，用落驗證」；首輪 0–1 個）。每推薦「依據」欄引訪談答案編號。
   - §7 code map。
   - §8 **草稿 manifest（逐檔）**：檔名／對應模板／修邊條矛盾／DoD／草稿路徑／**原檔狀態＝sha256（存在時）／NOT_EXISTS／DIRTY（連 git 狀態）**——草稿寫好嗰刻記低，呢個就係 Phase 5 嘅 baseline。
   - §9 執行時序。§10 風險（按發現填，零風險記「未發現」）。
   - §11 **批准請求表**：每項動作列 target（具體檔案／repo／host）＋副作用（寫檔／push／改 host config／重啟／安裝／憑證／部署／出網）＋可逆性。**PLAN 批核＝批准內容方向；啟用動作（push、改 host config、重啟 host、裝 plugin、攞憑證、部署）執行前逐類再確認**（§11 可預批指定項，其餘臨場問）。
3. 寫 `md-drafts/<name>.DRAFT.md`×N：每份 Phase 5 MD 交付物一份**完整草稿**——用對應模板、完整 wording、現有檔遷移**逐行原文**、檔頭【草稿—待老闆過目】＋來源模板＋對應 PLAN 節號。**禁一句交差（AP-16）、禁「[保留現有…]」省略**。
   - **Phase 4 期間唯一可寫位置＝`md-drafts/`**（＋唯讀查詢）：期間發現要新文件（指南／更新記錄等）→開草稿入 §8 manifest 等批，**唔准直接寫去 project 其他位置**。
   - **product_specification 係開案功能契約（AP-18）**：內容＝「產品要做咩功能＋每個功能點樣驗收」，來源＝Phase 0 訪談／用戶明確要求；reorg 個案由現有產品行為實讀返嚟。**fine-tuning 輪次、修復紀錄、驗證過程一律唔准入**——呢啲係項目歷史，入 memory／PROJECT／FROZEN。
4. 寫 `plan-data.json`（facts／痛點／矛盾／工具化／開源候選／風險／草稿 manifest 嘅機讀版）→由佢生成 `PLAN-REPORT.DRAFT.html`：**同一份數據兩個視圖**；預設完全離線零 CDN（KPI count-up／bar／流程動畫＝純 CSS/SVG；關聯圖＝純 SVG 節點連線＋CSS 流動效果；ECharts 只准本地檔增強）；來源文字一律 HTML escape；連結限 md-drafts/ 相對路徑；結論一律 **PASS／FAIL／UNVERIFIED＋證據**；動畫係呈現，唔係品質指標。
5. 自查 substance 清單→**成套呈交**俾老闆：PLAN.DRAFT＋**§8 全部草稿逐檔齊**＋plan-data.json＋HTML＋**gate-check 報告**——跑 `python <本 skill 目錄>/scripts/gate-check.py <PROJECT>`（預設 advisory：報告＋建議唔阻行，彈性說明喺報告尾部俾老闆裁量；`--strict` 先硬擋）。**缺任何一份（尤其 product_specification.DRAFT.md）＝Phase 4 未完成，唔准攞 PLAN 去批（AP-16）。**

**substance 閘門（範圍制）**：§1 六類齊；§4/§5 有 ref＋深度 tag＋口徑；§6 每個觸發器有評估結果（含 N/A）；§8 逐檔有原檔狀態 baseline；md-drafts 對 §8 manifest**逐檔存在並一齊呈交**（product_specification.DRAFT.md 必交）、無一句交差（AP-16）、**規格無歷史內容（AP-18）**；plan-data.json↔PLAN↔HTML 三方數字一致；HTML escape＋離線開到；批核前抽 §1 三個**安全**數字重跑（按全域執行安全規則）。**老闆批 §11＋過目草稿先入 Phase 5（全 skill 最重要閘門）。**

---

## Phase 5 — 漂移核對＋promote

**步驟**：
0. **promote 前再跑一次 gate-check**：G3（agent model placeholder）呢項必須清零先可以 promote——佢會靜默跌錯 provider，事後睇唔出，呢一項無彈性；其餘項按報告建議修或者老闆記入 §11 豁免。
1. **逐檔核對，唔係一刀切**：promote 每個檔之前，對返 §8 manifest 嘅原檔 sha256——一致→promote 呢個檔；漂移咗→呢項 **STOPPED_DRIFTED**（記新 hash），其他檔照常處理，漂移項更新草稿再批。
2. **只建採用嘅目錄**：邊個草稿要落邊個目錄就淨係建嗰啲；冇人用嘅目錄唔預先 mkdir。
3. **原檔保護**：目標已存在→先做**位元組級備份**（`docs/archive/<name>.<timestamp>.bak`，逐 byte 副本，**備份本身唔加 banner、唔改任何內容**）；然後先喺工作位置寫新檔（superseded banner 加喺新工作檔頂，唔係加喺備份度）。
4. **搬移紀錄**：`docs/archive/MANIFEST.md` 記 old→new 映射（原路徑→備份路徑→sha256）；搬移任何一步失敗→原檔回復原位，嗰項標 FAILED_RECOVERED。
5. **逐字 promote＋metadata 轉換白名單**（越權改動＝P0）：①刪／換檔頭 DRAFT 標記行（→正式狀態行）②快照時間戳填實際執行時間③**只有模板標明 `<執行時填：欄位名＋型別＋來源命令>` 嘅位先可以填**——路徑、權限、命令、業務規則唔喺白名單 ④編碼正規化 UTF-8/LF。
6. **確定性轉換＋idempotent 重跑**：promote 轉換係純函數——時間戳以 §8 批准記錄為準（重跑唔重新讀鐘）。重跑／中斷後續跑逐檔三態判定：目標內容==預期產出（transforms(草稿)）→**no-op（already promoted）**；目標==原 baseline→正常 backup＋promote；兩者皆非→STOPPED_DRIFTED。NOT_EXISTS 項目同一規則（已存在且等於預期產出→no-op；存在但唔等於→STOPPED_DRIFTED）。
7. memory 落地：append-only＋**狀態欄 current／superseded／revoked**（被取代原文保留但標 superseded；revoked＝撤回；現行指令只認 current 鏈最新）。

**閘門**：逐檔核對有結果（promote／STOPPED_DRIFTED／FAILED_RECOVERED 如實記）；promote 後逐檔 diff 符白名單；備份係位元組級而且未加過嘢。

---

## Phase 6 — 實作（照 §6 評估結論；結論係 N/A 就 N/A）

**步驟**：
1. agents（評估結論話起先起）：`agents/<NAME>.md`，frontmatter 必須 line 1（AP-01），**必須明寫 `model: <provider/model>` 有效字串**（AP-17，v2.2.2 修正）。實渐機制：專屬 agent 嘅 frontmatter 留空**或寫 `inherit`** 都唔會跟 ZCode 後台 default——會跌落 provider 清單第一個（可能係你唔想用嘅）；只有一般 subagent 先跟後台 default。「分配權喺後台」嘅正確實現＝**Phase 4 問用戶要 model 字串（記入 PLAN §11），逐個 agent 明寫入檔**；內建知識由 memory current 鏈抽；首輪 ≤3。
2. CLI（`cli/<CLI>.py`）：核心＝`status`／`doctor`／`verify`／`handover`；痛點子命令按 §6；**deploy 無部署場景＝N/A**。
3. 新建 SKILL（`skills/<NAME>-ops/SKILL.md`）／自建 MCP（stdio＋host config；**改 config＋重啟 host 屬啟用動作，入批准請求表**）。
4. 防漂移：`docs/frozen/*.sha256`（**SHA-256**，唔用 md5）＋invariant 測試（FROZEN／事實表寫成 assert）。
5. Secret 紀律：env／本地 secret 檔；.gitignore；**含 secret 嘅備份一律唔入 Git**。
6. 每個新命令實測前按**全域執行安全規則**審副作用（寫 DB／發訊息／起服務／出網？）——唔憑命令名判安全；NOT_RUN 嘅記錄原因。實測輸出貼 project_status。

**閘門**：**適用且已授權**嘅驗證全綠；doctor／verify 只喺有 CLI 先適用——**冇 CLI＝NOT_APPLICABLE（記錄）**，唔准為過閘門逆向生個 CLI 出嚟；§6 每項結論有對應實作或明記 N/A。

---

## Phase 7 — Plugin 打包（§6 結論話打包先做；N/A 合法）

marketplace.json＋`plugin/`（.zcode-plugin/plugin.json／agents／skills／commands／tools 用**複製**唔用引用）；包定義／skill／command／CLI／examples；**唔包** binary／state／secret／大歷史。**狀態制**：**PACKAGED**（bundle 齊＋JSON 過 `python -m json.tool`＋內容乾淨）→達到就可以交貨；**INSTALLED／LOAD VERIFIED**（安裝＋新 session 載到）係**啟用動作**——§11 批咗先做，未批就停喺 PACKAGED，唔算未完成。

---

## Phase 8 — 獨立 review（12 項，全部 PASS／FAIL／UNVERIFIED＋證據）

冇參與改動嘅唯讀 reviewer（「唔改檔、唔 commit」；重跑受全域執行安全規則約束，只重跑安全唯讀核對）：①FROZEN 對賬②數字一致（PLAN↔plan-data.json↔HTML 三方）③結構完整④路徑存在⑤secret 重跑（R3 狀態制）⑥適用嘅 doctor／verify 重跑⑦git 一致⑧agent frontmatter（line 1 開始、name/description 在、**`model:` 明寫有效字串**——留空／inherit＝P1，會跌落錯 provider，AP-17）⑨SOP／skill／CLI 邏輯一致⑩過時宣稱抽 3 對實況⑪PLAN·HTML 對賬⑫**草稿對賬（最終 MD vs 已批草稿 diff 經白名單過濾；越權改動＝P0）**。分級：P0 必修（0 P0 先交付）／P1 必修或書面豁免／P2 roadmap。修完覆核一輪。

---

## Phase 9 — Handover／Repo

①project_status 快照。②memory（狀態制 append）。③handoff（今輪逐項證據＋下一步 P0–Pn 每步驗收準則）。④收尾狀態：**LOCAL COMPLETE／NOT_PUSHED 係合法收尾狀態**（push 未批＝記入批准請求表待辦，唔迫人多做一步先准交貨）；push 批咗先做：feature branch→push 前重跑 secret scan＋`git status` 過濾→push 後**遠端驗證 tip**（`gh api`／`ls-remote`，唔准只信本地）。⑤plugin 副本 SHA-256 對賬。⑥PLAN 收尾＋**HTML 重新生成（AP-15）**。閘門：收尾狀態交代清楚（LOCAL COMPLETE 還係 PUSHED＋遠端驗證過）；PLAN/HTML 一致；下一手按 handoff P0 開到工。

---

## 反模式（18 條）

| # | 反模式 | 點解唔准 |
|---|---|---|
| AP-01 | 操作手冊覆蓋 agent frontmatter | frontmatter 唔喺 line 1，agent 載入唔到，直接消失 |
| AP-02 | 假綠 | verify 永遠 exit 0／測試冇 assert，制造全綠假象 |
| AP-03 | crash 未查系統錯誤報告就歸因 | 兩個方向都會帶錯修復方向 |
| AP-04 | UI 自動化代替 API | 慢、脆、易壞——功能一律行正式接口 |
| AP-05 | hardcode secret 入檔 | 遲早跟住 push 出去；只准 env／本地 secret 檔 |
| AP-06 | 複製 recipe 冇改 placeholder | 腳本「成功咁做咗錯嘅嘢」 |
| AP-07 | banner 後行號漂移 | 檔頂加 banner 後舊行號引用全部錯位 |
| AP-08 | 只 push 一半 | push 後必須遠端驗證 tip |
| AP-09 | 副本不同步 | 多份副本改主本唔同步其他——manifest＋單一來源 |
| AP-10 | tasklist 截斷 | 長 image name 被截——用 /FO CSV |
| AP-11 | argparse dest 撞名 | 後者靜默覆蓋前者 |
| AP-12 | 假穩定 | 無 baseline 對照嘅穩定宣稱唔准寫 |
| AP-13 | 照抄 subagent 摘要 | coordinator 要抽樣實測先准寫入權威文件 |
| AP-14 | 統計數字不可複現 | 數字必須連產生命令 |
| AP-15 | HTML 同 PLAN 脫鉤 | HTML 係 view，改 PLAN 必重新生成 |
| AP-16 | 一句交差／草稿唔齊 | PLAN 攞去批但 §8 草稿缺份（尤其 product_specification）或者一句帶過——Phase 4 呈交＝PLAN＋全部草稿＋json＋HTML，一個都不能少 |
| AP-17 | agent model 留空／寫 inherit | 實測：專屬 agent 唔會跟後台 default，靜靜跌落 provider 清單第一個——必須明寫 `model: <provider/model>`（Phase 4 問用戶，記入 PLAN §11） |
| AP-18 | 規格寫成病歷 | product_specification 係開案功能契約（功能＋驗收準則，大家跟住做）；fine-tuning 輪次／修復史／驗證過程係項目歷史——入 memory／PROJECT／FROZEN。歷史混入規格，下一手就分唔清「要做咩」同「做過咩」 |

---

## Recipes

**R1 session 查詢（其中一種實作；唯讀）**：適用於已核實 host／版本（`~/.zcode/cli/db/db.sqlite`，用 `Path.home()` 組路徑）**而且有讀取授權**嘅環境——**DB 存在唔代表授權**；有平台 session 工具／用戶匯出就用嗰啲，SQL 只係 fallback。三部分：part1 inventory（`SELECT id,title,directory,time_created FROM session WHERE directory LIKE '%<PROJECT>%' OR title LIKE '%<KEYWORD>%'`——**必帶範圍 WHERE，唔准全表**；id 有 `sess_` 前綴）；part2 user message 關鍵詞頻率（join part/message，role=user）；part3 角色統計（subagent＝`parent_id IN` 主 session ids，title bucket 分類）。**最後記錄：實際用咗邊個 tool／query／scope**。

**R2 檔案 inventory**：os.walk（大小／mtime；skip .git／node_modules）。

**R3 secret scan（狀態制）**：6 組 pattern（kv-literal／bearer／private key／dpapi／github token／aws key）；只報路徑＋次數，唔印值。**輸出分三部分**：①SCANNED（N 檔）②**NOT_SCANNED 清單（逐檔＋原因，例 size>2MB）→呢啲檔一律 UNVERIFIED** ③findings（路徑＋次數）。**「0 findings」只涵蓋已掃部分**——要發布／要 push 嘅檔案如有 NOT_SCANNED，整體只可標 **PARTIAL**，唔可以標 secret-clean。

**R4 git drift**：branch／HEAD／dirty／log-5／`sha256sum` 副本對賬。

**R5 shell 陷阱＋gh**：`curl.exe` 唔好用 `curl` alias；bash 反斜杠用 forward slash；tasklist /FO CSV；長腳本寫暫存 .py 唔好塞 `-c`；**gh 開源搜尋**：`gh search repos "<keywords>" --json fullName,description,license,pushedAt,stargazersCount`（欄位係 `license` 唔係 `licenseInfo`；`--json` 逗號後唔加空格；實施時用 `gh search repos --help` 核欄位表）。

---

## 模板（10 個）

`PLAN.template.md`（§1–§11；§6 評估表＋開源候選表；§8 manifest 含原檔狀態欄；§11 批准請求表格式）｜`plan-report.template.html`（json 驅動、離線 SVG、escape、PASS/FAIL/UNVERIFIED、草稿導覽 details）｜`product_specification.template.md`｜`agent.template.md`｜`memory.template.md`（含 current/superseded/revoked 狀態欄）｜`project_status.template.md`｜`FROZEN.template.md`｜`REVIEW_REPORT.template.md`（12 項狀態制）｜`marketplace.template.json`｜`plugin.template.json`

---

## 安裝／分發

本 skill 預設**零同步**：唔會自動複製去任何 project folder／其他主機。要分發（俾朋友／另一部機）＝用戶明確批准嘅獨立動作，逐次講明目標同內容。

## 本 skill 自身驗收 checklist

- frontmatter 齊；Phase 0–9 齊（每個目的／步驟／輸出／閘門）。
- 閘門全部範圍制（無湊數配額）。
- 10 模板齊；零項目例子（grep 驗證）。
- HTML 模板離線開到＋escape＋零 CDN。
- promote 白名單明確；N/A 狀態制貫穿（NOT_APPLICABLE／PACKAGED／LOCAL COMPLETE）。
- SELFTEST 有兩個沙盒行為案例結果＋>2MB canary。
- 獨立 review 0 P0。
