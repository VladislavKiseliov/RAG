# import pdfplumber
# import pandas as pd

# # Открываем PDF
# with pdfplumber.open("1234.pdf") as pdf:
#     # Выбираем страницу
#     page = pdf.pages[0]
#     # Извлекаем все таблицы на странице
#     tables = page.extract_tables()
#
#     # Получаем данные первой таблицы
#     table_data = tables[0]
#     print(tables)
#     # table_data будет выглядеть как [[Header1, Header2], [Value1, Value2], ...]
#
#
# def table_to_markdown(table_data):
#     # Преобразуем в DataFrame для удобства
#     df = pd.DataFrame(table_data[1:], columns=table_data[0])
#
#     # Конвертируем DataFrame в Markdown-строку
#     markdown_string = df.to_markdown(index=False)
#
#     return markdown_string
#
#
# # Применяем к данным, полученным на Шаге 1
# markdown_output = table_to_markdown(table_data)
# print(markdown_output)



# import pdfplumber
#
# with pdfplumber.open("1234.pdf") as pdf:
#     page = pdf.pages[0]
#     table = page.extract_table()
#     print(table)