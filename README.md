# open-project — Codex

Skill **3.1.1-codex.1**, plugin **0.2.2**, packet contract **2.0**.

只在用戶明確叫用時執行完整開案／重整。五個核心文件角色、全系統歷史覆蓋、輸出根、exact approval、獨立review及completion證據各自驗收。安裝本身不建project folder。

Codex 保留 portable plugin、native TOML agent繼承、explicit-only policy及Codex-only GitNexus admission；fixture-only唔等於真onboarding。

完整更新、舊packet遷移、兩host保護清單及ZCode可用prompt：[UPDATE-GUIDE.md](UPDATE-GUIDE.md)。行為契約：[workflow-contract.md](skills/open-project/references/workflow-contract.md)。

```text
python -m unittest discover -s tests -v
python scripts/build-plugin.py
```

工具入口在 `skills/open-project/scripts/`；先用 `--help` 核對參數。gate預設advisory，失敗仍可能exit0；`ready`／當前stage同errors先係結果。`--strict`僅改exit，不會授權或強制模型行為。

只用synthetic測試，唔讀寫live專案／DB／host config。PACKAGED、INSTALLED、LOAD_VERIFIED、INVOCATION_VERIFIED分開；未測不宣稱PASS。MIT，保留LICENSE。


## Codex real onboarding adapter (0.2.1)

The Python-backed plugin profile now has an executable real GitNexus adapter: [contract and commands](skills/open-project/references/gitnexus-real-adapter.md). It uses the existing pinned backend, an explicitly admitted source snapshot, source-derived structural queries, native Codex catalog lookup, freshness, bounded symbol lookup and retained rollback. It runs only on explicit onboarding/UPDATE requests. ZCode is unchanged. Current local execution evidence is separate from synthetic tests and native model invocation.

## Explicit open-project Jev bypass

Explicit invocation now uses a task-scoped, user-authorized Jev orchestration exception. Continue all authorized preparation, retain independent review and exact effect approvals. Unrelated tasks keep their governance. See UPDATE-GUIDE.md for the matching host-instruction installation; source changes alone do not prove a running session adopted it.
