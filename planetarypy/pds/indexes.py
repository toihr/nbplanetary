# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/api/02a_pds.indexes.ipynb.

# %% auto 0
__all__ = ['logger', 'storage_root', 'dynamic_urls', 'Index']

# %% ../../notebooks/api/02a_pds.indexes.ipynb 3
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import URLError

import tomlkit as toml
from dateutil import parser

import pandas as pd
from .. import utils
from ..config import config
from .ctx_index import CTXIndex
from .lroc_index import LROCIndex
from .utils import IndexLabel, fix_hirise_edrcumindex

logger = logging.getLogger(__name__)

storage_root = Path(config.storage_root)

# %% ../../notebooks/api/02a_pds.indexes.ipynb 4
dynamic_urls = {"mro.ctx": CTXIndex, "lro.lroc": LROCIndex}

# %% ../../notebooks/api/02a_pds.indexes.ipynb 6
class Index:
    """Index manager class.

    This class manages one index, identified by a dotted key, e.g. `cassini.iss.ring_summary`
    """

    def __init__(
        self,
        key: str,  # Nested (dotted) key, e.g. cassini.iss.ring_summary
        url: str = None,  # URL to index. If not given, will be read from config object.
    ):
        self.key = self.parse_key(key)
        self.set_url(url)
        try:
            self.timestamp = parser.parse(config.get_value(self.key)["timestamp"])
        except toml.exceptions.NonExistentKey:
            if self.local_label_path.exists():
                self.timestamp = datetime.fromtimestamp(
                    self.local_label_path.stat().st_mtime
                )
                self.update_timestamp()
            else:
                self.timestamp = None
        self.new_timestamp = None  # filled by needs_download()

    def parse_key(
        self,
        key: str,  # dotted key
    ):
        """Take care of different ways how the key could be structured.

        This involves adding the sub-key `indexes` for the config file structure,
        which is something the user of this class should not need to know.
        """
        tmp = key if key.startswith("missions") else "missions." + key
        subs = tmp.split(".")
        if subs[3] != "indexes":
            subs.insert(3, "indexes")
        return ".".join(subs)

    def set_url(self, url):  # URL to index.
        "Set URL from having it dynamically determined (for non-static index URLs)."
        self.url = config.get_value(self.key)["url"] if url is None else url
        if not self.url:  # empty ''
            self.url = dynamic_urls[self.instrument_key]().latest_index_label_url

    @property
    def isotimestamp(self):
        return self.timestamp.isoformat()

    @property
    def needs_download(self)->bool:  # Boolean indicating if download is required
        """Property indicating if the index needs to be downloaded.

        Need is True when
        (1) no local timestamp was stored or
        (2) when the remote timestamp is newer.
        """
        try:
            self.remote_timestamp = utils.get_remote_timestamp(self.url)
        except URLError:
            return None
        if self.timestamp:
            if self.remote_timestamp > self.timestamp:
                return True
            else:
                return False
        else:
            # also return True when the timestamp is not valid
            return True

    @property
    def key_tokens(self):
        return self.key.split(".")

    @property
    def mission(self):
        return self.key_tokens[1]

    @property
    def mission_key(self):
        return ".".join(self.key_tokens[1:2])

    @property
    def instrument(self):
        return self.key_tokens[2]

    @property
    def instrument_key(self):
        return ".".join(self.key_tokens[1:3])

    @property
    def index_name(self):
        "str: Examples: EDR, RDR, moon_summary"
        return self.key_tokens[3]

    @property
    def label_filename(self):
        return Path(self.url.split("/")[-1])

    @property
    def isupper(self):
        return self.label_filename.suffix.isupper()

    @property
    def table_filename(self):
        new_suffix = ".TAB" if self.isupper else ".tab"
        return self.label_filename.with_suffix(new_suffix)

    @property
    def label_path(self):
        return Path(urlsplit(self.url).path)

    @property
    def table_path(self):
        return self.label_path.with_name(self.table_filename.name)

    @property
    def table_url(self):
        tokens = urlsplit(self.url)
        return urlunsplit(
            tokens._replace(
                path=str(self.label_path.with_name(self.table_filename.name))
            )
        )

    @property
    def local_dir(self):
        p = storage_root / str(self.key).replace(".", "/")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def local_table_path(self):
        return self.local_dir / self.table_filename

    @property
    def local_label_path(self):
        return self.local_dir / self.label_filename

    @property
    def local_hdf_path(self):
        return self.local_table_path.with_suffix(".hdf")

    @property
    def local_parq_path(self):
        return self.local_table_path.with_suffix(".parq")

    @property
    def df(self):
        return pd.read_hdf(self.local_hdf_path)

    @property
    def parquet(self):
        return pd.read_parquet(self.local_parq_path)

    def download(
        self,
        convert_to_hdf: bool = False,  # Switch to enable conversion to HDF
        convert_to_parquet: bool = True,  # Switch to enable conversion to parquet
        force_update: bool = False,  # Switch to enable a fresh download and conversion
    ):
        """Wrapping URLs for downloading PDS indices and their label files."""
        # check timestamp
        ret = self.needs_download
        if ret is None:
            print("Could not check for any index updates, maybe server is offline?")
            return
        if not ret and not force_update:
            print("Stored index is up-to-date.")
            return
        label_url = self.url
        logger.info("Downloading %s." % label_url)
        utils.url_retrieve(label_url, self.local_label_path)
        logger.info("Downloading %s.", self.table_url)
        utils.url_retrieve(self.table_url, self.local_table_path)
        print(f"Downloaded {self.local_label_path} and {self.local_table_path}")
        if self.key == 'missions.mro.hirise.indexes.edr':  # HiRISE EDR index is broken on the PDS. Team knows.
            print("Fixing broken EDR index...")
            fix_hirise_edrcumindex(
                self.local_table_path, 
                self.local_table_path.with_name("temp.tab")
            )
            self.local_table_path.with_name("temp.tab").rename(self.local_table_path)
        self.timestamp = self.remote_timestamp
        self.update_timestamp()
        
        if convert_to_hdf:
            try:
                self.convert_to_hdf()
            except:  # any conversion error simpy leads to HDF marked as missing
                self.set_hdf_available(False)
            else:
                self.set_hdf_available(True)
                print(f"Converted to pandas HDF:\n{self.local_hdf_path}")
        elif convert_to_parquet:
            try:
                self.convert_to_parquet()
            except Exception as e: 
                print("Problems converting to parquet.")
                raise e
                
    def set_hdf_available(self, status):
        config.set_value(f"{self.key}.hdf_available", status)

    def set_parquet_available(self, status):
        config.set_value(f"{self.key}.parquet_available", status)

    def update_timestamp(self):
        # Note: the config object writes itself out after setting any value
        config.set_value(f"{self.key}.timestamp", self.isotimestamp)

    @property
    def label(self):
        return IndexLabel(self.local_label_path)

    def read_index_data(self):
        df = self.label.read_index_data()
        return df

    def convert_to_hdf(self):
        df = self.read_index_data()
        df.to_hdf(self.local_hdf_path, "df")

    def convert_to_parquet(self):
        df = self.read_index_data()
        df = df.convert_dtypes()
        df.to_parquet(self.local_parq_path)

    def __str__(self):
        s = f"Key: {self.key}\n"
        s += f"URL: {self.url}\n"
        s += f"Timestamp: {self.timestamp}\n"
        return s

    def __repr__(self):
        return self.__str__()
