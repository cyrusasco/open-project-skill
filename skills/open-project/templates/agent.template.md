# AGENTS.md — <PROJECT> operation manual

> Draft for review. This is project guidance, not a registered custom-agent definition.
> Do not add a rule that automatically invokes open-project for every task.

## Purpose and scope

<PROJECT goal, approved responsibilities, working root and limitations>

## Read for the active task

1. Read product_specification.md for desired behavior and acceptance.
2. Read relevant project_status.md facts and current memory events.
3. Respect FROZEN invariants; propose a separately approved change before modifying them.
4. Verify current environment only with relevant, authorized commands.

## Conditional operations

| Situation | Action |
|---|---|
| CLI exists | Use actual documented commands from the project root |
| No CLI | NOT_APPLICABLE; do not create one to satisfy a checklist |
| Validation applies and is authorized | Run it and record command, scope and evidence |
| Validation unavailable | NOT_RUN / UNVERIFIED with reason |
| Deployment not adopted | N/A |
| Push not authorized | LOCAL COMPLETE / NOT_PUSHED |

Commands must be separate explicit invocations. Do not pipe status into doctor/verify/deploy.

## Handover

Record completed evidence, remaining work and next acceptance steps. Append correction events to memory; do not rewrite old entries. Keep requirement acceptance separate from observed status.

## Boundaries

Do not disclose secrets, modify host settings or broaden the current task's authorization. Model/reasoning and permissions are selected by the user and host. Native delegation is optional and follows the actual available tools.
