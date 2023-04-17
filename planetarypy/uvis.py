# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/api/05_cassini_uvis.ipynb.

# %% auto 0
__all__ = ['storage_root', 'DataManager', 'get_data_path', 'get_label_path', 'get_user_guide']

# %% ../notebooks/api/05_cassini_uvis.ipynb 3
import tomlkit
from yarl import URL

from .config import config
from .pds.opusapi import OPUS
from .utils import url_retrieve

# %% ../notebooks/api/05_cassini_uvis.ipynb 4
storage_root = config.storage_root / "missions/cassini/uvis"
storage_root

# %% ../notebooks/api/05_cassini_uvis.ipynb 5
class DataManager:

    def __init__(
        self,
        pid: str,  # Product ID. If longer than PDS_ID, will be cut in attribute `pds_id`
        skip_download: bool = False  # skip trying to download
    ):
        self.pid = pid
        self.dict = None
        if not self.raw_data_path.exists() and not skip_download:
            self.download()

    def query(self, pds_id=None):
        pds_id = pds_id if pds_id is not None else self.pds_id
        opus = OPUS(silent=True)
        try:
            self.query_result = opus.query_image_id(pds_id)[0]
        except IndexError:
            raise FileNotFoundError("Project ID not found on PDS server.")
        self.opus_id = self.query_result[0]
        self.dict = self.query_result[1]

    @property
    def pds_id(self):
        return self.pid[:17]

    @property
    def folder(self):
        #         return storage_root / "/".join(self.raw_data_url.parts[4:7])
        return storage_root / self.pds_id

    @property
    def raw_data_url(self):
        if not self.dict:
            self.query()
        return URL(self.dict["couvis_raw"][0])

    @property
    def raw_label_url(self):
        if not self.dict:
            self.query()
        return URL(self.dict["couvis_raw"][1])

    @property
    def raw_data_path(self):
        return self.folder / (self.pds_id + ".DAT")

    @property
    def raw_label_path(self):
        return self.raw_data_path.with_suffix(".LBL")

    @property
    def calib_corr_path(self):
        return self.raw_data_path.with_name(self.raw_data_path.stem + "_CAL_3.DAT")

    @property
    def calib_label_path(self):
        return self.calib_corr_path.with_suffix(".LBL")

    @property
    def original_pid_file(self):
        return self.folder / "original_pid.txt"

    @property
    def results_file(self):
        return self.folder / "urls.toml"

    def download(self, overwrite=False):
        if self.raw_data_path.exists() and not overwrite:
            print("Local files exists. Use `overwrite=True` to download fresh.")
            return
        self.query()
        self.original_pid_file.mk_write(self.pid)
        self.results_file.mk_write(tomlkit.dumps(self.dict))
        self.raw_data_path.parent.mkdir(parents=True, exist_ok=True)
        for key in ["couvis_raw", "couvis_calib_corr"]:
            for url in self.dict[key]:
                url_retrieve(url, self.folder / URL(url).name)

    def __repr__(self):
        s = f"Product ID:\n{self.id}\n\n"
        for k, v in self.query_result[1].items():
            s += f"Key: {k},\nValue(s):\n{v}\n\n"
        return s

# %% ../notebooks/api/05_cassini_uvis.ipynb 19
def get_data_path(pid, skip_download=False):
    dm = DataManager(pid, skip_download=skip_download)
    return dm.raw_data_path if dm.raw_data_path.exists() else None


def get_label_path(pid):
    dm = DataManager(pid)
    return dm.raw_label_path

# %% ../notebooks/api/05_cassini_uvis.ipynb 22
def get_user_guide():
    url = URL("https://pds-rings.seti.org/cassini/uvis/1-UVIS_Users_Guide_-2018-Jan%2015-For%20PDS-REV-2018-07-06.pdf")
    local_path = storage_root / "uvis_user_guide.pdf"
    if not local_path.exists():
        url_retrieve(url, storage_root / "uvis_user_guide.pdf")
    return local_path
