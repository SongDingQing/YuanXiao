# Agent Control Plane Contracts

YuanXiao and ChangE are evolving from a mobile chat bridge into an auditable,
pausable, resumable, and extensible agent control plane. The short-term goal is
not to add more agents blindly; it is to make every agent's permissions, state,
artifacts, failures, and verification evidence visible and controllable from the
phone.

This document records the first public, sanitized contract layer. Private host
names, IP addresses, local machine paths, tokens, and keys stay in untracked
configuration.

## Design Inputs

The 2026-05-13 and 2026-05-14 agent-infra research notes emphasized these
directions:

- Normalize runner differences across Codex, Hermes, Gemini CLI, Qwen Code,
  OpenCode, Deep Agents, and future remote machines.
- Treat MCP and tool access as a capability registry with source, allowlist,
  isolation, approval, and audit metadata.
- Replace plain progress text with typed cards: approval, artifact, trace,
  failure, memory, checkpoint, and report.
- Split Plan orchestration into router, orchestrator, subagent, and evaluator
  nodes, while keeping ChangE as the reporting manager.
- Add a mobile smoke benchmark covering chat, typed cards, approval/reject,
  attachments, disconnect recovery, queue reorder, and report lookup.

## runner_adapter

`runner_adapter` describes one executable agent runner or relay. The Android UI
should eventually show runner status and permission hints instead of exposing a
raw "Codex/Hermes" toggle only.

Core fields:

- `adapter_id`: stable id.
- `display_name`: short user-facing name.
- `runner_type`: `codex`, `hermes`, `gemini_cli`, `qwen_code`, `opencode`,
  `deep_agent`, `remote_agent`, or `custom`.
- `client_mode`: how ChangE talks to it, such as local API, CLI resume, or
  HTTPS relay.
- `machine_id`: sanitized machine label.
- `status`: `available`, `degraded`, `disabled`, or `quarantined`.
- `session_endpoint`: non-secret endpoint metadata.
- `workspace_policy`: default working directory, allowlist, denylist, and
  sandbox class.
- `capabilities`: runner-level feature flags such as checkpoint, headless,
  subagents, streaming, and artifact upload.
- `approval_policy`: human approval defaults and dangerous action categories.
- `audit`: schema version and trace metadata.

Initial seeded adapters:

- Codex on the Mac mini.
- Hermes as the local front door.
- ChangE public relay.
- A placeholder remote agent entry for another machine.

## capability_registry

`capability_registry` records tool access independently from the runner that may
call it. It is the foundation for an MCP gateway/capability registry.

Core fields:

- `capability_id`: stable id.
- `name`: short description.
- `provider`: bridge module or gateway owner.
- `protocol`: Python call, local HTTP, SQLite read, file tail, MCP tool, etc.
- `tool_source`: sanitized source reference.
- `status`: `enabled`, `quarantined`, or `disabled`.
- `side_effect_level`: `none`, `local_read`, `local_write`, `external_send`,
  or `destructive`.
- `workspace_allowlist`: directories or logical workspaces it may touch.
- `secret_policy`: where secrets come from and how logs redact them.
- `isolation`: process/network/filesystem isolation notes.
- `approval_policy`: when YuanXiao must ask the owner before execution.
- `schemas`: input/output schema references.
- `android_renderer`: compact renderer hints for typed cards.
- `audit`: event and trace requirements.

## workflow_node

`workflow_node` makes Plan/CEO orchestration inspectable on the phone. It maps
well to a router -> orchestrator -> subagent -> evaluator flow without relying
on hidden in-agent status reports.

Core fields:

- `node_id`, `workflow_id`, `project_id`, `parent_node_id`.
- `node_type`: `router`, `orchestrator`, `subagent`, `evaluator`, `memory`, or
  `artifact`.
- `state`: `created`, `queued`, `running`, `waiting_approval`, `blocked`,
  `failed`, `completed`, or `cancelled`.
- `title`: compact visible label.
- `owner`: runner/person/session binding.
- `dependencies`: upstream nodes and blocking requirements.
- `todo`: small Android-renderable task list.
- `checkpoint`: resumable state and last verified point.
- `inputs` and `outputs`: sanitized structured data.
- `trace`: trace id, spans, and evidence references.
- `policy`: approval and retry policy for this node.

## typed_card

`typed_card` is the Android card layer for work that should not be flattened
into chat text.

Card types:

- `approval`: approve/reject or choose an option before a high-impact action.
- `artifact`: file, APK, report, screenshot, link, or build output metadata.
- `trace`: timeline, logs, queue movement, or runner execution trace.
- `failure`: error category, likely cause, retry option, and evidence.
- `memory`: durable decision, user preference, or project fact.
- `checkpoint`: resumable milestone and verification snapshot.
- `report`: compact progress or completion report.

Every card stores `actions`, `payload`, `renderer`, `status`, and audit events.
YuanXiao should render cards natively and allow direct card actions instead of
forcing the user to issue a new natural-language command.

## mobile_smoke_run

The smoke benchmark should become the release gate for future `煮元宵` work.
The bridge stores smoke runs in SQLite so the APK can show recent verification
results without calling a model.

Required cases:

- Main ChangE chat.
- Codex async receipt and final inbox delivery.
- Task card render.
- Approval and rejection.
- Attachments.
- Disconnect recovery.
- Queue reorder.
- Report lookup.
- Failure card render.
- Memory card render.

## First Implementation Scope

The current bridge stores these contracts in the existing ChangE/YuanXiao task
ledger database and exposes backward-compatible HTTP APIs:

- `GET /api/v1/runner-adapters`
- `GET /api/v1/capabilities`
- `GET /api/v1/workflow-nodes`
- `POST /api/v1/workflow-nodes`
- `GET /api/v1/cards`
- `POST /api/v1/cards`
- `POST /api/v1/cards/answer`
- `GET /api/v1/mobile-smoke-runs`
- `POST /api/v1/mobile-smoke-runs`

The Android APK can adopt these endpoints incrementally without breaking the
existing chat, task, Codex session, queue, or Plan APIs.
