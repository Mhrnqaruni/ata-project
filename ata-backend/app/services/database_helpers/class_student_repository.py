# /app/services/database_helpers/class_student_repository.py

from typing import List, Dict, Optional
import pandas as pd
from .base_repository import BaseRepository

DATA_DIR = "app/data"
CLASSES_DB_PATH = f"{DATA_DIR}/classes.csv"
STUDENTS_DB_PATH = f"{DATA_DIR}/students.csv"

class ClassStudentRepository:
    def __init__(self):
        self.classes = BaseRepository(
            CLASSES_DB_PATH, 
            columns=['id', 'name', 'description'],
            dtypes={'id': str, 'name': str, 'description': str}
        )
        self.students = BaseRepository(
            STUDENTS_DB_PATH, 
            columns=['id', 'name', 'studentId', 'class_id', 'overallGrade', 'performance_summary'],
            dtypes={'id': str, 'name': str, 'studentId': str, 'class_id': str, 'overallGrade': str, 'performance_summary': str}
        )

    # --- Class Methods ---
    def get_all_classes(self) -> List[Dict]: return self.classes._clean_df_for_export(self.classes.df)
    def get_class_by_id(self, class_id: str) -> Optional[Dict]:
        row = self.classes.df[self.classes.df['id'] == class_id]
        return self.classes._clean_df_for_export(row)[0] if not row.empty else None
    def add_class(self, record: Dict): self.classes._add_record(record)
    def update_class(self, class_id: str, data: Dict) -> Optional[Dict]:
        idx = self.classes.df.index[self.classes.df['id'] == class_id]
        if idx.empty: return None
        for key, value in data.items(): self.classes.df.loc[idx, key] = value
        self.classes._save_df(); return self.classes._clean_df_for_export(self.classes.df.loc[idx])[0]
    def delete_class(self, class_id: str) -> bool:
        initial_len = len(self.classes.df); self.classes.df = self.classes.df[self.classes.df['id'] != class_id]
        if len(self.classes.df) < initial_len: self.classes._save_df(); return True
        return False
        
    # --- Student Methods ---
    def get_all_students(self) -> List[Dict]: return self.students._clean_df_for_export(self.students.df)
    def get_students_by_class_id(self, class_id: str) -> List[Dict]:
        df = self.students.df; return self.students._clean_df_for_export(df[df['class_id'] == class_id])
    def add_student(self, record: Dict): self.students._add_record(record)
    def update_student(self, student_id: str, data: Dict) -> Optional[Dict]:
        idx = self.students.df.index[self.students.df['id'] == student_id]
        if idx.empty: return None
        for key, value in data.items(): self.students.df.loc[idx, key] = value
        self.students._save_df(); return self.students._clean_df_for_export(self.students.df.loc[idx])[0]
    def delete_student(self, student_id: str, class_id: str) -> bool:
        df = self.students.df
        initial_len = len(df)
        condition = ~((df['id'] == student_id) & (df['class_id'] == class_id))
        self.students.df = df[condition]
        if len(self.students.df) < initial_len:
            self.students._save_df()
            return True
        return False
    def delete_students_by_class_id(self, class_id: str) -> int:
        df = self.students.df; initial_len = len(df)
        self.students.df = df[df['class_id'] != class_id]
        num_deleted = initial_len - len(self.students.df)
        if num_deleted > 0: self.students._save_df()
        return num_deleted
        
    # --- [THE FIX IS HERE] ---
    def get_classes_as_dataframe(self, user_id: str) -> pd.DataFrame:
        # V2 TODO: When user_id is added to classes.csv, filter here.
        return self.classes.df.copy()
    def get_students_as_dataframe(self, user_id: str) -> pd.DataFrame:
        # V2 TODO: When user_id is added to students.csv, filter here.
        return self.students.df.copy()
    # --- [END OF FIX] ---