# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/api/02c_pds.apps.ipynb.

# %% auto 0
__all__ = ['find_indexes', 'get_index', 'find_instruments']

# %% ../../notebooks/api/02c_pds.apps.ipynb 3
import pandas as pd
from ..config import config
from .indexes import Index

# %% ../../notebooks/api/02c_pds.apps.ipynb 4
def find_indexes(
        instrument: str,  # Dotted mission.instrument key, e.g. cassini.iss
) -> list:  # List of configured index names
    "Find existing indexes for an instrument."
    return config.list_indexes(instrument)

# %% ../../notebooks/api/02c_pds.apps.ipynb 7
def get_index(
        instr: str,  # Dotted instrument index, e.g. cassini.iss
        index_name: str = '',  # Index name, for exmample 'moon_summary. Optional'
        # switch to refresh an index (i.e. download if update available).
        # Set to False for faster return time to avoid web scraping
        refresh: bool = True,  
        force: bool = False,  # switch off for faster return time.
) -> pd.DataFrame:  # The PDS index convert to pandas DataFrame
    """Example: get_index("cassini.iss", "index")"""
    # I need to add the check_update switch to the constructor b/c of dynamic url setting that always
    # wants to go online to find the latest volume URL.
    if not index_name:
        index = Index(instr, check_update=refresh)
    else:
        index = Index(instr + ".indexes." + index_name, check_update=refresh)
    if not index.local_table_path.exists() or force:
        index.download()
    elif refresh and index.update_available:
        index.download()
        print("An updated index is available. Downloading...")
    if not index.local_parq_path.exists():
        index.convert_to_parquet()
    return index.parquet

# %% ../../notebooks/api/02c_pds.apps.ipynb 15
def find_instruments(
        mission: str,  # Mission string, e.g. "cassini"
) -> list:  # List of configured instrument names
    "Find existing instruments for a mission."
    return config.list_instruments(mission)
