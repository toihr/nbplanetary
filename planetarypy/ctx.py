# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/03_ctx.ipynb.

# %% auto 0
__all__ = ['baseurl', 'storage_root', 'edrindex', 'catch_isis_error', 'CTXEDR', 'CTX', 'ctx_calib', 'CTXEDRCollection']

# %% ../notebooks/03_ctx.ipynb 3
import warnings
from pathlib import Path

import hvplot.xarray  # noqa
import rasterio
import rioxarray as rxr
from dask import compute, delayed
from .config import config
from .pds.apps import get_index
from .utils import file_variations, url_retrieve
from tqdm.auto import tqdm
from yarl import URL
from fastcore.script import call_parse
from fastcore.basics import store_attr

try:
    from kalasiris.pysis import (
        ProcessError,
        ctxcal,
        ctxevenodd,
        getkey,
        mroctx2isis,
        spiceinit,
    )
except KeyError:
    warnings.warn("kalasiris has a problem initializing ISIS")

# %% ../notebooks/03_ctx.ipynb 4
warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)
baseurl = URL(
    "https://pds-imaging.jpl.nasa.gov/data/mro/mars_reconnaissance_orbiter/ctx/"
)

storage_root = config.storage_root / "missions/mro/ctx"
edrindex = get_index("mro.ctx", "edr")

# %% ../notebooks/03_ctx.ipynb 6
def catch_isis_error(func):
    def inner(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ProcessError as err:
            print("Had ISIS error:")
            print(" ".join(err.cmd))
            print(err.stdout)
            print(err.stderr)

    return inner

# %% ../notebooks/03_ctx.ipynb 7
class CTXEDR:
    """Manage access to EDR data"""
    storage = storage_root / "edr"
    
    def __init__(
        self,
        id_:str,  # CTX product id (pid)
        source_dir:str='',  # alternative root folder for EDR data
        with_volume:bool=True,  # does the storage path include the volume folder
        with_id_dir:bool=False,  # does the storage path include an extra pid folder
    ):
        store_attr(but='source_dir')
        self.storage = Path(source_dir) if source_dir else self.storage
        
    @property
    def pid(self):
        return self.id_
    
    @pid.setter
    def pid(self, value):
        self.id_ = value
        
    @property
    def meta(self):
        "get the metadata from the index table"
        s = edrindex.query("PRODUCT_ID == @self.pid").squeeze()
        s.index = s.index.str.lower()
        return s

    @property
    def volume(self):
        "get the PDS volume number for the current product id"
        return self.meta.volume_id.lower()
    
    @property
    def source_folder(self):
        if self.with_volume:
            base = self.storage / self.volume
        else:
            base = self.storage
        if not self.with_id_dir:
            return base
        else: 
            return base / self.pid

    @property
    def source_path(self):
        return self.source_folder / f"{self.pid}.IMG"

    @property
    def url(self):
        "Calculate URL from input dataframe row."
        url = baseurl / self.meta.volume_id.lower() / "data" / (self.pid + ".IMG")
        return url

    def download(self, overwrite=False):
        if self.source_path.exists() and not overwrite:
            print("File exists. Use `overwrite=True` to download fresh.")
            return
        self.source_folder.mkdir(parents=True, exist_ok=True)
        url_retrieve(self.url, self.source_path)


# %% ../notebooks/03_ctx.ipynb 12
class CTX:
    """Class to manage dealing with CTX data.
    
    HAS a CTXEDR attribute as defined above.
    """
    proc_storage = storage_root / "edr"

    def __init__(
        self, 
        id_:str,  # CTX product id
        source_dir:str='',  # where the raw EDR data is stored, if not coming from plpy
        proc_storage:str='',  # where to store processed, if not plpy
        with_volume:bool=False,  # store with extra volume subfolder?
        with_id_dir:bool=True  # store with extra product_id subfolder?
    ):
        store_attr(but="source_dir,proc_storage")
        self.proc_storage = Path(proc_storage) if proc_storage else self.proc_storage
        self.edr = CTXEDR(id_, source_dir, with_volume, with_id_dir)
        
        (self.cub_name, self.cal_name, self.destripe_name) = file_variations(
            self.edr.source_path.name, [".cub", ".cal.cub", ".dst.cal.cub"]
        )
        self.is_read = False
        self.is_calib_read = False

    @property
    def pid(self):
        return self.edr.pid

    @property
    def proc_folder(self):
        "the folder for all processed data. could be same as source_dir"
        return self.proc_storage / self.edr.source_folder.relative_to(self.edr.source_folder)

    @property
    def cub_path(self):
        return self.proc_folder / self.cub_name
    
    @property
    def cal_path(self):
        return self.proc_folder / self.cal_name
    
    @property
    def destripe_path(self):
        return self.proc_folder / self.destripe_name


    @catch_isis_error
    def isis_import(self):
        mroctx2isis(from_=self.edr.source_path, to=self.cub_path)

    @catch_isis_error
    def spice_init(self):
        spiceinit(from_=self.cub_path, web="yes")

    @catch_isis_error
    def calibrate(self):
        ctxcal(from_=self.cub_path, to=self.cal_path)
        self.is_calib_read = False

    @catch_isis_error
    def destripe(self):
        if self.do_destripe():
            ctxevenodd(from_=self.cal_path, to=self.destripe_path)
            self.destripe_path.rename(self.cal_path)

    @catch_isis_error
    def do_destripe(self):
        value = int(
            getkey(
                from_=self.cal_path,
                objname="isiscube",
                grpname="instrument",
                keyword="SpatialSumming",
            )
        )
        return False if value == 2 else True

    def calib_pipeline(self, overwrite=False):
        if self.cal_path.exists() and not overwrite:
            return
        pbar = tqdm("isis_import spice_init calibrate destripe".split())
        for name in pbar:
            pbar.set_description(name)
            getattr(self, name)()
        pbar.set_description("Done.")

    def read_edr(self):
        "`da` stands for dataarray, standard abbr. within xarray."
        if not self.edr.source_path.exists():
            raise FileNotFoundError("EDR not downloaded yet.")
        if not self.is_read:
            self.edr_da = rxr.open_rasterio(self.edr.source_path)
            self.is_read = True
        return self.edr_da

    def read_calibrated(self):
        "`da` stands for dataarray, standard abbr. within xarray."
        if not self.is_calib_read:
            self.cal_da = rxr.open_rasterio(self.cal_path)
            self.is_calibd_read = True
        return self.cal_da

    def plot_da(self, data=None):
        data = self.edr_da if data is None else data
        return data.isel(band=0, drop=True).hvplot(
            x="y", y="x", rasterize=True, cmap="gray", data_aspect=1
        )

    def plot_calibrated(self):
        return self.plot_da(self.read_calibrated())

    def __str__(self):
        s = f"PRODUCT_ID: {self.edr.pid}\n"
        s += f"URL: {self.edr.url}\n"
        s += f"Local: {self.edr.source_path}\n"
        try:
            s += f"Shape: {self.read_edr().shape}"
        except FileNotFoundError:
            s += f"Not downloaded yet."
        return s

    def __repr__(self):
        return self.__str__()

# %% ../notebooks/03_ctx.ipynb 35
@call_parse
def ctx_calib(
    id_:str  # CTX product_id
):
    ctx = CTX(id_)
    print(ctx.edr.source_path)

# %% ../notebooks/03_ctx.ipynb 37
class CTXEDRCollection:
    """Class to deal with a set of CTX products."""

    def __init__(self, product_ids):
        self.product_ids = product_ids

    def get_urls(self):
        """Get URLs for list of product_ids.

        Returns
        -------
        List[yarl.URL]
            List of URL objects with the respective PDS URL for download.
        """
        urls = []
        for p_id in self.product_ids:
            ctx = CTXEDR(p_id)
            urls.append(ctx.url)
        self.urls = urls
        return urls

    def download_collection(self):
        lazys = []
        for p_id in self.product_ids:
            ctx = CTXEDR(p_id)
            lazys.append(delayed(ctx.download)())
        print("Launching parallel download...")
        compute(*lazys)
        print("Done.")

    def calibrate_collection(self):
        lazys = []
        for p_id in self.product_ids:
            ctx = CTXEDR(p_id)
            lazys.append(delayed(ctx.calib_pipeline)())
        print("Launching parallel calibration...")
        compute(*lazys)
        print("Done.")

    def calib_exist_check(self):
        return [(p_id, CTXEDR(p_id).cal_name.exists()) for p_id in self.product_ids]
