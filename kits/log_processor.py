import os
import logging

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