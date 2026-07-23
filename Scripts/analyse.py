"""
Application entry point for the flight analysis toolkit.

All execution paths (CLI, regression, future GUI) originate here.
"""


def cruise_analysis():
    print("\nCruise Analysis")
    print("Not implemented.")


def autotune_review():
    print("\nAutotune Review")
    print("Not implemented.")


def sensor_diagnostics():
    print("\nSensor Diagnostics")
    print("Not implemented.")


def log_summary():
    print("\nLog Summary")
    print("Not implemented.")


def menu():

    while True:

        print("\nFlight Analysis")
        print("================")
        print("1. Landing Analysis")
        print("2. Cruise Analysis")
        print("3. Autotune Review")
        print("4. Sensor Diagnostics")
        print("5. Log Summary")
        print("0. Exit")

        choice = input("\nSelection: ").strip()

        if choice == "1":
            from analyses.landing import LandingAnalysis

            landing = LandingAnalysis()
            landing.run()

        elif choice == "2":
            cruise_analysis()

        elif choice == "3":
            autotune_review()

        elif choice == "4":
            sensor_diagnostics()

        elif choice == "5":
            log_summary()

        elif choice == "0":
            break

        else:
            print("Invalid selection.")


if __name__ == "__main__":
    menu()