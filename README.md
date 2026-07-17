# AI Trading Bot

AI Trading Bot is a conservative algorithmic trading research platform. Its
initial scope is historical backtesting and simulated paper trading for
long-only US stocks and ETFs using daily bars.

## Current status

The project is in its foundation stage and is **paper-only**. It does not
download market data, implement strategies, execute orders, or connect to a
brokerage. Live trading is unavailable, and safety-focused configuration
rejects margin, short selling, options, crypto, and disabling paper trading.

> **Warning:** No Robinhood connection or integration exists. Do not provide
> brokerage credentials to this project.

## Environment setup

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On macOS or Linux, activate the environment with
`source .venv/bin/activate` instead.

Project commands must run inside the project virtual environment. On Windows,
either activate it as shown above or invoke its Python interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Run tests

From the repository root:

```powershell
python -m pytest
```

Without an activated environment on Windows, use:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
