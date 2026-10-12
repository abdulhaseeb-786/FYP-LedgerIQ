"""Infrastructure package."""
from app.modules.financial_statements.infrastructure.file_storage import LocalFileStorage, get_file_storage
__all__ = ["LocalFileStorage", "get_file_storage"]
