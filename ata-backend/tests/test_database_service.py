# /tests/test_database_service.py (CORRECTED FOR SQLALCHEMY)

import pytest
from unittest.mock import MagicMock

# We import the CLASS itself, not the shared singleton instance.
from app.services.database_service import DatabaseService
from app.db.models.class_student_models import Class

@pytest.fixture
def mock_db_session():
    """Provides a mock SQLAlchemy session."""
    return MagicMock()

@pytest.fixture
def db_service(mock_db_session):
    """
    Creates a DatabaseService instance with a mocked session, which is the
    correct way to test the service layer in isolation from a real database.
    """
    return DatabaseService(db_session=mock_db_session)


def test_add_and_get_class(db_service, mock_db_session):
    """
    Tests that a class can be added and then retrieved successfully.
    """
    user_id = "user_test_123"
    class_id = "cls_test_123"
    class_data = {"id": class_id, "name": "Test History Class", "description": "A class for testing.", "user_id": user_id}

    # 1. Configure the mock session to return a mock Class instance when queried
    mock_class_instance = Class(**class_data)
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_class_instance

    # 2. Call the service method to add the class
    db_service.add_class(class_data)

    # 3. Call the service method to get the class
    retrieved_class = db_service.get_class_by_id(class_id, user_id=user_id)

    # 4. Assert that the underlying ORM methods were called correctly
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()

    # 5. Assert that the retrieved class is the one we configured the mock to return
    assert retrieved_class is not None
    assert retrieved_class.name == "Test History Class"
    assert retrieved_class.id == class_id

def test_get_non_existent_class(db_service, mock_db_session):
    """Tests that getting a non-existent class returns None."""
    # Configure the mock session to return None, simulating a not-found scenario
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    retrieved_class = db_service.get_class_by_id("cls_no_exist", user_id="user_test_123")
    assert retrieved_class is None

def test_get_all_classes(db_service, mock_db_session):
    """
    Tests that get_all_classes correctly returns a list of classes.
    """
    user_id = "user_test_456"
    class1_data = {"id": "cls_1", "name": "Class 1", "description": "Desc 1", "user_id": user_id}
    class2_data = {"id": "cls_2", "name": "Class 2", "description": "Desc 2", "user_id": user_id}

    mock_class1 = Class(**class1_data)
    mock_class2 = Class(**class2_data)

    # Configure the mock session to return a list of mock objects
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_class1, mock_class2]

    # Act
    all_classes = db_service.get_all_classes(user_id=user_id)

    # Assert
    assert isinstance(all_classes, list)
    assert len(all_classes) == 2
    assert all_classes[0].name == 'Class 1'
    assert all_classes[1].name == 'Class 2'