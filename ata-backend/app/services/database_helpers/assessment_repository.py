# /app/services/database_helpers/assessment_repository.py

from typing import List, Dict, Optional
import pandas as pd
from .base_repository import BaseRepository

DATA_DIR = "app/data"
ASSESSMENTS_DB_PATH = f"{DATA_DIR}/assessments.csv"
RESULTS_DB_PATH = f"{DATA_DIR}/results.csv"

class AssessmentRepository:
    """A specialized repository for handling all data related to assessments and results."""
    def __init__(self):
        self.assessments = BaseRepository(
            ASSESSMENTS_DB_PATH,
            columns=['id', 'status', 'config', 'answer_sheet_paths', 'created_at', 'ai_summary'],
            dtypes={'id': str, 'status': str}
        )
        self.results = BaseRepository(
            RESULTS_DB_PATH,
            columns=['id', 'job_id', 'student_id', 'question_id', 'grade', 'feedback', 'extractedAnswer', 'status', 'report_token', 'answer_sheet_path', 'content_type'],
            dtypes={'grade': 'Float64', 'id': str, 'job_id': str, 'student_id': str, 'question_id': str, 'report_token': str, 'status': str, 'content_type': str}
        )

    # --- Assessment Job Methods ---
    def add_job(self, record: Dict): self.assessments._add_record(record)
    def get_job(self, job_id: str) -> Optional[Dict]:
        row = self.assessments.df[self.assessments.df['id'] == job_id]
        return self.assessments._clean_df_for_export(row)[0] if not row.empty else None
    def get_all_jobs(self) -> List[Dict]:
        df = self.assessments.df
        if df.empty or 'created_at' not in df.columns: return []
        return self.assessments._clean_df_for_export(df.sort_values(by='created_at', ascending=False))
    def update_job_status(self, job_id: str, status: str):
        self.assessments.df.loc[self.assessments.df['id'] == job_id, 'status'] = status; self.assessments._save_df()
    def update_job_summary(self, job_id: str, summary: str):
        self.assessments.df.loc[self.assessments.df['id'] == job_id, 'ai_summary'] = summary; self.assessments._save_df()
    def delete_job(self, job_id: str) -> bool:
        df = self.assessments.df
        initial_len = len(df)
        self.assessments.df = df[df['id'] != job_id]
        if len(self.assessments.df) < initial_len:
            self.assessments._save_df()
            return True
        return False
    def delete_results_by_job_id(self, job_id: str) -> int:
        df = self.results.df
        initial_len = len(df)
        self.results.df = df[df['job_id'] != job_id]
        num_deleted = initial_len - len(self.results.df)
        if num_deleted > 0:
            self.results._save_df()
        return num_deleted

    # --- [THE FIX IS HERE] ---
    def get_assessments_as_dataframe(self, user_id: str) -> pd.DataFrame:
        """Returns a copy of the assessments DataFrame for the chatbot sandbox."""
        # V2 TODO: This is a simplified model. A real implementation would join
        # results and assessments and filter by the user's classes.
        # For now, we return all results as the "assessments_df".
        return self.results.df.copy()
    # --- [END OF FIX] ---

    # --- Assessment Result Methods ---
    def add_result(self, record: Dict): self.results._add_record(record)
    def get_all_results_for_job(self, job_id: str) -> List[Dict]:
        df = self.results.df; return self.results._clean_df_for_export(df[df['job_id'] == job_id])
    def get_all_results(self) -> List[Dict]: return self.results._clean_df_for_export(self.results.df)
    def get_student_result_path(self, job_id: str, student_id: str) -> Optional[str]:
        df = self.results.df; student_results = df[(df['job_id'] == job_id) & (df['student_id'] == student_id)]
        if not student_results.empty: return student_results.iloc[0]['answer_sheet_path']
        return None
    def get_students_with_paths(self, job_id: str) -> List[Dict]:
        df = self.results.df
        matched = df[(df['job_id'] == job_id) & (df['answer_sheet_path'] != '') & (df['answer_sheet_path'].notna())]
        return matched[['student_id', 'answer_sheet_path', 'content_type']].drop_duplicates(subset=['student_id']).to_dict('records')
    def get_result_by_token(self, token: str) -> Optional[Dict]:
        row = self.results.df[self.results.df['report_token'] == token]
        return self.results._clean_df_for_export(row)[0] if not row.empty else None
    def update_result_path(self, job_id: str, student_id: str, path: str, content_type: str):
        df = self.results.df; condition = (df['job_id'] == job_id) & (df['student_id'] == student_id)
        self.results.df.loc[condition, 'answer_sheet_path'] = path
        self.results.df.loc[condition, 'content_type'] = content_type
        self.results.df.loc[condition, 'status'] = 'matched'; self.results._save_df()
    def update_result_status(self, job_id: str, student_id: str, question_id: str, status: str):
        df = self.results.df; condition = (df['job_id'] == job_id) & (df['student_id'] == student_id) & (df['question_id'] == question_id)
        self.results.df.loc[condition, 'status'] = status; self.results._save_df()
    def update_result_grade(self, job_id: str, student_id: str, question_id: str, grade: Optional[float], feedback: str, status: str):
        df = self.results.df; condition = (df['job_id'] == job_id) & (df['student_id'] == student_id) & (df['question_id'] == question_id)
        self.results.df.loc[condition, 'grade'] = grade
        self.results.df.loc[condition, 'feedback'] = feedback
        self.results.df.loc[condition, 'status'] = status; self.results._save_df()
    def update_result_with_isolated_answer(self, job_id: str, student_id: str, question_id: str, extracted_answer: str):
        df = self.results.df; condition = (df['job_id'] == job_id) & (df['student_id'] == student_id) & (df['question_id'] == question_id)
        self.results.df.loc[condition, 'extractedAnswer'] = extracted_answer; self.results._save_df()