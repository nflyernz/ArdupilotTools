from fnmatch import fnmatch
from pathlib import Path


class ParameterReader:

    def __init__(self, filename, config):

        self.filename = Path(filename)
        self.config = config

    def wanted_parameters(self):
        """
        Return the parameter patterns requested by the YAML configuration.
        """

        return set(self.config.get("parameters", []))

    def normalize_parameter(self, name, value):
        """
        Normalise firmware-specific parameter names and units so the rest
        of the framework sees a consistent parameter interface.
        """

        #
        # ArduPlane 4.6.x
        #

        if name == "RNGFND1_MAX_CM":
            name = "RNGFND1_MAX"
            value = value / 100.0

        return name, value

    @staticmethod
    def matches(name, patterns):
        """
        Return True if the parameter name matches any configured pattern.
        Supports both exact names and shell-style wildcards.
        """

        for pattern in patterns:
            if fnmatch(name, pattern):
                return True

        return False

    def read(self):
        """
        Read a MAVLink parameter export (.param/.params) and return only
        the parameters requested by the configuration.

        Firmware-specific parameter names and units are normalised before
        filtering so detectors always receive a consistent API.
        """

        patterns = self.wanted_parameters()

        params = {}

        with self.filename.open("r") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                parts = line.split()

                #
                # Expected format:
                # VehicleID ComponentID Name Value Type
                #

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

                name, value = self.normalize_parameter(name, value)

                #
                # Configuration filtering
                #

                if self.matches(name, patterns):
                    params[name] = value

        return params