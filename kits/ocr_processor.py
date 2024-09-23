from paddleocr import PaddleOCR
from kits.image_processor import preprocess_image, is_blank_page
from kits.doc_type_classify_processor import find_best_match
from kits.log_processor import logger
import os
import re
import csv
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from kits.file_processor import save_document_pages

def process_pdf(args):
    """处理单个 PDF 文件"""
    pdf_path, output_dir, document_types = args
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    logger.info(f"正在处理文件：{pdf_name}")

    try:
        # 将所有页面转换为图像
        images = convert_from_path(pdf_path)
        # 打开 PDF
        reader = PdfReader(pdf_path)
    except Exception as e:
        logger.error(f"无法处理 PDF 文件 {pdf_name}：{e}")
        return

    page_info = []  # 用于存储每页的信息
    page_types = []  # 用于存储每页的文档类型

    # 初始化 PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')

    # 第一次遍历：识别每页的文档类型
    previous_doc_type = None
    for i, image in enumerate(images):
        logger.info(f"处理第 {i + 1} 页")

        if is_blank_page(image):
            logger.info(f"第 {i + 1} 页是空白页")
            page_types.append("空白页")
            previous_doc_type = "空白页"
            continue

        try:
            preprocessed_image = preprocess_image(image)
            result = ocr.ocr(preprocessed_image, cls=True)
            text = ' '.join([line[1][0] for line in result[0]])
            text_cleaned = re.sub(r'\s+', '', text)

            logger.debug(f"OCR 提取的文本：\n{text}")
            logger.debug(f"清理后的文本：{text_cleaned}")

            doc_type = find_best_match(text_cleaned, document_types)
            
            if doc_type == "其他":
                if previous_doc_type and previous_doc_type != "空白页":
                    doc_type = previous_doc_type
                    logger.info(f"第 {i + 1} 页无法判断类型，归类为前一页类型：{doc_type}")
                else:
                    logger.info(f"第 {i + 1} 页无法判断类型，归类为其他")
            
            page_types.append(doc_type)
            previous_doc_type = doc_type
        except Exception as e:
            logger.error(f"OCR 处理页面 {i + 1} 时出错：{e}")
            page_types.append("其他")

    # 第二次遍历：根据识别结果保存文档
    current_doc_type = None
    pages_for_current_doc = []

    for i, doc_type in enumerate(page_types):
        if doc_type != current_doc_type:
            # 保存之前的文档页
            if pages_for_current_doc:
                logger.info(f"保存文档类型 '{current_doc_type}' 的页面：{[idx + 1 for idx in pages_for_current_doc]}")
                output_filename = save_document_pages(reader, pages_for_current_doc, pdf_name, current_doc_type, output_dir)
                if output_filename:
                    for page_num in pages_for_current_doc:
                        page_info.append([page_num + 1, output_filename])
                pages_for_current_doc = []
            current_doc_type = doc_type

        if doc_type != "空白页":
            pages_for_current_doc.append(i)

    # 保存最后一个文档
    if pages_for_current_doc:
        logger.info(f"保存文档类型 '{current_doc_type}' 的页面：{[idx + 1 for idx in pages_for_current_doc]}")
        output_filename = save_document_pages(reader, pages_for_current_doc, pdf_name, current_doc_type, output_dir)
        if output_filename:
            for page_num in pages_for_current_doc:
                page_info.append([page_num + 1, output_filename])

    # 保存 CSV 文件
    csv_filename = os.path.join(output_dir, f"{pdf_name}_page_info.csv")
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['页码', '文件名'])
        csv_writer.writerows(page_info)
    logger.info(f"已保存页面信息到 CSV 文件：{csv_filename}")