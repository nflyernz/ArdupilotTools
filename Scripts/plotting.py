import os
import matplotlib.pyplot as plt
import pandas as pd


def _time(df):
    return (df["TimeUS"] - df["TimeUS"].iloc[0]) / 1e6


def landing_dashboard(csv_dir, output_dir):

    tecs = pd.read_csv(os.path.join(csv_dir, "TECS.csv"))
    att = pd.read_csv(os.path.join(csv_dir, "ATT.csv"))
    arsp = pd.read_csv(os.path.join(csv_dir, "ARSP.csv"))
    aetr = pd.read_csv(os.path.join(csv_dir, "AETR.csv"))

    fig, axs = plt.subplots(2, 2, figsize=(15, 10))

    #
    # Height
    #

    t = _time(tecs)

    axs[0,0].plot(t, tecs["h"], label="Height")
    axs[0,0].plot(t, tecs["hdem"], label="Height Demand")
    axs[0,0].set_title("TECS Height")
    axs[0,0].grid(True)
    axs[0,0].legend()

    #
    # Airspeed
    #

    t2 = _time(arsp)

    axs[0,1].plot(t, tecs["sp"], label="TECS Speed")
    axs[0,1].plot(t, tecs["spdem"], label="Speed Demand")
    axs[0,1].plot(t2, arsp["Airspeed"], label="Pitot")
    axs[0,1].set_title("Airspeed")
    axs[0,1].grid(True)
    axs[0,1].legend()

    #
    # Throttle
    #

    t3 = _time(aetr)

    axs[1,0].plot(t, tecs["th"], label="TECS")
    axs[1,0].plot(t3, aetr["Thr"], label="Output")
    axs[1,0].set_title("Throttle")
    axs[1,0].grid(True)
    axs[1,0].legend()

    #
    # Pitch
    #

    t4 = _time(att)

    axs[1,1].plot(t4, att["Pitch"], label="Pitch")
    axs[1,1].plot(t4, att["DesPitch"], label="Desired")
    axs[1,1].plot(t, tecs["ph"], label="TECS")
    axs[1,1].set_title("Pitch")
    axs[1,1].grid(True)
    axs[1,1].legend()

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)

    outfile = os.path.join(output_dir, "landing_dashboard.png")

    plt.savefig(outfile, dpi=200)

    plt.close()

    print(f"Saved {outfile}")
