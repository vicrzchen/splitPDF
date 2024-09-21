import os
import logging

# 检查日志文件的路径是否正确
log_file_path = os.path.join(os.getcwd(), 'process.log')
print(f"日志文件路径：{log_file_path}")

# 创建日志记录器并设置日志级别
logger = logging.getLogger(__name__)  # 根据你的需要可以修改日志记录器名称
logger.setLevel(logging.DEBUG)

# 创建日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 创建文件处理器，将日志记录到文件
file_handler = logging.FileHandler(log_file_path, mode='w')  # 'w' 表示覆盖日志文件
file_handler.setLevel(logging.DEBUG)  # 设置文件日志级别为 DEBUG
file_handler.setFormatter(formatter)  # 设置文件日志格式

# 创建控制台处理器，将日志输出到控制台
console_handler = logging.StreamHandler()  # 默认输出到控制台
console_handler.setLevel(logging.INFO)  # 设置控制台日志级别为 INFO
console_handler.setFormatter(formatter)  # 设置控制台日志格式

# 将处理器添加到记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 测试日志
logger.debug("测试日志记录是否正常工作 - DEBUG")
logger.info("测试日志记录是否正常工作 - INFO")
logger.warning("测试日志记录是否正常工作 - WARNING")
logger.error("测试日志记录是否正常工作 - ERROR")
logger.critical("测试日志记录是否正常工作 - CRITICAL")

# 提示日志文件路径
print(f"日志文件已保存到：{log_file_path}")

# 手动刷新日志流，确保日志写入文件
logging.shutdown()