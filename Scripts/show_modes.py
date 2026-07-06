from common import read_messages

msgs = read_messages(
    "Logs/log_19_2026-7-5-09-43-10.bin",
    ["MODE"]
)

start = msgs["MODE"][0]["TimeUS"]

print()

for m in msgs["MODE"]:

    t = (m["TimeUS"] - start) / 1e6

    print(f"{t:8.1f} s   Mode={m['Mode']:2d}   Reason={m['Rsn']}")
