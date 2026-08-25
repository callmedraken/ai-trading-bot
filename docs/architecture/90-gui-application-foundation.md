# Architecture 90 — GUI Application Foundation

## Status

GUI-A1 architecture contract. This document defines the first graphical application
boundary without changing trading, risk, authority, credentials, brokerage,
reconciliation, deterministic identities, or production capture semantics.

## Goal

Introduce a native desktop application shell that can eventually present the
existing research, paper-operation, market-data, audit, and system-health
capabilities through reviewed application/service interfaces.

The GUI is a presentation and operator-control layer. It is never a second trading
engine or a privileged shortcut into production internals.

## Framework

Use Qt 6 through PySide6 for the desktop presentation layer.

PySide6 is an optional development/application dependency rather than a dependency
of the core trading package. Qt imports must remain under `trading_bot.gui` so
headless research, tests, CLI operation, paper operation, and production authority
remain independently usable without Qt.

The GUI-facing service boundary must use plain Python types and `typing.Protocol`;
it must not expose Qt objects to the domain/application layers.

## Dependency direction

The allowed direction is:

```text
Qt widgets / windows
        |
        v
GUI presentation models
        |
        v
GUI application-service protocol
        |
        v
reviewed application/domain services
```

The following direction is forbidden:

```text
GUI -> production SQLite
GUI -> Credential Manager
GUI -> Alpaca transport
GUI -> broker transport
GUI -> risk bypass
GUI -> production child/process primitives
```

A future adapter may call a reviewed production or paper service, but the GUI may
only receive the bounded result of that service. The adapter, not the widget,
owns
translation into GUI presentation models.

## GUI-A1 scope

GUI-A1 implements only a safe shell and mock-backed read-only overview:

- native application startup;
- main window with stable navigation;
- Home, Research, Paper, Market Data, and System pages;
- explicit operating-mode/status presentation;
- immutable presentation dataclasses;
- a plain-Python `GuiApplicationService` protocol;
- a deterministic `MockGuiApplicationService` used by the shell;
- no production action buttons;
- no credential, database, market-data provider, broker, scheduler, or recovery
  actions;
- no direct dependency on C3 implementation modules.

The mock service is deliberately static/deterministic. It exists to exercise the
presentation boundary without inventing new domain truth or external effects.

## Presentation models

GUI-A1 uses immutable dataclasses for the shell overview. At minimum the overview
must carry:

- operating mode;
- environment label;
- short status summary;
- component/status cards for research, paper operation, market data, and system;
- whether an item is informational, healthy, unavailable, or blocked.

These are presentation states, not authority states. A displayed `AVAILABLE` or
`HEALTHY` value never grants permission to perform an effect.

The GUI may define future mode labels such as broker-paper or live for display
contracts, but GUI-A1 must not expose controls that activate them. Paper/research
remain the only mock-backed operational modes in this checkpoint.

## Navigation contract

The initial sidebar/page identifiers are stable presentation identifiers:

```text
home
research
paper
market-data
system
```

Navigation changes only the visible page. It does not invoke trading, capture,
recovery, scheduling, credentials, or brokerage operations.

## Failure behavior

GUI construction must fail normally if the optional Qt dependency is missing.
Core package imports must remain unaffected.

A service/adaptor failure in later checkpoints must be converted to bounded
presentation error state; widgets must not display raw credential/provider/native
exception text merely because it is available downstream.

## Testing contract

GUI-A1 testing is split in two layers:

1. Pure Python tests for presentation models, protocol behavior, and deterministic
   mock state. These do not require Qt.
2. Optional Qt smoke tests when PySide6 is installed. Run them with the offscreen
   Qt platform and verify the shell can be constructed, has the expected pages,
   and navigation does not invoke an external effect.

The ordinary core test suite must continue to run without installing the `gui`
extra. Qt-specific tests must use `pytest.importorskip("PySide6")` or an equivalent
explicit skip.

## Packaging

Add a `gui` optional dependency group containing a PySide6 version that supports
the repository's supported Python versions, including Python 3.14 used by the
current Windows development environment.

Do not add PySide6 to unconditional runtime dependencies.

GUI-A1 may be launched with:

```text
python -m trading_bot.gui
```

No console-script entry point is required in this checkpoint.

## Explicit non-goals

GUI-A1 does not:

- change any C1/C2/C3 authority or capture code;
- access the production runtime or authority database;
- read Credential Manager;
- contact Alpaca or any broker;
- schedule unattended work;
- execute strategy/risk/order flows;
- change deterministic identities or serialized artifacts;
- enable broker-paper or live trading;
- replace existing CLI/application services.

## Follow-up checkpoints

Recommended progression after GUI-A1:

- GUI-A2: read-only research/backtest result browser over existing reviewed
  serializers/services;
- GUI-A3: paper-account and paper-operation read-only views;
- GUI-A4: charts/analytics and audit/lineage inspection;
- later operator controls only after each underlying action has a reviewed service
  boundary suitable for GUI use.

Production/recovery/live controls require their own architecture reviews and are
not implied by this foundation.
