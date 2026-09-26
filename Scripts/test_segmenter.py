from core.log_reader import FlightReader


def main():
    log = FlightReader(
        "Logs/log_19_2026-7-5-09-43-10.bin"
    ).read()

    print(log.get("MODE"))


if __name__ == "__main__":
    main()
