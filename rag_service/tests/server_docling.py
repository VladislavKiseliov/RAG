import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from test_docling import _build_converter, run_pipeline

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

app = FastAPI()
_converter = _build_converter()
_log.info("Converter initialized, warming up...")
# Прогрев на первом попавшемся PDF чтобы модели сразу загрузились в память
_pdfs = list(Path(".").glob("*.pdf"))
if _pdfs:
    import tempfile
    from pypdf import PdfReader, PdfWriter
    _r = PdfReader(_pdfs[0])
    _w = PdfWriter()
    _w.add_page(_r.pages[0])
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _f:
        _w.write(_f)
        _tmp = Path(_f.name)
    _converter.convert(_tmp)
    _tmp.unlink(missing_ok=True)
    _log.info("Warm-up done, server ready.")


class ConvertRequest(BaseModel):
    input_file: str
    output_dir: str


@app.post("/convert")
def convert(req: ConvertRequest):
    run_pipeline(Path(req.input_file), Path(req.output_dir), _converter)
    return {"status": "ok", "output_dir": req.output_dir}


if __name__ == "__main__":
    uvicorn.run("server_docling:app", host="127.0.0.1", port=7860, reload=False)