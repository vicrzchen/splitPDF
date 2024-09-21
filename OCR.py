import os
from pdf2image import convert_from_path
from paddleocr import PaddleOCR  # 确保正确导入
import cv2
import numpy as np
from PIL import Image

# 设置输入和输出目录
input_dir = './input'
output_dir = './output'

# 确保输出目录存在
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 遍历输入目录中的所有文件
for filename in os.listdir(input_dir):
    # 检查文件是否为PDF
    if filename.endswith('.pdf'):
        # 从PDF中提取图像
        pages = convert_from_path(os.path.join(input_dir, filename), 500)
        text = ''
        ocr = PaddleOCR(lang='ch')  # 创建OCR对象

        for page in pages:
            # 将PIL图像转换为NumPy数组 (BGR格式) 以供cv2使用
            page_np = np.array(page)

            # 检查图像是否为三通道（RGB），并转换为PaddleOCR要求的格式（RGB）
            if page_np.shape[-1] == 3:  # 三通道图像
                page_np = cv2.cvtColor(page_np, cv2.COLOR_RGB2BGR)

            # 使用paddleocr进行文本识别
            result = ocr.ocr(page_np)  # 使用ocr方法
            for line in result:
                for word_info in line:
                    text += word_info[1][0] + '\n'  # 获取识别的文本部分

        # 将文本保存到输出目录
        with open(os.path.join(output_dir, f'{os.path.splitext(filename)[0]}.txt'), 'w', encoding='utf-8') as f:
            f.write(text)