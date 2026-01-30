from pathlib import Path

from app.tasks import ingest_pdf_task


def main() -> None:
    directory = r"D:\Laboratoria\Rag OVER\RagProgramm\docs"
    collection = "my_collection"
    path = Path(directory)
    for file_path in path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() == ".pdf":
            result = ingest_pdf_task.delay(str(file_path), collection)
            print(result.id)


if __name__ == "__main__":
    main()
