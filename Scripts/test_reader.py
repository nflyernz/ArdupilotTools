from common import read_messages

msgs = read_messages(
    "Logs/log_19_2026-7-5-09-43-10.bin",
    ["MODE"]
)

print(f"MODE messages: {len(msgs['MODE'])}")

print(msgs["MODE"][:5])
