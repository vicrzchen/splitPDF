import os
import json
from kits.ocr_processor import process_pdf
from kits.log_processor import logger

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

    # 使用单线程处理
    for pdf_path in pdf_files:
        process_pdf((pdf_path, output_dir, document_types))

if __name__ == '__main__':
    main()
    # 手动刷新日志流，确保日志写入文件
    logger.flush()