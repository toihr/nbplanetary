# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/00_config.ipynb (unless otherwise specified).

__all__ = ['Config', 'config', 'config']

# Cell
import os
import shutil
from functools import reduce
from importlib.resources import path as resource_path
from typing import Union

import tomlkit as toml
from fastcore.utils import AttrDict, Path

# Cell
class Config:
    """Manage config stuff.

    Attributes
    -------
    path: pathlib.Path

    The key, value pairs found in the config file become attributes of the
    class instance after initialization.
    At minimum, there should be the `storage_root` attribute for storing data
    for this package.
    """

    # This part enables a config path location override using env PYCISS_CONFIG
    fname = "planetarypy_config.toml"
    # separating fname from fpath so that resource_path below is correct.
    path = Path(os.getenv("PLANETARYPY_CONFIG", Path.home() / f".{fname}"))

    def __init__(
        self,
        config_path:str=None  # str or pathlib.Path
    ):
        "Switch to other config file location with `config_path`."
        if config_path is not None:
            self.path = Path(config_path)
        if not self.path.exists():
            with resource_path("planetarypy.data", self.fname) as p:
                shutil.copy(p, self.path)
        self.read_config()
        self.update_missions()

    def read_config(self):
        """Read the configfile and store config dict.

        `storage_root` will be stored as attribute.
        """
        self.tomldoc = toml.loads(self.path.read_text())
        if not self.tomldoc["storage_root"]:
            self.ask_storage_root()
        else:
            self.storage_root = Path(self.tomldoc["storage_root"])

    @property
    def d(self):
        "get the Python dic from"
        return self.tomldoc

    def get_value(
        self,
        key:str  # A nested key in dotted format, e.g. cassini.uvis.indexes
    ):
        """Get sub-dictionary by nested key."""
        if not key.startswith('missions'):
            key = 'missions.' + key
        try:
            return reduce(lambda c, k: c[k], key.split("."), self.d)
        except toml.exceptions.NonExistentKey:
            return None

    def set_value(
        self,
        nested_key:str,  # A nested key in dotted format, e.g. cassini.uvis.ring_summary
        value:Union[float, str],  # Value for the given key to be stored
        save:bool=True  # Switch to control writing out to disk
    ):
        "Set value in sub-dic using dotted key."
        dic = self.tomldoc
        keys = nested_key.split(".")
        for key in keys[:-1]:
            dic = dic[key]
        dic[keys[-1]] = value
        if save:
            self.save()

    def save(self):
        "Write the TOML doc to file."
        self.path.write_text(toml.dumps(self.tomldoc))

    def ask_storage_root(self):
        """Use input() to ask user for the storage_root path.

        The path will be stored in the TOML-dict and saved into existing config file
        at `Class.path`, either default or as given during init.
        `storage_root` attribute is set as well.
        """
        path = input(
            "Provide the root storage path where all downloaded and produced data will be stored:"
        )
        self.tomldoc["storage_root"] = path
        self.storage_root = Path(path)
        self.save()

    @property
    def missions(self):
        return list(self.d["missions"].keys())

    def list_instruments(self, mission):
        if not mission.startswith("missions"):
            mission = "missions." + mission
        instruments = self.get_value(mission)
        return list(instruments.keys())

    def list_indexes(self, instrument):
        "instrument key needs to be <mission>.<instrument>"
        if not instrument.startswith("missions"):
            instrument = "missions." + instrument
        indexes = self.get_value(instrument + ".indexes")
        return list(indexes)

    def _copy_clean_to_resource(self):
        "Copy a clean config file without timestamps into resource path for repo commit."
        dic = self.tomldoc.copy()
        missions = dic["missions"]
        for mission in missions.keys():
            mdict = missions[mission]
            for instr in mdict.keys():
                instrdict = mdict[instr]
                for index in instrdict["indexes"]:
                    instrdict["indexes"][index]["timestamp"] = ""
        with resource_path("planetarypy.data", self.fname) as p:
            Path(p).write_text(toml.dumps(dic))

    def update_missions(self):
        "Check if a new version with more URLs exist at resource path."
        with resource_path("planetarypy.data", self.fname) as p:
            new = toml.loads(Path(p).read_text())["missions"]
        old = self.tomldoc["missions"]
        for mission in new:
            missiondata = new[mission]
            if mission not in old:
                old[mission] = missiondata
                continue
            for instr in missiondata:
                instrdata = missiondata[instr]
                if instr not in old[mission]:
                    old[mission][instr] = instrdata
                    continue
                for index in instrdata["indexes"]:
                    indexdata = instrdata["indexes"][index]
                    if index not in old[mission][instr]["indexes"]:
                        old[mission][instr]["indexes"][index] = indexdata
                        continue
                    oldindexdata = old[mission][instr]["indexes"][index]
                    if indexdata["url"] != oldindexdata["url"]:
                        oldindexdata["url"] = indexdata["url"]
        self.save()

    def populate_timestamps(self):
        pass

    def __repr__(self):
        return AttrDict(self.d).__repr__()

# Cell
config = Config()

# Cell
config = Config()