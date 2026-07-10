from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TreeNode(BaseModel):
    name: str
    path: str
    type: str  # file | folder
    language: str | None = None
    children: list["TreeNode"] | None = None


class WorkspaceTree(BaseModel):
    job_id: int
    workspace_path: str
    main_path: str | None = None
    editable: bool
    tree: Any


class WorkspaceFileOut(BaseModel):
    job_id: int
    path: str
    file_name: str
    language: str
    content: str
    last_modified_at: str | None = None
    size_bytes: int | None = None
    editable: bool = False


class WorkspaceSaveRequest(BaseModel):
    path: str
    content: str
    expected_last_modified_at: str | None = None


class WorkspaceCreateFile(BaseModel):
    path: str
    content: str = ""


class WorkspacePathRequest(BaseModel):
    path: str


class WorkspaceRenameRequest(BaseModel):
    old_path: str
    new_path: str


class WorkspaceOpResult(BaseModel):
    ok: bool = True
    action: str
    path: str | None = None
    last_modified_at: str | None = None
