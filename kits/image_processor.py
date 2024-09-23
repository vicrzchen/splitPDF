import numpy as np
import cv2
from PIL import Image
from kits.log_processor import logger

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