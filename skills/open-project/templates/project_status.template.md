# <PROJECT> — Project status／handover

> capture time：<ISO8601_WITH_OFFSET>　source snapshot／revision：<ID>
> 本文件係當前 observed 狀態；desired behavior／固定 acceptance 見 product_specification。
> completion：<LOCAL COMPLETE/PARTIAL/CHANGES REQUIRED>　repo：<NOT_PUSHED/PUSHED+REMOTE VERIFIED>
> package：<N/A/PACKAGED/INSTALLED/LOAD VERIFIED>；四狀態不混用。

## §0 事實、未知與證據

| fact ID | observed fact／值 | evidence ID | capture time／source version／scope |
|---|---|---|---|
| F1 | <observed value> | <ref> | <time/hash/range> |

| unknown ID | UNVERIFIED／原因 | 影響 required coverage | 下一步驗證 |
|---|---|---|---|
| U1 | <missing or NOT_RUN reason> | <impact> | <safe check/needed authorization> |

## §1 目前快照

| 項目 | 狀態 | evidence／命令／exit |
|---|---|---|
| PROJECT_ROOT | <resolved path> | <ref> |
| canonical packet | md-drafts/plan-data.json | <plan_id; revision; packet digest> |
| rendered views | <PLAN/HTML paths> | <same digest; last render evidence> |
| gate／ready | <advisory/strict; ready/status> | <report; missing; suggestions> |
| approval | <separate JSON ref or pending> | <plan/revision/digest/selected IDs> |
| promote | <per-file states/journal ref> | <draft/target/baseline/expected refs> |
| CLI | <adopted path or NOT_APPLICABLE> | <§6 decision; actual checks> |
| host enforcement／loaded | <UNKNOWN or observed proof> | <fresh-session/role evidence> |
| git | <branch; HEAD; dirty> | <command/time> |
| GitNexus onboarding | <overall PLANNED/BLOCKED/VERIFIED/NOT_APPLICABLE; each Skill／Plugin ID> | <tools row; source identity; graph／catalog owner; receipt／verification／freshness refs> |

## §2 Repo／package review

| 項目 | observed 結果／來源 |
|---|---|
| repo | <owner/repo or N/A> |
| local checkout／worktrees | <path; branch; SHA; dirty> |
| remote tip | <verified SHA/time or NOT_VERIFIED/NOT_PUSHED> |
| issues／PR／releases | <evidence or NOT_RUN reason> |
| source／package／installed／loaded | <separate paths/hashes/evidence> |
| secret coverage | <SCANNED count; NOT_SCANNED paths/reasons; findings counts only> |

push 未授權可 NOT_PUSHED 合法交貨；已 push 需驗遠端 tip，唔只信本地。

## §3 本輪已完成

| ID | 完成結果 | requirement／acceptance ID | evidence／command／exit／scope |
|---|---|---|---|
| DONE1 | <observed completion> | <REQ/test ID> | <ref> |

不要用舊 SELFTEST／SKILL-REPORT 當當前 PASS；寫當前 source revision、可重跑命令及實際 exit。

## §4 未完成與覆蓋限制

| ID | 未完成／UNKNOWN／NOT_RUN | 具體原因／授權缺口 | acceptance／下一步 |
|---|---|---|---|
| OPEN1 | <item> | <reason> | <criterion> |

full／partial／summary-only／unread、global metadata/content coverage、missing sources、WAL／併發 delta、fresh session／browser／live integration 分開記。reorg 不因 S 規模省掉全域 discovery。無 CLI／Plugin／deploy 可 N/A＋理由。

### GitNexus逐產物進度

| artifact ID／kind | source root／project ID | graph_status／catalog_status | owner／receipt／verification／freshness | blocker及下一步acceptance |
|---|---|---|---|---|
| <每個採用／建立Skill及Plugin一列；無產物有理由N/A> | <canonical identity; source revision/hash> | <PLANNED/BLOCKED/VERIFIED/NOT_APPLICABLE; N/A理由> | <actual refs or NOT_RUN> | <real-project／catalog adapter等依賴; owner> |

plan ready／PACKAGED唔等於onboard。fixture-only能力唔借作真實project證據；required onboarding未完保留PARTIAL。STALE不自動UPDATE／build；既有project／task／native session／Project Pair不重綁，歷史搜尋報告不自動入graph。

## §5 Roadmap（P0–Pn）

| priority | action／owner | 固定 acceptance | 依賴／現有授權／缺口 |
|---|---|---|---|
| P0 | <action> | <criterion> | <dependency> |
| P1 | <action> | <criterion> | <dependency> |
| P2 | <action or N/A> | <criterion> | <dependency> |

## §6 風險／恢復

| risk ID | observed 風險／來源 | 影響 | 緩解／剩餘限制 |
|---|---|---|---|
| R1 | <risk> | <impact> | <action> |

promote journal／backups：`.open-project-promotion/`，內部 .gitignore 保護記錄。FAILED_RECOVERED／FAILED_UNRECOVERED 只指 target_file_bytes；journal／backup／新空 parent directories 可保留。合作鎖不阻外部 writer。FROZEN 舊 bytes 以外部 manifest 指版本；memory correction events append。

## §7 Handoff／新 session 入口

- 明確任務／範圍：<request ref>。
- 根目錄與 canonical files：<PROJECT_ROOT; packet; spec; status; memory; frozen manifest>。
- 本輪證據：<source/evidence IDs; revision; tests/report>。
- 下一步先做：<P0 action＋acceptance＋可重跑命令>。
- 授權邊界：<already authorized / concrete missing authorization>。
- GitNexus交接：<逐artifact graph／catalog狀態、source／receipts／freshness、owner／blockers、下一步驗收；無產物N/A理由>。
- 最終 review：<ACCEPTED/CHANGES REQUIRED/PARTIAL; required coverage; P0/P1 status>。
- 收尾：<LOCAL COMPLETE/NOT_PUSHED/PACKAGED 等具體結果>。

新 session 讀到入口不自動觸發 open-project；只有用戶明確要求先按本流程續行。
