from pathlib import Path


class ParameterReader:

    def __init__(self, filename, config):

        self.filename = Path(filename)
        self.config = config

    def wanted_parameters(self):
        """
        Return a set of parameter names requested by the YAML configuration.
        """

        wanted = set()

        groups = self.config.get("parameter_groups", {})

        for group in groups.values():
            for parameter in group:
                wanted.add(parameter)

        return wanted

    def read(self):
        """
        Read a MAVLink parameter export (.param/.params) and return only
        the parameters requested by the configuration.

        Older ArduPlane firmware versions may use different parameter
        names and/or units. These are normalised here so the rest of
        the framework sees a consistent API.
        """

        wanted = self.wanted_parameters()

        params = {}

        with open(self.filename, "r") as f:

            for line in f:

                line = line.strip()

                # Skip blank lines
                if not line:
                    continue

                # Skip comments
                if line.startswith("#"):
                    continue

                parts = line.split()

                # Expected format:
                # VehicleID ComponentID Name Value Type
                if len(parts) < 5:
                    continue

                name = parts[2]

                try:
                    value = float(parts[3])
                except ValueError:
                    value = parts[3]

                #
                # Firmware compatibility
                #

                # ArduPlane 4.6.x
                # RNGFND1_MAX_CM (cm)
                if name == "RNGFND1_MAX_CM":
                    name = "RNGFND1_MAX"
                    value = value / 100.0

                if name in wanted:
                    params[name] = value

        return params
