# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/07_diviner.ipynb (unless otherwise specified).

__all__ = ['hostname', 'get_data_path']

# Cell

from pathlib import Path
import socket
from yarl import URL

import hvplot.xarray  # noqa
from .config import config
from .utils import url_retrieve

# Cell
hostname = socket.gethostname()
if hostname.startswith("luna") and hostname.endswith("diviner.ucla.edu"):
    storage_root = Path("/q/marks/feidata/DIV:opsL1A/data")
else:
    storage_root = config.storage_root / "missions/lro/diviner"

# Cell
def get_data_path(tstr):
    dm = DataManager(tstr)
    if not dm.local_path.exists():
        dm.download()
    return dm.local_path