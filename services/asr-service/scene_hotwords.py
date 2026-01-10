"""
场景热词系统

提供基于使用场景的预定义热词库，用于替代基于 RAG 的热词检索。

原理：
- 不依赖第一遍识别结果（避免文本语义匹配发音的问题）
- 基于使用场景预先加载所有相关热词
- Fun-ASR LLM 会自动匹配声学特征和发音
"""

from typing import List, Dict

# ==================== 技术场景热词 ====================

TECH_HOTWORDS = [
    # 核心技术平台
    "GitHub", "GitLab", "Bitbucket", "Git",
    "Docker", "Kubernetes", "K8S",
    "AWS", "Azure", "阿里云", "腾讯云",
    "Jenkins", "Travis", "CircleCI",

    # 编程语言
    "Python", "Java", "JavaScript", "TypeScript",
    "Go", "Golang", "Rust", "C++", "C#",
    "PHP", "Ruby", "Swift", "Kotlin",

    # 框架和库
    "React", "Vue", "Angular", "Node.js",
    "Django", "Flask", "FastAPI", "Spring Boot",
    "TensorFlow", "PyTorch", "Keras",

    # 数据库
    "MySQL", "PostgreSQL", "MongoDB", "Redis",
    "Elasticsearch", "Cassandra", "Oracle",
    "SQL Server", "SQLite",

    # 技术概念
    "API", "REST", "GraphQL", "gRPC",
    "微服务", "容器", "镜像", "集群",
    "CI/CD", "DevOps", "敏捷开发",
    "前端", "后端", "全栈",

    # 上下文词（帮助 LLM 理解领域）
    "代码", "仓库", "分支", "提交", "合并",
    "拉取请求", "PR", "MR",
    "部署", "运维", "监控", "日志",
    "测试", "单元测试", "集成测试",
    "重构", "优化", "调试", "Bug",
]

# ==================== 医疗场景热词 ====================

MEDICAL_HOTWORDS = [
    # 常见疾病
    "高血压", "糖尿病", "冠心病", "心绞痛",
    "脑卒中", "中风", "癌症", "肿瘤",
    "肺炎", "哮喘", "慢阻肺", "支气管炎",
    "胃炎", "胃溃疡", "肝炎", "肾炎",

    # 检查项目
    "心电图", "ECG", "CT", "核磁共振", "MRI",
    "X光", "B超", "超声", "彩超",
    "血常规", "尿常规", "肝功能", "肾功能",
    "血糖", "血压", "血脂", "甲状腺功能",

    # 医学术语
    "诊断", "治疗", "手术", "化疗", "放疗",
    "住院", "出院", "复查", "随访",
    "处方", "药物", "剂量", "副作用",

    # 常用药物
    "阿司匹林", "青霉素", "头孢", "抗生素",
    "降压药", "降糖药", "胰岛素",

    # 上下文词
    "患者", "病人", "症状", "体征",
    "病史", "家族史", "过敏史",
    "医生", "护士", "医院", "门诊", "急诊",
]

# ==================== 金融场景热词 ====================

FINANCE_HOTWORDS = [
    # 投资产品
    "股票", "基金", "债券", "期货", "外汇",
    "ETF", "指数基金", "货币基金",
    "私募", "公募", "信托",

    # 市场术语
    "涨停", "跌停", "涨幅", "跌幅",
    "开盘", "收盘", "成交量", "换手率",
    "市盈率", "市净率", "PE", "PB",
    "分红", "配股", "增发", "IPO",

    # 金融机构
    "银行", "证券", "保险", "基金公司",
    "交易所", "上交所", "深交所",
    "央行", "中国人民银行",

    # 财务指标
    "营收", "利润", "净利润", "毛利率",
    "资产", "负债", "现金流",
    "ROE", "ROA", "EBITDA",

    # 上下文词
    "投资", "理财", "风险", "收益",
    "账户", "资金", "交易", "买入", "卖出",
    "持仓", "仓位", "止损", "止盈",
]

# ==================== 教育场景热词 ====================

EDUCATION_HOTWORDS = [
    # 学科
    "数学", "语文", "英语", "物理", "化学",
    "生物", "历史", "地理", "政治",
    "编程", "计算机", "人工智能", "AI",

    # 考试
    "高考", "中考", "期末考", "模拟考",
    "SAT", "GRE", "托福", "雅思",
    "四级", "六级", "专四", "专八",

    # 教学
    "课程", "教材", "作业", "练习",
    "考试", "成绩", "分数", "GPA",
    "学分", "选课", "必修", "选修",

    # 上下文词
    "老师", "学生", "班级", "年级",
    "学校", "大学", "中学", "小学",
    "学习", "复习", "预习", "背诵",
]

# ==================== 电商场景热词 ====================

ECOMMERCE_HOTWORDS = [
    # 平台
    "淘宝", "天猫", "京东", "拼多多",
    "亚马逊", "Amazon", "eBay",
    "抖音", "快手", "小红书",

    # 活动
    "双十一", "618", "黑五", "秒杀",
    "促销", "打折", "优惠券", "满减",
    "包邮", "直播", "带货",

    # 商品
    "SKU", "库存", "现货", "预售",
    "评价", "好评", "差评", "售后",

    # 上下文词
    "店铺", "商家", "买家", "卖家",
    "订单", "物流", "快递", "发货",
    "退货", "换货", "退款",
]

# ==================== 场景映射 ====================

SCENE_HOTWORDS_MAP: Dict[str, List[str]] = {
    "tech": TECH_HOTWORDS,
    "medical": MEDICAL_HOTWORDS,
    "finance": FINANCE_HOTWORDS,
    "education": EDUCATION_HOTWORDS,
    "ecommerce": ECOMMERCE_HOTWORDS,
    "general": [],  # 通用场景，不添加特定热词
    "user": [],     # 用户自定义热词场景（仅使用 RAG 热词）
}

# 场景描述（用于文档和日志）
SCENE_DESCRIPTIONS: Dict[str, str] = {
    "tech": "技术开发场景 (编程、运维、架构)",
    "medical": "医疗健康场景 (诊断、检查、治疗)",
    "finance": "金融投资场景 (股票、基金、交易)",
    "education": "教育培训场景 (课程、考试、学习)",
    "ecommerce": "电商直播场景 (购物、促销、物流)",
    "general": "通用场景 (无特定热词)",
    "user": "用户自定义热词场景 (仅使用 RAG 用户热词)",
}


def get_scene_hotwords(scene: str = "tech") -> List[str]:
    """
    获取指定场景的热词列表

    Args:
        scene: 场景类型，可选值:
            - tech: 技术开发场景 (默认)
            - medical: 医疗健康场景
            - finance: 金融投资场景
            - education: 教育培训场景
            - ecommerce: 电商直播场景
            - general: 通用场景 (无热词)

    Returns:
        热词列表 (50-100个)

    Examples:
        >>> hotwords = get_scene_hotwords("tech")
        >>> len(hotwords)
        80
        >>> "GitHub" in hotwords
        True
    """
    scene = scene.lower()

    # 返回场景对应的热词列表
    return SCENE_HOTWORDS_MAP.get(scene, [])


def get_available_scenes() -> List[str]:
    """
    获取所有可用场景列表

    Returns:
        场景代码列表
    """
    return list(SCENE_HOTWORDS_MAP.keys())


def get_scene_description(scene: str) -> str:
    """
    获取场景描述

    Args:
        scene: 场景代码

    Returns:
        场景描述文本
    """
    return SCENE_DESCRIPTIONS.get(scene.lower(), "未知场景")


def get_scene_stats() -> Dict[str, int]:
    """
    获取各场景的热词统计

    Returns:
        {场景: 热词数量} 字典
    """
    return {
        scene: len(hotwords)
        for scene, hotwords in SCENE_HOTWORDS_MAP.items()
    }


# ==================== 热词管理功能 ====================

def check_duplicate(word: str, scene: str = None) -> Dict[str, List[str]]:
    """
    检查热词是否已存在

    Args:
        word: 要检查的热词
        scene: 场景代码（可选）。如果指定，只检查该场景；否则检查所有场景

    Returns:
        包含重复信息的字典: {场景名: [场景描述]}
        如果没有重复则返回空字典

    Examples:
        >>> check_duplicate("GitHub")
        {'tech': ['技术开发场景 (编程、运维、架构)']}
        >>> check_duplicate("新词汇")
        {}
    """
    duplicates = {}

    scenes_to_check = [scene.lower()] if scene else SCENE_HOTWORDS_MAP.keys()

    for scene_name in scenes_to_check:
        if scene_name in SCENE_HOTWORDS_MAP:
            hotwords = SCENE_HOTWORDS_MAP[scene_name]
            if word in hotwords:
                duplicates[scene_name] = [get_scene_description(scene_name)]

    return duplicates


def add_hotword(word: str, scene: str, force: bool = False) -> Dict[str, any]:
    """
    添加热词到指定场景（带防重检测）

    Args:
        word: 要添加的热词
        scene: 场景代码 (tech/medical/finance/education/ecommerce)
        force: 是否强制添加（即使已存在于其他场景）。默认 False

    Returns:
        操作结果字典:
        {
            "success": bool,
            "message": str,
            "duplicates": Dict[str, List[str]] (仅在失败时)
        }

    Examples:
        >>> add_hotword("OpenAI", "tech")
        {'success': True, 'message': '热词 "OpenAI" 已成功添加到 tech 场景'}

        >>> add_hotword("GitHub", "medical")
        {'success': False, 'message': '热词 "GitHub" 已存在于其他场景',
         'duplicates': {'tech': ['技术开发场景']}}
    """
    scene = scene.lower()

    # 验证场景是否存在
    if scene not in SCENE_HOTWORDS_MAP:
        return {
            "success": False,
            "message": f"无效的场景代码: {scene}",
            "available_scenes": list(SCENE_HOTWORDS_MAP.keys())
        }

    # general 和 user 场景不允许添加预定义热词
    if scene in ["general", "user"]:
        return {
            "success": False,
            "message": f"{scene} 场景不支持添加预定义热词"
        }

    # 检查当前场景是否已存在
    if word in SCENE_HOTWORDS_MAP[scene]:
        return {
            "success": False,
            "message": f"热词 \"{word}\" 已存在于 {scene} 场景",
            "duplicates": {scene: [get_scene_description(scene)]}
        }

    # 检查其他场景是否已存在
    if not force:
        duplicates = check_duplicate(word)
        if duplicates:
            return {
                "success": False,
                "message": f"热词 \"{word}\" 已存在于其他场景",
                "duplicates": duplicates
            }

    # 添加热词
    SCENE_HOTWORDS_MAP[scene].append(word)

    return {
        "success": True,
        "message": f"热词 \"{word}\" 已成功添加到 {scene} 场景",
        "scene": scene,
        "word": word,
        "total_count": len(SCENE_HOTWORDS_MAP[scene])
    }


def remove_hotword(word: str, scene: str) -> Dict[str, any]:
    """
    从指定场景删除热词

    Args:
        word: 要删除的热词
        scene: 场景代码

    Returns:
        操作结果字典:
        {
            "success": bool,
            "message": str
        }

    Examples:
        >>> remove_hotword("GitHub", "tech")
        {'success': True, 'message': '热词 "GitHub" 已从 tech 场景删除'}
    """
    scene = scene.lower()

    # 验证场景是否存在
    if scene not in SCENE_HOTWORDS_MAP:
        return {
            "success": False,
            "message": f"无效的场景代码: {scene}",
            "available_scenes": list(SCENE_HOTWORDS_MAP.keys())
        }

    # general 和 user 场景不允许删除
    if scene in ["general", "user"]:
        return {
            "success": False,
            "message": f"{scene} 场景不支持删除热词"
        }

    # 检查热词是否存在
    if word not in SCENE_HOTWORDS_MAP[scene]:
        return {
            "success": False,
            "message": f"热词 \"{word}\" 不存在于 {scene} 场景"
        }

    # 删除热词
    SCENE_HOTWORDS_MAP[scene].remove(word)

    return {
        "success": True,
        "message": f"热词 \"{word}\" 已从 {scene} 场景删除",
        "scene": scene,
        "word": word,
        "total_count": len(SCENE_HOTWORDS_MAP[scene])
    }


def list_all_hotwords() -> Dict[str, List[str]]:
    """
    列出所有场景的热词

    Returns:
        {场景名: [热词列表]} 字典

    Examples:
        >>> all_words = list_all_hotwords()
        >>> len(all_words['tech'])
        80
    """
    return {
        scene: hotwords.copy()
        for scene, hotwords in SCENE_HOTWORDS_MAP.items()
    }


# ==================== 示例和测试 ====================

if __name__ == "__main__":
    # 测试代码
    print("=== 场景热词系统测试 ===\n")

    # 显示所有场景
    print("可用场景:")
    for scene in get_available_scenes():
        desc = get_scene_description(scene)
        count = len(get_scene_hotwords(scene))
        print(f"  - {scene}: {desc} ({count} 个热词)")

    print("\n场景热词统计:")
    stats = get_scene_stats()
    for scene, count in stats.items():
        print(f"  {scene}: {count} 个")

    # 测试技术场景
    print("\n=== 技术场景热词示例 ===")
    tech_words = get_scene_hotwords("tech")
    print(f"总数: {len(tech_words)}")
    print(f"前 20 个: {', '.join(tech_words[:20])}")

    # 测试医疗场景
    print("\n=== 医疗场景热词示例 ===")
    medical_words = get_scene_hotwords("medical")
    print(f"总数: {len(medical_words)}")
    print(f"前 20 个: {', '.join(medical_words[:20])}")
