from pymavlink import mavutil
import os
import pandas as pd

def open_log(filename):
    """
    Open an ArduPilot BIN log.
    """
    return mavutil.mavlink_connection(filename)


def read_messages(filename, wanted):
    """
    Read selected MAVLink log message types.

    Parameters
    ----------
    filename : str
    wanted : list[str]

    Returns
    -------
    dict
        Dictionary keyed by message type.
    """

    log = open_log(filename)

    data = {m: [] for m in wanted}

    while True:
        msg = log.recv_match(type=wanted)

        if msg is None:
            break

        data[msg.get_type()].append(msg.to_dict())

    return data
def save_csv(data, output_dir):
    """
    Save each message type as a CSV file.
    """

    os.makedirs(output_dir, exist_ok=True)

    for msg_type, records in data.items():
        if not records:
            continue

        df = pd.DataFrame(records)

        filename = os.path.join(output_dir, f"{msg_type}.csv")
        df.to_csv(filename, index=False)

        print(f"Saved {filename}")


def log_name(path):
    """
    Return filename without extension.
    """

    return os.path.splitext(os.path.basename(path))[0]
