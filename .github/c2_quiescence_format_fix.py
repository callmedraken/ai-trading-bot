from pathlib import Path

path = Path("src/trading_bot/runtime/windows_transactional_authority.py")
text = path.read_text(encoding="utf-8")
old = "            if self._harness_binding is None or lease._binding is not self._harness_binding:\n"
new = (
    "            if (\n"
    "                self._harness_binding is None\n"
    "                or lease._binding is not self._harness_binding\n"
    "            ):\n"
)
if text.count(old) != 1:
    raise RuntimeError(f"expected one formatting target, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
