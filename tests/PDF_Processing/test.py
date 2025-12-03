# --- Импорт Необходимых Библиотек ---
# Для считывания PDF
import PyPDF2
# Для анализа структуры PDF и извлечения текста (pdfminer)
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTRect, LTFigure, LTTextBoxHorizontal
# Для извлечения текста из таблиц в PDF
import pdfplumber
# Для работы с изображениями и OCR
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import os
import pdfplumber
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import warnings


# --- 1. Вспомогательные Функции ---


def visualize_pdf_elements(pdf_path, pagenum):
    """
    Визуализирует все элементы (текст, фигуры, таблицы) на странице PDF.

    :param pdf_path: Путь к файлу PDF
    :param pagenum: Номер страницы (начиная с 0)
    """

    # --- 1. Извлечение данных (Ваш код) ---
    pdf = pdfplumber.open(pdf_path)
    page = pdf.pages[pagenum]

    # Координаты страницы
    page_width = page.width
    page_height = page.height

    # Находим все таблицы на странице
    found_tables = page.find_tables()

    # Все элементы (текст, фигуры и т.д.)
    # pdfplumber не имеет прямого доступа к _objs, если только вы не работаете с ним напрямую
    # Лучше использовать page.rects, page.chars и т.д.
    elements_to_draw = []

    # Добавляем все прямоугольники и линии (рамки таблиц, границы)
    for rect in page.rects:
        # Добавляем координаты (x0, top, x1, bottom) и тип элемента
        elements_to_draw.append((rect['x0'], rect['top'], rect['x1'], rect['bottom'], 'rect'))

    # Добавляем все символы/текстовые блоки для визуализации
    for char in page.chars:
        elements_to_draw.append((char['x0'], char['top'], char['x1'], char['bottom'], 'char'))

    pdf.close()

    # --- 2. Настройка Matplotlib для отрисовки ---

    fig, ax = plt.subplots(1, figsize=(10, 15))  # Устанавливаем размер графика

    # Устанавливаем пределы осей в соответствии с размером страницы PDF
    # Ось X: от 0 до ширины страницы
    ax.set_xlim(0, page_width)
    # Ось Y: от 0 до высоты страницы (ось Y инвертирована, чтобы 0 был сверху)
    ax.set_ylim(page_height, 0)

    ax.set_title(f"Визуализация элементов страницы {pagenum + 1} ({page_width}x{page_height})")

    # --- 3. Отрисовка элементов ---

    # 3.1 Отрисовка текстовых элементов и фигур
    for x0, top, x1, bottom, element_type in elements_to_draw:
        width = x1 - x0
        height = bottom - top

        # Выбираем цвет в зависимости от типа элемента
        if element_type == 'rect':
            color = 'gray'
            alpha = 0.2
            label = 'Фигура/Рамка'
        elif element_type == 'char':
            color = 'blue'
            alpha = 0.5
            label = 'Текст'
        else:
            continue

        # Отрисовка ограничивающей рамки
        rect = Rectangle((x0, top), width, height, linewidth=1, edgecolor=color, facecolor=color, alpha=alpha,
                         label=label if element_type in ('rect', 'char') else None)
        ax.add_patch(rect)

    # 3.2 Отрисовка найденных таблиц (самый важный шаг)

    table_bboxes = []
    for table in found_tables:
        x0, top, x1, bottom = table.bbox
        table_bboxes.append(table.bbox)

        width = x1 - x0
        height = bottom - top

        # Отрисовка рамки таблицы жирным красным цветом
        table_rect = Rectangle((x0, top), width, height, linewidth=2, edgecolor='red', facecolor='none',
                               label='Таблица')
        ax.add_patch(table_rect)

        # Добавляем подпись
        ax.text(x0, top - 5, f"Таблица {found_tables.index(table) + 1}", color='red', fontsize=8)

    # Убираем дублирование легенды
    handles, labels = ax.get_legend_handles_labels()
    unique_labels = dict(zip(labels, handles))
    ax.legend(unique_labels.values(), unique_labels.keys(), loc='lower right')

    plt.show()


def text_extraction(element):
    """
    Извлекает текст и его форматы (шрифт/размер) из текстового элемента.
    """
    line_text = element.get_text()
    line_formats = []

    for text_line in element:
        if isinstance(text_line, LTTextContainer):
            for character in text_line:
                if isinstance(character, LTChar):
                    line_formats.append(character.fontname)
                    line_formats.append(character.size)

    format_per_line = list(set(line_formats))
    return (line_text, format_per_line)


def extract_table(pdf_path, page_num, table_num):
    """
    Извлекает данные конкретной таблицы с помощью pdfplumber.
    """
    with pdfplumber.open(pdf_path) as pdf:
        table_page = pdf.pages[page_num]
        table = table_page.extract_tables()[table_num]
    return table


def table_converter(table):
    """
    Преобразует список списков (таблицу) в Markdown-подобную строку.
    """
    table_string = ''
    for row in table:
        # Очистка: замена переносов строки на пробелы и None на 'None'
        cleaned_row = [
            item.replace('\n', ' ') if item is not None and '\n' in item else 'None' if item is None else item
            for item in row
        ]
        # Форматирование в строку |col1|col2|
        table_string += ('|' + '|'.join(cleaned_row) + '|' + '\n')

    return table_string.rstrip('\n')  # Удаляем последний разрыв строки


def crop_image(element, pageObj):
    """
    Вырезает область изображения из PDF и сохраняет ее как временный PDF.
    """
    [image_left, image_top, image_right, image_bottom] = [element.x0, element.y0, element.x1, element.y1]

    # Установка координат для обрезки страницы
    pageObj.mediabox.lower_left = (image_left, image_bottom)
    pageObj.mediabox.upper_right = (image_right, image_top)

    cropped_pdf_writer = PyPDF2.PdfWriter()
    cropped_pdf_writer.add_page(pageObj)

    with open('cropped_image.pdf', 'wb') as cropped_pdf_file:
        cropped_pdf_writer.write(cropped_pdf_file)


def convert_to_images(input_file):
    """
    Преобразует PDF-файл (обычно обрезанный) в PNG-изображение.
    """
    images = convert_from_path(input_file)
    image = images[0]
    output_file = "PDF_image.png"
    image.save(output_file, "PNG")
    return output_file


def image_to_text(image_path):
    """
    Считывает текст из изображения с помощью Tesseract OCR.
    """
    img = Image.open(image_path)
    # Используем lang='rus+eng' для двуязычного распознавания
    text = pytesseract.image_to_string(img, lang='rus+eng')
    return text


# --- 2. Основной Цикл Обработки PDF ---

# Находим путь к PDF (ЗАМЕНИ НА СВОЙ ПУТЬ)
pdf_path = '1234.pdf'
pagenum = 0
visualize_pdf_elements('12345.pdf', pagenum)

# Создаём объекты PyPDF2 для чтения и обработки страниц
pdfFileObj = open(pdf_path, 'rb')
pdfReaded = PyPDF2.PdfReader(pdfFileObj)

# Создаём словарь для хранения всего извлеченного контента
text_per_page = {}

# Извлекаем страницы из PDF
for pagenum, page in enumerate(extract_pages(pdf_path)):

    # Инициализируем переменные
    pageObj = pdfReaded.pages[pagenum]
    page_content = []  # Список для последовательного контента

    table_num = 0
    first_element = True
    table_extraction_flag = False

    # Открываем pdfplumber для текущей страницы
    pdf = pdfplumber.open(pdf_path)
    page_tables = pdf.pages[pagenum]
    # Находим все таблицы на странице
    tables = page_tables.find_tables()
    pdf.close()  # Закрываем pdfplumber после использования

    # Находим все элементы страницы (текст, прямоугольники, фигуры)
    page_elements = [(element.y1, element) for element in page._objs]
    print(f"{page._objs=}")
    print(f"{page_elements=}")
    # Сортируем все элементы по координате Y1 (сверху вниз)
    page_elements.sort(key=lambda a: a[0], reverse=True)

    # Итеративно обходим элементы
    for i, component in enumerate(page_elements):
        pos = component[0]
        element = component[1]

        if isinstance(element, LTTextBoxHorizontal):
            (line_text1, format_per_line) = text_extraction(element)
            print(f"{line_text1=} {format_per_line=} {LTTextBoxHorizontal}")



        # 1. Обработка Текста
        if isinstance(element, LTTextContainer):
            # Проверяем, не находится ли текст в области таблицы
            if table_extraction_flag == False:
                (line_text, format_per_line) = text_extraction(element)
                page_content.append(line_text)
                print(f"{line_text=}")
            # Иначе (text_extraction_flag == True) - пропускаем текст
            pass


        # 3. Обработка Таблиц (и соответствующих LTRect)
        elif isinstance(element, LTRect):
            if first_element == True and (table_num + 1) <= len(tables):
                # Находим границы таблицы
                lower_side = page.bbox[3] - tables[table_num].bbox[3]
                upper_side = element.y1

                # Извлекаем и конвертируем таблицу
                table = extract_table(pdf_path, pagenum, table_num)
                table_string = table_converter(table)
                page_content.append(table_string)

                # Устанавливаем флаг, чтобы пропускать текст внутри границ
                table_extraction_flag = True
                first_element = False

            # Проверяем, вышли ли мы из области таблицы
            if element.y0 >= lower_side and element.y1 <= upper_side:
                pass
            elif not isinstance(page_elements[i + 1][1], LTRect):
                # Сброс флагов, когда прямоугольник закончился
                table_extraction_flag = False
                first_element = True
                table_num += 1

    # Добавляем весь собранный контент в словарь
    dctkey = 'Page_' + str(pagenum)
    text_per_page[dctkey] = page_content

# Закрываем главный объект файла
pdfFileObj.close()

# --- 3. Финальный Вывод и Очистка ---

# Удаляем содержимое страницы (Для демонстрации выводим контент Page_0)
if 'Page_0' in text_per_page:
    result = ''.join(text_per_page['Page_0'])
    print("\n--- СТРУКТУРИРОВАННЫЙ КОНТЕНТ СТРАНИЦЫ 0 ---\n")
    print(result)
    with open("file.txt", "w", encoding="utf-8") as file:
        file.write(result)

else:
    print("Страница 0 не найдена.")

# Удаляем временные файлы OCR
# try:
#     if os.path.exists('cropped_image.pdf'):
#         os.remove('cropped_image.pdf')
#     if os.path.exists('PDF_image.png'):
#         os.remove('PDF_image.png')
#     print("\n[INFO] Временные файлы очищены.")
# except Exception as e:
#     print(f"\n[ERROR] Не удалось очистить временные файлы: {e}")