# Codex port provenance

ZCode upstream: https://github.com/cyrusasco/open-project-skill
Upstream tested commit: f4e32bed5a11b9d83567c8e580db82cd908d9ba3
Reviewed original baseline: 44f5d3129cfe46e9646286a49ee552c0429d608c

This branch is an independent Codex edition. Main remains ZCode. Do not merge the whole branch into main.

The initial port copied the common parser, schema, renderer, promotion, generic templates and tests as exact bytes. Codex-specific onboarding now extends its gate, workflow and selected templates/tests. The table below lists only resources that remain byte-identical to the upstream tested commit. Selectively transfer future common fixes, then test both editions. No automatic overwrite of installed copies or host settings.

Host differences: explicit invocation policy in agents/openai.yaml; portable plugin manifest and Codex catalog; native agent TOML/manual; JSONL/native-app session adapter; independent SKILL/host reference/README. ZCode commands, .zcode-plugin and host-zcode reference are intentionally absent.

## Exact shared files

| Path | Raw SHA-256 |
|---|---|
| .gitignore | 20795132003acc6774e8e0741f1c7b8fb1f96877363bc9d80d77f4b31f8534c1 |
| LICENSE | da9c207ac178f429ac002df6617a18633a4629ec8d0db86f6e92f1a04cb8422c |
| skills/open-project/schemas/plan.schema.json | 6e4423cc81707b689bde32acf5b36323291b86a3453f84210df2069f9ab11add |
| skills/open-project/scripts/plan_contract.py | 3487d3c21dd3e1eebfb44bfc128cb4fc2b1a0c44c64c905d863b1e223281f390 |
| skills/open-project/scripts/plan_render.py | 7d61941a3e876c85f66015e62e7bd85069c69c5c278ee7f02da51c29009a9c27 |
| skills/open-project/scripts/promote.py | e25deff6b5c1aec787617145a5919e603f0aca5bed12c244c84c1a3143d09c82 |
| skills/open-project/scripts/render-plan.py | 2afbc69d9afeaf9afd1dd15c29c5139b8d116bd1adf1088efbf1ee562a1925cd |
| skills/open-project/templates/FROZEN.template.md | 5ea0ec62cb60ebdb18099b60e7e6ed057a87693345ee0432167dfb177fa50597 |
| skills/open-project/templates/memory.template.md | c72cd57556db1cbff8b93f4b128c0106f9e7168fbed2587746f7d7ff2b1c27ed |
| skills/open-project/templates/plan-report.template.html | bad4d96174e2bc4144fa69625ae42341e6249ca9c0df4d1e1c12072b1220fc03 |
| tests/test_promote.py | 04438a60ce2bb0de798d558bd1e7fa80ffdf348e7bb91c4c793b07a216ef60b7 |
| tests/test_renderer.py | 33925aacc246c8cc723173d44c324629eb9aa73ef49a31d803b7ac5346c463b7 |

## Codex-only GitNexus integration (0.1.1)

Skill revision 3.0.0-codex.2 requires every Codex review packet to include the installed gitnexus-project-onboarding workflow. Its G6 profile uses the existing tools array under packet1.0. Plans enumerate each Skill/Plugin, graph/catalog dispositions, steps, acceptance and blockers; unsupported real-project admission stays BLOCKED. No onboarding backend, graph, catalog or host setting is changed by this release. Main remains untouched.

The gate, build allowlist, workflow contract, selected templates and their tests are now intentional Codex-only deltas. The shared-file table excludes those changed bytes. Native loading evidence from0.1.0 is retained with its exact tested version; it does not certify the current package.
