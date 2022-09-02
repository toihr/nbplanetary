# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/04_hirise.ipynb.

# %% auto 0
__all__ = ['logger', 'storage_root', 'baseurl', 'rdrindex', 'OBSID', 'ProductPathfinder', 'COLOR_PRODUCT', 'RGB_NOMAP',
           'RGB_NOMAPCollection', 'SOURCE_PRODUCT', 'RED_PRODUCT', 'IR_PRODUCT', 'BG_PRODUCT']

# %% ../notebooks/04_hirise.ipynb 3
import logging
import warnings
import webbrowser

import rasterio
import rioxarray as rxr
from dask import compute, delayed
from fastcore.utils import Path
from yarl import URL

import hvplot.xarray  # noqa
from .config import config
from .pds.apps import get_index
from .utils import check_url_exists, url_retrieve

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# %% ../notebooks/04_hirise.ipynb 4
logger = logging.getLogger(__name__)

# %% ../notebooks/04_hirise.ipynb 5
storage_root = config.storage_root / "missions/mro/hirise"
baseurl = URL("https://hirise-pds.lpl.arizona.edu/PDS")
rdrindex = get_index("mro.hirise", "rdr")

# %% ../notebooks/04_hirise.ipynb 6
class OBSID:
    """Manage HiRISE observation ids.

    For example PSP_003092_0985.
    `phase` is set to PSP for orbits < 11000, no setting required.
    """

    def __init__(
        self,
        obsid: str,  # e.g. PSP_003092_0985
    ):
        phase, orbit, targetcode = obsid.split("_")
        self._orbit = int(orbit)
        self._targetcode = targetcode

    @property
    def orbit(self):
        return str(self._orbit).zfill(6)

    @orbit.setter
    def orbit(self, value: int):  # e.g. 11000, < 1_000_000
        if value > 999999:
            raise ValueError("Orbit cannot be larger than 999999")
        elif len(value) != 6:
            raise ValueError("Orbit string must be 6 digits.")
        self._orbit = value

    @property
    def targetcode(self):
        return self._targetcode

    @targetcode.setter
    def targetcode(
        self,
        value: str,  # e.g. "0985", must be 4 digits
    ):
        if len(str(value)) != 4:
            raise ValueError("Targetcode must be exactly 4 characters.")
        self._targetcode = value

    @property
    def phase(self):
        return "PSP" if int(self.orbit) < 11000 else "ESP"

    @property
    def id(self):
        return f"{self.phase}_{self.orbit}_{self.targetcode}"

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.id

    @property
    def upper_orbit_folder(self):
        """
        get the upper folder name wa
        rdrhere the given orbit folder is residing on the
        hisync server, e.g. 'ORB_011900_011999'
        """
        lower = int(self.orbit) // 100 * 100
        lowerstr = str(lower).zfill(6)
        upperstr = str(lower + 99).zfill(6)
        return f"ORB_{lowerstr}_{upperstr}"

    @property
    def storage_path_stem(self):
        return f"{self.phase}/{self.upper_orbit_folder}/{self.id}"

# %% ../notebooks/04_hirise.ipynb 13
class ProductPathfinder:
    """Determine paths and URLs for HiRISE RDR products (also EXTRAS.)

    We use the PDS definition of PRODUCT_ID here, e.g. PSP_003092_0985_RED.

    Attributes `jp2_path` and `label_path` get you the official RDR mosaic product,
    with `kind` steering if you get the COLOR or the RED product.
    All other properties go to the RDR/EXTRAS folder.
    The "PDS" part of the path is handled in the OBSID class.
    """

    kinds = ["RED", "BG", "IR", "COLOR", "IRB", "MIRB", "MRGB", "RGB", "RGB.NOMAP"]

    @classmethod
    def from_path(cls, path):
        path = Path(path)
        return cls(path.stem)

    def __init__(
        self,
        initstr: str,  # PRODUCT_ID string, e.g. PSP_003092_0985_RED
        check_url: bool = True,  # for performance, the user might not want the url check
    ):
        tokens = initstr.split("_")
        self._obsid = OBSID("_".join(tokens[:3]))
        try:
            self.kind = tokens[3]
        except IndexError:
            self._kind = None
        self.check_url = check_url

    @property
    def obsid(self):
        return self._obsid

    @obsid.setter
    def obsid(self, value: str):  # e.g. "PSP_003092_0985"
        self._obsid = OBSID(value)

    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(
        self,
        value: str,  # one of "RED", "BG", "IR", "COLOR", "IRB", "MIRB", "MRGB", "RGB", "RGB.NOMAP"
    ):
        if value not in self.kinds:
            raise ValueError(f"kind must be in {self.kinds}")
        self._kind = value

    @property
    def product_id(self):
        return f"{self.obsid}_{self.kind}"

    def __str__(self) -> str:  # PRODUCT_ID string, e.g. PSP_003092_0985_RED
        return self.product_id

    def __repr__(self):
        return self.__str__()

    @property
    def storage_stem(
        self,
    ) -> str:  # e.g. 'PSP/ORB_003000_003099/PSP_003092_0985/PSP_003092_0985_RED'
        return f"{self.obsid.storage_path_stem}/{self.product_id}"

    @property
    def label_fname(self) -> str:  # e.g. 'PSP_003092_0985_RED.LBL'
        return f"{self.product_id}.LBL"

    @property
    def label_path(self):
        return Path("RDR") / (self.storage_stem + ".LBL")

    @property
    def local_label_path(self):
        path = self.label_path
        return storage_root / (f"{path.parent.name}/{path.name}")

    def download_label(self, overwrite=False):
        """Download the label file."""
        self.local_label_path.parent.mkdir(exist_ok=True, parents=True)
        if self.local_label_path.exists and not overwrite:
            return
        else:
            url_retrieve(self.label_url, self.local_label_path)

    def _make_url(self, obj):
        path = getattr(self, f"{obj}_path")
        url = baseurl / str(path)
        if self.check_url:
            if not check_url_exists(url):
                warnings.warn(f"{url} does not exist on the server.")
        return url

    def __getattr__(self, item):
        tokens = item.split("_")
        try:
            if tokens[-1] == "url":
                return self._make_url("_".join(tokens[:-1]))
        except IndexError:
            raise AttributeError(f"No attribute named '{item}' found.")

    @property
    def jp2_fname(self):
        return self.product_id + ".JP2"

    @property
    def jp2_path(self):
        prefix = "RDR/"
        postfix = ""
        if self.kind not in ["RED", "COLOR"]:
            prefix += "EXTRAS/"
        if self.kind in ["IRB"]:
            postfix = ".NOMAP"
        return prefix + self.storage_stem + postfix + ".JP2"

    @property
    def nomap_jp2_path(self):
        if self.kind in ["RED", "IRB", "RGB"]:
            return f"EXTRAS/RDR/{self.storage_stem}.NOMAP.JP2"
        else:
            raise ValueError(f"No NOMAP exists for {self.kind}.")

    @property
    def quicklook_path(self):
        if self.kind in ["COLOR", "RED"]:
            return Path("EXTRAS/RDR/") / (self.storage_stem + ".QLOOK.JP2")
        else:
            raise ValueError(f"No quicklook exists for {self.kind} products.")

    @property
    def abrowse_path(self):
        if self.kind in ["COLOR", "MIRB", "MRGB", "RED"]:
            return Path("EXTRAS/RDR/") / (self.storage_stem + ".abrowse.jpg")
        else:
            raise ValueError(f"No abrowse exists for {self.kind}")

    @property
    def browse_path(self):
        inset = ""
        if self.kind in ["IRB", "RGB"]:
            inset = ".NOMAP"
        if self.kind not in ["COLOR", "MIRB", "MRGB", "RED", "IRB", "RGB"]:
            raise ValueError(f"No browse exists for {self.kind}")
        else:
            return Path("EXTRAS/RDR/") / (self.storage_stem + inset + ".browse.jpg")

    @property
    def thumbnail_path(self):
        if self.kind in ["BG", "IR"]:
            raise ValueError(f"No thumbnail exists for {self.kind}")
        inset = ""
        if self.kind in ["IRB", "RGB"]:
            inset = ".NOMAP"
        return Path("EXTRAS/RDR/") / (self.storage_stem + inset + ".thumb.jpg")

    @property
    def nomap_thumbnail_path(self):
        if self.kind in ["RED", "IRB", "RGB"]:
            return Path("EXTRAS/RDR") / (self.storage_stem + ".NOMAP.thumb.jpg")
        else:
            raise ValueError(f"No NOMAP thumbnail exists for {self.kind} images.")

    @property
    def nomap_browse_path(self):
        if self.kind in ["RED", "IRB", "RGB"]:
            return Path("EXTRAS/RDR") / (self.storage_stem + ".NOMAP.browse.jpg")
        else:
            raise ValueError(f"No NOMAP browse exists for {self.kind} images.")

    @property
    def edr_storage_stem(self):
        return Path("EDR") / self.storage_stem

    @property
    def homepage(self) -> str:  # URL to the product's homepage
        return f"https://uahirise.org/{self.obsid}"

    def go_to_homepage(self):
        webbrowser.open(self.homepage)

# %% ../notebooks/04_hirise.ipynb 33
class COLOR_PRODUCT:
    def __init__(self, obsid):
        self.obsid = obsid
        # this should be reset by the subclass
        self.pathfinder = ProductPathfinder(self.obsid + "_COLOR")

    @property
    def product_id(self):
        return self.pathfinder.product_id

    @property
    def meta(self):
        color_id = self.obsid + "_COLOR"
        s = rdrindex.query("PRODUCT_ID == @color_id").squeeze()
        s.index = s.index.str.lower()
        return s

    @property
    def url(self):
        # set `name` in the subclass
        return URL(getattr(self.pathfinder, self.name + "_url"))

    @property
    def remote_path(self):
        # set `name` in subclass
        return Path(getattr(self.pathfinder, self.name + "_path"))

    @property
    def local_path(self):
        path = self.remote_path
        return storage_root / (f"{path.parent.name}/{path.name}")

    def download(self, overwrite=False):
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        if self.local_path.exists() and not overwrite:
            print("File exists. Use `overwrite=True` to download fresh.")
            return
        url_retrieve(self.url, self.local_path)

    def read(self):
        self.da = rxr.open_rasterio(self.local_path, chunks=(1, 2024, 2024))
        return self.da

    def show(self, **kwargs):
        self.read()
        return self.plot_da(**kwargs)

    def plot_da(self, xslice=None, yslice=None):
        if xslice is not None or yslice is not None:
            data = self.da.isel(x=xslice, y=yslice)
        else:
            data = self.da

        return data.hvplot.image(
            x="x",
            y="y",
            rasterize=True,
            widget_location="top_left",
            cmap="gray",
            frame_height=800,
            frame_width=800,
            flip_yaxis=True,
        )

# %% ../notebooks/04_hirise.ipynb 34
class RGB_NOMAP(COLOR_PRODUCT):
    def __init__(self, obsid):
        super().__init__(obsid)
        self.name = "nomap_jp2"
        self.pathfinder = ProductPathfinder(obsid + "_RGB")

# %% ../notebooks/04_hirise.ipynb 45
class RGB_NOMAPCollection:
    """Class to deal with a set of RGB_NOMAP products."""

    def __init__(self, obsids):
        self.obsids = obsids

    def get_urls(self):
        """Get URLs for list of obsids.

        Returns
        -------
        List[yarl.URL]
            List of URL objects with the respective PDS URL for download.
        """
        urls = []
        for obsid in self.obsids:
            rgb = RGB_NOMAP(obsid)
            urls.append(rgb.url)
        self.urls = urls
        return urls

    @property
    def local_paths(self):
        paths = []
        for obsid in self.obsids:
            rgb = RGB_NOMAP(obsid)
            paths.append(rgb.local_path)
        return paths

    def download_collection(self):
        lazys = []
        for obsid in self.obsids:
            rgb = RGB_NOMAP(obsid)
            lazys.append(delayed(rgb.download)())
        print("Launching parallel download...")
        compute(*lazys)
        print("Done.")

# %% ../notebooks/04_hirise.ipynb 46
class SOURCE_PRODUCT:
    """Manage SOURCE_PRODUCT id.

    Example
    -------
    'PSP_003092_0985_RED4_0'
    """

    red_ccds = ["RED" + str(i) for i in range(10)]
    ir_ccds = ["IR10", "IR11"]
    bg_ccds = ["BG12", "BG13"]
    ccds = red_ccds + ir_ccds + bg_ccds

    def __init__(self, spid, saveroot=None, check_url=True):
        tokens = spid.split("_")
        obsid = "_".join(tokens[:3])
        ccd = tokens[3]
        color, ccdno = self._parse_ccd(ccd)
        self.pid = ProductPathfinder("_".join([obsid, color]))
        self.ccd = ccd
        self.channel = tokens[4]
        self.saveroot = storage_root if saveroot is None else saveroot

    def __getattr__(self, value):
        return getattr(self.pid, value)

    def _parse_ccd(self, value):
        sep = 2 if value[:2] in ProductPathfinder.kinds else 3
        return value[:sep], value[sep:]

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        if int(value) not in [0, 1]:
            raise ValueError("channel must be in [0, 1]")
        self._channel = value

    @property
    def ccd(self):
        return self._ccd

    @ccd.setter
    def ccd(self, value):
        if value not in self.ccds:
            raise ValueError("CCD value must be in {}.".format(self.ccds))
        self._ccd = value
        if self.pid is not None:
            self.pid.color = self.color

    @property
    def color(self):
        return self._parse_ccd(self.ccd)[0]

    @property
    def ccdno(self):
        offset = len(self.color)
        return self.ccd[offset:]

    def __str__(self):
        return "{}: {}{}_{}".format(
            self.__class__.__name__, self.pid, self.ccdno, self.channel
        )

    def __repr__(self):
        return self.__str__()

    @property
    def spid(self):
        return f"{self.pid}{self.ccdno}_{self.channel}"

    @property
    def fname(self):
        return self.spid + ".IMG"

    @property
    def remote_path(self):
        return Path(self.pid.edr_storage_stem).parent / self.fname

    @property
    def url(self):
        u = baseurl / str(self.remote_path)
        if self.check_url:
            if not check_url_exists(u):
                warnings.warn(f"{u} does not exist on the server.")
        return u

    @property
    def local_path(self):
        savepath = self.saveroot / str(self.obsid) / self.fname
        return savepath

    @property
    def local_cube(self):
        return self.local_path.with_suffix(".cub")

    @property
    def stitched_cube_name(self):
        return f"{self.pid.obsid.id}_{self.ccd}.cub"

    @property
    def stitched_cube_path(self):
        return self.local_cube.with_name(self.stitched_cube_name)

    def download(self, overwrite=False):
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        if self.local_path.exists() and not overwrite:
            print("File exists. Use `overwrite=True` to download fresh.")
            return
        url_retrieve(self.url, self.local_path)

# %% ../notebooks/04_hirise.ipynb 61
class RED_PRODUCT(SOURCE_PRODUCT):
    "This exists to support creating a RED_PRODUCT_ID from parts of a SOURCE_PRODUCT id."

    def __init__(self, obsid, ccdno, channel, **kwargs):
        self.ccds = self.red_ccds
        super().__init__(f"{obsid}_RED{ccdno}_{channel}", **kwargs)

# %% ../notebooks/04_hirise.ipynb 66
class IR_PRODUCT(SOURCE_PRODUCT):
    def __init__(self, obsid, ccdno, channel):
        self.ccds = self.ir_ccds
        super().__init__(f"{obsid}_IR{ccdno}_{channel}", **kwargs)


class BG_PRODUCT(SOURCE_PRODUCT):
    def __init__(self, obsid, ccdno, channel):
        self.ccds = self.ir_ccds
        super().__init__(f"{obsid}_BG{ccdno}_{channel}", **kwargs)
