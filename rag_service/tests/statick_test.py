import os
import uuid
from datetime import datetime, timezone


def build_object_key(filename: str, doc_id: uuid.UUID) -> str:
    name, ext = os.path.splitext(filename)
    now = datetime.now(timezone.utc)
    return f"documents/{now:%Y/%m}/{doc_id}{ext.lower()}"

filename = "test.txt"
doc_id = uuid.uuid4()
key = build_object_key(filename, doc_id)
print(doc_id)
print(key)



key = "documents/2026/05/ef7bc53e-c643-4b7b-ad0f-d78ee8132d61.pdf"
name,ext = os.path.splitext(key)
parts = key.split("/")
name,exc = os.path.splitext(parts[3])
print(name)