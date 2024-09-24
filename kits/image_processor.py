import numpy as np
import cv2
from PIL import Image
import os
from datetime import datetime

def is_blank_page(image):
    """判断页面是否为空白页"""
    gray = image.convert('L')
    histogram = gray.histogram()
    non_white_pixels = sum(histogram[:-10])  # 排除接近白色的像素
    total_pixels = sum(histogram)
    ratio = non_white_pixels / total_pixels
    return ratio < 0.01  # 比例小于1%认为是空白页

def preprocess_image(image, output_dir='output', filename=None, save_png=False):
    """使用自适应阈值保留重要内容"""
    if filename is None:
        filename = datetime.now().strftime("%Y%m%d%H%M%S")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 将PIL图像转换为NumPy数组并转换为灰度图像
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    # 使用自适应阈值方法
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # 或cv2.ADAPTIVE_THRESH_MEAN_C
        cv2.THRESH_BINARY,  # 反色，黑底白字
        15,  # 邻域大小
        10   # 常数，从均值或加权均值中减去
    )

    if save_png:
        # 保存二值化图像
        binary_path = os.path.join(output_dir, f"{filename}_binary.png")
        cv2.imwrite(binary_path, binary)
        return binary_path

    return binary

# 示例使用
# image = Image.open("/path/to/your_image.png")
# preprocess_image(image, save_png=True)