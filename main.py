import os
import re
import logging
import json
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageOps
from PyPDF2 import PdfReader, PdfWriter
import jieba
import numpy as np
from multiprocessing import Pool
import ast

# 设置日志记录，保存到文件 'process.log'
logging.basicConfig(
    level=logging.DEBUG,  # 根据需要调整日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='process.log',
    filemode='w'
)

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
    """
    # 定义包含函数，检查关键词是否在文本中
    def contains(keyword):
        return keyword in text

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
        logging.error(f"解析表达式 '{expression}' 时出错：{e}")
        return False

    # 检查 AST 中的所有节点是否都是允许的类型
    for subnode in ast.walk(node):
        if not isinstance(subnode, allowed_nodes):
            raise ValueError(f"表达式包含不允许的节点：{ast.dump(subnode)}")

    # 定义安全的全局和局部命名空间
    safe_globals = {'contains': contains, '__builtins__': None}
    safe_locals = {}

    # 评估表达式
    try:
        result = eval(compile(node, filename='', mode='eval'), safe_globals, safe_locals)
    except Exception as e:
        logging.error(f"评估表达式 '{expression}' 时出错：{e}")
        result = False

    return result

def find_best_match(text, document_types):
    """根据表达式匹配文档类型"""
    best_match = '其他'
    for doc_type, info in document_types.items():
        expression = info.get('expression', '')
        if not expression:
            continue
        try:
            match = evaluate_expression(expression, text)
            logging.debug(f"文档类型 '{doc_type}' 的表达式评估结果：{match}")
            if match:
                best_match = doc_type
                logging.info(f"文本匹配结果：{best_match}")
                break  # 找到匹配的文档类型，退出循环
        except Exception as e:
            logging.error(f"评估文档类型 '{doc_type}' 的表达式时出错：{e}")
    return best_match

def save_document_pages(reader, page_indices, pdf_name, doc_type, output_dir):
    """将指定的页面保存为新的 PDF 文件，避免文件名重复"""
    writer = PdfWriter()
    for idx in page_indices:
        try:
            page = reader.pages[idx]
            writer.add_page(page)
        except Exception as e:
            logging.error(f"添加页面 {idx + 1} 时出错：{e}")

    if not writer.pages:
        logging.info(f"没有需要保存的页面，跳过保存文档类型 '{doc_type}'")
        return

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
        logging.info(f"保存文件：{output_filename}")
    except Exception as e:
        logging.error(f"保存文件 {output_filename} 时出错：{e}")

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
    gray = image.convert('L')  # 转为灰度
    # 自动对比度
    gray = ImageOps.autocontrast(gray)
    # 二值化处理
    binary = gray.point(lambda x: 0 if x < 160 else 255, '1')
    return binary

def process_pdf(args):
    """处理单个 PDF 文件"""
    pdf_path, output_dir, document_types = args
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    logging.info(f"正在处理文件：{pdf_name}")

    try:
        # 将所有页面转换为图像
        images = convert_from_path(pdf_path)
        # 打开 PDF
        reader = PdfReader(pdf_path)
    except Exception as e:
        logging.error(f"无法处理 PDF 文件 {pdf_name}：{e}")
        return

    current_doc_type = '其他'
    pages_for_current_doc = []
    new_doc_type = '其他'  # 初始化 new_doc_type

    for i, image in enumerate(images):
        logging.info(f"处理第 {i + 1} 页")

        # 判断是否为空白页
        if is_blank_page(image):
            logging.info(f"第 {i + 1} 页是空白页，已跳过")
            # 空白页后面是新文档的开始
            if pages_for_current_doc:
                logging.info(f"遇到空白页，保存当前文档类型 '{current_doc_type}' 的页面：{[idx + 1 for idx in pages_for_current_doc]}")
                save_document_pages(reader, pages_for_current_doc, pdf_name, current_doc_type, output_dir)
                pages_for_current_doc = []
            current_doc_type = '其他'  # 重置文档类型
            continue

        try:
            # 预处理图像
            preprocessed_image = preprocess_image(image)

            # 运行 OCR
            text = pytesseract.image_to_string(preprocessed_image, lang='chi_sim')
            text_cleaned = re.sub(r'\s+', '', text)  # 移除所有空白字符

            logging.debug(f"OCR 提取的文本：\n{text}")
            logging.debug(f"清理后的文本：{text_cleaned}")

            # 查找最佳匹配的文档类型
            new_doc_type = find_best_match(text_cleaned, document_types)
        except Exception as e:
            logging.error(f"OCR 处理页面 {i + 1} 时出错：{e}")
            new_doc_type = '其他'

        if new_doc_type != current_doc_type:
            # 保存之前的文档页
            if pages_for_current_doc:
                logging.info(f"文档类型变化，保存当前文档类型 '{current_doc_type}' 的页面：{[idx + 1 for idx in pages_for_current_doc]}")
                save_document_pages(reader, pages_for_current_doc, pdf_name, current_doc_type, output_dir)
                pages_for_current_doc = []
            current_doc_type = new_doc_type

        # 添加页面到当前文档
        pages_for_current_doc.append(i)

    # 保存最后一个文档
    if pages_for_current_doc:
        logging.info(f"保存文档类型 '{current_doc_type}' 的页面：{[idx + 1 for idx in pages_for_current_doc]}")
        save_document_pages(reader, pages_for_current_doc, pdf_name, current_doc_type, output_dir)

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