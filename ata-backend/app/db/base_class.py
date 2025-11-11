# /ata-backend/app/db/base_class.py (Corrected and Final Version)

from sqlalchemy.ext.declarative import as_declarative, declared_attr

@as_declarative()
class Base:
    """
    A base class for all SQLAlchemy models.
    It automatically generates a __tablename__ for each model.
    """
    id: any
    __name__: str
    
    # This is a helper that automatically creates a table name for any class
    # that inherits from this Base. For example, a class named 'Class' will
    # get a table named 'classes'. A class named 'Student' gets 'students'.
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"