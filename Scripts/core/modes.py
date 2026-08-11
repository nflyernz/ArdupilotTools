"""
ArduPlane flight mode definitions.
"""

PLANE_MODES = {

    0: "MANUAL",

    1: "CIRCLE",

    2: "STABILIZE",

    3: "TRAINING",

    4: "ACRO",

    5: "FBWA",

    6: "FBWB",

    7: "CRUISE",

    8: "AUTOTUNE",

    10: "AUTO",

    11: "RTL",

    12: "LOITER",

    13: "TAKEOFF",

    15: "GUIDED",

    16: "QSTABILIZE",

    17: "QHOVER",

    18: "QLOITER",

    19: "QLAND",
}


def mode_name(mode_number):
    """
    Return the ArduPlane mode name for a mode number.
    """

    try:
        mode_number = int(mode_number)
    except (TypeError, ValueError):
        return "UNKNOWN"

    return PLANE_MODES.get(
        mode_number,
        f"UNKNOWN({mode_number})"
    )