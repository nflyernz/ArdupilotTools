from pathlib import Path
import yaml


class Config:

    def __init__(self, filename):

        with open(filename, "r") as f:
            self.data = yaml.safe_load(f)

    def get(self, key, default=None):
        """
        Retrieve a configuration value.

        Supports dotted paths, e.g.

            config.get("barometer.smoothing_samples")
            config.get("rangefinder.continuous_seconds")
        """

        value = self.data

        for part in key.split("."):

            if not isinstance(value, dict):
                return default

            if part not in value:
                return default

            value = value[part]

        return value
