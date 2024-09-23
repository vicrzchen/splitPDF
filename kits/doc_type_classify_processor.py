import re
import ast
from kits.log_processor import logger
import jieba

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