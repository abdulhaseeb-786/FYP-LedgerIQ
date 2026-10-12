import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings


class FileStorageAdapter(ABC):
    @abstractmethod
    async def save_upload(self, upload_file: UploadFile, directory: str = "inputs") -> str:
        pass

    @abstractmethod
    def get_file_path(self, storage_path: str) -> Path:
        pass


class LocalFileStorage(FileStorageAdapter):
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "inputs").mkdir(exist_ok=True)
        (self.base_dir / "outputs").mkdir(exist_ok=True)

    async def save_upload(self, upload_file: UploadFile, directory: str = "inputs") -> str:
        target_dir = self.base_dir / directory
        target_dir.mkdir(parents=True, exist_ok=True)

        unique_id = uuid.uuid4().hex[:8]
        safe_name = f"{unique_id}_{upload_file.filename}"
        target_path = target_dir / safe_name

        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        return str(target_path)

    def get_file_path(self, storage_path: str) -> Path:
        return Path(storage_path)


def get_file_storage() -> FileStorageAdapter:
    return LocalFileStorage()
