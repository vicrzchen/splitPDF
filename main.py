import os
import re
import logging
import json
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from PIL import Image, ImageOps
from PyPDF2 import PdfReader, PdfWriter
import jieba
import numpy as np
from multiprocessing import Pool
import ast
import csv
import cv2

def setup_logging():
    # 检查日志文件的路径是否正确
    log_file_path = os.path.join(os.getcwd(), 'process.log')
    print(f"日志文件路径：{log_file_path}")

    # 创建日志记录器并设置日志级别
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # 创建日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 创建文件处理器，将日志记录到文件
    file_handler = logging.FileHandler(log_file_path, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 创建控制台处理器，将日志输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 将处理器添加到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()


# 定义停用词列表（可根据需要扩充）
stopwords = set(['的', '了', '和', '是', '在', '对', '及', '与', '有', '不'])

def sanitize_filename(filename):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def preprocess_text(text):
    """预处理文本，保留中文字符，分词并去除停用词"""
    # 去除非中文字符
    text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
    # 使用 jieba 分词
    words = jieba.lcut(text)
    # 去除停用词
    words = [word for word in words if word not in stopwords]
    return words

def evaluate_expression(expression, text):
    """
    安全地评估逻辑表达式，表达式可以包含:
    - and, or, not
    - 括号 ()
    - contains('关键词')
    - percentage('关键词', 阈值)
    """
    # 定义包含函数，检查关键词是否在文本中
    def contains(keyword):
        return keyword in text

    # 定义百分比函数，检查关键词在文本中的出现频率
    def percentage(keyword, threshold):
        word_count = len(text.split())
        keyword_count = text.count(keyword)
        return (keyword_count / word_count) * 100 >= threshold

    # 定义允许的节点类型
    allowed_nodes = (
        ast.Expression, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.Compare,
        ast.Call, ast.Load, ast.Name, ast.Str, ast.Constant, ast.Num,
        ast.And, ast.Or, ast.Not, ast.USub, ast.Subscript, ast.Index
    )

    # 将表达式解析为 AST
    try:
        node = ast.parse(expression, mode='eval')
    except Exception as e:
        logger.error(f"解析表达式 '{expression}' 时出错：{e}")
        return False

    # 检查 AST 中的所有节点是否都是允许的类型
    for subnode in ast.walk(node):
        if not isinstance(subnode, allowed_nodes):
            raise ValueError(f"表达式包含不允许的节点：{ast.dump(subnode)}")

    # 定义安全的全局和局部命名空间
    safe_globals = {'contains': contains, 'percentage': percentage, '__builtins__': None}
    safe_locals = {}

    # 评估表达式
    try:
        result = eval(compile(node, filename='', mode='eval'), safe_globals, safe_locals)
    except Exception as e:
        logger.error(f"评估表达式 '{expression}' 时出错：{e}")
        result = False

    return result

def find_best_match(text, document_types):
    """根据表达式匹配文档类型"""
    best_match = '其他'
    max_length = 0
    for doc_type, info in document_types.items():
        expression = info.get('expression', '')
        if not expression:
            continue
        try:
            match = evaluate_expression(expression, text)
            logger.debug(f"文档类型 '{doc_type}' 的表达式评估结果：{match}")
            if match:
                # 计算匹配文本的长度
                match_length = len(expression)
                if match_length > max_length:
                    max_length = match_length
                    best_match = doc_type
        except Exception as e:
            logger.error(f"评估文档类型 '{doc_type}' 的表达式时出错：{e}")
    
    logger.info(f"文本匹配结果：{best_match}")
    return best_match

def save_document_pages(reader, page_indices, pdf_name, doc_type, output_dir):
    """将指定的页面保存为新的 PDF 文件，避免文件名重复"""
    writer = PdfWriter()
    for idx in page_indices:
        try:
            page = reader.pages[idx]
            writer.add_page(page)
        except Exception as e:
            logger.error(f"添加页面 {idx + 1} 时出错：{e}")

    if not writer.pages:
        logger.info(f"没有需要保存的页面，跳过保存文档类型 '{doc_type}'")
        return None

    # 处理文件命名，避免重复
    base_filename = sanitize_filename(f"{pdf_name}_{doc_type}")
    output_filename = base_filename + ".pdf"
    counter = 1
    while os.path.exists(os.path.join(output_dir, output_filename)):
        output_filename = f"{base_filename}-{counter}.pdf"
        counter += 1

    output_path = os.path.join(output_dir, output_filename)
    try:
        with open(output_path, 'wb') as f:
            writer.write(f)
        logger.info(f"保存文件：{output_filename}")
        return output_filename
    except Exception as e:
        logger.error(f"保存文件 {output_filename} 时出错：{e}")
        return None

def is_blank_page(image):
    """判断页面是否为空白页"""
    gray = image.convert('L')
    histogram = gray.histogram()
    # 计算非白色像素的比例
    non_white_pixels = sum(histogram[:-10])  # 排除接近白色的像素
    total_pixels = sum(histogram)
    ratio = non_white_pixels / total_pixels
    return ratio < 0.01  # 比例小于 1% 认为是空白页

def preprocess_image(image):
    """对图像进行预处理，提高 OCR 准确性"""
    # 将PIL图像转换为NumPy数组
    np_image = np.array(image)
    
    # 检查图像是否为RGB格式
    if len(np_image.shape) == 3 and np_image.shape[2] == 3:
        # 转换为灰度图像
        gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
    else:
        gray = np_image
    
    # 自动对比度调整
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    
    # 二值化处理
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary

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
    for i, image in enumerate(images):
        logger.info(f"处理第 {i + 1} 页")

        if is_blank_page(image):
            logger.info(f"第 {i + 1} 页是空白页")
            page_types.append("空白页")
            continue

        try:
            preprocessed_image = preprocess_image(image)
            result = ocr.ocr(preprocessed_image, cls=True)
            text = ' '.join([line[1][0] for line in result[0]])
            text_cleaned = re.sub(r'\s+', '', text)

            logger.debug(f"OCR 提取的文本：\n{text}")
            logger.debug(f"清理后的文本：{text_cleaned}")

            doc_type = find_best_match(text_cleaned, document_types)
            page_types.append(doc_type)
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

def main():
    # 输入和输出目录
    input_dir = './input'  # 替换为你的 PDF 文件夹路径
    output_dir = './output'  # 替换为你想保存输出文件的路径

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 加载文档类型配置
    with open('document_types.json', 'r', encoding='utf-8') as f:
        document_types = json.load(f)

    pdf_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]

    # 使用多进程加速处理
    pool_args = [(pdf_path, output_dir, document_types) for pdf_path in pdf_files]
    with Pool(processes=4) as pool:
        pool.map(process_pdf, pool_args)

if __name__ == '__main__':
    main()
    # 手动刷新日志流，确保日志写入文件
    logging.shutdown()