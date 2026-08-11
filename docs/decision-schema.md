# Decision record schema (as implemented)

Documents `DecisionRecord` and related types in `src/aris/decisions/queue.py`
**as they exist today**. This is not a proposed audit-trail design — Phase D
owns that redesign. Nested fields from `Recommendation` /
`StrategyAction` are included only because `DecisionRecord.recommendation`
embeds them.

## `DecisionRecord`

Written by `DecisionQueue.resolve()` when the engineer answers a pending turn.

| Field | Type | What it captures |
|---|---|---|
| `kind` | `DecisionKind` | Which prompt class was resolved (`confirm_strat`, `pit`, `tactical`, `safety_car`, `manual_pit`) |
| `lap` | `int` | Lap number passed into `resolve` (caller-supplied) |
| `accepted` | `bool` | `True` if `choice_id` is `"yes"`, `"confirm"`, or `"edit"` |
| `choice_id` | `str` | Raw option id chosen (`"yes"` / `"no"` / `"edit"` / `"confirm"`, etc.) |
| `recommendation` | `Recommendation \| None` | The top recommendation that was pending when resolved (may be `None`) |
| `edited_fields` | `dict[str, Any]` | Engineer edits submitted with the resolve (e.g. `pit_lap`, `compound`); empty if none |

### What it does **not** capture today

Compared to a full audit trail, the current record does **not** store:

- A data / state snapshot reference (no `RaceState` id, hash, or serialized state)
- The full candidate action set considered by `recommend()` (only the top recommendation is attached)
- An explicit “chosen action” field separate from `choice_id` + embedded `recommendation.action`
- A structured reasoning basis beyond whatever text lives on the nested `Recommendation` (`evidence`, `narration_context`, `tactical`)

`DecisionQueue` also keeps conversational `history` / `pending` `DecisionTurn`s
in memory; those are UI/session state, not part of `DecisionRecord`.

## Nested: `Recommendation` (`aris.recommend`)

| Field | Type | Notes |
|---|---|---|
| `rank` | `int` | Rank among returned top-k |
| `label` | `str` | Human label for the card |
| `action` | `StrategyAction` | Proposed action |
| `delta_vs_stay_out_s` | `float` | Simulated delta vs stay-out |
| `mean_race_time_s` | `float` | MC / sim mean race time |
| `confidence_std_s` | `float` | Spread from MC |
| `p10_delta_s` / `p90_delta_s` | `float` | Percentile band on delta |
| `evidence` | `str` | Short evidence string from the scorer |
| `narration_context` | `dict` | Context passed to narrator |
| `tactical` | `str \| None` | Optional tactical tag |

## Nested: `StrategyAction` (`aris.simulate`)

| Field | Type | Notes |
|---|---|---|
| `kind` | `ActionKind` | `stay_out` / `pit_now` / `pit_lap` |
| `pit_lap` | `int \| None` | Single pit lap when kind is `pit_lap` |
| `pit_compound` | `str \| None` | Compound for that pit |
| `pit_laps` | `list[int] \| None` | Multi-stop schedule (when used) |
| `pit_compounds` | `list[str] \| None` | Compounds for multi-stop |

## Related queue types (not the record)

| Type | Role |
|---|---|
| `DecisionTurn` | One chat turn (`aris` or `engineer`) with optional options / editable fields / attached recommendation |
| `DecisionOption` | Clickable option (`id`, `label`, `recommended`) |
| `DecisionQueue` | Holds `history`, `pending`, and append-only `decisions: list[DecisionRecord]` |
