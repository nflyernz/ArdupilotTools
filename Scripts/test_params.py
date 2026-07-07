from core.config import Config
from core.params import ParameterReader

cfg = Config("Config/landing.yaml")

reader = ParameterReader(
    "Params/_11_2026-6-14-09-37-12.params",
    cfg
)

params = reader.read()

print()

for name in sorted(params):
    print(f"{name:20} {params[name]}")
