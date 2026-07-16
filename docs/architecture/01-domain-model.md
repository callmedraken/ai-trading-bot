# Domain model

The domain layer defines framework-independent values and entities shared by
the research platform. It includes normalized symbols, supported assets,
UTC market bars, order requests, fills, order state, and long-only positions.

Domain objects are immutable and validate their own invariants. Prices,
quantities, commissions, and monetary calculations use `Decimal`; timestamps
must be timezone-aware and are stored in UTC. Symbols are normalized and the
supported asset universe is limited to US stocks and ETFs.

Orders describe proposals and recorded state. They do not execute trades or
change accounts. Execution, deterministic risk approval, and accounting remain
separate responsibilities so no strategy or model can bypass those boundaries.
