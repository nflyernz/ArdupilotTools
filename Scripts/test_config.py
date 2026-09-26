from core.config import Config


def main():
    cfg = Config("Config/landing.yaml")

    print(cfg.get("analysis"))
    print()
    print(cfg.get("messages"))


if __name__ == "__main__":
    main()
