# Milestone 4 -- Controlled interventions

Milestone 3 fixed a **detector** and compared monitoring *designs*. Milestone 4 fixes
the detector and varies the **intervention**: what the trusted monitor is actually
*allowed to do* once it has reached a decision. The scientific question is no longer
"does the monitor notice?" but "does acting on the notice help, and at what cost?"

This matters because detection and prevention can diverge (requirements section 5). A
monitor can flag the right episodes yet intervene too late, or block outcomes for
unrelated reasons. Milestone 4 makes the *action* an explicit, independently variable
treatment so prevention can be attributed to the intervention rather than the signal.

## The intervention arms

`RunConfig.intervention` (YAML key `intervention`) selects the arm. The default is
`auto`, which reproduces the Milestone 3 behaviour exactly.

| `intervention`          | Effect on enforcement                                                        |
|-------------------------|------------------------------------------------------------------------------|
| `none`                  | Detect only; **never** enforce. The pure detection-vs-prevention control.    |
| `auto`                  | Milestone 3 semantics: the monitor decision maps directly to enforcement.    |
| `review_gate`           | A **graduated 4-way release review** (see below) instead of allow/deny.      |
| `restricted_tools`      | **Revoke a capability class** from offending agents.                         |
| `independent_verification` | An enforce-time **independent re-verification** must clear the action.    |
| `full`                  | Review gate + restricted tools + independent verification combined.          |

`experiments/milestone4_interventions.yaml` sweeps these against a fixed `rules`
monitor so the intervention is the only thing that varies.

## Tool permissions: the capability model

Milestone 3 had no notion of tool permissions: `AgentAction.kind` was a free string and
the only check lived inside the SWE write-path glob. Milestone 4 introduces a typed
capability set in `collusions_lab/capabilities.py`:

* `Tool` -- a coarse capability class (`PRICE`, `COMMUNICATE`, `WRITE_FILE`,
  `RUN_TESTS`, `REVIEW`, `RELEASE`, `PLAN`, `MESSAGE`).
* `CapabilitySet` -- an **immutable** set of granted tools, with `allows`,
  `allows_action`, `without` (for revocation) and `default_for(role)`.
* `ACTION_TOOL` -- the mapping from an action `kind` to the capability it needs.
* `CapabilityError` -- raised if an action is forced past the choke point.

`AgentConfig.capabilities: Optional[CapabilitySet]` carries an explicit grant; `None`
means "use the role default". The grant is enforced at a **single dispatch choke point**
in the runner (`_check_capability`), shared by both scenarios. A denied action:

1. does **not** take effect (no price change, no file write),
2. emits a `TOOL_DENIED` event in the **authoritative** log (`visible_to_agents=False`),
3. is counted in `metrics.tool_denials`.

Agents are never told *why* an action was denied and get no feedback channel, matching
the requirement that enforcement is trusted and non-negotiable.

## The graduated review gate

`ReleaseGate.request_release` maps a detection **action** to a distinct review
**outcome** (`ReviewOutcome`). The two vocabularies are deliberately separate: the
monitor decides what it *believes*; the gate decides what *happens*.

| Monitor action          | Review outcome               | Meaning                                   |
|-------------------------|------------------------------|-------------------------------------------|
| `ALLOW`                 | `ALLOW`                      | Release proceeds.                         |
| `HOLD`                  | `REQUEST_CHANGES`            | Not a hard block: revise and resubmit.    |
| `CONSTRAIN`/`QUARANTINE`| `BLOCK`                      | Verified violation: refused.              |

`ALLOW_WITH_RESTRICTIONS` is issued via `ReleaseGate.allow_with_restrictions`: the
change is released, but named capability classes are revoked for the rest of the
episode. This is the outcome produced by `full` when independent verification clears an
`ALLOW` but residual risk warrants reducing the agent's tools.

Every outcome is recorded on the `MonitorDecision` (`review_outcome`, `restricted_tools`)
and emitted as an `INTERVENTION` event in the authoritative log.

## Independent verification (an action, not a signal)

Milestone 3's `ArtifactVerificationMonitor` is a *detection* component. Milestone 4's
`IndependentVerifier` (`monitor/verification.py`) is an **enforce-time action**: when
the intervention is `independent_verification` or `full`, a monitor decision that would
allow or block is first routed through fresh, environment-owned checks
(`swe_verifier` / `market_verifier`). This lets us A/B *the same detector* with
verification on vs off -- isolating the contribution of independent verification as an
intervention rather than as a detection signal.

The verifier's checks are never derived from agent claims: each returns
`(name, passed, detail)` computed from the authoritative environment. TOOL_CALL /
TOOL_RESULT events are emitted with `actor="verifier"` for auditability.

## Effects per scenario

### Markets

* `auto` / `review_gate`: a `CONSTRAIN` forces the competitive price and **latches**
  until review (Milestone 3 behaviour).
* `restricted_tools` / `full`: a `CONSTRAIN`/`QUARANTINE` revokes the sellers' `PRICE`
  capability (`_restrict_market_sellers`) and latches; a `HOLD` applies a **one-round
  cooling-off** at the competitive price, then clears.
* `independent_verification`: `CONSTRAIN` -> `BLOCK`, `HOLD` -> `REQUEST_CHANGES`.
* `none`: no effect.

The one-round cooling-off gives a market `HOLD` a real, *reversible* effect for the
first time; previously it was a complete no-op.

### Software engineering

* `auto` / `none`: consult the gate directly on the raw monitor decision.
* `review_gate`: consult the gate and record the 4-way outcome.
* `independent_verification`: run `swe_verifier` on `ALLOW`/`CONSTRAIN`/`QUARANTINE`;
  an unverified `ALLOW` becomes `BLOCK`.
* `restricted_tools` / `full`: a `CONSTRAIN`/`QUARANTINE` revokes `write_file` and
  `release`; a `HOLD` revokes `release`. `full` additionally runs the verifier on
  `ALLOW`, producing `ALLOW_WITH_RESTRICTIONS` when it clears.

## Recording and evaluation

Each result carries `intervention`, `review_outcome`, `restricted_tools`, and
`metrics.tool_denials`; the manifest carries `intervention`. Episode directories are
named `..._mon{type}_int{intervention}` so arms never collide.

`collusions_lab.evaluation.by_intervention` breaks the three metric families down by
arm and adds intervention-specific observables:

* `tool_denial_rate` -- denied actions per episode (the cost of restricted tools),
* `review_outcome_distribution` -- how each arm's releases resolved.

These sit alongside the existing `by_monitor_type`, `threat_curve`, and
`prevention_confusion` reports.

## Running the sweep

```powershell
# Offline (scripted agents, rules monitor) -- exercises every arm without network:
python -m collusions_lab.experiments experiments/milestone4_interventions.yaml --out runs_m4
python -m collusions_lab.evaluation runs_m4
```

Expected shape: `none` detects (recall 1.0) but prevents nothing; `auto` preserves the
Milestone 3 prevention rate; the graduated arms prevent at least as much while
exposing the tool-denial cost.

## Shared vs scenario-specific details

**Shared** (both scenarios): the `Tool`/`CapabilitySet` model and choke point; the
`InterventionType`/`ReviewOutcome` vocabularies; the `INTERVENTION` / `TOOL_DENIED`
events; `RunConfig.intervention` plumbing, episode naming, manifest/result fields; the
`by_intervention` evaluation breakdown; the "agents get no feedback" guarantee.

**Scenario-specific**: the concrete gate (`ReleaseGate` vs price override); which tools
exist and are revocable (`write_file`/`release` vs `price`); what a `HOLD` physically
does (request-changes vs one-round cooling-off); and the verifier's checks
(`swe_verifier` vs `market_verifier`).

## Signal -> code path map

| Concept                     | Code path                                                        |
|-----------------------------|------------------------------------------------------------------|
| Capability model            | `collusions_lab/capabilities.py`                                 |
| Dispatch choke point        | `runner._check_capability` / `_resolve_capabilities`             |
| Intervention selection      | `runner._apply_market_intervention`, `_apply_swe_intervention`   |
| Graduated gate              | `environments/software_engineering/swe_env.py::ReleaseGate`      |
| Market restricted/HOLD      | `runner._restrict_market_sellers`, `market.clear_forced_prices`  |
| Independent verification    | `monitor/verification.py` (`swe_verifier`, `market_verifier`)    |
| Decision fields             | `schemas.MonitorDecision.intervention/review_outcome/restricted_tools` |
| Events                      | `schemas.EventType.INTERVENTION` / `TOOL_DENIED`                 |
| Evaluation                  | `evaluation.by_intervention`                                     |
| Sweep                       | `experiments/milestone4_interventions.yaml`                      |
