from pathlib import Path
from typing import Any, Dict, List

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate


def setup_rag_chain(llm: Any, retriever: Any, prompt_template: str):
    if llm is None or retriever is None or not prompt_template:
        raise ValueError("setup_rag_chain requires llm, retriever, and prompt_template")

    prompt = ChatPromptTemplate.from_template(prompt_template)
    combine_docs_chain = create_stuff_documents_chain(llm=llm, prompt=prompt)
    return create_retrieval_chain(retriever=retriever, combine_docs_chain=combine_docs_chain)


def _extract_sources(source_docs: List[Document]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for doc in source_docs:
        metadata = getattr(doc, "metadata", {}) or {}
        source_path = metadata.get("source")
        page_num = metadata.get("page")
        score = metadata.get("_score")
        sources.append(
            {
                "source": Path(source_path).name if source_path else None,
                "page": page_num + 1 if isinstance(page_num, int) else None,
                "score": float(score) if isinstance(score, (float, int)) else None,
            }
        )
    return sources


def answer_question(question: str, qa_chain: Any) -> Dict[str, Any]:
    if not question or not question.strip():
        return {"answer": "Пожалуйста, задайте корректный вопрос.", "sources": []}

    result = qa_chain.invoke({"query": question})

    answer = (
        result.get("result")
        or result.get("answer")
        or result.get("output_text")
        or ""
    )

    source_docs = (
        result.get("source_documents")
        or result.get("context")
        or []
    )

    if not isinstance(source_docs, list):
        source_docs = []

    sources = _extract_sources(source_docs) if source_docs else []
    return {"answer": answer, "sources": sources}
