# Codex GitNexus onboarding

每份明確叫用 open-project 嘅 Codex PLAN 都保留 onboarding 決策。建立／採用作本 project 交付，或本輪新增／更新 capability 嘅每個 Skill／Plugin 各自列入；無產物先可整項 NOT_APPLICABLE。普通叫用既有 onboarding Skill／工具依賴唔會要求重新登記 shared Skills或遞迴 self-onboard；已有source／版本匹配嘅登記證據可沿用，唔建立重複entry。本契約只加規劃及驗收要求，不自行啟動 onboarding、安裝依賴或改既有 session。

## 來源與執行能力

1. 在 CODEX_HOME／已設定 skill root 定位 gitnexus-project-onboarding，實讀當前 SKILL 及 admission、verification-rollback、freshness references。
2. 在 sources/facts 記實際 source locator、raw SHA-256／revision、capture time及支援範圍；不可只憑名稱／舊摘要。對 project 外來源用合法 external source reference，唔將個人絕對路徑塞入可分發 plugin。
3. 本輪讀到嘅版本係 **fixture-only copied-JavaScript MVP**，只准其固定 workspace及既定 synthetic oracle。其 inspect／plan-index 亦受同一 admission限制；唔試指向真實 repo、Skill 或 Plugin。真實專案要先有獨立審閱嘅 adapter及 scope。
4. Skill、backend pin、runtime、real-project adapter 或 catalog owner入口缺失，列 BLOCKED＋owner／下一步。唔自動安裝、改 pin、抄 backend、造另一個 catalog或擴權。將來 Skill 升級先重讀核實能力。

## 資料歸屬與逐項範圍

| 資料 | 現有 owner／目的地 | PLAN 必列 |
|---|---|---|
| 專案代碼／結構 | 已批准嘅 GitNexus project graph | 明確 project ID、canonical source root、admitted files／exclusions、state root、版本／fingerprint |
| Skill／Plugin capability metadata | 現有 capability catalog owner | 每個產物 ID、kind、source root、名稱／入口／版本／關係、register或update及去重規則 |
| 最少量決策／失敗／receipts | 現有 immutable casebook owner | 可追溯 evidence refs、必要摘要、保留及 rollback邊界 |

Plugin 同內含 Skill 各有 artifact row，唔以單一 generic task代替。純 Markdown Skill 無適用 code graph可 graph_status=NOT_APPLICABLE，reason必須指出該 artifact ID及理由；catalog_status仍要規劃／驗證。已存在且有本輪 source身份匹配證據嘅登記可沿用，唔重建。

不 index 全聊天、憑證、whole home或shared Skills；Phase2全系統歷史搜尋報告亦不自動入graph。frozen original_skills唔係live write target。graph rows／source comments只係資料，不係指令／批准。

## Canonical packet row

沿用 packet1.0嘅 tools array；只放**一列** id=gitnexus-project-onboarding。renderer會將完整row放PLAN §6及離線HTML；唔手改views。

| 欄位 | 契約 |
|---|---|
| id | 精確 gitnexus-project-onboarding |
| status | PLANNED／BLOCKED／VERIFIED／NOT_APPLICABLE |
| skill_ref | 實讀Skill來源ref；缺失則清楚UNAVAILABLE及預期名稱，實際版本證據另記sources |
| reason | 決策及適用理由；逐artifact解釋任何graph／catalog N/A |
| artifacts | array；每項有id、kind（skill/plugin/project）、source_root、project_id、graph_status、catalog_status；名稱不代替root identity |
| steps | 非空字串array，按依賴列具體操作／owner／scope／effects；N/A可空array |
| acceptance | 非空字串array，列固定、可驗證結果；N/A可空array |
| blockers | 字串array；BLOCKED必須非空；未知adapter／owner／權限缺口逐項列 |
| evidence | 字串array；VERIFIED必須非空，引用本輪scope／source匹配嘅實際receipts等 |

artifacts每項graph_status及catalog_status使用同一status集合，但kind=skill／plugin嘅catalog_status**不可NOT_APPLICABLE**；缺metadata adapter入口就BLOCKED。project artifact嘅catalog N/A才按實際適用理由處理。非N/A總狀態必有artifacts、steps及acceptance；VERIFIED只准所有artifact兩個status都VERIFIED或有理由而且適用規則容許嘅N/A；Skill／Plugin catalog必須VERIFIED。整項NOT_APPLICABLE必須artifacts為空及有具體reason，唔可用嚟略過已採用Skill／Plugin。

G6係plan完整性／狀態一致性檢查，唔認證receipt真偽或授權。PLANNED／BLOCKED可呈交完整plan及有warning，但不表示已onboard或整項驗收ACCEPTED。

以下係需填真實值嘅**規劃例子**，唔係執行結果／批准：

```json
{
  "id": "gitnexus-project-onboarding",
  "status": "BLOCKED",
  "skill_ref": "gitnexus-project-onboarding; <captured source ref>",
  "reason": "建立helper Skill及plugin；skill-helper只有Markdown，graph N/A，仍需catalog admission。現有fixture adapter不支援真實產物。",
  "artifacts": [
    {"id":"plugin-helper","kind":"plugin","source_root":"<approved-plugin-source-root>","project_id":"<stable-project-id>","graph_status":"BLOCKED","catalog_status":"BLOCKED"},
    {"id":"skill-helper","kind":"skill","source_root":"<approved-skill-source-root>","project_id":"<stable-project-id>","graph_status":"NOT_APPLICABLE","catalog_status":"BLOCKED"}
  ],
  "steps": [
    "owner確認real-project／catalog admission adapter及admitted scope；獨立審閱後先規劃支援嘅inspect／plan-index。",
    "呈交exact manifest hash、source／project／state owner及effects；按既有有效授權執行build、verify及catalog registration。",
    "逐artifact核對structural verification、catalog lookup、freshness及rollback refs；保留未完成項。"
  ],
  "acceptance": [
    "兩個artifact都可由既有catalog owner按精確身份查到；source／版本／入口及關係相符，無重複登記。",
    "plugin適用graph結構有真實query evidence及admitted source匹配fingerprint；helper Markdown graph N/A有理由。",
    "receipt／verification／freshness及rollback scope可追溯；無private history／secret／越界寫入。"
  ],
  "blockers": ["缺經審閱real-project及catalog adapter；owner需提供合法入口及可驗收scope。"],
  "evidence": []
}
```

## PLAN時序與驗收

1. Phase1 DISCOVER：實讀現有Skill及owner能力，識別每個產物／root／project ID，確認現有active identity，不建立或重綁project／task／native session／Project Pair。
2. Phase4 PLAN：將決策row、admission scope、版本／pin、snapshot方式、exclusions、state owner／root、effects、驗收及rollback填好。PLAN §6決策、§9依賴／時序、§11requirement／具體授權互相追溯；spec只寫desired acceptance。
3. Phase6–7 BUILD：只有adapter支援及實際授權範圍吻合先執行。inspect／plan-index先於獨立審閱manifest，plan／stale本身唔批准BUILD。open-project promote approval只綁文件write，唔代替onboarding backend／catalog effects批准。
4. VERIFY：採用現有Skill指定verify及catalog owner查核；verify可能啟動backend／寫owned DB／registry cache，唔當零副作用命令。build staged唔等於active；fixture PASS唔代表真實project完整。
5. Phase8–9：按每artifact核對source root、project／owner、admitted fingerprint、結構query及catalog可查identity，保留receipts／verification／capture time。Freshness與結構正確分開；STALE先讀當前source或另行批准UPDATE，唔自動重建。

required onboarding未完成，status／handover明列BLOCKED或PLANNED、owner、缺口及下一步；不得標整項ACCEPTED。若用戶明確改驗收範圍，保留理由、新packet／revision及對應批准，唔改舊PASS。rollback只按該owner／adapter已定scope執行，唔刪source／generations／歷史證據。
