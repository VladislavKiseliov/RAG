from pathlib import Path
from dotenv import load_dotenv

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate


def setup_rag_chain(llm=None, retriever=None, prompt_template=None):
    """
    Настраивает современную цепочку RAG вместо RetrievalQA.
    """
    if llm is None or retriever is None or prompt_template is None:
        print("⚠️ setup_rag_chain вызван без необходимых параметров")
        return None

    # 1. Создаем цепочку для обработки документов (Combine Documents Chain)
    # Она отвечает за то, как чанки текста вставляются в промпт.
    combine_docs_chain = create_stuff_documents_chain(
        llm=llm,
        prompt=prompt_template
    )

    # 2. Создаем финальную цепочку поиска (Retrieval Chain)
    # Она соединяет retriever и цепочку обработки документов.
    rag_chain = create_retrieval_chain(
        retriever=retriever,
        combine_docs_chain=combine_docs_chain
    )

    return rag_chain


def answer_question(question: str, qa_chain) -> str:
    """Отвечает на вопрос, используя настроенную цепочку RAG."""


    if not question.strip():
        return "Пожалуйста, задайте корректный вопрос."

    try:

        result = qa_chain.invoke({"query": question})

        answer = result.get('result', "❌ Gemini не смог сгенерировать ответ.")
        sources = result.get('source_documents', [])

        sources_str_list = []
        with open('output1.txt', 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 50 + "\nНАЧАЛО НОВОГО ОТВЕТА\n" + "=" * 50 + "\n\n")

            # Используем один цикл для итерации по источникам
            for i, doc in enumerate(sources, 1):
                # 1. Записываем метаданные
                # Мы преобразуем словарь в строку, чтобы избежать TypeError
                f.write(f"--- Источник {i} ---\n")
                f.write("Метаданные: " + str(doc.metadata) + "\n")

                # 2. Записываем содержимое страницы (page_content)
                f.write("Текст:\n")
                f.write(doc.page_content)

                f.write("\n" + "-" * 50 + "\n")

        for doc in sources:
            score = doc.metadata.get('_score')
            print(f"{score=}")
            score_display = f"{score:.4f}" if isinstance(score, (float, int)) else 'N/A'

            page_num = doc.metadata.get('page')
            display_page = page_num + 1 if isinstance(page_num, int) else 'N/A'

            sources_str_list.append(
                f"📄 {Path(doc.metadata.get('source', 'Unknown')).name}, стр. {display_page} (Score: {score_display})"
            )

        sources_str = "\n".join(sources_str_list)

        return f"{answer}\n\nИсточники:\n{sources_str}"

    except Exception as e:
        return f"❌ Ошибка при генерации ответа: {e}"


# --- ДЕМОНСТРАЦИЯ И ТЕСТИРОВАНИЕ ---
if __name__ == '__main__':
    # Тестовый блок не будет работать без параметров, поэтому просто выводим сообщение
    print("Для тестирования запустите main.py или используйте API")
