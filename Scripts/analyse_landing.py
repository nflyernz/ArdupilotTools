import sys
import os
from plotting import landing_dashboard
from common import read_messages, save_csv, log_name

MESSAGES = [
    "MODE",
    "ATT",
    "AETR",
    "ARSP",
    "RFND",
    "TECS",
    "TEC2",
    "TEC3"
]

if len(sys.argv) != 2:
    print("Usage:")
    print("    python Scripts/analyse_landing.py Logs/log_xxx.bin")
    sys.exit(1)

logfile = sys.argv[1]

if not os.path.exists(logfile):
    print(f"Cannot find {logfile}")
    sys.exit(1)

print(f"Reading {logfile}")

data = read_messages(logfile, MESSAGES)

output = f"Output/CSV/{log_name(logfile)}"

save_csv(data, output)

plot_dir = f"Output/Plots/{log_name(logfile)}"

landing_dashboard(output, plot_dir)

print()
print("Finished.")
print(f"CSV files written to {output}")
