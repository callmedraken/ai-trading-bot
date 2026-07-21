# CPU Mean-CVaR optimizer

The optional CPU optimizer converts an immutable specialized portfolio request
into a continuous long-only Mean-CVaR linear program. It does not generate
scenarios, rebalance, create proposals, run risk, execute orders, mutate a
ledger, integrate with a backtest, or connect to a broker.

## Specialized contracts and package boundary

`portfolio.mean_cvar` contains solver-independent frozen contracts.
`MeanCvarOptimizationRequest` combines an existing
`PortfolioOptimizationRequest`, compatible `ReturnScenarioSet`, and
`MeanCvarOptimizationParameters`. The base request's `risk_aversion` is the
only authoritative risk-aversion value. Scenario timestamp, horizon, and
ordered universe must match the base request exactly.

`MeanCvarOptimizationResult` retains the specialized request and wraps the
existing `PortfolioOptimizationResult`. An optimal result requires a target
and finite exact expected return and CVaR. Every unsuccessful status prohibits
all three. `FEASIBLE` is not used.

`optimization.cpu_mean_cvar` owns the optional SciPy boundary, float matrices,
solver invocation, Decimal cleanup, diagnostics, and deterministic identity.
SciPy is imported lazily, so the core project and domain models remain usable
without numerical dependencies.

## Objective, losses, and matrix ordering

For asset weights `w`, cash weight `c`, forecast returns `mu`, scalar cash
return `r_cash`, scenario losses `loss_s`, VaR `z`, scenario probabilities
`p_s`, confidence `alpha`, and excess loss `u_s`:

```text
expected return = sum(w_j * mu_j) + c * r_cash
loss_s = -(sum(w_j * scenario_return_s,j) + c * r_cash)
CVaR = z + sum(p_s * u_s) / (1 - alpha)
```

The conceptual maximization of expected return minus risk aversion times CVaR
is supplied to `linprog` as:

```text
minimize risk_aversion * CVaR - expected return
```

Each scenario uses `loss_s - z - u_s <= 0`. Its `A_ub` row therefore contains
negative scenario returns, negative cash return, `-1` for `z`, and `-1` for
that scenario's excess variable. The scalar scenario-set cash return supplies
both the cash reward forecast and cash return in every scenario.

Variables are ordered as asset weights in configured order, cash, `z`, excess
variables in scenario producer order, then optional turnover helpers for every
asset and cash. Rows are ordered as budget equality, scenario inequalities,
optional expected-return floor, paired turnover inequalities in asset/cash
order, and the aggregate turnover inequality.

## Supported constraints and turnover

Asset weights are bounded from zero through `maximum_position_weight`; cash is
bounded by its configured minimum and maximum; all weights plus cash equal one;
`z` is unbounded; and excess and turnover helpers are nonnegative. The optional
minimum expected return is a total arithmetic return over the request horizon.

One-way turnover includes assets and cash. For each component `i`:

```text
target_i - current_i <= d_i
current_i - target_i <= d_i
sum(d_i) <= 2 * maximum_one_way_rebalance_turnover
```

`minimum_position_weight` is explicitly unsupported because either-zero-or-at-
least-minimum is nonconvex and requires integer variables. Only obvious
zero-turnover infeasibility is rejected before solving; HiGHS decides other
feasibility questions.

## Solver, cleanup, and exact recomputation

The adapter calls `scipy.optimize.linprog(method="highs")` with presolve
enabled, display disabled, explicit applicable primal and dual feasibility
tolerances, and an optional iteration limit. It never uses a wall-clock limit.

Nominally successful output must exist and be finite. Values cross the boundary
through `Decimal(str(value))`, never `Decimal(float)`. Asset weights between
negative solver tolerance and zero are clamped to zero; materially negative or
above-bound weights fail. Assets are quantized with the configured quantum and
`ROUND_HALF_EVEN`. Cash receives the exact residual from one minus the asset
sum. The adapter neither repairs nor renormalizes an invalid residual.

The resulting target is constructed and all portfolio constraints and the
optional expected-return floor are revalidated in exact Decimal arithmetic. A
coarse quantum may therefore turn a float-feasible solution into a deliberate
`FAILED` result.

Expected return is recomputed from the cleaned target. Exact discrete CVaR is
computed for every unique scenario loss as a candidate `z`:

```text
z + sum(probability_s * max(loss_s - z, 0)) / (1 - alpha)
```

The minimum `(CVaR, z)` pair supplies a deterministic lower-`z` tie rule. The
reported objective is then recomputed from exact expected return and CVaR. Raw
solver `z` and excess values are not reported.

## Status, diagnostics, and unavailable behavior

SciPy statuses map as follows: zero becomes `OPTIMAL` only after cleanup; one
becomes `FAILED` with `SOLVER_LIMIT_REACHED`; two becomes `INFEASIBLE`; three
becomes `UNBOUNDED`; and four or unknown values become `FAILED`. Solver codes,
not messages, control behavior.

Stable diagnostics distinguish solver availability and status, limits,
nonfinite output, materially negative weights, invalid cash residuals,
post-cleanup expected-return or portfolio violations, objective value, maximum
constraint violation, and cleanup clamp count. Human-readable solver messages
are audit text only.

When SciPy is absent, public optimization returns `UNAVAILABLE`, solver name
`scipy-highs-unavailable`, no target or metrics, and `SCIPY_UNAVAILABLE`.
SciPy is an `optimization-cpu` project extra, not a runtime dependency.

## Identity and determinism

UUID5 target identity includes the complete canonical request fingerprint,
solver identity, cleaned ordered asset weights, and exact cash residual. Result
identity includes the request fingerprint, mapped status, target ID when
present, exact cleaned metrics, objective, and ordered stable diagnostic codes.
Messages, iterations, wall-clock values, object identity, and dictionary order
never affect IDs.

Matrix construction, cleanup, validation, and identity are deterministic.
Repeated equal solves are expected to agree in the same supported SciPy/HiGHS
and platform environment. Floating solver output is not promised to be
bit-for-bit identical across versions or platforms; materially different
cleaned outputs intentionally have different IDs. No epsilon objective forces
uniqueness. Lexicographic secondary optimization is deferred.

Future solver adapters, including a possible cuOpt adapter, may consume the
same specialized contract but must document their own numerical boundary,
cleanup, status mapping, dependency behavior, and determinism limits. GPU code,
mixed-integer constraints, scenario generation, and all trading-stage
integrations remain deferred.
