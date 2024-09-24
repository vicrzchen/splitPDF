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
    - similar('关键词', 相似度阈值)
    """
    # 定义包含函数，检查关键词是否在文本中
    def contains(keyword):
        logger.debug(f"检查关键词 '{keyword}' 是否在文本中")
        result = keyword in text
        logger.debug(f"关键词 '{keyword}' {'在' if result else '不在'}文本中")
        return result

    # 定义百分比函数，检查关键词在文本中的出现频率
    def percentage(keyword, threshold):
        logger.debug(f"检查关键词 '{keyword}' 在文本中的出现频率是否超过阈值 {threshold}%")
        word_count = len(text.split())
        keyword_count = text.count(keyword)
        percentage = (keyword_count / word_count) * 100
        result = percentage >= threshold
        logger.debug(f"关键词 '{keyword}' 在文本中的出现频率为 {percentage:.2f}%，{'超过' if result else '未超过'}阈值 {threshold}%")
        return result

    # 定义相似度函数，检查关键词与文本中词语的相似度
    def similar(keyword, threshold):
        logger.debug(f"检查关键词 '{keyword}' 与文本中词语的相似度是否超过阈值 {threshold}")
        # 对关键词进行分词
        keyword_words = jieba.lcut(keyword)
        # 在原始文本中查找关键词
        start = 0
        while True:
            match_index = text.find(keyword_words[0], start)
            if match_index == -1:
                break
            end_index = match_index + len(keyword)
            if text[match_index:end_index] == keyword:
                logger.debug(f"关键词 '{keyword}' 在文本中完全匹配")
                return True
            ratio = levenshtein_ratio(keyword, text[match_index:end_index])
            logger.debug(f"关键词 '{keyword}' 与文本片段 '{text[match_index:end_index]}' 的相似度为 {ratio:.2f}")
            if ratio >= threshold:
                logger.debug(f"关键词 '{keyword}' 与文本片段 '{text[match_index:end_index]}' 的相似度超过阈值 {threshold}")
                return True
            start = match_index + len(keyword_words[0])
        logger.debug(f"关键词 '{keyword}' 与文本中词语的相似度均未超过阈值 {threshold}")
        return False

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
    safe_globals = {'contains': contains, 'percentage': percentage, 'similar': similar, '__builtins__': None}
    safe_locals = {}

    # 评估表达式
    try:
        result = eval(compile(node, filename='', mode='eval'), safe_globals, safe_locals)
    except Exception as e:
        logger.error(f"评估表达式 '{expression}' 时出错：{e}")
        result = False

    return result

def levenshtein_ratio(s1, s2):
    """计算两个字符串的编辑距离相似度"""
    m, n = len(s1), len(s2)
    if m < n:
        return levenshtein_ratio(s2, s1)

    if n == 0:
        return 1.0

    previous_row = range(n + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return (n - previous_row[-1]) / n

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