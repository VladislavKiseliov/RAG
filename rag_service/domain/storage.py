from enum import Enum


class StorageDomain(str, Enum):
    KNOWLEDGE_BASE = "knowledge_base"
    USERS = "users"
    PROJECTS = "projects"
