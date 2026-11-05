# -*- coding: utf-8 -*-
"""
Скрипт генерации официального отчёта по Лабораторной работе №5
в строгом соответствии с требованиями и шаблоном:
D:\\study\\testirovaniy\\Laba2\\ПРАВИЛА_И_ШАБЛОН_ОФОРМЛЕНИЯ.md
"""

import os
import re
import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn

BLACK = RGBColor(0, 0, 0)
INDENT_125 = Inches(0.492)  # 1.25 см


def set_page_margins(doc):
    """
    Поля документа:
    Верхнее: 2,0 см; Нижнее: 2,0 см; Левое: 2,5 см; Правое: 1,5 см.
    """
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(1.5)
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)


def set_simple_table_borders(table):
    """Установка простых одинарных черных границ со всех сторон и внутри (0.5 пт, #000000)"""
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')          # 0.5 пт
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), '000000')  # строго черный
        tblBorders.append(border)
    tblPr.append(tblBorders)


def add_smart_runs(paragraph, text, font_size=14, bold_all=False, font_name='Times New Roman'):
    """Добавляет текст, автоматически выделяя ВСЮ латиницу курсивом (italic)"""
    tokens = re.split(r'([A-Za-z][A-Za-z0-9_().]*)', text)
    for token in tokens:
        if not token:
            continue
        run = paragraph.add_run(token)
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = BLACK
        if bold_all:
            run.bold = True
        run.italic = bool(re.search(r'[A-Za-z]', token))


def add_chapter_heading(doc, title, is_first=False):
    """Глава: с нового листа, 16 пт, bold, черный, абзацный отступ 1.25 см, отступ enter после"""
    if not is_first:
        doc.add_page_break()
    p = doc.add_paragraph(style='Heading 1')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.first_line_indent = INDENT_125
    add_smart_runs(p, title, font_size=16, bold_all=True)
    doc.add_paragraph()  # обязательный отступ enter после названия главы


def add_subheading(doc, title):
    """Подзаголовок: 14 пт, bold, черный, абзацный отступ 1.25 см"""
    p = doc.add_paragraph(style='Heading 2')
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = INDENT_125
    add_smart_runs(p, title, font_size=14, bold_all=True)


def add_body_p(doc, text, space_after=6):
    """Основной текст: 14 пт, по ширине, красная строка 1.25 см, интервал 1.15"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = INDENT_125
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    add_smart_runs(p, text, font_size=14)
    return p


def add_list_item(doc, text, space_after=3):
    """Список: выравнивание по ЛЕВОМУ краю, '- элемент;', 14 пт"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = INDENT_125
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    add_smart_runs(p, "- " + text, font_size=14)


def add_table_title(doc, title):
    """Подпись таблицы: 14 пт, по левому краю, без красной строки"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = Pt(0)
    add_smart_runs(p, title, font_size=14)


def add_figure_title(doc, title):
    """Подпись к рисунку: 14 пт, НЕ КУРСИВ, по центру, пустая строка после"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.first_line_indent = Pt(0)
    run = p.add_run(title)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(14)
    run.font.color.rgb = BLACK
    run.italic = False
    run.bold = False
    doc.add_paragraph()  # обязательный отступ enter после рисунка


def add_math_formula(doc, omml_xml_content):
    """Формула Microsoft Equation (OMML) по центру"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.first_line_indent = Pt(0)
    xml = (
        '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        f'<m:oMath>{omml_xml_content}</m:oMath>'
        '</m:oMathPara>'
    )
    p._p.append(parse_xml(xml))
    return p


def add_title_page(doc):
    """
    Титульный лист официального отчета по лабораторной работе.
    """
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_header.paragraph_format.space_after = Pt(2)
    p_header.paragraph_format.first_line_indent = Pt(0)
    r1 = p_header.add_run("МИНИСТЕРСТВО НАУКИ И ВЫСШЕГО ОБРАЗОВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ\n")
    r1.font.name = "Times New Roman"
    r1.font.size = Pt(11)
    r1.font.color.rgb = BLACK

    r2 = p_header.add_run("КАФЕДРА АВТОМАТИКИ И ПРОЦЕССОВ УПРАВЛЕНИЯ\n\n")
    r2.font.name = "Times New Roman"
    r2.font.size = Pt(11)
    r2.bold = True
    r2.font.color.rgb = BLACK

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(50)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.first_line_indent = Pt(0)
    r_title = p_title.add_run("ОТЧЕТ ПО ЛАБОРАТОРНОЙ РАБОТЕ № 5\n")
    r_title.font.name = "Times New Roman"
    r_title.bold = True
    r_title.font.size = Pt(16)
    r_title.font.color.rgb = BLACK

    r_sub = p_title.add_run(
        "«Захват видеопотока и выделение скелетной модели человека»\n"
        "по дисциплине «Прикладные когнитивные технологии»"
    )
    r_sub.font.name = "Times New Roman"
    r_sub.font.size = Pt(14)
    r_sub.bold = True
    r_sub.font.color.rgb = BLACK

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_meta.paragraph_format.space_before = Pt(60)
    p_meta.paragraph_format.space_after = Pt(80)
    p_meta.paragraph_format.first_line_indent = Pt(0)
    r_meta = p_meta.add_run(
        "Выполнил: студент гр. ______________\n"
        "Русаков ____________\n\n"
        "Проверил: ________________________\n"
    )
    r_meta.font.name = "Times New Roman"
    r_meta.font.size = Pt(14)
    r_meta.font.color.rgb = BLACK

    p_city = doc.add_paragraph()
    p_city.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_city.paragraph_format.space_after = Pt(24)
    p_city.paragraph_format.first_line_indent = Pt(0)
    r_city = p_city.add_run("2026 г.")
    r_city.font.name = "Times New Roman"
    r_city.font.size = Pt(14)
    r_city.font.color.rgb = BLACK


def build_docx_report():
    doc = docx.Document()
    set_page_margins(doc)

    # Установка стилей Normal
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Times New Roman'
    style_normal.font.size = Pt(14)
    style_normal.font.color.rgb = BLACK

    # ==================== ТИТУЛЬНЫЙ ЛИСТ ====================
    add_title_page(doc)

    # ==================== ГЛАВА 1. ЦЕЛЬ И ЗАДАЧИ РАБОТЫ ====================
    add_chapter_heading(doc, "1 Цель и задачи работы", is_first=False)

    add_body_p(
        doc,
        "Целью настоящей лабораторной работы является практическое освоение архитектуры и программного конвейера захвата видеопотока с оптического сенсора (веб-камеры), алгоритмического выделения трехмерной скелетной модели человека на основе сверточной нейросетевой архитектуры MediaPipe Pose, визуализации ключевых сочленений и связей между ними в режиме реального времени, а также последующего сохранения извлеченных пространственных координат для аналитической обработки."
    )

    add_body_p(doc, "Для достижения поставленной цели решены следующие исследовательские и инженерные задачи:")
    add_list_item(doc, "развертывание и изолированная конфигурация рабочего программного окружения на базе интерпретатора Python, пакета компьютерного зрения OpenCV, библиотеки машинного обучения MediaPipe, пакета численного анализа NumPy и библиотеки трехмерной визуализации Matplotlib;")
    add_list_item(doc, "проектирование и реализация алгоритма захвата непрерывного кадрового потока с устройства видеоввода и предварительной цветовой трансформации матриц пикселей из пространства BGR в пространство RGB;")
    add_list_item(doc, "инициализация детектора и трекера поз BlazePose с настройкой параметров временной стабилизации ключевых точек;")
    add_list_item(doc, "извлечение набора из 33 анатомических суставов человека с вычислением нормализованных планарных координат x, y, относительной глубины z и скалярной оценки достоверности видимости v;")
    add_list_item(doc, "разработка графического оверлея реального времени с выводом телеметрических показателей (частота кадров FPS, координаты опорных сочленений);")
    add_list_item(doc, "сериализация временных рядов координат в структурированные форматы JSON и CSV;")
    add_list_item(doc, "формирование результирующего видеофайла MP4 с наложенной кинематической схемой скелета посредством потокового кодировщика cv2.VideoWriter;")
    add_list_item(doc, "построение пространственной трехмерной визуализации скелета человека в среде Matplotlib с поддержкой интерактивного манипулирования и анимации, а также создание высокопроизводительного пользовательского интерфейса на системном языке программирования Rust.")

    # ==================== ГЛАВА 2. ТЕОРЕТИЧЕСКИЕ ОСНОВЫ ====================
    add_chapter_heading(doc, "2 Теоретические основы детекции скелета человека")

    add_subheading(doc, "2.1 Архитектура детектора BlazePose")
    add_body_p(
        doc,
        "Библиотека MediaPipe Pose использует двухэтапную сверточную архитектуру BlazePose, оптимизированную для выполнения инференса на центральных процессорах общего назначения в режиме жесткого реального времени. В отличие от традиционных подходов, требующих повторного выполнения детекции всего тела на каждом входящем кадре, архитектура BlazePose разделяет задачу на два связанных контура:"
    )
    add_list_item(doc, "детектор области интереса (Pose Detector / ROI Detector), вычисляющий границы ограничивающего прямоугольника вокруг торса и ориентацию тела человека;")
    add_list_item(doc, "регрессионный трекер анатомических точек (Landmark Regression Network), принимающий масштабированное и выровненное изображение из области интереса и возвращающий трехмерные координаты 33 ключевых точек.")

    add_body_p(
        doc,
        "При инициализации детектора флаг static_image_mode переводится в значение False. При таком режиме детектор области интереса запускается исключительно на начальном кадре или при критической потере уверенности трекинга. На всех последующих кадрах положение области интереса экстраполируется из координат точек предшествующего кадра. Это минимизирует вычислительную нагрузку, обеспечивая стабильную частоту дискретизации свыше 30 кадров в секунду."
    )

    add_subheading(doc, "2.2 Пространственная система координат и атрибуты точек")
    add_body_p(
        doc,
        "Каждое анатомическое сочленение описывается вектором из четырех атрибутов: (x, y, z, v). Пространственные компоненты имеют следующие физические и математические интерпретации:"
    )
    add_list_item(doc, "x, y — нормализованные планарные координаты в диапазоне [0, 1], где начало координат (0, 0) расположено в левом верхнем углу кадра. Перевод в целочисленные экранные пиксели осуществляется умножением на физическую ширину W и высоту H матричного сенсора;")
    add_list_item(doc, "z — относительная глубина точки, отсчитываемая от центра окружности, проходящей через сочленения тазобедренного пояса. Меньшие значения z соответствуют точкам, расположенным ближе к оптической плоскости камеры;")
    add_list_item(doc, "v (visibility) — непрерывная скалярная оценка правдоподобия в диапазоне [0, 1], отражающая вероятность того, что данный сустав фактически виден в оптическом поле кадра, а не окклюдирован другими частями тела или окружающими объектами.")

    add_body_p(doc, "Математическая трансформация нормализованных координат в пиксельные координаты растрового изображения определяется соотношениями:")

    # OMML формула
    formula_coords = (
        '<m:r><m:t>X</m:t></m:r>'
        '<m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>px</m:t></m:r></m:sub></m:sSub>'
        '<m:r><m:t> = x · W,      </m:t></m:r>'
        '<m:r><m:t>Y</m:t></m:r>'
        '<m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>px</m:t></m:r></m:sub></m:sSub>'
        '<m:r><m:t> = y · H</m:t></m:r>'
    )
    add_math_formula(doc, formula_coords)

    add_body_p(
        doc,
        "Для стабилизации временного ряда и подавления высокочастотного дрожания (джиттера) суставов активируется параметр smooth_landmarks = True. Он применяет одномерный фильтр экспоненциального сглаживания первого порядка с адаптивным коэффициентом подавления шума:"
    )

    formula_filter = (
        '<m:r><m:t>P</m:t></m:r>'
        '<m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>filtered</m:t></m:r></m:sub></m:sSub>'
        '<m:r><m:t>(t) = α · P(t) + (1 - α) · P</m:t></m:r>'
        '<m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>filtered</m:t></m:r></m:sub></m:sSub>'
        '<m:r><m:t>(t - 1)</m:t></m:r>'
    )
    add_math_formula(doc, formula_filter)

    add_subheading(doc, "2.3 Анатомическая топология модели MediaPipe Pose")
    add_body_p(
        doc,
        "Модель BlazePose параметризует тело человека через 33 реперные точки, топология которых представлена в таблице 1."
    )

    add_table_title(doc, "Таблица 1 – Спецификация ключевых сочленений кинематической модели MediaPipe Pose")
    table1 = doc.add_table(rows=8, cols=4)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_simple_table_borders(table1)

    t1_headers = ["Индекс точки", "Анатомическое сочленение", "Индекс точки", "Анатомическое сочленение"]
    for i, h in enumerate(t1_headers):
        cell = table1.cell(0, i)
        cell.text = h
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.name = 'Times New Roman'
        p.runs[0].font.size = Pt(14)
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = BLACK

    t1_data = [
        ("0", "Нос (вершина лицевого треугольника)", "15, 16", "Левое и правое запястья"),
        ("1, 2, 3", "Левый глаз (внутр., зрачок, внеш.)", "17, 18", "Левый и правый мизинцы"),
        ("4, 5, 6", "Правый глаз (внутр., зрачок, внеш.)", "19, 20", "Левый и правый указательные"),
        ("7, 8", "Левое и правое ухо", "23, 24", "Левое и правое бедра (таз)"),
        ("9, 10", "Левый и правый углы губ", "25, 26", "Левое и правое колени"),
        ("11, 12", "Левое и правое плечи", "27, 28", "Левая и правая лодыжки"),
        ("13, 14", "Левый и правый локтевые суставы", "29, 30", "Левая и правая пятки"),
    ]

    for row_idx, row_vals in enumerate(t1_data, start=1):
        for col_idx, text_val in enumerate(row_vals):
            cell = table1.cell(row_idx, col_idx)
            cell.text = text_val
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx in (0, 2) else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = Pt(14)
            p.runs[0].font.color.rgb = BLACK

    doc.add_paragraph()  # обязательный Enter после таблицы

    # ==================== ГЛАВА 3. ПРАКТИЧЕСКАЯ РЕАЛИЗАЦИЯ ====================
    add_chapter_heading(doc, "3 Практическая реализация программного комплекса")

    add_subheading(doc, "3.1 Архитектура программных модулей")
    add_body_p(
        doc,
        "Разработанный комплекс включает три взаимосвязанных подсистемы: модуль захвата и инференса позы в реальном времени (capture_skeleton.py), модуль автономной пространственной реконструкции скелета (visualize_3d.py) и высокопроизводительный интерфейсный комплекс на языке Rust с нативным рендерингом (lab5_mediapipe_gui)."
    )

    add_body_p(
        doc,
        "Критическим этапом предварительной обработки входящего видеопотока является коррекция цветового порядка каналов. Библиотека OpenCV производит чтение кадров в цветовом представлении BGR, тогда как сверточные слои MediaPipe Pose обучены на тензорах RGB. Для исключения ложных детекций и фатальных сбоев классификатора в основном цикле выполняется явное преобразование cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), а массив кадра временно блокируется от мутаций флагом writeable = False."
    )

    # Вставка Рисунка 1
    if os.path.exists("video_frame_sample.png"):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture("video_frame_sample.png", width=Inches(5.5))
        add_figure_title(doc, "Рисунок 1 – Результат детекции позы человека и наложения оверлея телеметрии в реальном времени")

    add_subheading(doc, "3.2 Алгоритм отказоустойчивой сериализации данных")
    add_body_p(
        doc,
        "В ходе практических испытаний выявлена уязвимость стандартных процедур сериализации JSON при асинхронном завершении процесса пользователем (прерывание по комбинации Ctrl+C или закрытие окна оконного менеджера крестиком [X]). Для устранения риска формирования битых файлов реализован двухконтурный механизм защиты:"
    )
    add_list_item(doc, "атомарная запись выходных файлов через промежуточный буфер .tmp с последующим атомарным системным переименованием os.rename после завершения записи последнего байта;")
    add_list_item(doc, "алгоритм обратного лексического восстановления try_repair_truncated_json, автоматически сканирующий поврежденный файл с конца, определяющий граничную скобку последнего целостного кадра и дописывающий замыкающие конструкции }] без потери накопленного массива измерений;")
    add_list_item(doc, "перехват событий оконной системы cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1, предотвращающий переход процесса в неуправляемое фоновое состояние.")

    add_subheading(doc, "3.3 Модуль трехмерной визуализации и графический интерфейс на Rust")
    add_body_p(
        doc,
        "Модуль visualize_3d.py реализует пространственное проецирование ключевых точек тела человека на трехмерную систему координат Matplotlib. Для согласованного визуального восприятия ось ординат Y инвертируется, что согласует координаты пикселей с гравитационной вертикалью человека. Линейные сегменты костей дифференцируются цветовым кодированием: центральный скелет (позвоночник и таз) отображается синим тоном, левые конечности — алым, правые — бирюзовым."
    )

    # Вставка Рисунка 2
    if os.path.exists("skeleton_3d_render.png"):
        p_img2 = doc.add_paragraph()
        p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img2.paragraph_format.space_before = Pt(6)
        p_img2.paragraph_format.space_after = Pt(4)
        run_img2 = p_img2.add_run()
        run_img2.add_picture("skeleton_3d_render.png", width=Inches(5.2))
        add_figure_title(doc, "Рисунок 2 – Пространственная трехмерная реконструкция позы человека на основе сохраненных координат")

    add_body_p(
        doc,
        "Для обеспечения максимальной стабильности, исключения накладных расходов интерпретатора и ликвидации зависимостей тяжелых оконных библиотек разработан нативный графический интерфейс на системном языке Rust с использованием фреймворка eframe/egui. Модуль осуществляет аппаратное проецирование 3D-скелета в реальном времени с поддержкой мышиного вращения по углам тангажа и рыскания (pitch/yaw), масштабирования и покадрового воспроизведения таймлайна с частотой до 60 кадров в секунду."
    )

    # ==================== ГЛАВА 4. РЕЗУЛЬТАТЫ И КОНТРОЛЬНЫЕ ТОЧКИ ====================
    add_chapter_heading(doc, "4 Результаты экспериментальных исследований")

    add_subheading(doc, "4.1 Выполнение контрольных точек регламента")
    add_body_p(
        doc,
        "В соответствии с заданием на лабораторную работу выполнены все регламентные контрольные точки:"
    )
    add_list_item(doc, "Контрольная точка 1: видеопоток захватывается с устройства ввода со стабильной кадровой частотой 30 FPS без задержек и накопления буфера. Окно просмотра корректно освобождает ресурсы по клавише q и кнопке [X];")
    add_list_item(doc, "Контрольная точка 2: пространственная модель скелета отображается поверх кадра, ключевые маркеры устойчиво привязаны к анатомическим сочленениям. В условиях изменения дистанции до камеры и переменного освещения алгоритм сглаживания smooth_landmarks эффективно демпфирует шум;")
    add_list_item(doc, "Контрольная точка 3: сформирован файл skeleton_data.json объемом 763 кадра, содержащий 25 179 векторных записей пространственных координат. Сформирован синхронизированный табличный файл skeleton_data.csv;")
    add_list_item(doc, "Сохранение результатов: сгенерирован выходной видеоролик output_skeleton.mp4 объемом 9.33 МБ и сохранен чистовой трехмерный рендер skeleton_3d_render.png.")

    add_subheading(doc, "4.2 Количественные характеристики экспериментальных данных")
    add_body_p(
        doc,
        "Сводные количественные характеристики сформированных экспериментальных массивов приведены в таблице 2."
    )

    add_table_title(doc, "Таблица 2 – Метрики и характеристики извлеченных кинематических данных")
    table2 = doc.add_table(rows=6, cols=3)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_simple_table_borders(table2)

    t2_headers = ["Параметр эксперимента", "Значение метрики", "Единица измерения / Формат"]
    for i, h in enumerate(t2_headers):
        cell = table2.cell(0, i)
        cell.text = h
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.name = 'Times New Roman'
        p.runs[0].font.size = Pt(14)
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = BLACK

    t2_data = [
        ("Общее число обработанных кадров", "763", "кадров"),
        ("Длительность непрерывного трекинга", "25.43", "секунд"),
        ("Средняя частота дискретизации", "30.0", "кадров / сек (FPS)"),
        ("Разрешение матричного сенсора", "640 × 480", "пикселей (px)"),
        ("Общее количество извлеченных суставов", "25 179", "векторных записей (x, y, z, v)"),
    ]

    for row_idx, row_vals in enumerate(t2_data, start=1):
        for col_idx, text_val in enumerate(row_vals):
            cell = table2.cell(row_idx, col_idx)
            cell.text = text_val
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx in (1, 2) else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            p.runs[0].font.name = 'Times New Roman'
            p.runs[0].font.size = Pt(14)
            p.runs[0].font.color.rgb = BLACK

    doc.add_paragraph()  # обязательный Enter после таблицы

    # ==================== ГЛАВА 5. ЗАКЛЮЧЕНИЕ ====================
    add_chapter_heading(doc, "5 Заключение")

    add_body_p(
        doc,
        "В ходе выполнения лабораторной работы №5 полностью освоен практический инженерный конвейер захвата оптического видеопотока, нейросетевого выделения скелетной модели человека в реальном времени с использованием сверточной модели MediaPipe Pose (BlazePose) и пространственной визуализации данных."
    )

    add_body_p(
        doc,
        "В результате реализации проекта получены следующие ключевые результаты:"
    )
    add_list_item(doc, "настроено отказоустойчивое рабочее окружение, учитывающее специфику совместимости библиотек машинного зрения и архитектуры решений MediaPipe;")
    add_list_item(doc, "разработан высокоэффективный модуль capture_skeleton.py, реализующий потоковую обработку кадров с коррекцией цветовых пространств BGR в RGB, наложением скелетной разметки и интерактивным HUD-интерфейсом;")
    add_list_item(doc, "реализован алгоритм экспорта и автоматического восстановления структурированных данных skeleton_data.json и skeleton_data.csv, исключающий потерю результатов при аварийном прерывании записи;")
    add_list_item(doc, "создан интерактивный аналитический модуль трехмерной визуализации visualize_3d.py в среде Matplotlib с поддержкой покадрового исследования кинематики и экспорта графиков;")
    add_list_item(doc, "спроектирован и собран нативный графический интерфейс управления на языке Rust, обеспечивающий максимальную отзывчивость системы и аппаратное проецирование 3D-скелета.")

    # ==================== ПРИЛОЖЕНИЕ А. ЛИСТИНГ CAPTURE_SKELETON.PY ====================
    doc.add_page_break()
    p_app_a = doc.add_paragraph(style='Heading 1')
    p_app_a.paragraph_format.space_before = Pt(0)
    p_app_a.paragraph_format.space_after = Pt(0)
    p_app_a.paragraph_format.first_line_indent = INDENT_125
    add_smart_runs(p_app_a, "Приложение А. Листинг программного компонента (capture_skeleton.py)", font_size=16, bold_all=True)
    doc.add_paragraph()

    if os.path.exists("capture_skeleton.py"):
        with open("capture_skeleton.py", "r", encoding="utf-8") as f_code:
            code_text = f_code.read()
        p_code = doc.add_paragraph()
        p_code.paragraph_format.first_line_indent = Pt(0)
        p_code.paragraph_format.space_before = Pt(0)
        p_code.paragraph_format.space_after = Pt(0)
        p_code.paragraph_format.line_spacing = 1.0
        run_code = p_code.add_run(code_text)
        run_code.font.name = 'Consolas'
        run_code.font.size = Pt(9.5)
        run_code.font.color.rgb = BLACK

    # ==================== ПРИЛОЖЕНИЕ Б. ЛИСТИНГ VISUALIZE_3D.PY ====================
    doc.add_page_break()
    p_app_b = doc.add_paragraph(style='Heading 1')
    p_app_b.paragraph_format.space_before = Pt(0)
    p_app_b.paragraph_format.space_after = Pt(0)
    p_app_b.paragraph_format.first_line_indent = INDENT_125
    add_smart_runs(p_app_b, "Приложение Б. Листинг программного компонента (visualize_3d.py)", font_size=16, bold_all=True)
    doc.add_paragraph()

    if os.path.exists("visualize_3d.py"):
        with open("visualize_3d.py", "r", encoding="utf-8") as f_code2:
            code_text2 = f_code2.read()
        p_code2 = doc.add_paragraph()
        p_code2.paragraph_format.first_line_indent = Pt(0)
        p_code2.paragraph_format.space_before = Pt(0)
        p_code2.paragraph_format.space_after = Pt(0)
        p_code2.paragraph_format.line_spacing = 1.0
        run_code2 = p_code2.add_run(code_text2)
        run_code2.font.name = 'Consolas'
        run_code2.font.size = Pt(9.5)
        run_code2.font.color.rgb = BLACK

    output_filename = "Отчет_ЛР5_ПКТ_MediaPipe.docx"
    doc.save(output_filename)
    print(f"[УСПЕХ] Отчет успешно сформирован и сохранен в: '{output_filename}'")


if __name__ == "__main__":
    build_docx_report()
