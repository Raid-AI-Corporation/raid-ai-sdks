"""File-input helper for multipart uploads."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ._core import FilePart

DEFAULT_CONTENT_TYPE = "application/octet-stream"


@dataclass
class FileInput:
    """A file to upload.

    ``data`` is the raw bytes; ``file_name`` and ``content_type`` become the
    multipart part's filename and MIME type.
    """

    data: bytes
    file_name: str
    content_type: str = DEFAULT_CONTENT_TYPE

    @classmethod
    def from_path(cls, path: str | os.PathLike[str], content_type: str | None = None) -> FileInput:
        """Read a file from disk into a :class:`FileInput`."""
        with open(path, "rb") as fh:
            data = fh.read()
        name = os.path.basename(os.fspath(path))
        return cls(data=data, file_name=name, content_type=content_type or DEFAULT_CONTENT_TYPE)

    def to_part(self, field: str) -> FilePart:
        return (field, (self.file_name, self.data, self.content_type))


FileArg = FileInput
