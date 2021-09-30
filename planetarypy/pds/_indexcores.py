# AUTOGENERATED! DO NOT EDIT! File to edit: notebooks/02f_pds.utils.ipynb (unless otherwise specified).

__all__ = ['index_to_df', 'PVLColumn', 'IndexLabel', 'decode_line', 'find_mixed_type_cols', 'fix_hirise_edrcumindex']

# Cell
from fastcore.utils import Path

import pandas as pd
import pvl
from planetarypy import utils

# Cell
def index_to_df(indexpath, label, convert_times=True):
    """The main reader function for PDS Indexfiles.

    In conjunction with an IndexLabel object that figures out the column widths,
    this reader should work for all PDS TAB files.

    Parameters
    ----------
    indexpath : str or pathlib.Path
        The path to the index TAB file.
    label : pdstools.IndexLabel object
        Label object that has both the column names and the columns widths as attributes
        'colnames' and 'colspecs'
    convert_times : bool
        Switch to control if to convert columns with "TIME" in name (unless COUNT is as well in name) to datetime
    """
    indexpath = Path(indexpath)
    df = pd.read_fwf(
        indexpath, header=None, names=label.colnames, colspecs=label.colspecs
    )
    if convert_times:
        for column in [i for i in df.columns if "TIME" in i and "COUNT" not in i]:
            if column == "LOCAL_TIME":
                # don't convert local time
                continue
            print(f"Converting times for column {column}.")
            try:
                df[column] = pd.to_datetime(df[column])
            except ValueError:
                df[column] = pd.to_datetime(
                    df[column], format=utils.nasa_dt_format_with_ms, errors="coerce"
                )
        print("Done.")
    return df

# Cell
class PVLColumn:
    """Manages just one of the columns in a table that is described via PVL."""

    def __init__(self, pvlobj):
        self.pvlobj = pvlobj

    @property
    def name(self):
        return self.pvlobj["NAME"]

    @property
    def name_as_list(self):
        "needs to return a list for consistency for cases when it's an array."
        if self.items is None:
            return [self.name]
        else:
            return [self.name + "_" + str(i + 1) for i in range(self.items)]

    @property
    def start(self):
        "Decrease by one as Python is 0-indexed."
        return self.pvlobj["START_BYTE"] - 1

    @property
    def stop(self):
        return self.start + self.pvlobj["BYTES"]

    @property
    def items(self):
        return self.pvlobj.get("ITEMS")

    @property
    def item_bytes(self):
        return self.pvlobj.get("ITEM_BYTES")

    @property
    def item_offset(self):
        return self.pvlobj.get("ITEM_OFFSET")

    @property
    def colspecs(self):
        if self.items is None:
            return (self.start, self.stop)
        else:
            i = 0
            bucket = []
            for _ in range(self.items):
                off = self.start + self.item_offset * i
                bucket.append((off, off + self.item_bytes))
                i += 1
            return bucket

    def decode(self, linedata):
        if self.items is None:
            start, stop = self.colspecs
            return linedata[start:stop]
        else:
            bucket = []
            for (start, stop) in self.colspecs:
                bucket.append(linedata[start:stop])
            return bucket

    def __repr__(self):
        return self.pvlobj.__repr__()

# Cell
class IndexLabel(object):
    """Support working with label files of PDS Index tables.

    Parameters
    ----------
    labelpath : str, pathlib.Path
        Path to the labelfile for a PDS Indexfile. The actual table should reside in the same
        folder to be automatically parsed when calling the `read_index_data` method.
    """

    def __init__(self, labelpath):
        self.path = Path(labelpath)
        "search for table name pointer and store key and fpath."
        tuple = [i for i in self.pvl_lbl if i[0].startswith("^")][0]
        self.tablename = tuple[0][1:]
        self.index_name = tuple[1]

    @property
    def index_path(self):
        p = self.path.parent / self.index_name
        if not p.exists():
            import warnings

            warnings.warn("Fudging to lower case.")
            p = self.path.parent / self.index_name.lower()
        if not p.exists():
            warnings.warn("`index_path` still doesn't exist.")
        return p

    @property
    def pvl_lbl(self):
        return pvl.load(str(self.path))

    @property
    def table(self):
        return self.pvl_lbl[self.tablename]

    @property
    def pvl_columns(self):
        return self.table.getlist("COLUMN")

    @property
    def columns_dic(self):
        return {col["NAME"]: col for col in self.pvl_columns}

    @property
    def colnames(self):
        """Read the columns in an PDS index label file.

        The label file for the PDS indices describes the content
        of the index files.
        """
        colnames = []
        for col in self.pvl_columns:
            colnames.extend(PVLColumn(col).name_as_list)
        return colnames

    @property
    def colspecs(self):
        colspecs = []
        columns = self.table.getlist("COLUMN")
        for column in columns:
            pvlcol = PVLColumn(column)
            if pvlcol.items is None:
                colspecs.append(pvlcol.colspecs)
            else:
                colspecs.extend(pvlcol.colspecs)
        return colspecs

    def read_index_data(self, convert_times=True):
        return index_to_df(self.index_path, self, convert_times=convert_times)

# Cell
def decode_line(linedata, labelpath):
    """Decode one line of tabbed data with the appropriate label file.

    Parameters
    ----------
    linedata : str
        One line of a .tab data file
    labelpath : str or pathlib.Path
        Path to the appropriate label that describes the data.
    """
    label = IndexLabel(labelpath)
    for column in label.pvl_columns:
        pvlcol = PVLColumn(column)
        print(pvlcol.name, pvlcol.decode(linedata))

# Cell
def find_mixed_type_cols(df, fix=True):
    """For a given dataframe, find the columns that are of mixed type.

    Tool to help with the performance warning when trying to save a pandas DataFrame as a HDF.
    When a column changes datatype somewhere, pickling occurs, slowing down the reading process of the HDF file.

    Parameters
    ----------
    df : pandas.DataFrame
        Dataframe to be searched for mixed data-types
    fix : bool
        Switch to control if NaN values in these problem columns should be replaced by the string 'UNKNOWN'
    Returns
    -------
    List of column names that have data type changes within themselves.
    """
    result = []
    for col in df.columns:
        weird = (df[[col]].applymap(type) != df[[col]].iloc[0].apply(type)).any(axis=1)
        if len(df[weird]) > 0:
            print(col)
            result.append(col)
    if fix is True:
        for col in result:
            df[col].fillna("UNKNOWN", inplace=True)
    return result

# Cell
def fix_hirise_edrcumindex(infname, outfname):
    """Fix HiRISE EDRCUMINDEX.

    The HiRISE EDRCUMINDEX has some broken lines where the SCAN_EXPOSURE_DURATION is of format
    F10.4 instead of the defined F9.4.
    This function simply replaces those incidences with one less decimal fraction, so 20000.0000
    becomes 20000.000.

    Parameters
    ----------
    infname : str
        Path to broken EDRCUMINDEX.TAB
    outfname : str
        Path where to store the fixed TAB file
    """
    with open(infname) as f:
        with open(outfname, "w") as newf:
            for line in tqdm(f):
                exp = line.split(",")[21]
                if float(exp) > 9999.999:
                    # catching the return of write into dummy variable
                    _ = newf.write(line.replace(exp, exp[:9]))
                else:
                    _ = newf.write(line)