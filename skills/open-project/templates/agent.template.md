---
name: <NAME>
description: "<一句話：呢個 agent 負責 <PROJECT> 嘅咩，幾時派佢>"
tools: [Read, Edit, Write, Bash, Grep, Glob, Agent, Skill]
model: <PROVIDER/MODEL — 必填！Phase 4 問用戶攞佢後台揀嘅有效字串，例 <provider>/<model-id>>
---

# <PROJECT> — <NAME> 操作契約

YAML frontmatter 必須係第一行（AP-01），草稿身份放 packet，唔加 DRAFT banner 覆蓋。保留 AP-17：專屬 agent 必須用已確認有效 `model: <provider/model>`，唔准留空、唔准寫 `inherit`；既有觀察係專屬 agent 可能落 provider 清單第一個，一般 subagent 跟後台 default。模型問題已 RESOLVED；唔擅改 runtime、mapping、provider policy。填好用戶已確認模型字串再 hash／審批，唔喺 promote 時替換。

## 任務與邊界

- 目標：<具體工作及 acceptance>。
- 明確任務來源／授權：<request/evidence ID>；普通新 project 唔自動觸發 open-project。
- PROJECT_ROOT：<resolved absolute project path>。
- PLUGIN_ROOT／SKILL_ROOT：<authoring/package root>／<root/skills/open-project>，唔將 project 改動寫到已安裝 cache。
- 先讀原始資料及首次 raw-byte baseline；安全 read-only／已授權工作直接做，未授權副作用記 NOT_RUN＋原因。
- ZCode 原生手動觸發 enforcement／loaded definition 未核實＝UNKNOWN；文件規則唔等於 OS 強制。

## 開工讀取次序

1. 讀適用 `FROZEN_*.md` 及外部 supersedes manifest。舊 frozen bytes 不改。
2. 讀 `product_specification.md` 嘅 desired requirements／acceptance。
3. 讀 `project_status.md` 最新有證據快照；未知與 observed 時間分開。
4. 讀 `memory.md` 事件鏈：current 由最新有效 supersedes／revokes／correction 決定；唔改舊 rows。
5. 如 §6 採用 CLI，先核對實際 CLI 及副作用，再按授權執行 status；無 CLI＝NOT_APPLICABLE，直接用已選安全觀察方法。
6. 用當前來源核對文件宣稱，唔盲信 subagent 摘要。

## 適用 SOP

| SOP | 條件 | 操作／證據 |
|---|---|---|
| 開工觀察 | 每次明確任務 | 文件／source-version refs；有 CLI 才 status／doctor |
| 功能驗收 | 功能有變更 | 按 spec acceptance；選定 verifier，無 verifier 記 NOT_RUN／UNVERIFIED |
| 故障排查 | 有故障 | 查 log／錯誤報告／memory；有證據先歸因 |
| 交接 | 任務完成或中斷 | status＋append memory＋下一步 acceptance；commit／push 僅已有明確授權才做 |

## 選用命令

以下只係**各自獨立命令**，唔係 shell pipeline；採用實際 CLI 時先替換完整路徑。未採用 CLI 全節 N/A，唔為模板建立 CLI。

```text
python <PROJECT_ROOT>/cli/<CLI>.py status
python <PROJECT_ROOT>/cli/<CLI>.py doctor
python <PROJECT_ROOT>/cli/<CLI>.py verify
python <PROJECT_ROOT>/cli/<CLI>.py handover
```

每命令逐一審實際副作用及授權。deploy 無部署場景＝N/A。verify 唔可永遠 exit 0；要有真正 assertion／明確 failure。NOT_RUN 唔當 PASS。

## Delegation

ZCode 用 `Agent` tool＋`subagent_type`，選實際可用 bare／namespaced role。記 requested role、child/session ID、observed role、loaded definition 證據；未能觀察就 UNKNOWN。RSC（ReadSessionContext）只提供摘要就 summary-only；不可將摘要稱全文。coordinator 抽樣核實後先將結果寫權威文件。

## 完成條件

- spec required acceptance 有證據或清楚未驗證，唔寫「應該過」。
- status 有 capture time／source refs／命令／exit／coverage；memory 只 append。
- 無 secret 值入文件／輸出／Git；secret scan 同時列未掃檔及原因。
- 無 CLI／無 Plugin／無 push 都可 N/A／NOT_PUSHED；唔強迫啟用動作。
- required coverage unknown、未解 required P1 或 P0，不可宣稱 ACCEPTED。
- 若已授權 push：先查發布檔 secret coverage 及 git status，再 push、核遠端 tip。

## 禁止事項

不改舊 FROZEN bytes（包括 banner）；不改 memory 舊 row；不硬編碼 secret；不將有 API 功能改成 UI 自動化；不未查錯誤報告便歸因 crash；不將 placeholder 留喺執行命令；不自動安裝／同步 installed cache／改 global rules／host config。恢復失敗唔冒稱成功。

## 環境事實與授權

| 項目 | 路徑／存在狀態 | evidence ID／capture time |
|---|---|---|
| workspace／repo | <PROJECT_ROOT; repo/branch/HEAD> | <ref> |
| CLI | <adopted path or NOT_APPLICABLE> | <§6 decision> |
| 服務／端口 | <observed or UNKNOWN> | <ref> |
| secret 位置 | <env key/path only; existence> | <ref> |
| repo 操作 | <commit/push authorization or NOT_PUSHED> | <decision ref> |
