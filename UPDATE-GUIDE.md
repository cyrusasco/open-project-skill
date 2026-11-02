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
