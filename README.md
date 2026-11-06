> Current release (2026-11-07): Skill 3.1.2 / Plugin 0.2.2; packet 2.0 unchanged. Evidence: [IMPROVEMENTS-RESULT.json](IMPROVEMENTS-RESULT.json), [independent review](IMPROVEMENTS-REVIEW.md).
> Related-project history only: global relevance search, bounded screening, then relevant deep reading.
> New `--stage checkpoint` checks continuation; streaming Git capture accepts large valid output without loading it all.

# open-project — ZCode

Skill **3.1.2**, plugin **0.2.2**, packet contract **2.0**.

只在用戶明確叫用時執行完整開案／重整。五個核心文件角色、全系統歷史覆蓋、輸出根、exact approval、獨立review及completion證據各自驗收。安裝本身不建project folder。

ZCode 保留 native Agent/subagent_type、ReadSessionContext、commands、frontmatter與model/provider規則。**無 GitNexus，G6固定N/A。**

完整更新、舊packet遷移、兩host保護清單及ZCode可用prompt：[UPDATE-GUIDE.md](UPDATE-GUIDE.md)。行為契約：[workflow-contract.md](skills/open-project/references/workflow-contract.md)。

```text
python -m unittest discover -s tests -v
python scripts/build-plugin.py
```

工具入口在 `skills/open-project/scripts/`；先用 `--help` 核對參數。gate預設advisory，失敗仍可能exit0；`ready`／當前stage同errors先係結果。`--strict`僅改exit，不會授權或強制模型行為。

只用synthetic測試，唔讀寫live專案／DB／host config。PACKAGED、INSTALLED、LOAD_VERIFIED、INVOCATION_VERIFIED分開；未測不宣稱PASS。MIT，保留LICENSE。

## Explicit open-project Jev bypass

Explicit invocation now uses a task-scoped, user-authorized Jev orchestration exception. Continue all authorized preparation, retain independent review and exact effect approvals. Unrelated tasks keep their governance. See UPDATE-GUIDE.md for the matching host-instruction installation; source changes alone do not prove a running session adopted it.
