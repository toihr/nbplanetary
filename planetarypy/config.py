# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/00_config.ipynb (unless otherwise specified).

__all__ = ['Config']

# Cell
import os
import shutil
from functools import reduce
from importlib.resources import path as resource_path
from pathlib import Path

import strictyaml as yaml

# Cell
class Config:
    """Manage config stuff.

    Attributes
    -------
    path: pathlib.Path

    The key, value pairs found in the config file become attributes of the
    class instance after initialization.
    At minimum, there should be the `archive_path` attribute for storing data
    for this package.
    """

    # This enables a config path location override using env PYCISS_CONFIG
    fname = "planetarypy_config.yaml"
    path = Path(os.getenv("PLANETARYPY_CONFIG", Path.home() / f".{fname}"))

    def __init__(self, other_config=None):
        "Switch to other config file location with `other_config`."
        if other_config is not None:
            self.path = Path(other_config)
        if not self.path.exists():
            with resource_path("planetarypy.data", self.fname) as p:
                shutil.copy(p, self.path)
        self.read_config()

    def read_config(self):
        """Read the configfile and store config dict.

        If found, load config via `yaml` and store YAML dict as `d`.
        `storage_root` will be stored as attribute.
        """
        self.d = yaml.load(self.path.read_text())
        if not self.d["storage_root"].data:
            self.ask_storage_root()
        else:
            self.storage_root = Path(self.d["storage_root"].data)

    def get_config_value(self, key):
        """Get sub-dictionary by nested key.

        Parameters
        ----------
        nested_key: str
            A nested key in dotted format, e.g. cassini.uvis.indexes
        """
        return reduce(lambda c, k: c[k], key.split("."), self.d)

    def set_config_value(self, nested_key, value):
        """Set sub-dic using dotted key.

        Parameters
        ----------
        key: str
            A nested key in dotted format, e.g. cassini.uvis.ring_summary
        value: convertable to string
            Value for the given key to be stored.
        """
        dic = self.d
        keys = nested_key.split(".")
        for key in keys[:-1]:
            dic = dic[key]
        dic[keys[-1]] = value
        self.save()

    def save(self):
        "Write the YAML dict to file."
        with self.path.open("w") as f:
            f.write(self.d.as_yaml())

    def ask_storage_root(self):
        """Use input() to ask user for the storage_root path.

        The path will be stored in the YAML-dict and saved into existing config file
        at `Class.path`, either default or as given during init.
        `storage_root` attribute is set as well.
        """
        path = input(
            "Provide the root storage path where all downloaded and produced data will be stored:"
        )
        self.d["storage_root"] = path
        self.storage_root = Path(path)
        self.save()