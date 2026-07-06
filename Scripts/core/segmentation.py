from .segments import ModeSegment
from .modes import PLANE_MODES


class FlightSegmenter:

    def __init__(self, log):
        self.log = log

    def mode_segments(self):

        mode_df = self.log.get("MODE")

        if mode_df.empty:
            return []

        segments = []

        for i in range(len(mode_df)):

            row = mode_df.iloc[i]

            start = int(row["TimeUS"])

            mode_num = int(row["Mode"])

            mode_name = PLANE_MODES.get(
                mode_num,
                f"UNKNOWN({mode_num})"
            )

            if i < len(mode_df) - 1:
                end = int(mode_df.iloc[i + 1]["TimeUS"])
            else:
                end = start

            duration = (end - start) / 1e6

            segments.append(
                ModeSegment(
                    mode=mode_name,
                    start_us=start,
                    end_us=end,
                    duration_s=duration,
                )
            )

        return segments
