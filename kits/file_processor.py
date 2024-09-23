import os
from PyPDF2 import PdfReader, PdfWriter
from kits.doc_type_classify_processor import sanitize_filename
from kits.log_processor import logger

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