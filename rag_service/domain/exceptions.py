class DocumentAlreadyExists(Exception):
    """Брошено при конфликте уникальности по file_hash."""
    def __init__(self, file_hash: str) -> None:
        super().__init__(f"Document with hash '{file_hash}' already exists")
        self.file_hash = file_hash


class DocumentNotFound(Exception):
    """Брошено, если документ не найден (например, при сборке текста)."""
    def __init__(self, doc_id: str) -> None:
        super().__init__(f"Document '{doc_id}' not found")
        self.doc_id = doc_id
