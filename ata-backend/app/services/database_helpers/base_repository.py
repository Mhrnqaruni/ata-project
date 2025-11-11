# /app/services/database_helpers/base_repository.py

import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional

class BaseRepository:
    """A base class for our CSV repositories to share common I/O and cleaning logic."""
    def __init__(self, path: str, columns: List[str], dtypes: Optional[Dict] = None):
        self.path = path
        self.columns = columns # Store columns for later use
        self.dtypes = dtypes   # Store dtypes for later use
        self.df = self._load_or_initialize_csv(path, columns, dtypes)

    def _load_or_initialize_csv(self, path: str, columns: List[str], dtypes: Optional[Dict] = None) -> pd.DataFrame:
        """Loads a CSV from a given path or creates it if it doesn't exist."""
        try:
            # keep_default_na=False is crucial for preventing "NA" string from becoming NaN
            return pd.read_csv(path, keep_default_na=False, na_values=['', 'None', 'null'], dtype=dtypes)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            df = pd.DataFrame(columns=columns)
            if dtypes:
                df = df.astype(dtypes)
            df.to_csv(path, index=False)
            return df

    def _clean_df_for_export(self, df: pd.DataFrame) -> List[Dict]:
        """Replaces all pandas/numpy-specific null types with Python's native None."""
        df_copy = df.copy()
        df_copy.replace({pd.NA: None, np.nan: None}, inplace=True)
        return df_copy.to_dict('records')

    def _save_df(self):
        """Saves the current state of the DataFrame back to its CSV file."""
        self.df.to_csv(self.path, index=False)

    # --- [THE DEFINITIVE FIX IS HERE] ---
    def _add_record(self, record: Dict):
        """
        Adds a new record (as a dict) to the DataFrame and saves.
        This version is hardened to prevent FutureWarning from pd.concat.
        """
        # Create a single-row DataFrame from the new record.
        new_row_df = pd.DataFrame([record])
        
        # Ensure the new row has the same columns in the same order as the main DataFrame.
        new_row_df = new_row_df.reindex(columns=self.columns)

        # If dtypes were specified for the main DataFrame, apply them to the new row.
        # This makes the concatenation explicit and removes the warning.
        if self.dtypes:
            new_row_df = new_row_df.astype(self.dtypes)

        # Now, concatenate the two DataFrames.
        self.df = pd.concat([self.df, new_row_df], ignore_index=True)
        self._save_df()
    # --- [END OF FIX] ---