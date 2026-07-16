# Paper ledger

`PaperLedger` is the authoritative in-memory accounting component for a
simulated, long-only account. It accepts completed immutable `OrderFill`
objects and exposes cash, public position views, realized profit and loss,
ordered fill history, and immutable account snapshots.

For buys, gross cost plus commission reduces cash and is added to total cost
basis. Average cost is total cost basis divided by total quantity. For sells,
average cost determines the basis removed. Realized profit and loss is gross
proceeds less sell commission and removed basis; prior buy commissions are
therefore recognized through that basis.

Each fill is fully validated and its next accounting values are calculated
before any state is changed. Duplicate fill identifiers are rejected, and a
failed fill changes neither balances, positions, profit and loss, nor history.
Full sales remove the position exactly.

Snapshots require a positive `Decimal` price for every open position, ignore
extra prices, and calculate market value, equity, and unrealized profit and
loss without changing ledger state. Buying power equals cash because margin is
prohibited.

The ledger does not generate or execute orders, assess strategies, download
market data, persist records, connect to brokers, or make trading decisions.
