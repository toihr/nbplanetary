# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/02c_pds.apps.ipynb (unless otherwise specified).

__all__ = ['find_indexes', 'get_index', 'find_instruments']

# Cell
import pandas as pd
from ..config import config
from .indexes import Index

# Cell
def find_indexes(
    instrument: str,  # Dotted mission.instrument key, e.g. cassini.iss
) -> list:            # List of configured index names
    "Find existing indexes for an instrument."
    return config.list_indexes(instrument)

# Cell
def get_index(
    instr: str,  # Dotted instrument index, e.g. cassini.iss
    index_name: str,  # Index name, for exmample 'moon_summary'
) -> pd.DataFrame:  # The PDS index convert to pandas DataFrame
    """Example: get_index("cassini.iss", "index")"""
    index = Index(instr + ".indexes." + index_name)
    index.download()
    try:
        return index.parquet
    except FileNotFoundError:
        index.convert_to_parquet()
        return index.parquet

# Cell
def find_instruments(
    mission: str,  # Mission string, e.g. "cassini"
) -> list:  # List of configured instrument names
    "Find existing instruments for a mission."
    return config.list_instruments(mission)