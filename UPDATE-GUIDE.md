# open-project — Jev bypass update (2026-11-06)

| Host | Branch | Skill | Plugin |
|---|---|---|---|
| ZCode | main | 3.1.1 | 0.2.1 |
| Codex | codex-port | 3.1.1-codex.1 | 0.2.2 |

## 本次行為

明確叫用 open-project 後自動使用 USER_AUTHORIZED_BYPASS，唔再要求 Jev route、feasibility、score、monitoring、completion 或重問 bypass。仍須完成已授權盤點、相關歷史深讀、五稿、render/gate及獨立review；PARTIAL係checkpoint，唔係剩餘可做工作嘅終點。

只限本次明確啟動任務及已授權child；普通工作／引文／安裝不觸發。用戶可明確要求恢復Jev。正式寫入、部署、push、OS/sandbox、實際security hook、模型/provider、JevCompact及GUI/browser規則保留；ZCode無GitNexus，Codex保留既有接入義務。

## Codex 更新（來源＋有界用戶指令例外）

在已選定來源根以正常 PowerShell7 執行：

```powershell
.\scripts\install-with-jev-bypass.ps1
```

此入口會先選實際生效的user instructions（Codex非空AGENTS.override.md優先，否則AGENTS.md），預檢並備份原bytes，只追加精確標記的 open-project Jev 例外，再調用原生 installer。已加相同例外時no-op；有本地修改或漂移時停止，不覆蓋。原 install-plugin.ps1 保持原有單純安裝行為，不能單靠它解決全域「每個任務必經Jev」指令衝突。步驟失敗會如實報PARTIAL/BLOCKED，不移除其他插件或重設設定。

## ZCode 更新 prompt

```text
請從 cyrusasco/open-project-skill main 更新 open-project：Skill3.1.1 / Plugin0.2.1。
保留既有未提交修改，先核對版本、hash、native agent/AP-17、model/provider、commands及hook設定。
本用戶已要求：明確叫用open-project時自動bypass TypeSafe/Jev orchestration，不再重問；其他任務照舊。
按下方helper先preview ~/.zcode/AGENTS.md，再用preview的before_sha256做精確apply，只追加有界例外並保留原bytes backup。不要修改或停用security hooks。若hook本身真強制阻擋，保留阻擋證據並報該host限制，不能冒稱已成功。
用ZCode原生方法更新已選plugin／skill來源；GitNexus=N/A。新session核對實際載入及明確叫用時免Jev行為；沒有實測則UNKNOWN。不要修改原項目／舊session的失敗紀錄。
```

## 預檢、套用與回復

以下 PATH 為已選定 host 的 AGENTS.md 絕對路徑，HASH 使用剛取得的 before_sha256：

```text
python scripts/configure-jev-bypass.py --instructions PATH
python scripts/configure-jev-bypass.py --instructions PATH --apply --expected-sha256 HASH
```

回復只移除自己完整且未修改的block；保留block前後其他用戶文字。先preview再apply：

```text
python scripts/configure-jev-bypass.py --instructions PATH --remove
python scripts/configure-jev-bypass.py --instructions PATH --remove --apply --expected-sha256 HASH
```

此helper不提供OS權限；不要經另一工具繞過權限拒絕。普通SKILL執行不自動編輯global instructions。安裝／配置／模型行為三層分開驗證，現有session可能保留舊context；恢復前重新讀實際已安裝版本及例外。沿用Project Pair及未完成packet，受影響內容用新revision，不重用舊批准。

## 既有 packet 與保護規則

以下是0.2.0共同修訂的歷史指引；版本及本次Jev例外以本頁上方為準。原有五角色、exact approval、drift及completion規則繼續適用。

# open-project 0.2.0 — 兩個 host 更新指引

| Host | Branch | Skill | Plugin | GitNexus |
|---|---|---|---|---|
| ZCode | `main` | `3.1.0` | `0.2.0` | **N/A**；不安裝、不探測、不索引，缺少 receipt 不阻擋完成 |
| Codex | `codex-port` | `3.1.0-codex.1` | `0.2.0` | Codex-only onboarding；現有 fixture MVP 唔代表真項目 adapter |

兩版共同使用 packet **2.0**。唔 merge 整條 branch；保留各 host 原生設定。普通安裝唔建立 project folder，亦唔自動啟動開案。

## 本次共同修正

- `route=new/reorg` 同輸出目的地分開。有舊 code／session 唔代表新文件要寫返舊 folder；先定 docs/code/source roots，再按授權建立 staging。
- 五個核心文件角色必交：`agent.md` 項目操作手冊、`product_specification.md`、`project_status.md`、`memory.md`、`REVIEW_REPORT.md`。既有別名要明確映射；project manual 唔係 native subagent。
- 全系統歷史 discovery、實際取回及模型深讀分開；必要來源未掃完唔叫全史完成。新專案無歷史可寫明有證據嘅 N/A。
- `PLAN_READY`、`PROMOTED` 同 `COMPLETE` 分開。搬 folder／加 plugin／改 spec，要先完成受影響 packet／草稿／render／gate 及適用批准；舊 review 不能直接當最後版本驗收。
- 決定事件推導唯一當前批准狀態。封存有 source→destination→supersedes 證據；git 有預期 untracked 可以接受，但唔稱 clean。
- Plugin 清楚選知識 bundle 或本機 adapter；每項 included／external／excluded、hash 同連結要對賬。唔將私人全庫、secret、runtime state 包入。
- advisory 預設及 explicit strict 保留；checker 係驗收，唔係 host 強制。命令及實際 JSON 欄位以 skill 內 `references/workflow-contract.md` 同 `--help` 為準。

## 舊 packet 遷移

1. 保留 schema1.0 packet、首次已知 baseline、批准、journal 及備份，唔先覆寫舊資料。
2. 診斷舊包缺項；補 roots、五個角色、Phase 義務、來源／功能／review／package 證據，形成新2.0 revision。
3. 重新 render／gate，再使用真正覆蓋該 revision／bytes／effects 嘅批准；同 scope 唔代表新內容自動已批。
4. 舊在途操作只可用原 packet／批准／既有 journal 嘅明確 legacy recovery；不能借此啟動新寫入或移植授權。
5. 未有收尾證據只報 PARTIAL／REVIEW_PENDING，唔用舊版 READY 當全流程完成。

## ZCode 更新 prompt

```text
請更新 open-project，只用 https://github.com/cyrusasco/open-project-skill 的 main。
目標：Skill3.1.0／Plugin0.2.0／packet2.0；先核對實際遠端HEAD與來源。
先盤點已安裝 standalone skill、command、plugin 的來源／版本及本地修改；保留 dirty files、原始bytes、設定與回復入口，唔直接覆蓋。
保護現有 Agent/subagent_type、ReadSessionContext、.zcode-plugin、commands、native agent frontmatter、已確認 model/provider、hooks/global instructions/host config。模型問題已解決，不重設。
ZCode 無 GitNexus：G6=N/A，唔安裝／探測／索引，唔搬 Codex TOML、openai.yaml policy 或原生安裝指令。
先喺獨立來源副本跑 unittest、build、核心角色缺件／新folder／搬移後packet漂移／review版本／批准矛盾等驗收；只用 synthetic DB，唔對 live session DB 寫入。
按已授權範圍，用 ZCode 原生方法更新選定副本；冇必要唔加全域hook／其他設定。使用新session核對實際載入來源、版本、namespace及明確叫用行為；未實測就UNKNOWN。
唔直接修 ThreadDock／WhatsApp 的 live 文件。先重新讀各自最新狀態，再各出 repair packet，避免覆蓋並行工作。
交付來源HEAD、保護檔案對賬、測試命令/exit/coverage、package hashes、安裝/loaded/invocation狀態及rollback方法。PACKAGED唔等於INSTALLED。
```

## Codex 更新

只使用 `codex-port`，先確認 `SOURCE.json`／`VERSION`／portable manifest 全部係本次版本，跑測試及 build。喺正常有 profile 寫入權限嘅 PowerShell7、Python3.11+ 執行：

```powershell
.\scripts\install-plugin.ps1
```

原生 installer 不直接改 cache／global model；如同名 marketplace 指向另一來源，會停止並保留現有設定。唔用 sandbox／權限 workaround。已安裝0.1.1唔代表0.2.0已更新。

手動叫用 prompt：

```text
$open-project-codex:open-project new <goal or folder>
$open-project-codex:open-project reorg <project folder>
```

保留 YAML boolean `policy.allow_implicit_invocation: false`。Codex GitNexus 按現有 graph／catalog／casebook owner 分工；真 onboarding 缺 reviewed adapter 就 BLOCKED，不自造 receipt，不把 PLAN 當 BUILD 批准。呢項唔適用 ZCode。

## 驗收及回復

`python -m unittest discover -s tests -v` 只證明列明 synthetic 範圍；看當前 `TEST-RESULTS.json`，唔沿用舊測試數。
`python scripts/build-plugin.py` 建 allowlisted 獨立 package，不安裝。SOURCE／PACKAGED／INSTALLED／LOAD_VERIFIED／INVOCATION_VERIFIED 分開記錄。
新版本 host load、真模型叫用或真 GitNexus 未實測就 UNKNOWN／BLOCKED。回復使用保留嘅上版來源及原生 host 操作；唔 reset 用戶其他改動或混合兩版設定。


## Codex-only 0.2.1 follow-up

This branch adds the real Python plugin onboarding adapter. ZCode main stays on 0.2.0 and requires no GitNexus update. Preserve `allow_implicit_invocation: false`. Read `skills/open-project/references/gitnexus-real-adapter.md`, then use plan/build/verify/complete for an explicitly authorized source. A native plugin update and actual model invocation remain separate from graph/catalog onboarding; source updates do not silently rewrite the current session or global hooks.
