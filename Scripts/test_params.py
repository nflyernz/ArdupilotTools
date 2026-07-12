from pathlib import Path

from core.config import Config
from core.params import ParameterReader


cfg = Config("Config/landing.yaml")

paramfile = Path("Params") / "log_11_2026-6-14-09-37-12.params"

reader = ParameterReader(
    paramfile,
    cfg
)

params = reader.read()

print()
print(f"Loaded {len(params)} parameters")
print("-" * 60)

for name in sorted(params):
    print(f"{name:20} {params[name]}")
