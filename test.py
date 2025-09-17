from RagGogNew import answer_question

if __name__ == "__main__":
    question = "Что говорится о машинном обучении?"
    answer = answer_question(question)
    print("Вопрос:", question)
    print("\nОтвет:\n", answer)