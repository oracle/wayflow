# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
from pathlib import Path
from typing import Union

import pandas as pd

from wayflowcore.exceptions import SecurityException


def secure_to_csv(df: pd.DataFrame, filepath: Union[str, Path]) -> None:
    """
    Securely write a DataFrame to a CSV file with strict permissions.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to be written to the CSV file.
    filepath : str or pathlib.Path
        The path where the CSV file should be saved. If the directory doesn't
        exist, it will be created with secure permissions.
    """
    _filepath = Path(filepath).resolve()  # filepath sanitation
    _filepath.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Due to security constraints, we set the permissions for all the files we generate to 600 (rw only for owner)
    old_umask = os.umask(0o077)
    try:
        df.to_csv(_filepath, index=False)
        if _filepath.stat().st_mode & 0o777 != 0o600:  # Verify final permissions
            raise SecurityException("Final file has incorrect permissions")
    finally:
        # Whatever happens, we restore the original umask
        os.umask(old_umask)
