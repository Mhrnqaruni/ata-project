# /ata-backend/app/services/database_helpers/chat_repository.py

from typing import List, Dict, Optional
from .base_repository import BaseRepository

DATA_DIR = "app/data"
CHAT_SESSIONS_DB_PATH = f"{DATA_DIR}/chat_sessions.csv"
CHAT_MESSAGES_DB_PATH = f"{DATA_DIR}/chat_messages.csv"

class ChatRepository:
    """A specialized repository for handling all data related to chat sessions and messages."""
    def __init__(self):
        self.sessions = BaseRepository(
            CHAT_SESSIONS_DB_PATH,
            columns=['id', 'user_id', 'name', 'created_at'],
            dtypes={'id': str, 'user_id': str, 'name': str}
        )
        self.messages = BaseRepository(
            CHAT_MESSAGES_DB_PATH,
            columns=['id', 'session_id', 'role', 'content', 'file_id', 'created_at'],
            dtypes={'id': str, 'session_id': str, 'role': str, 'content': str, 'file_id': str}
        )

    # --- Chat Session Methods ---
    def create_session(self, record: Dict):
        """Adds a new chat session record."""
        self.sessions._add_record(record)

    def get_sessions_by_user_id(self, user_id: str) -> List[Dict]:
        """Retrieves all chat session summaries for a specific user, newest first."""
        df = self.sessions.df
        user_sessions = df[df['user_id'] == user_id]
        if 'created_at' in user_sessions.columns:
            user_sessions = user_sessions.sort_values(by='created_at', ascending=False)
        return self.sessions._clean_df_for_export(user_sessions)

    # --- [THIS IS THE NEWLY ADDED METHOD] ---
    def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """Retrieves a single chat session by its unique ID."""
        df = self.sessions.df
        session = df[df['id'] == session_id]
        if not session.empty:
            return self.sessions._clean_df_for_export(session)[0]
        return None
    # --- [END OF NEW METHOD] ---

    # --- Chat Message Methods ---
    def add_message(self, record: Dict):
        """Adds a new chat message record."""
        self.messages._add_record(record)

    def get_messages_by_session_id(self, session_id: str) -> List[Dict]:
        """Retrieves all messages for a specific chat session, in guaranteed chronological order."""
        df = self.messages.df
        session_messages = df[df['session_id'] == session_id]
        
        if 'created_at' in session_messages.columns and not session_messages.empty:
            session_messages = session_messages.sort_values(by='created_at', ascending=True)
            
        return self.messages._clean_df_for_export(session_messages)
    

        # Add inside the ChatRepository class

    def delete_session_by_id(self, session_id: str) -> bool:
        """Deletes a single chat session record by its ID."""
        df = self.sessions.df
        initial_len = len(df)
        self.sessions.df = df[df['id'] != session_id]
        if len(self.sessions.df) < initial_len:
            self.sessions._save_df()
            return True
        return False

    def delete_messages_by_session_id(self, session_id: str) -> int:
        """Deletes all messages associated with a given session ID."""
        df = self.messages.df
        initial_len = len(df)
        self.messages.df = df[df['session_id'] != session_id]
        num_deleted = initial_len - len(self.messages.df)
        if num_deleted > 0:
            self.messages._save_df()
        return num_deleted