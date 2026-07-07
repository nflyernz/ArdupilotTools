from core.config import Config

cfg = Config("Config/landing.yaml")

print(cfg.get("analysis"))
print()
print(cfg.get("messages"))
print()
print(cfg.get("parameters"))
