import streamlit as st
import pandas as pd
import numpy as np
import re
import logging
from typing import Dict, List, Set, Tuple, Any
import itertools
from collections import defaultdict
import time
from io import BytesIO
from functools import lru_cache

# 设置页面
st.set_page_config(
    page_title="🎈彩票完美覆盖分析系统🎈",
    page_icon="🎯",
    layout="wide"
)

# ==================== 配置常量 ====================
COVERAGE_CONFIG = {
    'min_number_count': {
        'six_mark': 11,  # 六合彩
        '10_number': 3,   # 10个号码的彩种
        'fast_three': 3,  # 快三和值
    },
    'min_avg_amount': {
        'six_mark': 2,
        '10_number': 1,
        'fast_three': 1,
    },
    'similarity_thresholds': {
        'excellent': 90,
        'good': 80,
        'fair': 70
    },
    'target_lotteries': {
        'six_mark': [
            '新澳门六合彩', '澳门六合彩', '香港六合彩', '一分六合彩',
            '五分六合彩', '三分六合彩', '香港⑥合彩', '分分六合彩',
            '台湾大乐透', '大发六合彩', '快乐6合彩',
            '幸运六合彩', '极速六合彩', '腾讯六合彩', '五分彩六合',
            '三分彩六合', '一分彩六合', '幸运⑥合', '极速⑥合'
        ],
        '10_number': [
            '时时彩', '重庆时时彩', '新疆时时彩', '天津时时彩',
            '分分时时彩', '五分时时彩', '三分时时彩', '北京时时彩',
            'PK10', '北京PK10', 'PK拾', '幸运PK10', '赛车', '大发赛车',
            '幸运28', '北京28', '加拿大28', '极速PK10', '分分PK10', '大发快三',
            '幸运飞艇', '澳洲幸运10', '极速飞艇', '澳洲飞艇',
            '北京赛车', '极速赛车', '幸运赛車', '分分赛车',
            '腾讯分分彩', '五分时时彩', '三分时时彩', '一分时时彩',
            '幸运5', '幸运8', '幸运10', '幸运12'
        ],
        'fast_three': [
            '快三', '快3', 'K3', '分分快三', '五分快三', '三分快三',
            '北京快三', '江苏快三', '安徽快三', '大发快三',
            '澳洲快三', '宾果快三', '加州快三', '幸运快三',
            '澳门快三', '香港快三', '台湾快三', '极速快三'
        ],
        '3d_series': [
            '排列三', '排列3', '福彩3D', '3D', '极速3D',
            '幸运排列3', '一分排列3', '三分排列3', '五分排列3',
            '大发排列3', '好运排列3', '极速排列3'
        ],
        'five_star': [
            '五星彩', '五星直选', '五星组选', '五星通选',
            '五星彩种', '五星彩票', '极速五星'
        ]
    }
}

# ==================== 日志设置 ====================
def setup_logging():
    """设置日志系统"""
    logger = logging.getLogger('CoverageAnalysis')
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==================== 全彩种分析器 ====================
class MultiLotteryCoverageAnalyzer:
    """全彩种覆盖分析器 - 支持六合彩、时时彩、PK10、快三等"""
    
    def __init__(self):
        # 定义各彩种的号码范围
        self.lottery_configs = {
            'six_mark': {
                'number_range': set(range(1, 50)),
                'total_numbers': 49,
                'type_name': '六合彩',
                'play_keywords': ['特码', '特玛', '特马', '特碼', '正码', '正特', '正肖', '平码', '平特'],
                'default_min_number_count': 11,  # 🆕 默认阈值
                'default_min_avg_amount': 10     # 🆕 默认阈值
            },
            'six_mark_tail': {  # 🆕 新增：六合彩尾数玩法
                'number_range': set(range(0, 10)),  # 尾数0-9
                'total_numbers': 10,
                'type_name': '六合彩尾数',
                'play_keywords': ['尾数', '特尾', '全尾'],
                'default_min_number_count': 3,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            },
            '10_number': {
                'number_range': set(range(1, 11)),
                'total_numbers': 10,
                'type_name': '10个号码彩种',
                'play_keywords': ['定位胆', '一字定位', '一字', '定位', '大小单双', '龙虎', '冠军', '亚军', '季军', '第四名', '第五名', '第六名', '第七名', '第八名', '第九名', '第十名', '第一名', '第二名', '第三名', '前一'],
                'default_min_number_count': 3,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            },
            '10_number_sum': {  # 🆕 新增：冠亚和玩法
                'number_range': set(range(3, 20)),  # 冠亚和3-19
                'total_numbers': 17,
                'type_name': '冠亚和',
                'play_keywords': ['冠亚和', '冠亚和值'],
                'default_min_number_count': 5,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            },
            'fast_three_base': {  # 🆕 新增：快三基础玩法
                'number_range': set(range(1, 7)),  # 基础号码1-6
                'total_numbers': 6,
                'type_name': '快三基础',
                'play_keywords': ['三军', '独胆', '单码', '二不同号', '三不同号'],
                'default_min_number_count': 2,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            },
            'fast_three_sum': {  # 🆕 新增：快三和值玩法
                'number_range': set(range(3, 19)),  # 和值范围3-18
                'total_numbers': 16,
                'type_name': '快三和值',
                'play_keywords': ['和值', '点数'],
                'default_min_number_count': 4,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            },
            'ssc_3d': {  # 🆕 新增：时时彩和3D系列
                'number_range': set(range(0, 10)),  # 号码0-9
                'total_numbers': 10,
                'type_name': '时时彩/3D',
                'play_keywords': ['定位胆', '第1球', '第2球', '第3球', '第4球', '第5球', '万位', '千位', '百位', '十位', '个位'],
                'default_min_number_count': 3,   # 🆕 默认阈值
                'default_min_avg_amount': 5      # 🆕 默认阈值
            }
        }
        
        # 完整的彩种列表
        self.target_lotteries = {}
        for lottery_type, lotteries in COVERAGE_CONFIG['target_lotteries'].items():
            self.target_lotteries[lottery_type] = lotteries
        
        # 增强的列名映射字典
        self.column_mappings = {
            '会员账号': ['会员账号', '会员账户', '账号', '账户', '用户账号', '玩家账号', '用户ID', '玩家ID', '用户名称', '玩家名称'],
            '彩种': ['彩种', '彩神', '彩票种类', '游戏类型', '彩票类型', '游戏彩种', '彩票名称', '彩系', '游戏名称'],
            '期号': ['期号', '期数', '期次', '期', '奖期', '期号信息', '期号编号', '开奖期号', '奖期号'],
            '玩法': ['玩法', '玩法分类', '投注类型', '类型', '投注玩法', '玩法类型', '分类', '玩法名称', '投注方式'],
            '内容': ['内容', '投注内容', '下注内容', '注单内容', '投注号码', '号码内容', '投注信息', '号码', '选号'],
            '金额': ['金额', '下注总额', '投注金额', '总额', '下注金额', '投注额', '金额数值', '单注金额', '投注额', '钱', '元']
        }
        
        self.account_keywords = ['会员', '账号', '账户', '用户', '玩家', 'id', 'name', 'user', 'player']
        
        # 玩法分类映射 - 扩展支持六合彩正码正特
        self.play_mapping = {
            # ========== 六合彩号码玩法 ==========
            # 特码相关
            '特码': '特码',
            '特码A': '特码',
            '特码B': '特码',
            '特码球': '特码',
            '特码_特码': '特码',
            '特玛': '特码',
            '特马': '特码',
            '特碼': '特码',
            
            # 正码相关
            '正码': '正码',
            '正码一': '正码一',
            '正码二': '正码二',
            '正码三': '正码三',
            '正码四': '正码四',
            '正码五': '正码五',
            '正码六': '正码六',
            '正码1': '正码一',
            '正码2': '正码二',
            '正码3': '正码三',
            '正码4': '正码四',
            '正码5': '正码五',
            '正码6': '正码六',
            '正码1-6': '正码',
            '正码1-6 正码': '正码',
            '正码1-6_正码': '正码',
            '正码1-6_正码一': '正码一',
            '正码1-6_正码二': '正码二',
            '正码1-6_正码三': '正码三',
            '正码1-6_正码四': '正码四',
            '正码1-6_正码五': '正码五',
            '正码1-6_正码六': '正码六',
            
            # 正特相关
            '正特': '正特',
            '正玛特': '正特',
            '正码特': '正特',
            '正一特': '正1特',
            '正二特': '正2特',
            '正三特': '正3特',
            '正四特': '正4特',
            '正五特': '正5特',
            '正六特': '正6特',
            '正1特': '正1特',
            '正2特': '正2特',
            '正3特': '正3特',
            '正4特': '正4特',
            '正5特': '正5特',
            '正6特': '正6特',
            '正码特_正一特': '正1特',
            '正码特_正二特': '正2特',
            '正码特_正三特': '正3特',
            '正码特_正四特': '正4特',
            '正码特_正五特': '正5特',
            '正码特_正六特': '正6特',
            '正玛特_正一特': '正1特',
            '正玛特_正二特': '正2特',
            '正玛特_正三特': '正3特',
            '正玛特_正四特': '正4特',
            '正玛特_正五特': '正5特',
            '正玛特_正六特': '正6特',
            '正玛特': '正特',
            '正玛特_正一特': '正1特',
            '正玛特_正二特': '正2特', 
            '正玛特_正三特': '正3特',
            '正玛特_正四特': '正4特',
            '正玛特_正五特': '正5特',
            '正玛特_正六特': '正6特',
            
            # 平码相关
            '平码': '平码',
            '平特': '平特',
            
            # 尾数相关
            '尾数': '尾数',
            '尾数_头尾数': '尾数_头尾数',
            '特尾': '特尾',
            '全尾': '全尾',
            '尾数_正特尾数': '尾数',
            
            # ========== 时时彩/PK10/赛车号码玩法 ==========
            # 定位胆相关
            '定位胆': '定位胆',
            '一字定位': '定位胆',
            '一字': '定位胆',
            '定位': '定位胆',
            
            # 名次玩法
            '冠军': '冠军',
            '亚军': '亚军',
            '季军': '季军',
            '第一名': '冠军',
            '第二名': '亚军',
            '第三名': '季军',
            '第四名': '第四名',
            '第五名': '第五名',
            '第六名': '第六名',
            '第七名': '第七名',
            '第八名': '第八名',
            '第九名': '第九名',
            '第十名': '第十名',
            '第1名': '冠军',
            '第2名': '亚军',
            '第3名': '季军',
            '第4名': '第四名',
            '第5名': '第五名',
            '第6名': '第六名',
            '第7名': '第七名',
            '第8名': '第八名',
            '第9名': '第九名',
            '第10名': '第十名',
            '前一': '冠军',
            
            # 分组名次
            '1-5名': '1-5名',
            '6-10名': '6-10名',
            '1~5名': '1-5名',
            '6~10名': '6-10名',
            '定位胆_第1~5名': '定位胆_第1~5名',
            '定位胆_第6~10名': '定位胆_第6~10名',
            
            # 球位玩法（时时彩）
            '第1球': '第1球',
            '第2球': '第2球',
            '第3球': '第3球',
            '第4球': '第4球',
            '第5球': '第5球',
            '1-5球': '1-5球',
            
            # 位数玩法（时时彩）
            '万位': '万位',
            '千位': '千位',
            '百位': '百位',
            '十位': '十位',
            '个位': '个位',
            '定位_万位': '万位',
            '定位_千位': '千位',
            '定位_百位': '百位',
            '定位_十位': '十位',
            '定位_个位': '个位',
            
            # ========== 快三号码玩法 ==========
            '和值': '和值',
            '和值_大小单双': '和值',
            '点数': '和值',
            
            # ========== 3D系列号码玩法 ==========
            '百位': '百位',
            '十位': '十位',
            '个位': '个位',
            '百十': '百十',
            '百个': '百个',
            '十个': '十个',
            '百十个': '百十个',
            '定位胆_百位': '百位',
            '定位胆_十位': '十位',
            '定位胆_个位': '个位',
            
            # ========== 其他号码玩法 ==========
            '总和': '总和',
            '斗牛': '斗牛'
        }

        # 扩展玩法映射
        self.play_mapping.update({
            # 🆕 新增：快三基础玩法
            '三军': '三军',
            '三軍': '三军',
            '独胆': '三军', 
            '单码': '三军',
            '二不同号': '二不同号',
            '二不同': '二不同号',
            '二不同號': '二不同号',
            '三不同号': '三不同号',
            '三不同': '三不同号',
            '三不同號': '三不同号',
            
            # 🆕 新增：冠亚和玩法
            '冠亚和': '冠亚和',
            '冠亚和值': '冠亚和',
            '冠亞和': '冠亚和',
            '冠亞和值': '冠亚和',
            
            # 🆕 扩展：六合彩尾数玩法
            '尾数_头尾数': '尾数_头尾数',
            '头尾数': '尾数_头尾数',
            '特尾': '特尾',
            '全尾': '全尾',
            
            # 🆕 扩展：时时彩球位玩法
            '第1球': '第1球',
            '第2球': '第2球', 
            '第3球': '第3球',
            '第4球': '第4球',
            '第5球': '第5球',
            '1-5球': '1-5球',
            
            # 🆕 扩展：3D系列玩法
            '百十': '百十',
            '百个': '百个',
            '十个': '十个',
            '百十个': '百十个'
        })
        
        self.position_mapping = {
            # ========== 六合彩位置 ==========
            '特码': ['特码', '特玛', '特马', '特碼', '特码球', '特码_特码', '特码A', '特码B'],
            '正码': ['正码', '正码1-6 正码', '正码1-6_正码', '正码1-6'],
            '正码一': ['正码一', '正码1', '正一码', '正码1-6_正码一', '正1', 'zm1', 'z1m'],
            '正码二': ['正码二', '正码2', '正二码', '正码1-6_正码二', '正2', 'zm2', 'z2m'],
            '正码三': ['正码三', '正码3', '正三码', '正码1-6_正码三', '正3', 'zm3', 'z3m'],
            '正码四': ['正码四', '正码4', '正四码', '正码1-6_正码四', '正4', 'zm4', 'z4m'],
            '正码五': ['正码五', '正码5', '正五码', '正码1-6_正码五', '正5', 'zm5', 'z5m'],
            '正码六': ['正码六', '正码6', '正六码', '正码1-6_正码六', '正6', 'zm6', 'z6m'],
            
            '正特': ['正特', '正玛特', '正码特'],
            '正一特': ['正一特', '正1特', '正码特_正一特', '正玛特_正一特', '正玛特_正1特', 'z1t', 'zyte'],
            '正二特': ['正二特', '正2特', '正码特_正二特', '正玛特_正二特', '正玛特_正2特', 'z2t', 'zte'],
            '正三特': ['正三特', '正3特', '正码特_正三特', '正玛特_正三特', '正玛特_正3特', 'z3t', 'zste'],
            '正四特': ['正四特', '正4特', '正码特_正四特', '正玛特_正四特', '正玛特_正4特', 'z4t', 'zsite'],
            '正五特': ['正五特', '正5特', '正码特_正五特', '正玛特_正五特', '正玛特_正5特', 'z5t', 'zwte'],
            '正六特': ['正六特', '正6特', '正码特_正六特', '正玛特_正六特', '正玛特_正6特', 'z6t', 'zlte'],
            
            '平码': ['平码', '平特码', '平特', 'pm', 'pingma'],
            '平特': ['平特', '平特肖', '平特码', 'pt', 'pingte'],
            '尾数': ['尾数', '尾数_头尾数', '尾数_正特尾数', '尾码', 'ws', 'weishu'],
            '特尾': ['特尾', '特尾数', '特码尾数', 'tw', 'tewei'],
            '全尾': ['全尾', '全尾数', '全部尾数', 'qw', 'quanwei'],
            
            # ========== 时时彩/PK10/赛车位置 ==========
            '冠军': ['冠军', '第一名', '第1名', '1st', '前一', '前一位', '第一位', '1位', 'gj', 'guanjun'],
            '亚军': ['亚军', '第二名', '第2名', '2nd', '前二', '第二位', '2位', 'yj', 'yajun'],
            '季军': ['季军', '第三名', '第3名', '3rd', '前三', '第三位', '3位', 'jj', 'jijun'],
            '第四名': ['第四名', '第4名', '4th', '第四位', '4位', 'dsm', 'disiming'],
            '第五名': ['第五名', '第5名', '5th', '第五位', '5位', 'dwm', 'diwuming'],
            '第六名': ['第六名', '第6名', '6th', '第六位', '6位', 'dlm', 'diliuming'],
            '第七名': ['第七名', '第7名', '7th', '第七位', '7位', 'dqm', 'diqiming'],
            '第八名': ['第八名', '第8名', '8th', '第八位', '8位', 'dbm', 'dibaming'],
            '第九名': ['第九名', '第9名', '9th', '第九位', '9位', 'djm', 'dijiuming'],
            '第十名': ['第十名', '第10名', '10th', '第十位', '10位', 'dsm2', 'dishiming'],
            
            '第1球': ['第1球', '第一球', '万位', '第一位', '定位_万位', '万位定位', 'd1q', 'di1qiu'],
            '第2球': ['第2球', '第二球', '千位', '第二位', '定位_千位', '千位定位', 'd2q', 'di2qiu'],
            '第3球': ['第3球', '第三球', '百位', '第三位', '定位_百位', '百位定位', 'd3q', 'di3qiu'],
            '第4球': ['第4球', '第四球', '十位', '第四位', '定位_十位', '十位定位', 'd4q', 'di4qiu'],
            '第5球': ['第5球', '第五球', '个位', '第五位', '定位_个位', '个位定位', 'd5q', 'di5qiu'],
            
            '1-5名': ['1-5名', '1~5名', '1至5名', '1到5名', '前五名', '1-5ming'],
            '6-10名': ['6-10名', '6~10名', '6至10名', '6到10名', '后五名', '6-10ming'],
            '定位胆_第1~5名': ['定位胆_第1~5名', '定位胆1-5名', '1-5名定位胆'],
            '定位胆_第6~10名': ['定位胆_第6~10名', '定位胆6-10名', '6-10名定位胆'],
            
            # ========== 快三位置 ==========
            '和值': ['和值', '和数', '和', '和值_大小单双', '点数', 'hz', 'hezhi'],
            '三军': ['三军', '三軍', '独胆', '单码', 'sj', 'sanjun'],
            '二不同号': ['二不同号', '二不同', '二不同號', 'ebth', 'erbutonghao'],
            '三不同号': ['三不同号', '三不同', '三不同號', 'sbth', 'sanbutonghao'],
            
            # ========== 3D系列位置 ==========
            '百位': ['百位', '定位_百位', '百位定位', 'bw', 'baiwei', '第1位_3D'],
            '十位': ['十位', '定位_十位', '十位定位', 'sw', 'shiwei', '第2位_3D'],
            '个位': ['个位', '定位_个位', '个位定位', 'gw', 'gewei', '第3位_3D'],
            '百十': ['百十', '百十位', '百十定位', 'bs', 'baishi'],
            '百个': ['百个', '百个位', '百个定位', 'bg', 'baige'],
            '十个': ['十个', '十个位', '十个定位', 'sg', 'shige'],
            '百十个': ['百十个', '百十个位', '百十个定位', 'bsg', 'baishige'],
            
            # ========== 五星彩位置 ==========
            '万位': ['万位', '第1位', '第一位', '1st', 'ww', 'wanwei'],
            '千位': ['千位', '第2位', '第二位', '2nd', 'qw', 'qianwei'],
            '百位_5x': ['百位_5x', '第3位', '第三位', '3rd', 'bw5', 'baiwei5'],
            '十位_5x': ['十位_5x', '第4位', '第四位', '4th', 'sw5', 'shiwei5'],
            '个位_5x': ['个位_5x', '第5位', '第五位', '5th', 'gw5', 'gewei5'],
            
            # ========== 快乐8位置 ==========
            '选一': ['选一', '一中一', '1中1', '选1', 'xuan1', 'x1'],
            '选二': ['选二', '二中二', '2中2', '选2', 'xuan2', 'x2'],
            '选三': ['选三', '三中三', '3中3', '选3', 'xuan3', 'x3'],
            '选四': ['选四', '四中四', '4中4', '选4', 'xuan4', 'x4'],
            '选五': ['选五', '五中五', '5中5', '选5', 'xuan5', 'x5'],
            '选六': ['选六', '六中六', '6中6', '选6', 'xuan6', 'x6'],
            '选七': ['选七', '七中七', '7中7', '选7', 'xuan7', 'x7'],
            '选八': ['选八', '八中八', '8中8', '选8', 'xuan8', 'x8'],
            '选九': ['选九', '九中九', '9中9', '选9', 'xuan9', 'x9'],
            '选十': ['选十', '十中十', '10中10', '选10', 'xuan10', 'x10']
        }

        # 🆕 新增：分组玩法到具体位置的映射
        self.group_play_expansion = {
            '1-5名': {
                'positions': ['冠军', '亚军', '季军', '第四名', '第五名'],
                'description': '前五名分组玩法',
                'total_numbers': 10,
                'min_numbers_per_account': 5
            },
            '6-10名': {
                'positions': ['第六名', '第七名', '第八名', '第九名', '第十名'],
                'description': '后五名分组玩法',
                'total_numbers': 10,
                'min_numbers_per_account': 5
            },
            '1~5名': {
                'positions': ['冠军', '亚军', '季军', '第四名', '第五名'],
                'description': '前五名分组玩法(变体)',
                'total_numbers': 10,
                'min_numbers_per_account': 5
            },
            '6~10名': {
                'positions': ['第六名', '第七名', '第八名', '第九名', '第十名'],
                'description': '后五名分组玩法(变体)',
                'total_numbers': 10,
                'min_numbers_per_account': 5
            }
        }

        # 扩展位置映射
        self.position_mapping.update({
            # 🆕 新增：快三基础玩法位置
            '三军': ['三军', '三軍', '独胆', '单码', 'sj', 'sanjun'],
            '二不同号': ['二不同号', '二不同', '二不同號', 'ebth', 'erbutonghao'],
            '三不同号': ['三不同号', '三不同', '三不同號', 'sbth', 'sanbutonghao'],
            
            # 🆕 新增：冠亚和位置
            '冠亚和': ['冠亚和', '冠亚和值', '冠亞和', '冠亞和值', 'gyh', 'guanyabe'],
            
            # 🆕 扩展：六合彩尾数位置
            '尾数_头尾数': ['尾数_头尾数', '头尾数', '头尾', '尾数头尾', 'tws', 'touweishu'],
            '特尾': ['特尾', '特尾数', '特码尾数', 'tw', 'tewei'],
            '全尾': ['全尾', '全尾数', '全部尾数', 'qw', 'quanwei'],
            
            # 🆕 扩展：时时彩球位
            '第1球': ['第1球', '第一球', '万位', '第一位', '定位_万位', '万位定位', 'd1q', 'di1qiu'],
            '第2球': ['第2球', '第二球', '千位', '第二位', '定位_千位', '千位定位', 'd2q', 'di2qiu'],
            '第3球': ['第3球', '第三球', '百位', '第三位', '定位_百位', '百位定位', 'd3q', 'di3qiu'],
            '第4球': ['第4球', '第四球', '十位', '第四位', '定位_十位', '十位定位', 'd4q', 'di4qiu'],
            '第5球': ['第5球', '第五球', '个位', '第五位', '定位_个位', '个位定位', 'd5q', 'di5qiu'],
            
            # 🆕 扩展：3D系列位置
            '百十': ['百十', '百十位', '百十定位', 'bs', 'baishi'],
            '百个': ['百个', '百个位', '百个定位', 'bg', 'baige'],
            '十个': ['十个', '十个位', '十个定位', 'sg', 'shige'],
            '百十个': ['百十个', '百十个位', '百十个定位', 'bsg', 'baishige']
        })

    def filter_number_bets_only(self, df):
        """过滤只保留涉及具体号码投注的记录 - 包含分组玩法"""
        
        # 定义非号码投注的关键词
        non_number_keywords = [
            '大小', '单双', '龙虎', '和值大小', '和值单双', '特单', '特双', '特大', '特小',
            '大', '小', '单', '双', '龙', '虎', '合数单双', '合数大小', '尾数大小',
            '尾数单双', '总和大小', '总和单双'
        ]
        
        # 定义需要保留的号码投注玩法 - 包含分组玩法
        number_play_keywords = [
            '特码', '正码', '平码', '平特', '尾数', '特尾', '全尾',  # 六合彩
            '正特', '正一特', '正二特', '正三特', '正四特', '正五特', '正六特',  # 新增正码特
            '正1特', '正2特', '正3特', '正4特', '正5特', '正6特',  # 新增数字格式
            '正玛特', '正码特',  # 新增变体
            '定位胆', '冠军', '亚军', '季军', '第四名', '第五名', '第六名',  # PK10/赛车
            '第七名', '第八名', '第九名', '第十名', '前一',  # PK10/赛车
            '和值', '点数',  # 快三（具体数字）
            '百位', '十位', '个位', '百十', '百个', '十个', '百十个',  # 3D系列
            '1-5名', '6-10名', '1~5名', '6~10名'  # 🆕 关键：包含分组玩法
        ]
        
        # 过滤条件1：玩法必须包含号码投注关键词
        play_condition = df['玩法'].str.contains('|'.join(number_play_keywords), na=False)
        
        # 过滤条件2：投注内容不能包含非号码关键词
        content_condition = ~df['内容'].str.contains('|'.join(non_number_keywords), na=False)
        
        # 过滤条件3：投注内容必须包含数字
        number_condition = df['内容'].str.contains(r'\d', na=False)
        
        # 综合条件：玩法正确 且 (内容不包含非号码关键词 或 内容包含数字)
        final_condition = play_condition & (content_condition | number_condition)
        
        filtered_df = df[final_condition].copy()
        
        # 记录过滤统计
        removed_count = len(df) - len(filtered_df)
        logger.info(f"📊 过滤非号码投注: 移除 {removed_count} 条记录，保留 {len(filtered_df)} 条记录")
        
        return filtered_df

    def filter_records_with_numbers(self, df):
        """过滤只保留包含有效号码的投注记录"""
        
        # 定义各彩种的号码范围
        lottery_configs = {
            'six_mark': set(range(1, 50)),
            '10_number': set(range(1, 11)),
            'fast_three': set(range(3, 19))
        }
        
        # 识别彩种类型
        if '彩种类型' not in df.columns:
            df['彩种类型'] = df['彩种'].apply(self.identify_lottery_category)
        
        # 提取号码并过滤
        valid_records = []
        
        for idx, row in df.iterrows():
            lottery_category = row['彩种类型']
            
            if pd.isna(lottery_category):
                continue
                
            # 提取号码
            numbers = self.cached_extract_numbers(row['内容'], lottery_category)
            
            # 检查是否包含有效号码
            if numbers:
                valid_records.append(idx)
        
        filtered_df = df.loc[valid_records].copy()
        
        # 记录过滤统计
        removed_count = len(df) - len(filtered_df)
        logger.info(f"📊 过滤无号码投注: 移除 {removed_count} 条记录，保留 {len(filtered_df)} 条记录")
        
        # 显示被过滤的记录类型
        if removed_count > 0:
            removed_df = df.drop(valid_records)
            st.info(f"🔍 过滤统计: 移除了 {removed_count} 条无号码投注记录")
            
            if not removed_df.empty:
                with st.expander("查看被过滤的记录样本", expanded=False):
                    st.write("被过滤的玩法分布:")
                    play_dist = removed_df['玩法'].value_counts().head(10)
                    st.dataframe(play_dist.reset_index().rename(columns={'index': '玩法', '玩法': '数量'}))
                    
                    st.write("被过滤的记录样本:")
                    st.dataframe(removed_df[['会员账号', '彩种', '玩法', '内容', '金额']].head(10))
        
        return filtered_df

    def fixed_extract_amount(self, amount_str):
        """修复的金额提取方法"""
        return self.cached_extract_amount(str(amount_str))

    def expand_group_play_records(self, df):
        """将分组玩法记录展开为多个独立的位置记录"""
        expanded_rows = []
        
        for idx, row in df.iterrows():
            play_method = str(row['玩法']).strip()
            
            # 检查是否是分组玩法
            is_group_play = False
            group_key = None
            
            for key in self.group_play_expansion.keys():
                if key in play_method:
                    is_group_play = True
                    group_key = key
                    break
            
            if is_group_play and group_key:
                # 获取分组配置
                group_config = self.group_play_expansion[group_key]
                positions = group_config['positions']
                
                # 解析投注内容
                content = str(row['内容']).strip()
                
                # 🆕 改进：解析复杂格式 "冠军-01,第三名-02,第四名-03,第五名-04,亚军-05"
                bets_by_position = {}
                
                # 尝试用逗号分割
                if ',' in content or '，' in content:
                    # 统一替换为半角逗号
                    content_clean = content.replace('，', ',')
                    parts = [p.strip() for p in content_clean.split(',')]
                    
                    for part in parts:
                        if part:
                            # 尝试用"-"或":"分割
                            separator = None
                            for sep in ['-', ':', '：']:
                                if sep in part:
                                    separator = sep
                                    break
                            
                            if separator:
                                pos_num = part.split(separator, 1)
                                if len(pos_num) == 2:
                                    position_name = pos_num[0].strip()
                                    number_part = pos_num[1].strip()
                                    
                                    # 标准化位置名称
                                    normalized_position = self.normalize_play_category(position_name, '10_number')
                                    
                                    # 提取号码
                                    numbers = []
                                    # 提取数字
                                    num_matches = re.findall(r'\d{1,2}', number_part)
                                    for num_str in num_matches:
                                        if num_str.isdigit():
                                            num = int(num_str)
                                            if 1 <= num <= 10:  # PK10号码范围
                                                numbers.append(num)
                                    
                                    if numbers and normalized_position in positions:
                                        if normalized_position not in bets_by_position:
                                            bets_by_position[normalized_position] = []
                                        bets_by_position[normalized_position].extend(numbers)
                
                # 🆕 如果没有解析出具体位置，尝试根据上下文推断
                if not bets_by_position:
                    # 提取所有数字
                    all_numbers = []
                    num_matches = re.findall(r'\d{1,2}', content)
                    for num_str in num_matches:
                        if num_str.isdigit():
                            num = int(num_str)
                            if 1 <= num <= 10:
                                all_numbers.append(num)
                    
                    if all_numbers:
                        # 将数字均匀分配到各个位置
                        num_per_position = min(len(all_numbers) // len(positions), 5)
                        if num_per_position > 0:
                            for i, position in enumerate(positions):
                                start_idx = i * num_per_position
                                end_idx = start_idx + num_per_position
                                if start_idx < len(all_numbers) and end_idx <= len(all_numbers):
                                    position_numbers = all_numbers[start_idx:end_idx]
                                    if position_numbers:
                                        bets_by_position[position] = position_numbers
                
                # 创建展开后的记录
                if bets_by_position:
                    for position, numbers in bets_by_position.items():
                        if numbers:  # 只创建有号码的记录
                            new_row = row.copy()
                            new_row['玩法'] = position
                            new_row['内容'] = ', '.join([f"{num:02d}" for num in sorted(set(numbers))])
                            expanded_rows.append(new_row)
                else:
                    # 无法解析，保留原始记录
                    expanded_rows.append(row)
            else:
                # 非分组玩法，直接保留
                expanded_rows.append(row)
        
        if expanded_rows:
            expanded_df = pd.DataFrame(expanded_rows)
            original_count = len(df)
            expanded_count = len(expanded_df)
            logger.info(f"📊 分组玩法展开: 从 {original_count} 条记录展开到 {expanded_count} 条记录")
            
            return expanded_df
        
        return df

    def enhanced_data_preprocessing(self, df_clean):
        """增强数据预处理流程 - 完全不显示中间过程"""
        # 1. 首先识别彩种类型
        df_clean['彩种类型'] = df_clean['彩种'].apply(self.identify_lottery_category)
        
        # 2. 统一玩法分类
        df_clean['玩法'] = df_clean.apply(
            lambda row: self.normalize_play_category(
                row['玩法'], 
                row['彩种类型'] if not pd.isna(row['彩种类型']) else 'six_mark'
            ), 
            axis=1
        )
        
        # 3. 提取号码 - 对于分组玩法，提取所有号码
        df_clean['提取号码'] = df_clean.apply(
            lambda row: self.cached_extract_numbers(
                row['内容'], 
                row['彩种类型'] if not pd.isna(row['彩种类型']) else 'six_mark',
                row['玩法']
            ), 
            axis=1
        )
        
        # 4. 统计每个记录的号码数量（不显示）
        df_clean['号码数量'] = df_clean['提取号码'].apply(len)
        
        # 5. 过滤无号码记录
        initial_count = len(df_clean)
        df_clean = df_clean[df_clean['提取号码'].apply(lambda x: len(x) > 0)]
        no_number_count = initial_count - len(df_clean)
        
        # 6. 过滤非号码投注玩法 - 保持分组玩法
        df_clean = self.filter_number_bets_only(df_clean)
        non_number_play_count = initial_count - no_number_count - len(df_clean)
        
        final_count = len(df_clean)
        
        # 🆕 只记录到日志，不显示
        logger.info(f"数据预处理: 从 {initial_count} 条记录中保留 {final_count} 条有效记录")
        logger.info(f"过滤统计: 无号码记录 {no_number_count} 条，非号码投注 {non_number_play_count} 条")
        logger.info(f"平均号码数/记录: {df_clean['号码数量'].mean():.1f}")
        
        return df_clean, no_number_count, non_number_play_count

    def analyze_group_play_period(self, df_target, period, lottery, min_number_count, min_avg_amount):
        """专门分析特定期号的分组玩法 - 完全不显示中间过程"""
        # 筛选该期号的所有数据
        period_data = df_target[
            (df_target['期号'] == period) & 
            (df_target['彩种'] == lottery)
        ]
        
        if len(period_data) < 2:
            return None
        
        # 按账户分组，合并所有号码
        account_numbers = {}
        account_amount_stats = {}
        account_bet_contents = {}
        
        for account in period_data['会员账号'].unique():
            account_data = period_data[period_data['会员账号'] == account]
            
            all_numbers = set()
            total_amount = 0
            
            for _, row in account_data.iterrows():
                numbers = row['提取号码'] if '提取号码' in row else self.cached_extract_numbers(row['内容'], '10_number', row['玩法'])
                all_numbers.update(numbers)
                
                # 提取金额
                if '投注金额' in row:
                    amount = row['投注金额']
                elif '金额' in row:
                    amount = self.extract_bet_amount(row['金额'])
                else:
                    amount = 0
                total_amount += amount
            
            if all_numbers:
                account_numbers[account] = sorted(all_numbers)
                account_bet_contents[account] = ", ".join([f"{num:02d}" for num in sorted(all_numbers)])
                
                number_count = len(all_numbers)
                avg_amount_per_number = total_amount / number_count if number_count > 0 else 0
                
                account_amount_stats[account] = {
                    'number_count': number_count,
                    'total_amount': total_amount,
                    'avg_amount_per_number': avg_amount_per_number
                }
        
        if len(account_numbers) < 2:
            return None
        
        # 尝试所有可能的2账户组合
        all_accounts = list(account_numbers.keys())
        perfect_combinations = []
        
        for i in range(len(all_accounts)):
            for j in range(i+1, len(all_accounts)):
                acc1 = all_accounts[i]
                acc2 = all_accounts[j]
                
                set1 = set(account_numbers[acc1])
                set2 = set(account_numbers[acc2])
                combined_set = set1 | set2
                
                # 检查是否覆盖1-10
                if len(combined_set) == 10 and set1.isdisjoint(set2):
                    # 检查金额匹配度
                    avg1 = account_amount_stats[acc1]['avg_amount_per_number']
                    avg2 = account_amount_stats[acc2]['avg_amount_per_number']
                    similarity = self.calculate_similarity([avg1, avg2])
                    
                    # 检查金额阈值
                    if avg1 >= float(min_avg_amount) and avg2 >= float(min_avg_amount):
                        result_data = {
                            'accounts': sorted([acc1, acc2]),
                            'account_count': 2,
                            'total_amount': account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount'],
                            'avg_amount_per_number': (account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount']) / 10,
                            'similarity': similarity,
                            'similarity_indicator': self.get_similarity_indicator(similarity),
                            'individual_amounts': {
                                acc1: account_amount_stats[acc1]['total_amount'],
                                acc2: account_amount_stats[acc2]['total_amount']
                            },
                            'individual_avg_per_number': {
                                acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                acc2: account_amount_stats[acc2]['avg_amount_per_number']
                            },
                            'bet_contents': {
                                acc1: account_bet_contents[acc1],
                                acc2: account_bet_contents[acc2]
                            },
                            'merged_numbers': sorted(combined_set)
                        }
                        
                        perfect_combinations.append(result_data)
        
        if perfect_combinations:
            return {
                'period': period,
                'lottery': lottery,
                'position': '全期号合并',
                'lottery_category': '10_number',
                'total_combinations': len(perfect_combinations),
                'all_combinations': perfect_combinations,
                'filtered_accounts': len(account_numbers),
                'total_numbers': 10
            }
        
        return None

    def analyze_pk10_group_plays(self, df_target, period, lottery, play_method, min_number_count, min_avg_amount):
        """专门分析PK10分组玩法（1-5名, 6-10名）"""
        
        # 筛选指定期号、彩种和玩法的数据
        group_data = df_target[
            (df_target['期号'] == period) & 
            (df_target['彩种'] == lottery) & 
            (df_target['玩法'] == play_method)
        ]
        
        if len(group_data) < 2:
            return None
        
        # 分析每个账户
        account_numbers = {}
        account_amount_stats = {}
        account_bet_contents = {}
        
        for account in group_data['会员账号'].unique():
            account_data = group_data[group_data['会员账号'] == account]
            
            all_numbers = set()
            total_amount = 0
            
            for _, row in account_data.iterrows():
                # 提取号码
                numbers = row['提取号码'] if '提取号码' in row else self.cached_extract_numbers(row['内容'], '10_number', play_method)
                all_numbers.update(numbers)
                
                # 提取金额
                if '投注金额' in row:
                    amount = row['投注金额']
                elif '金额' in row:
                    amount = self.extract_bet_amount(row['金额'])
                else:
                    amount = 0
                total_amount += amount
            
            if all_numbers:
                account_numbers[account] = sorted(all_numbers)
                account_bet_contents[account] = ", ".join([f"{num:02d}" for num in sorted(all_numbers)])
                
                number_count = len(all_numbers)
                avg_amount_per_number = total_amount / number_count if number_count > 0 else 0
                
                account_amount_stats[account] = {
                    'number_count': number_count,
                    'total_amount': total_amount,
                    'avg_amount_per_number': avg_amount_per_number
                }
        
        # 检查是否有足够的账户
        if len(account_numbers) < 2:
            return None
        
        # 分组玩法需要覆盖1-10所有号码
        total_numbers = 10
        
        # 寻找完美组合
        perfect_combinations = []
        accounts = list(account_numbers.keys())
        
        # 尝试所有可能的2账户组合
        for i in range(len(accounts)):
            for j in range(i+1, len(accounts)):
                acc1 = accounts[i]
                acc2 = accounts[j]
                
                set1 = set(account_numbers[acc1])
                set2 = set(account_numbers[acc2])
                combined_set = set1 | set2
                
                # 检查是否覆盖1-10且没有重复号码
                if len(combined_set) == total_numbers and set1.isdisjoint(set2):
                    # 计算金额匹配度
                    avg1 = account_amount_stats[acc1]['avg_amount_per_number']
                    avg2 = account_amount_stats[acc2]['avg_amount_per_number']
                    similarity = self.calculate_similarity([avg1, avg2])
                    
                    # 检查金额阈值
                    if avg1 >= float(min_avg_amount) and avg2 >= float(min_avg_amount):
                        result_data = {
                            'accounts': sorted([acc1, acc2]),
                            'account_count': 2,
                            'total_amount': account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount'],
                            'avg_amount_per_number': (account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount']) / 10,
                            'similarity': similarity,
                            'similarity_indicator': self.get_similarity_indicator(similarity),
                            'individual_amounts': {
                                acc1: account_amount_stats[acc1]['total_amount'],
                                acc2: account_amount_stats[acc2]['total_amount']
                            },
                            'individual_avg_per_number': {
                                acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                acc2: account_amount_stats[acc2]['avg_amount_per_number']
                            },
                            'bet_contents': {
                                acc1: account_bet_contents[acc1],
                                acc2: account_bet_contents[acc2]
                            },
                            'merged_numbers': sorted(combined_set)
                        }
                        
                        perfect_combinations.append(result_data)
        
        if perfect_combinations:
            # 排序：相似度高的在前
            perfect_combinations.sort(key=lambda x: -x['similarity'])
            
            return {
                'period': period,
                'lottery': lottery,
                'position': play_method,
                'lottery_category': '10_number',
                'total_combinations': len(perfect_combinations),
                'all_combinations': perfect_combinations,
                'filtered_accounts': len(account_numbers),
                'total_numbers': total_numbers,
                'is_group_play': True
            }
        
        return None

    def get_lottery_thresholds(self, lottery_category, user_min_avg_amount=None):
        """根据彩种类型获取阈值配置 - 使用配置中的默认阈值"""
        config = self.get_lottery_config(lottery_category)
        
        # 使用配置中的默认阈值，如果用户提供了值则使用用户的
        min_number_count = config.get('default_min_number_count', 3)
        min_avg_amount = config.get('default_min_avg_amount', 5)
        
        # 如果用户提供了平均金额阈值，使用用户的设置
        if user_min_avg_amount is not None:
            min_avg_amount = float(user_min_avg_amount)
        
        return {
            'min_number_count': min_number_count,
            'min_avg_amount': min_avg_amount,
            'description': config['type_name']
        }
    
    def get_dynamic_min_number_count(self, lottery_category, play_method=None):
        """根据彩种和玩法动态获取最小号码数量 - 通用版本"""
        play_str = str(play_method).strip().lower() if play_method else ""
        
        # 获取彩种配置
        config = self.get_play_specific_config(lottery_category, play_method)
        
        # 根据彩种类型和玩法设置动态最小号码数量
        if lottery_category == 'six_mark':
            if any(keyword in play_str for keyword in ['尾数', '全尾', '特尾']):
                return 3  # 六合彩尾数：0-9共10个号码，最小3个
            else:
                return 11  # 六合彩基础：1-49共49个号码，最小11个
        
        elif lottery_category == '10_number':
            if any(keyword in play_str for keyword in ['冠亚和', '冠亚和值']):
                return 5  # 冠亚和：3-19共17个号码，最小5个
            else:
                return 3  # 时时彩/PK10基础：1-10共10个号码，最小3个
        
        elif lottery_category == 'fast_three':
            if any(keyword in play_str for keyword in ['和值', '点数']):
                return 4  # 快三和值：3-18共16个号码，最小4个
            elif any(keyword in play_str for keyword in ['三军', '独胆', '单码']):
                return 2  # 快三基础：1-6共6个号码，最小2个
            else:
                return 4  # 默认使用和值阈值
        
        elif lottery_category == 'ssc_3d':
            return 3  # 时时彩/3D：0-9共10个号码，最小3个
        
        else:
            # 默认配置
            return config.get('default_min_number_count', 3)

    def identify_lottery_category(self, lottery_name):
        """识别彩种类型 - 增强六合彩识别"""
        lottery_str = str(lottery_name).strip().lower()
        
        # 检查六合彩
        for lottery in self.target_lotteries['six_mark']:
            if lottery.lower() in lottery_str:
                return 'six_mark'
        
        # 检查快三彩种
        for lottery in self.target_lotteries['fast_three']:
            if lottery.lower() in lottery_str:
                return 'fast_three'
        
        # 检查10个号码的彩种
        for lottery in self.target_lotteries['10_number']:
            if lottery.lower() in lottery_str:
                return '10_number'

        if any(word in lottery_str for word in ['排列三', '排列3', '福彩3d', '3d', '极速3d', '排列', 'p3', 'p三']):
            return '3d_series'
        
        if any(word in lottery_str for word in ['三色', '三色彩', '三色球']):
            return 'three_color'

        lottery_keywords_mapping = {
            'six_mark': ['六合', 'lhc', '⑥合', '6合', '特码', '平特', '连肖', '六合彩', '大乐透'],
            '10_number': ['pk10', 'pk拾', '飞艇', '赛车', '赛車', '幸运10', '北京赛车', '极速赛车', 
                         '时时彩', 'ssc', '分分彩', '時時彩', '重庆时时彩', '腾讯分分彩'],
            'fast_three': ['快三', '快3', 'k3', 'k三', '骰宝', '三军', '和值', '点数'],
            '3d_series': ['排列三', '排列3', '福彩3d', '3d', '极速3d', '排列', 'p3', 'p三'],
            'three_color': ['三色', '三色彩', '三色球']
        }
        
        for category, keywords in lottery_keywords_mapping.items():
            for keyword in keywords:
                if keyword in lottery_str:
                    return category
        
        # 模糊匹配
        if any(word in lottery_str for word in ['六合', 'lhc', '⑥合', '6合']):
            return 'six_mark'
        elif any(word in lottery_str for word in ['快三', '快3', 'k3']):
            return 'fast_three'
        elif any(word in lottery_str for word in ['时时彩', 'ssc']):
            return '10_number'
        elif any(word in lottery_str for word in ['pk10', 'pk拾', '赛车']):
            return '10_number'
        elif any(word in lottery_str for word in ['28', '幸运28']):
            return '10_number'
        
        return None
    
    def get_lottery_config(self, lottery_category):
        """获取彩种配置"""
        return self.lottery_configs.get(lottery_category, self.lottery_configs['six_mark'])

    def get_play_specific_config(self, lottery_category, play_method):
        """根据玩法和彩种类型获取具体的配置"""
        play_str = str(play_method).strip().lower() if play_method else ""
        
        # 🆕 六合彩尾数玩法 - 最高优先级
        if any(keyword in play_str for keyword in ['尾数', '全尾', '特尾']):
            return self.lottery_configs['six_mark_tail']
        
        # 🆕 快三基础玩法
        elif lottery_category == 'fast_three' and any(keyword in play_str for keyword in ['三军', '独胆', '单码', '二不同号', '三不同号']):
            return self.lottery_configs['fast_three_base']
        
        # 🆕 快三和值玩法
        elif lottery_category == 'fast_three' and any(keyword in play_str for keyword in ['和值', '点数']):
            return self.lottery_configs['fast_three_sum']
        
        # 🆕 冠亚和玩法
        elif lottery_category == '10_number' and any(keyword in play_str for keyword in ['冠亚和', '冠亚和值']):
            return self.lottery_configs['10_number_sum']
        
        # 🆕 时时彩和3D系列
        elif lottery_category in ['10_number', '3d_series'] and any(keyword in play_str for keyword in ['第1球', '第2球', '第3球', '第4球', '第5球', '万位', '千位', '百位', '十位', '个位']):
            return self.lottery_configs['ssc_3d']
        
        # 默认配置
        default_config = self.lottery_configs.get(lottery_category, self.lottery_configs['six_mark'])
        return default_config
    
    def enhanced_column_mapping(self, df):
        """增强版列名识别"""
        column_mapping = {}
        actual_columns = [str(col).strip() for col in df.columns]
        
        for standard_col, possible_names in self.column_mappings.items():
            found = False
            for actual_col in actual_columns:
                actual_col_lower = actual_col.lower().replace(' ', '').replace('_', '').replace('-', '')
                
                for possible_name in possible_names:
                    possible_name_lower = possible_name.lower().replace(' ', '').replace('_', '').replace('-', '')
                    
                    if (possible_name_lower in actual_col_lower or 
                        actual_col_lower in possible_name_lower or
                        len(set(possible_name_lower) & set(actual_col_lower)) / len(possible_name_lower) > 0.7):
                        column_mapping[actual_col] = standard_col
                        found = True
                        break
                if found:
                    break
            
            if not found:
                st.warning(f"⚠️ 未识别到 {standard_col} 对应的列名")
        
        # 检查必要列是否都已识别
        required_columns = ['会员账号', '彩种', '期号', '玩法', '内容']
        missing_columns = [col for col in required_columns if col not in column_mapping.values()]
        
        if missing_columns:
            st.error(f"❌ 缺少必要列: {missing_columns}")
            return None
        
        return column_mapping
    
    def validate_data_quality(self, df):
        """数据质量验证"""
        issues = []
        
        # 检查必要列
        required_cols = ['会员账号', '彩种', '期号', '玩法', '内容']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            issues.append(f"缺少必要列: {missing_cols}")
        
        # 检查空值
        for col in required_cols:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    issues.append(f"列 '{col}' 有 {null_count} 个空值")

        # 检查重复数据
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            issues.append(f"发现 {duplicate_count} 条重复记录")
        
        if issues:
            with st.expander("⚠️ 数据质量问题", expanded=True):
                for issue in issues:
                    st.warning(f"  - {issue}")
        # else:
            # st.success("✅ 数据质量检查通过")
        
        return issues

    def normalize_position(self, play_method):
        """统一位置名称 - 增强正码特位置识别"""
        play_str = str(play_method).strip()
        
        # ========== 最高优先级：正玛特独立映射 ==========
        if '正玛特' in play_str:
            if '正一' in play_str or '正1' in play_str:
                return '正一特'
            elif '正二' in play_str or '正2' in play_str:
                return '正二特'
            elif '正三' in play_str or '正3' in play_str:
                return '正三特'
            elif '正四' in play_str or '正4' in play_str:
                return '正四特'
            elif '正五' in play_str or '正5' in play_str:
                return '正五特'
            elif '正六' in play_str or '正6' in play_str:
                return '正六特'
            else:
                return '正特'
        
        # ========== 新增：正码特独立映射 ==========
        if '正码特' in play_str:
            if '正一' in play_str or '正1' in play_str:
                return '正一特'
            elif '正二' in play_str or '正2' in play_str:
                return '正二特'
            elif '正三' in play_str or '正3' in play_str:
                return '正三特'
            elif '正四' in play_str or '正4' in play_str:
                return '正四特'
            elif '正五' in play_str or '正5' in play_str:
                return '正五特'
            elif '正六' in play_str or '正6' in play_str:
                return '正六特'
            else:
                return '正特'
        
        # 特殊处理：正码1-6 正码 -> 正码
        if play_str == '正码1-6 正码':
            return '正码'
        
        # 特殊处理：正码1-6_正码 -> 正码
        if play_str == '正码1-6_正码':
            return '正码'
        
        # 特殊处理：正码特_正五特 -> 正五特
        if '正码特_正五特' in play_str or '正玛特_正五特' in play_str:
            return '正五特'
        
        # 特殊处理：正码1-6_正码一 -> 正码一
        if '正码1-6_正码一' in play_str:
            return '正码一'
        
        # 直接映射
        for standard_pos, variants in self.position_mapping.items():
            if play_str in variants:
                return standard_pos
        
        # 关键词匹配
        for standard_pos, variants in self.position_mapping.items():
            for variant in variants:
                if variant in play_str:
                    return standard_pos
        
        # 智能匹配 - 六合彩正码
        play_lower = play_str.lower()
        if '正码一' in play_lower or '正码1' in play_lower or '正一码' in play_lower:
            return '正码一'
        elif '正码二' in play_lower or '正码2' in play_lower or '正二码' in play_lower:
            return '正码二'
        elif '正码三' in play_lower or '正码3' in play_lower or '正三码' in play_lower:
            return '正码三'
        elif '正码四' in play_lower or '正码4' in play_lower or '正四码' in play_lower:
            return '正码四'
        elif '正码五' in play_lower or '正码5' in play_lower or '正五码' in play_lower:
            return '正码五'
        elif '正码六' in play_lower or '正码6' in play_lower or '正六码' in play_lower:
            return '正码六'
        
        # 智能匹配 - 六合彩正特
        elif '正一特' in play_lower or '正1特' in play_lower:
            return '正一特'
        elif '正二特' in play_lower or '正2特' in play_lower:
            return '正二特'
        elif '正三特' in play_lower or '正3特' in play_lower:
            return '正三特'
        elif '正四特' in play_lower or '正4特' in play_lower:
            return '正四特'
        elif '正五特' in play_lower or '正5特' in play_lower:
            return '正五特'
        elif '正六特' in play_lower or '正6特' in play_lower:
            return '正六特'
        
        # 智能匹配 - 六合彩其他
        elif '平码' in play_lower:
            return '平码'
        elif '平特' in play_lower:
            return '平特'
        elif '特码' in play_lower or '特玛' in play_lower or '特马' in play_lower or '特碼' in play_lower:
            return '特码'
        
        # 智能匹配 - PK10/赛车
        elif '冠军' in play_lower or '第一名' in play_lower or '1st' in play_lower:
            return '冠军'
        elif '亚军' in play_lower or '第二名' in play_lower or '2nd' in play_lower:
            return '亚军'
        elif '季军' in play_lower or '第三名' in play_lower or '3rd' in play_lower:
            return '季军'
        elif '第四名' in play_lower or '第四位' in play_lower or '4th' in play_lower:
            return '第四名'
        elif '第五名' in play_lower or '第五位' in play_lower or '5th' in play_lower:
            return '第五名'
        elif '第六名' in play_lower or '第六位' in play_lower or '6th' in play_lower:
            return '第六名'
        elif '第七名' in play_lower or '第七位' in play_lower or '7th' in play_lower:
            return '第七名'
        elif '第八名' in play_lower or '第八位' in play_lower or '8th' in play_lower:
            return '第八名'
        elif '第九名' in play_lower or '第九位' in play_lower or '9th' in play_lower:
            return '第九名'
        elif '第十名' in play_lower or '第十位' in play_lower or '10th' in play_lower:
            return '第十名'
        elif '前一' in play_lower or '前一位' in play_lower or '第一位' in play_lower:
            return '前一'
        
        # 智能匹配 - 快三
        elif '和值' in play_lower or '和数' in play_lower or '和' in play_lower:
            return '和值'
        
        return play_str

    def enhanced_normalize_special_characters(self, text):
        """增强特殊字符处理"""
        if not text:
            return text

        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    def enhanced_extract_position_from_content(self, play_method, content, lottery_category):
        """从内容中提取具体位置信息 - 针对定位胆等复合玩法"""
        play_str = str(play_method).strip()
        content_str = str(content).strip()
        
        # 🆕 增强定位胆玩法识别
        if play_str == '定位胆' and (':' in content_str or '：' in content_str):
            # 提取位置信息（如"亚军:03,04,05"中的"亚军"）
            position_match = re.match(r'^([^:：]+)[:：]', content_str)
            if position_match:
                position = position_match.group(1).strip()
                
                # 🆕 增强位置名称映射
                position_mapping = {
                    '冠军': '冠军', '亚军': '亚军', '季军': '季军',
                    '第四名': '第四名', '第五名': '第五名', '第六名': '第六名',
                    '第七名': '第七名', '第八名': '第八名', '第九名': '第九名', '第十名': '第十名',
                    '第1名': '冠军', '第2名': '亚军', '第3名': '季军',
                    '第4名': '第四名', '第5名': '第五名', '第6名': '第六名',
                    '第7名': '第七名', '第8名': '第八名', '第9名': '第九名', '第10名': '第十名',
                    '第一名': '冠军', '第二名': '亚军', '第三名': '季军',
                    '第四位': '第四名', '第五位': '第五名', '第六位': '第六名',
                    '第七位': '第七名', '第八位': '第八名', '第九位': '第九名', '第十位': '第十名',
                    '1st': '冠军', '2nd': '亚军', '3rd': '季军', '4th': '第四名', '5th': '第五名',
                    '6th': '第六名', '7th': '第七名', '8th': '第八名', '9th': '第九名', '10th': '第十名',
                    '前一': '冠军', '前二': '亚军', '前三': '季军',
                    # 🆕 新增：处理可能的空格和格式变体
                    '冠 军': '冠军', '亚 军': '亚军', '季 军': '季军',
                    '冠　军': '冠军', '亚　军': '亚军', '季　军': '季军',
                    # 🆕 新增：处理数字格式
                    '第 1 名': '冠军', '第 2 名': '亚军', '第 3 名': '季军',
                    '第1 名': '冠军', '第2 名': '亚军', '第3 名': '季军',
                }
                
                normalized_position = position_mapping.get(position, position)
                return normalized_position
        
        # 🆕 新增：处理没有冒号但内容明确包含位置名称的情况
        if play_str == '定位胆':
            content_lower = content_str.lower()
            position_keywords = {
                '冠军': ['冠军', '第一名', '第1名', '1st', '前一'],
                '亚军': ['亚军', '第二名', '第2名', '2nd'],
                '季军': ['季军', '第三名', '第3名', '3rd'],
                '第四名': ['第四名', '第4名', '4th'],
                '第五名': ['第五名', '第5名', '5th'],
                '第六名': ['第六名', '第6名', '6th'],
                '第七名': ['第七名', '第7名', '7th'],
                '第八名': ['第八名', '第8名', '8th'],
                '第九名': ['第九名', '第9名', '9th'],
                '第十名': ['第十名', '第10名', '10th']
            }
            
            for position, keywords in position_keywords.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        return position
        
        return play_str
    
    def normalize_play_category(self, play_method, lottery_category='six_mark'):
        """统一玩法分类 - 增强各种玩法的识别"""
        play_str = str(play_method).strip()
        
        # 规范化特殊字符
        import re
        play_normalized = re.sub(r'\s+', ' ', play_str)
        
        # ========== 最高优先级：正玛特独立映射 ==========
        if '正玛特' in play_normalized:
            if '正一' in play_normalized or '正1' in play_normalized:
                return '正一特'
            elif '正二' in play_normalized or '正2' in play_normalized:
                return '正二特'
            elif '正三' in play_normalized or '正3' in play_normalized:
                return '正三特'
            elif '正四' in play_normalized or '正4' in play_normalized:
                return '正四特'
            elif '正五' in play_normalized or '正5' in play_normalized:
                return '正五特'
            elif '正六' in play_normalized or '正6' in play_normalized:
                return '正六特'
            else:
                return '正特'
        
        # ========== 新增：正码特独立映射 ==========
        if '正码特' in play_normalized:
            if '正一' in play_normalized or '正1' in play_normalized:
                return '正一特'
            elif '正二' in play_normalized or '正2' in play_normalized:
                return '正二特'
            elif '正三' in play_normalized or '正3' in play_normalized:
                return '正三特'
            elif '正四' in play_normalized or '正4' in play_normalized:
                return '正四特'
            elif '正五' in play_normalized or '正5' in play_normalized:
                return '正五特'
            elif '正六' in play_normalized or '正6' in play_normalized:
                return '正六特'
            else:
                return '正特'
        
        # 特殊处理：正码1-6 正码 -> 正码
        if play_normalized == '正码1-6 正码':
            return '正码'
        
        # 特殊处理：正码1-6_正码 -> 正码  
        if play_normalized == '正码1-6_正码':
            return '正码'
        
        # 特殊处理：正码特_正五特 -> 正5特
        if '正码特_正五特' in play_normalized or '正玛特_正五特' in play_normalized:
            return '正五特'
        
        # 特殊处理：正码1-6_正码一 -> 正码一
        if '正码1-6_正码一' in play_normalized:
            return '正码一'
        
        # 1. 直接映射（完全匹配）
        if play_normalized in self.play_mapping:
            return self.play_mapping[play_normalized]
        
        # 2. 关键词匹配（包含匹配）
        for key, value in self.play_mapping.items():
            if key in play_normalized:
                return value
        
        # 3. 处理特殊格式（下划线、连字符分隔）
        if '_' in play_normalized or '-' in play_normalized:
            parts = re.split(r'[_-]', play_normalized)
            if len(parts) >= 2:
                main_play = parts[0].strip()
                sub_play = parts[1].strip()
                
                # 处理正码特和正玛特格式
                if '正码特' in main_play or '正玛特' in main_play:  # 关键修复
                    if '正一' in sub_play or '正1' in sub_play:
                        return '正1特'
                    elif '正二' in sub_play or '正2' in sub_play:
                        return '正2特'
                    elif '正三' in sub_play or '正3' in sub_play:
                        return '正3特'
                    elif '正四' in sub_play or '正4' in sub_play:
                        return '正4特'
                    elif '正五' in sub_play or '正5' in sub_play:
                        return '正5特'
                    elif '正六' in sub_play or '正6' in sub_play:
                        return '正6特'
                    else:
                        return '正特'
        
        # 4. 根据彩种类型智能匹配
        play_lower = play_normalized.lower()
        
        if lottery_category == 'six_mark':
            # 六合彩号码玩法智能匹配 - 增强正玛特识别
            if any(word in play_lower for word in ['特码', '特玛', '特马', '特碼']):
                return '特码'
            elif any(word in play_lower for word in ['正码一', '正码1', '正一码']):
                return '正码一'
            elif any(word in play_lower for word in ['正码二', '正码2', '正二码']):
                return '正码二'
            elif any(word in play_lower for word in ['正码三', '正码3', '正三码']):
                return '正码三'
            elif any(word in play_lower for word in ['正码四', '正码4', '正四码']):
                return '正码四'
            elif any(word in play_lower for word in ['正码五', '正码5', '正五码']):
                return '正码五'
            elif any(word in play_lower for word in ['正码六', '正码6', '正六码']):
                return '正码六'
            elif any(word in play_lower for word in ['正一特', '正1特']):
                return '正1特'
            elif any(word in play_lower for word in ['正二特', '正2特']):
                return '正2特'
            elif any(word in play_lower for word in ['正三特', '正3特']):
                return '正3特'
            elif any(word in play_lower for word in ['正四特', '正4特']):
                return '正4特'
            elif any(word in play_lower for word in ['正五特', '正5特']):
                return '正5特'
            elif any(word in play_lower for word in ['正六特', '正6特']):
                return '正6特'
            # 🆕 关键修复：增强尾数玩法识别
            elif any(word in play_lower for word in ['尾数']):
                return '尾数'
            elif any(word in play_lower for word in ['全尾']):
                return '全尾'
            elif any(word in play_lower for word in ['特尾']):
                return '特尾'
            # 关键修复：增强正玛特识别
            elif any(word in play_lower for word in ['正玛特']):
                # 如果正玛特后面有具体位置信息
                if '正一' in play_lower or '正1' in play_lower:
                    return '正1特'
                elif '正二' in play_lower or '正2' in play_lower:
                    return '正2特'
                elif '正三' in play_lower or '正3' in play_lower:
                    return '正3特'
                elif '正四' in play_lower or '正4' in play_lower:
                    return '正4特'
                elif '正五' in play_lower or '正5' in play_lower:
                    return '正5特'
                elif '正六' in play_lower or '正6' in play_lower:
                    return '正6特'
                else:
                    return '正特'
            elif any(word in play_lower for word in ['正特', '正码特']):
                return '正特'
            elif any(word in play_lower for word in ['平码']):
                return '平码'
            elif any(word in play_lower for word in ['平特']):
                return '平特'
            
        elif lottery_category == '10_number':
            # 时时彩/PK10/赛车号码玩法智能匹配
            if any(word in play_lower for word in ['冠军', '第一名', '第1名', '1st', '前一']):
                return '冠军'
            elif any(word in play_lower for word in ['亚军', '第二名', '第2名', '2nd']):
                return '亚军'
            elif any(word in play_lower for word in ['季军', '第三名', '第3名', '3rd']):
                return '季军'
            elif any(word in play_lower for word in ['第四名', '第4名', '4th']):
                return '第四名'
            elif any(word in play_lower for word in ['第五名', '第5名', '5th']):
                return '第五名'
            elif any(word in play_lower for word in ['第六名', '第6名', '6th']):
                return '第六名'
            elif any(word in play_lower for word in ['第七名', '第7名', '7th']):
                return '第七名'
            elif any(word in play_lower for word in ['第八名', '第8名', '8th']):
                return '第八名'
            elif any(word in play_lower for word in ['第九名', '第9名', '9th']):
                return '第九名'
            elif any(word in play_lower for word in ['第十名', '第10名', '10th']):
                return '第十名'
            elif any(word in play_lower for word in ['万位', '第一位', '第一球']):
                return '第1球'
            elif any(word in play_lower for word in ['千位', '第二位', '第二球']):
                return '第2球'
            elif any(word in play_lower for word in ['百位', '第三位', '第三球']):
                return '第3球'
            elif any(word in play_lower for word in ['十位', '第四位', '第四球']):
                return '第4球'
            elif any(word in play_lower for word in ['个位', '第五位', '第五球']):
                return '第5球'
            elif any(word in play_lower for word in ['定位胆', '一字定位', '一字', '定位']):
                return '定位胆'
            elif any(word in play_lower for word in ['1-5名', '1~5名']):
                return '1-5名'
            elif any(word in play_lower for word in ['6-10名', '6~10名']):
                return '6-10名'
            elif any(word in play_lower for word in ['冠亚和', '冠亚和值']):
                return '冠亚和'
        
        elif lottery_category == 'fast_three':
            # 快三号码玩法智能匹配
            if any(word in play_lower for word in ['和值', '和数', '和']):
                return '和值'
            elif any(word in play_lower for word in ['三军', '独胆', '单码']):
                return '三军'
            elif any(word in play_lower for word in ['二不同号', '二不同']):
                return '二不同号'
            elif any(word in play_lower for word in ['三不同号', '三不同']):
                return '三不同号'
        
        elif lottery_category == '3d_series':
            # 3D系列号码玩法智能匹配
            if any(word in play_lower for word in ['百位']):
                return '百位'
            elif any(word in play_lower for word in ['十位']):
                return '十位'
            elif any(word in play_lower for word in ['个位']):
                return '个位'
            elif any(word in play_lower for word in ['百十']):
                return '百十'
            elif any(word in play_lower for word in ['百个']):
                return '百个'
            elif any(word in play_lower for word in ['十个']):
                return '十个'
            elif any(word in play_lower for word in ['百十个']):
                return '百十个'
        
        # 5. 通用号码玩法匹配
        if any(word in play_lower for word in ['总和']):
            return '总和'
        elif any(word in play_lower for word in ['斗牛']):
            return '斗牛'
        
        return play_normalized
    
    @lru_cache(maxsize=5000)
    def cached_extract_numbers(self, content, lottery_category, play_method=None):
        """带缓存的号码提取 - 修复版本，支持玩法参数"""
        content_str = str(content) if content else ""
        return self.enhanced_extract_numbers(content_str, lottery_category, play_method)
    
    def enhanced_extract_numbers(self, content, lottery_category='six_mark', play_method=None):
        """增强号码提取 - 专门处理PK10位置-号码格式和复杂格式"""
        content_str = str(content).strip()
        numbers = []
        
        try:
            # 处理空内容
            if not content_str or content_str.lower() in ['', 'null', 'none', 'nan']:
                return []
            
            # 获取正确的配置
            config = self.get_play_specific_config(lottery_category, play_method)
            number_range = config['number_range']
            
            # 🆕 特殊处理：对于PK10系列的位置-号码格式（最高优先级）
            play_str = str(play_method).strip().lower() if play_method else ""
            
            # 1. 首先处理特殊格式："冠军-01,第三名-02,第四名-03,第五名-04,亚军-05"
            if lottery_category == '10_number' and ('-' in content_str or ':' in content_str or '：' in content_str):
                # 清理内容
                content_clean = content_str
                
                # 移除中文括号及其内容
                content_clean = re.sub(r'[\(（][^\)）]+[\)）]', '', content_clean)
                
                # 检查是否是位置-号码格式
                position_patterns = [
                    # 格式1: "冠军-01"
                    r'([^\d\-:：,，]+)[\-:：]\s*(\d{1,2})',
                    # 格式2: "冠军:01"
                    r'([^,:：\d]+)[,:：]\s*(\d{1,2})',
                    # 格式3: "冠军01" (无分隔符)
                    r'([^\d]+)(\d{1,2})'
                ]
                
                # 尝试多种模式匹配
                for pattern in position_patterns:
                    matches = re.findall(pattern, content_clean)
                    if matches:
                        for match in matches:
                            if len(match) >= 2:
                                position_part = match[0].strip()
                                num_str = match[1].strip()
                                
                                # 如果num_str是纯数字，直接处理
                                if num_str.isdigit():
                                    num = int(num_str)
                                    if num in number_range:
                                        numbers.append(num)
                        
                        if numbers:
                            # 去重并返回
                            numbers = list(set(numbers))
                            numbers = [num for num in numbers if num in number_range]
                            numbers.sort()
                            return numbers
                
                # 2. 处理逗号分隔的数字："01,02,03,04,05"
                if ',' in content_clean or '，' in content_clean:
                    # 替换全角逗号为半角逗号
                    content_clean = content_clean.replace('，', ',')
                    
                    # 分割并处理每个部分
                    parts = [p.strip() for p in content_clean.split(',')]
                    for part in parts:
                        # 提取数字
                        num_matches = re.findall(r'\d{1,2}', part)
                        for num_str in num_matches:
                            if num_str.isdigit():
                                num = int(num_str)
                                if num in number_range:
                                    numbers.append(num)
                    
                    if numbers:
                        numbers = list(set(numbers))
                        numbers = [num for num in numbers if num in number_range]
                        numbers.sort()
                        return numbers
            
            # 3. 通用数字提取（原有逻辑保持不变）
            # 从整个内容中提取所有数字
            all_number_matches = re.findall(r'\b\d{1,2}\b', content_str)
            if all_number_matches:
                for num_str in all_number_matches:
                    if num_str.isdigit():
                        num = int(num_str)
                        if num in number_range:
                            numbers.append(num)
                if numbers:
                    return list(set(numbers))
            
            # 处理分隔符格式
            separators = [',', '，', ' ', ';', '；', '、', '/', '\\', '|']
            for sep in separators:
                if sep in content_str:
                    parts = content_str.split(sep)
                    for part in parts:
                        part_clean = part.strip()
                        num_matches = re.findall(r'\b\d{1,2}\b', part_clean)
                        for num_str in num_matches:
                            if num_str.isdigit():
                                num = int(num_str)
                                if num in number_range:
                                    numbers.append(num)
                    if numbers:
                        break
            
            # 去重并排序
            numbers = list(set(numbers))
            numbers = [num for num in numbers if num in number_range]
            numbers.sort()

            return numbers
                
        except Exception as e:
            logger.warning(f"号码提取失败: {content_str}, 错误: {str(e)}")
            return []
    
    @lru_cache(maxsize=5000)
    def cached_extract_amount(self, amount_text):
        """带缓存的金额提取"""
        return self.extract_bet_amount(amount_text)
    
    def extract_bet_amount(self, amount_text):
        """金额提取函数 - 修复版本：支持多种复杂格式"""
        try:
            if pd.isna(amount_text) or amount_text is None:
                return 0.0
            
            # 转换为字符串并清理
            text = str(amount_text).strip()
            
            # 如果已经是空字符串，返回0
            if text == '':
                return 0.0
            
            # 🆕 新增：处理你的数据格式 "投注：20.000 抵用：0 中奖：0.000"
            if '投注：' in text or '投注:' in text:
                # 提取投注金额部分
                bet_patterns = [
                    r'投注[：:]\s*([\d\.,]+)',
                    r'下注[：:]\s*([\d\.,]+)',
                    r'投注金额[：:]\s*([\d\.,]+)',
                    r'金额[：:]\s*([\d\.,]+)'
                ]
                
                for pattern in bet_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        bet_amount_str = match.group(1)
                        # 清理千位分隔符
                        bet_amount_str = bet_amount_str.replace(',', '').replace('，', '')
                        try:
                            amount = float(bet_amount_str)
                            if amount >= 0:
                                return amount
                        except:
                            pass
            
            # 🆕 新增：处理特殊格式 "20.000"（三位小数）
            if re.match(r'^\d+\.\d{3}$', text):
                try:
                    amount = float(text)
                    return amount
                except:
                    pass
            
            # 🆕 新增：处理千位分隔符 "20,000" 或 "20，000"
            if ',' in text or '，' in text:
                try:
                    clean_text = text.replace(',', '').replace('，', '')
                    amount = float(clean_text)
                    return amount
                except:
                    pass
            
            # 方法1: 直接转换（处理纯数字）
            try:
                # 移除所有非数字字符（除了点和负号）
                clean_text = re.sub(r'[^\d.-]', '', text)
                if clean_text and clean_text != '-' and clean_text != '.':
                    amount = float(clean_text)
                    if amount >= 0:
                        return amount
            except:
                pass
            
            # 方法2: 使用正则表达式提取第一个数字
            numbers = re.findall(r'\d+\.?\d*', text)
            if numbers:
                # 只取第一个匹配的数字
                return float(numbers[0])
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"金额提取失败: {amount_text}, 错误: {str(e)}")
            return 0.0
    
    def calculate_similarity(self, avgs):
        """计算金额匹配度"""
        if not avgs or max(avgs) == 0:
            return 0
        return (min(avgs) / max(avgs)) * 100
    
    def get_similarity_indicator(self, similarity):
        """获取相似度颜色指示符"""
        thresholds = COVERAGE_CONFIG['similarity_thresholds']
        if similarity >= thresholds['excellent']: 
            return "🟢"
        elif similarity >= thresholds['good']: 
            return "🟡"
        elif similarity >= thresholds['fair']: 
            return "🟠"
        else: 
            return "🔴"
    
    def find_perfect_combinations(self, account_numbers, account_amount_stats, account_bet_contents, min_avg_amount, total_numbers, lottery_category, play_method=None, max_amount_ratio=10):
        """寻找完美组合 - 优化版本：基于数学配对的通用优化，支持所有彩种，包含金额平衡检查"""
        
        all_results = {2: [], 3: [], 4: []}
        
        # 转换账户数据为集合
        account_sets = {account: set(numbers) for account, numbers in account_numbers.items()}
        
        # 预计算：只保留满足金额阈值的账户
        valid_accounts = []
        for account in account_numbers.keys():
            avg_amount = account_amount_stats[account]['avg_amount_per_number']
            if avg_amount >= float(min_avg_amount):
                valid_accounts.append(account)
        
        logger.info(f"📊 {lottery_category}-{play_method}: 优化前 {len(account_numbers)} 账户, 优化后 {len(valid_accounts)} 有效账户")
        
        if len(valid_accounts) < 2:
            return all_results
        
        # 根据彩种类型获取动态最小号码数量
        min_number_count = self.get_dynamic_min_number_count(lottery_category, play_method)
        logger.info(f"🎯 {lottery_category}-{play_method}: 总号码数={total_numbers}, 最小号码数={min_number_count}")
        
        # 按号码数量分组
        accounts_by_count = {}
        for account in valid_accounts:
            count = len(account_sets[account])
            if count >= min_number_count:  # 只保留满足最小号码数量的账户
                if count not in accounts_by_count:
                    accounts_by_count[count] = []
                accounts_by_count[count].append(account)
        
        if not accounts_by_count:
            return all_results
        
        # 获取所有可能的号码数量
        available_counts = sorted(accounts_by_count.keys())
        
        # ==================== 2账户组合 ====================
        # 计算所有可能的2账户号码数量配对
        possible_pairs_2 = set()
        for count1 in available_counts:
            for count2 in available_counts:
                if count1 + count2 == total_numbers:
                    # 检查是否满足最小号码数量要求
                    if count1 >= min_number_count and count2 >= min_number_count:
                        possible_pairs_2.add(tuple(sorted([count1, count2])))
        
        logger.info(f"🎯 {lottery_category} 2账户可能的号码数量配对: {len(possible_pairs_2)} 种")
        
        # 用于跟踪已经找到的组合，避免重复
        found_combinations_2 = set()
        
        for count1, count2 in possible_pairs_2:
            if count1 not in accounts_by_count or count2 not in accounts_by_count:
                continue
                
            for acc1 in accounts_by_count[count1]:
                for acc2 in accounts_by_count[count2]:
                    if acc1 == acc2:
                        continue
                        
                    # 创建组合键，确保顺序一致
                    combo_key = tuple(sorted([acc1, acc2]))
                    if combo_key in found_combinations_2:
                        continue
                        
                    # 检查并集是否完美覆盖 且 没有重复号码
                    set1 = account_sets[acc1]
                    set2 = account_sets[acc2]
                    combined_set = set1 | set2
                    if len(combined_set) == total_numbers and set1.isdisjoint(set2):  # 添加互斥性检查
                        # 金额检查
                        avg_amounts = [
                            account_amount_stats[acc1]['avg_amount_per_number'],
                            account_amount_stats[acc2]['avg_amount_per_number']
                        ]
                        
                        # 检查金额平衡（最大金额与最小金额的倍数）
                        individual_amounts = [
                            account_amount_stats[acc1]['total_amount'],
                            account_amount_stats[acc2]['total_amount']
                        ]
                        max_amount = max(individual_amounts)
                        min_amount = min(individual_amounts)
                        
                        # 检查金额平衡条件
                        amount_balanced = True
                        if min_amount > 0 and max_amount / min_amount > max_amount_ratio:
                            amount_balanced = False
                        
                        if min(avg_amounts) >= float(min_avg_amount) and amount_balanced:
                            # 标记这个组合已经找到
                            found_combinations_2.add(combo_key)
                            
                            similarity = self.calculate_similarity(avg_amounts)
                            total_amount = account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount']
                            
                            result_data = {
                                'accounts': sorted([acc1, acc2]),  # 确保账户顺序一致
                                'account_count': 2,
                                'total_amount': total_amount,
                                'avg_amount_per_number': total_amount / total_numbers,
                                'similarity': similarity,
                                'similarity_indicator': self.get_similarity_indicator(similarity),
                                'individual_amounts': {
                                    acc1: account_amount_stats[acc1]['total_amount'],
                                    acc2: account_amount_stats[acc2]['total_amount']
                                },
                                'individual_avg_per_number': {
                                    acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                    acc2: account_amount_stats[acc2]['avg_amount_per_number']
                                },
                                'bet_contents': {
                                    acc1: account_bet_contents[acc1],
                                    acc2: account_bet_contents[acc2]
                                }
                            }
                            all_results[2].append(result_data)
        
        # ==================== 3账户组合 ====================
        # 计算所有可能的3账户号码数量配对
        possible_triples_3 = set()
        
        for count1 in available_counts:
            for count2 in available_counts:
                for count3 in available_counts:
                    if count1 + count2 + count3 == total_numbers:
                        # 检查是否满足最小号码数量要求
                        if (count1 >= min_number_count and 
                            count2 >= min_number_count and 
                            count3 >= min_number_count):
                            possible_triples_3.add(tuple(sorted([count1, count2, count3])))
        
        logger.info(f"🎯 {lottery_category} 3账户可能的号码数量配对: {len(possible_triples_3)} 种")
        
        # 用于跟踪已经找到的组合，避免重复
        found_combinations_3 = set()
        
        for count1, count2, count3 in possible_triples_3:
            if (count1 not in accounts_by_count or 
                count2 not in accounts_by_count or 
                count3 not in accounts_by_count):
                continue
                
            for acc1 in accounts_by_count[count1]:
                for acc2 in accounts_by_count[count2]:
                    if acc1 == acc2:
                        continue
                        
                    set1 = account_sets[acc1]
                    set2 = account_sets[acc2]
                    # 如果前两个账户有重复，跳过
                    if not set1.isdisjoint(set2):
                        continue
                        
                    set1_2 = set1 | set2
                    # 如果前两个账户的并集号码数小于它们号码数之和（说明有重复）
                    if len(set1_2) < count1 + count2:
                        continue
                        
                    for acc3 in accounts_by_count[count3]:
                        if acc3 in [acc1, acc2]:
                            continue
                        
                        set3 = account_sets[acc3]
                        # 检查第三个账户与前两个账户是否有重复
                        if not set1.isdisjoint(set3) or not set2.isdisjoint(set3):
                            continue
                            
                        combined_set = set1_2 | set3
                        if len(combined_set) == total_numbers:
                            # 创建组合键，确保顺序一致
                            combo_key = tuple(sorted([acc1, acc2, acc3]))
                            if combo_key in found_combinations_3:
                                continue
                                
                            # 金额检查
                            avg_amounts = [
                                account_amount_stats[acc1]['avg_amount_per_number'],
                                account_amount_stats[acc2]['avg_amount_per_number'],
                                account_amount_stats[acc3]['avg_amount_per_number']
                            ]
                            
                            # 检查金额平衡（最大金额与最小金额的倍数）
                            individual_amounts = [
                                account_amount_stats[acc1]['total_amount'],
                                account_amount_stats[acc2]['total_amount'],
                                account_amount_stats[acc3]['total_amount']
                            ]
                            max_amount = max(individual_amounts)
                            min_amount = min(individual_amounts)
                            
                            # 检查金额平衡条件
                            amount_balanced = True
                            if min_amount > 0 and max_amount / min_amount > max_amount_ratio:
                                amount_balanced = False
                            
                            if min(avg_amounts) >= float(min_avg_amount) and amount_balanced:
                                # 标记这个组合已经找到
                                found_combinations_3.add(combo_key)
                                
                                similarity = self.calculate_similarity(avg_amounts)
                                total_amount = (account_amount_stats[acc1]['total_amount'] + 
                                              account_amount_stats[acc2]['total_amount'] + 
                                              account_amount_stats[acc3]['total_amount'])
                                
                                result_data = {
                                    'accounts': sorted([acc1, acc2, acc3]),  # 确保账户顺序一致
                                    'account_count': 3,
                                    'total_amount': total_amount,
                                    'avg_amount_per_number': total_amount / total_numbers,
                                    'similarity': similarity,
                                    'similarity_indicator': self.get_similarity_indicator(similarity),
                                    'individual_amounts': {
                                        acc1: account_amount_stats[acc1]['total_amount'],
                                        acc2: account_amount_stats[acc2]['total_amount'],
                                        acc3: account_amount_stats[acc3]['total_amount']
                                    },
                                    'individual_avg_per_number': {
                                        acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                        acc2: account_amount_stats[acc2]['avg_amount_per_number'],
                                        acc3: account_amount_stats[acc3]['avg_amount_per_number']
                                    },
                                    'bet_contents': {
                                        acc1: account_bet_contents[acc1],
                                        acc2: account_bet_contents[acc2],
                                        acc3: account_bet_contents[acc3]
                                    }
                                }
                                all_results[3].append(result_data)
        
        # ==================== 4账户组合 ====================
        # 计算所有可能的4账户号码数量配对
        possible_quads_4 = set()
        
        for count1 in available_counts:
            for count2 in available_counts:
                for count3 in available_counts:
                    for count4 in available_counts:
                        if count1 + count2 + count3 + count4 == total_numbers:
                            # 检查是否满足最小号码数量要求
                            if (count1 >= min_number_count and 
                                count2 >= min_number_count and 
                                count3 >= min_number_count and 
                                count4 >= min_number_count):
                                possible_quads_4.add(tuple(sorted([count1, count2, count3, count4])))
        
        logger.info(f"🎯 {lottery_category} 4账户可能的号码数量配对: {len(possible_quads_4)} 种")
        
        # 用于跟踪已经找到的组合，避免重复
        found_combinations_4 = set()
        
        for count1, count2, count3, count4 in possible_quads_4:
            if (count1 not in accounts_by_count or 
                count2 not in accounts_by_count or 
                count3 not in accounts_by_count or 
                count4 not in accounts_by_count):
                continue
                
            for acc1 in accounts_by_count[count1]:
                for acc2 in accounts_by_count[count2]:
                    if acc1 == acc2:
                        continue
                        
                    set1 = account_sets[acc1]
                    set2 = account_sets[acc2]
                    # 检查前两个账户是否有重复
                    if not set1.isdisjoint(set2):
                        continue
                        
                    set1_2 = set1 | set2
                    # 如果前两个账户的并集号码数小于它们号码数之和
                    if len(set1_2) < count1 + count2:
                        continue
                        
                    for acc3 in accounts_by_count[count3]:
                        if acc3 in [acc1, acc2]:
                            continue
                        
                        set3 = account_sets[acc3]
                        # 检查第三个账户与前两个账户是否有重复
                        if not set1.isdisjoint(set3) or not set2.isdisjoint(set3):
                            continue
                            
                        set1_2_3 = set1_2 | set3
                        if len(set1_2_3) < count1 + count2 + count3:
                            continue
                            
                        for acc4 in accounts_by_count[count4]:
                            if acc4 in [acc1, acc2, acc3]:
                                continue
                            
                            set4 = account_sets[acc4]
                            # 检查第四个账户与前三个账户是否有重复
                            if (not set1.isdisjoint(set4) or not set2.isdisjoint(set4) or 
                                not set3.isdisjoint(set4)):
                                continue
                                
                            combined_set = set1_2_3 | set4
                            if len(combined_set) == total_numbers:
                                # 创建组合键，确保顺序一致
                                combo_key = tuple(sorted([acc1, acc2, acc3, acc4]))
                                if combo_key in found_combinations_4:
                                    continue
                                    
                                # 金额检查
                                avg_amounts = [
                                    account_amount_stats[acc1]['avg_amount_per_number'],
                                    account_amount_stats[acc2]['avg_amount_per_number'],
                                    account_amount_stats[acc3]['avg_amount_per_number'],
                                    account_amount_stats[acc4]['avg_amount_per_number']
                                ]
                                
                                # 检查金额平衡（最大金额与最小金额的倍数）
                                individual_amounts = [
                                    account_amount_stats[acc1]['total_amount'],
                                    account_amount_stats[acc2]['total_amount'],
                                    account_amount_stats[acc3]['total_amount'],
                                    account_amount_stats[acc4]['total_amount']
                                ]
                                max_amount = max(individual_amounts)
                                min_amount = min(individual_amounts)
                                
                                # 检查金额平衡条件
                                amount_balanced = True
                                if min_amount > 0 and max_amount / min_amount > max_amount_ratio:
                                    amount_balanced = False
                                
                                if min(avg_amounts) >= float(min_avg_amount) and amount_balanced:
                                    # 标记这个组合已经找到
                                    found_combinations_4.add(combo_key)
                                    
                                    similarity = self.calculate_similarity(avg_amounts)
                                    total_amount = (account_amount_stats[acc1]['total_amount'] + 
                                                  account_amount_stats[acc2]['total_amount'] + 
                                                  account_amount_stats[acc3]['total_amount'] +
                                                  account_amount_stats[acc4]['total_amount'])
                                    
                                    result_data = {
                                        'accounts': sorted([acc1, acc2, acc3, acc4]),  # 确保账户顺序一致
                                        'account_count': 4,
                                        'total_amount': total_amount,
                                        'avg_amount_per_number': total_amount / total_numbers,
                                        'similarity': similarity,
                                        'similarity_indicator': self.get_similarity_indicator(similarity),
                                        'individual_amounts': {
                                            acc1: account_amount_stats[acc1]['total_amount'],
                                            acc2: account_amount_stats[acc2]['total_amount'],
                                            acc3: account_amount_stats[acc3]['total_amount'],
                                            acc4: account_amount_stats[acc4]['total_amount']
                                        },
                                        'individual_avg_per_number': {
                                            acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                            acc2: account_amount_stats[acc2]['avg_amount_per_number'],
                                            acc3: account_amount_stats[acc3]['avg_amount_per_number'],
                                            acc4: account_amount_stats[acc4]['avg_amount_per_number']
                                        },
                                        'bet_contents': {
                                            acc1: account_bet_contents[acc1],
                                            acc2: account_bet_contents[acc2],
                                            acc3: account_bet_contents[acc3],
                                            acc4: account_bet_contents[acc4]
                                        }
                                    }
                                    all_results[4].append(result_data)
        
        # 统计结果
        total_found = sum(len(results) for results in all_results.values())
        logger.info(f"✅ {lottery_category}-{play_method}: 找到 {total_found} 个完美组合")
        
        return all_results

    def analyze_period_lottery_position(self, group, period, lottery, position, user_min_number_count, user_min_avg_amount, max_amount_ratio=10):
        """分析特定期数、彩种和位置 - 增强分组玩法分析，包含金额平衡检查"""
        
        lottery_category = self.identify_lottery_category(lottery)
        if not lottery_category:
            return None
        
        # 检查是否是分组玩法
        play_str = str(position).strip()
        is_group_play = False
        
        # 分组玩法关键词
        group_play_keywords = ['1-5名', '6-10名', '1~5名', '6~10名']
        
        for keyword in group_play_keywords:
            if keyword in play_str:
                is_group_play = True
                break
        
        # 获取配置
        if is_group_play:
            # 对于分组玩法，号码总数是10（1-10）
            config = self.get_play_specific_config('10_number', position)
            total_numbers = 10  # 固定为10，因为分组玩法需要覆盖1-10
        else:
            config = self.get_play_specific_config(lottery_category, position)
            total_numbers = config['total_numbers']
        
        # 使用动态阈值
        default_min_number_count = config.get('default_min_number_count', 3)
        default_min_avg_amount = config.get('default_min_avg_amount', 5)
        
        # 如果用户提供了阈值，则使用用户的，否则使用默认值
        min_number_count = int(user_min_number_count) if user_min_number_count is not None else default_min_number_count
        min_avg_amount = float(user_min_avg_amount) if user_min_avg_amount is not None else default_min_avg_amount
        
        has_amount_column = '投注金额' in group.columns
        account_numbers = {}
        account_amount_stats = {}
        account_bet_contents = {}
        
        for account in group['会员账号'].unique():
            account_data = group[group['会员账号'] == account]
            
            all_numbers = set()
            total_amount = 0
            
            for _, row in account_data.iterrows():
                if '提取号码' in row:
                    numbers = row['提取号码']
                else:
                    numbers = self.cached_extract_numbers(row['内容'], lottery_category, position)
                
                all_numbers.update(numbers)
                
                if has_amount_column:
                    amount = row['投注金额']
                    total_amount += amount
            
            if all_numbers:
                account_numbers[account] = sorted(all_numbers)
                account_bet_contents[account] = ", ".join([f"{num:02d}" for num in sorted(all_numbers)])
                number_count = len(all_numbers)
                avg_amount_per_number = total_amount / number_count if number_count > 0 else 0
                
                account_amount_stats[account] = {
                    'number_count': number_count,
                    'total_amount': total_amount,
                    'avg_amount_per_number': avg_amount_per_number
                }
        
        # 筛选有效账户 - 对于分组玩法，使用宽松的阈值
        if is_group_play:
            # 分组玩法：至少5个号码（覆盖1-5名或6-10名）
            dynamic_min_number_count = 5
        else:
            dynamic_min_number_count = self.get_dynamic_min_number_count(lottery_category, position)
        
        filtered_account_numbers = {}
        filtered_account_amount_stats = {}
        filtered_account_bet_contents = {}
        
        for account, numbers in account_numbers.items():
            stats = account_amount_stats[account]
            if len(numbers) >= dynamic_min_number_count and stats['avg_amount_per_number'] >= min_avg_amount:
                filtered_account_numbers[account] = numbers
                filtered_account_amount_stats[account] = account_amount_stats[account]
                filtered_account_bet_contents[account] = account_bet_contents[account]
        
        if len(filtered_account_numbers) < 2:
            return None
        
        # 对于分组玩法，调整分析参数
        if is_group_play:
            # 分组玩法：两个账户的组合需要覆盖1-10
            # 检查两个账户的号码是否合并后覆盖1-10
            all_accounts = list(filtered_account_numbers.keys())
            
            if len(all_accounts) >= 2:
                # 尝试所有可能的2账户组合
                for i in range(len(all_accounts)):
                    for j in range(i+1, len(all_accounts)):
                        acc1 = all_accounts[i]
                        acc2 = all_accounts[j]
                        
                        set1 = set(filtered_account_numbers[acc1])
                        set2 = set(filtered_account_numbers[acc2])
                        combined_set = set1 | set2
                        
                        # 检查是否覆盖1-10 且 没有重复号码
                        if len(combined_set) == 10 and set1.isdisjoint(set2):
                            # 计算金额匹配度
                            avg1 = filtered_account_amount_stats[acc1]['avg_amount_per_number']
                            avg2 = filtered_account_amount_stats[acc2]['avg_amount_per_number']
                            similarity = self.calculate_similarity([avg1, avg2])
                            
                            # 检查金额平衡
                            amount1 = filtered_account_amount_stats[acc1]['total_amount']
                            amount2 = filtered_account_amount_stats[acc2]['total_amount']
                            max_amount = max(amount1, amount2)
                            min_amount = min(amount1, amount2)
                            
                            # 检查金额平衡条件
                            amount_balanced = True
                            if min_amount > 0 and max_amount / min_amount > max_amount_ratio:
                                amount_balanced = False
                            
                            if amount_balanced:
                                result_data = {
                                    'accounts': sorted([acc1, acc2]),
                                    'account_count': 2,
                                    'total_amount': filtered_account_amount_stats[acc1]['total_amount'] + filtered_account_amount_stats[acc2]['total_amount'],
                                    'avg_amount_per_number': (filtered_account_amount_stats[acc1]['total_amount'] + filtered_account_amount_stats[acc2]['total_amount']) / 10,
                                    'similarity': similarity,
                                    'similarity_indicator': self.get_similarity_indicator(similarity),
                                    'individual_amounts': {
                                        acc1: filtered_account_amount_stats[acc1]['total_amount'],
                                        acc2: filtered_account_amount_stats[acc2]['total_amount']
                                    },
                                    'individual_avg_per_number': {
                                        acc1: filtered_account_amount_stats[acc1]['avg_amount_per_number'],
                                        acc2: filtered_account_amount_stats[acc2]['avg_amount_per_number']
                                    },
                                    'bet_contents': {
                                        acc1: filtered_account_bet_contents[acc1],
                                        acc2: filtered_account_bet_contents[acc2]
                                    }
                                }
                                
                                return {
                                    'period': period,
                                    'lottery': lottery,
                                    'position': position,
                                    'lottery_category': lottery_category,
                                    'total_combinations': 1,
                                    'all_combinations': [result_data],
                                    'filtered_accounts': len(filtered_account_numbers),
                                    'total_numbers': 10
                                }
        
        # 对于非分组玩法，使用原有逻辑
        all_results = self.find_perfect_combinations(
            filtered_account_numbers, 
            filtered_account_amount_stats, 
            filtered_account_bet_contents,
            min_avg_amount,
            total_numbers,
            lottery_category,
            position,
            max_amount_ratio  # 新增参数
        )
        
        total_combinations = sum(len(results) for results in all_results.values())
        
        if total_combinations > 0:
            all_combinations = []
            for results in all_results.values():
                all_combinations.extend(results)
            
            all_combinations.sort(key=lambda x: (x['account_count'], -x['similarity']))
            
            return {
                'period': period,
                'lottery': lottery,
                'position': position,
                'lottery_category': lottery_category,
                'total_combinations': total_combinations,
                'all_combinations': all_combinations,
                'filtered_accounts': len(filtered_account_numbers),
                'total_numbers': total_numbers
            }
        
        return None

    def analyze_account_behavior(self, df):
        """新增：账户行为分析"""
        account_stats = {}
        
        for account in df['会员账号'].unique():
            account_data = df[df['会员账号'] == account]
            
            # 基础统计
            total_periods = account_data['期号'].nunique()
            total_records = len(account_data)
            total_lotteries = account_data['彩种'].nunique()
            
            # 彩种偏好分析
            lottery_preference = account_data['彩种'].value_counts().head(3).to_dict()
            
            # 玩法偏好分析  
            play_preference = account_data['玩法'].value_counts().head(5).to_dict()
            
            # 活跃度等级
            activity_level = self._get_activity_level(total_periods)
            
            account_stats[account] = {
                'total_periods': total_periods,
                'total_records': total_records,
                'total_lotteries': total_lotteries,
                'lottery_preference': lottery_preference,
                'play_preference': play_preference,
                'activity_level': activity_level,
                'avg_records_per_period': total_records / total_periods if total_periods > 0 else 0
            }
        
        return account_stats
    
    def _get_activity_level(self, total_periods):
        """获取活跃度等级"""
        if total_periods <= 10:
            return '低活跃'
        elif total_periods <= 50:
            return '中活跃' 
        elif total_periods <= 100:
            return '高活跃'
        else:
            return '极高活跃'
    
    def display_account_behavior_analysis(self, account_stats):
        """显示账户行为分析结果"""
        st.subheader("👤 账户行为分析")
        
        if not account_stats:
            st.info("暂无账户行为分析数据")
            return
        
        # 转换为DataFrame便于显示
        stats_list = []
        for account, stats in account_stats.items():
            stats_list.append({
                '账户': account,
                '活跃度': stats['activity_level'],
                '投注期数': stats['total_periods'],
                '总记录数': stats['total_records'],
                '涉及彩种': stats['total_lotteries'],
                '主要彩种': ', '.join([f"{k}({v})" for k, v in list(stats['lottery_preference'].items())[:2]]),
                '期均记录': f"{stats['avg_records_per_period']:.1f}"
            })
        
        df_stats = pd.DataFrame(stats_list)
        df_stats = df_stats.sort_values('投注期数', ascending=False)
        
        st.dataframe(
            df_stats,
            use_container_width=True,
            hide_index=True,
            height=min(400, len(df_stats) * 35 + 38)
        )
        
        # 活跃度分布
        activity_dist = df_stats['活跃度'].value_counts()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总账户数", len(account_stats))
        with col2:
            st.metric("高活跃账户", activity_dist.get('高活跃', 0) + activity_dist.get('极高活跃', 0))
        with col3:
            st.metric("平均期数", f"{df_stats['投注期数'].mean():.1f}")

    def analyze_period_merge_coverage(self, df_target, period, lottery, min_number_count, min_avg_amount):
        """按期号合并分析：不考虑位置，只看整个期号的号码覆盖"""
        # 筛选该期号的数据
        period_data = df_target[
            (df_target['期号'] == period) & 
            (df_target['彩种'] == lottery)
        ]
        
        if len(period_data) < 2:
            return None
        
        # 按账户分组，合并所有号码（不考虑位置）
        account_numbers = {}
        account_amount_stats = {}
        account_bet_contents = {}
        
        for account in period_data['会员账号'].unique():
            account_data = period_data[period_data['会员账号'] == account]
            
            all_numbers = set()
            total_amount = 0
            
            for _, row in account_data.iterrows():
                numbers = row['提取号码'] if '提取号码' in row else self.cached_extract_numbers(row['内容'], '10_number', row['玩法'])
                all_numbers.update(numbers)
                
                # 提取金额
                if '投注金额' in row:
                    amount = row['投注金额']
                elif '金额' in row:
                    amount = self.extract_bet_amount(row['金额'])
                    total_amount += amount
                else:
                    amount = 0
                    total_amount += amount
            
            if all_numbers:
                account_numbers[account] = sorted(all_numbers)
                account_bet_contents[account] = ", ".join([f"{num:02d}" for num in sorted(all_numbers)])
                
                number_count = len(all_numbers)
                avg_amount_per_number = total_amount / number_count if number_count > 0 else 0
                
                account_amount_stats[account] = {
                    'number_count': number_count,
                    'total_amount': total_amount,
                    'avg_amount_per_number': avg_amount_per_number
                }
        
        if len(account_numbers) < 2:
            return None
        
        # 尝试所有可能的2账户组合
        all_accounts = list(account_numbers.keys())
        perfect_combinations = []
        
        for i in range(len(all_accounts)):
            for j in range(i+1, len(all_accounts)):
                acc1 = all_accounts[i]
                acc2 = all_accounts[j]
                
                set1 = set(account_numbers[acc1])
                set2 = set(account_numbers[acc2])
                combined_set = set1 | set2
                
                # 检查是否覆盖1-10
                if len(combined_set) == 10 and set1.isdisjoint(set2):
                    # 检查金额匹配度
                    avg1 = account_amount_stats[acc1]['avg_amount_per_number']
                    avg2 = account_amount_stats[acc2]['avg_amount_per_number']
                    similarity = self.calculate_similarity([avg1, avg2])
                    
                    # 记录所有组合
                    meets_threshold = avg1 >= float(min_avg_amount) and avg2 >= float(min_avg_amount)
                    
                    result_data = {
                        'accounts': sorted([acc1, acc2]),
                        'account_count': 2,
                        'total_amount': account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount'],
                        'avg_amount_per_number': (account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount']) / 10,
                        'similarity': similarity,
                        'similarity_indicator': self.get_similarity_indicator(similarity),
                        'individual_amounts': {
                            acc1: account_amount_stats[acc1]['total_amount'],
                            acc2: account_amount_stats[acc2]['total_amount']
                        },
                        'individual_avg_per_number': {
                            acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                            acc2: account_amount_stats[acc2]['avg_amount_per_number']
                        },
                        'bet_contents': {
                            acc1: account_bet_contents[acc1],
                            acc2: account_bet_contents[acc2]
                        },
                        'merged_numbers': sorted(combined_set),
                        'meets_amount_threshold': meets_threshold
                    }
                    
                    perfect_combinations.append(result_data)
        
        if perfect_combinations:
            # 筛选满足金额阈值的组合
            filtered_combinations = [combo for combo in perfect_combinations if combo['meets_amount_threshold']]
            
            if filtered_combinations:
                # 移除临时字段
                for combo in filtered_combinations:
                    del combo['meets_amount_threshold']
                
                return {
                    'period': period,
                    'lottery': lottery,
                    'position': '按期号合并',
                    'lottery_category': '10_number',
                    'total_combinations': len(filtered_combinations),
                    'all_combinations': filtered_combinations,
                    'filtered_accounts': len(account_numbers),
                    'total_numbers': 10
                }
        
        return None
    
    def analyze_with_progress(self, df_target, six_mark_params, ten_number_params, fast_three_params, ssc_3d_params, analysis_mode, max_amount_ratio=10):
        """带进度显示的分析 - 根据不同彩种使用不同的分析方法"""
        all_period_results = {}
        
        # 根据分析模式筛选数据
        if analysis_mode == "仅分析六合彩":
            df_target = df_target[df_target['彩种类型'] == 'six_mark']
            # 六合彩：按位置分析
            return self.analyze_by_position(df_target, six_mark_params, 'six_mark', max_amount_ratio)
            
        elif analysis_mode == "仅分析时时彩/PK10/赛车":
            df_target = df_target[df_target['彩种类型'] == '10_number']
            # PK10/时时彩/赛车：按期号合并分析
            return self.analyze_by_period_merge(df_target, ten_number_params, '10_number', max_amount_ratio)
            
        elif analysis_mode == "仅分析快三":
            df_target = df_target[df_target['彩种类型'] == 'fast_three']
            # 快三：按位置分析（和值）
            return self.analyze_by_position(df_target, fast_three_params, 'fast_three', max_amount_ratio)
            
        else:
            # 自动识别所有彩种：分别用不同方法分析
            all_results = {}
            
            # 六合彩：按位置分析
            six_mark_data = df_target[df_target['彩种类型'] == 'six_mark']
            if len(six_mark_data) > 0:
                six_mark_results = self.analyze_by_position(six_mark_data, six_mark_params, 'six_mark', max_amount_ratio)
                all_results.update(six_mark_results)
            
            # PK10/时时彩/赛车：按期号合并分析
            ten_number_data = df_target[df_target['彩种类型'] == '10_number']
            if len(ten_number_data) > 0:
                ten_number_results = self.analyze_by_period_merge(ten_number_data, ten_number_params, '10_number', max_amount_ratio)
                all_results.update(ten_number_results)
            
            # 快三：按位置分析
            fast_three_data = df_target[df_target['彩种类型'] == 'fast_three']
            if len(fast_three_data) > 0:
                fast_three_results = self.analyze_by_position(fast_three_data, fast_three_params, 'fast_three', max_amount_ratio)
                all_results.update(fast_three_results)
            
            return all_results
    
    def analyze_by_position(self, df_target, params, lottery_category, max_amount_ratio=10):
        """按位置分析 - 适用于六合彩、快三等需要按位置单独分析的彩种"""
        all_period_results = {}
        
        if lottery_category == 'six_mark':
            min_number_count = params['min_number_count']
            min_avg_amount = params['min_avg_amount']
            total_numbers = 49  # 六合彩总号码数
        elif lottery_category == 'fast_three':
            min_number_count = params.get('sum_min_number_count', 4)  # 默认和值阈值
            min_avg_amount = params.get('sum_min_avg_amount', 5)
            total_numbers = 16  # 快三和值总号码数
        else:
            min_number_count = 3
            min_avg_amount = 5
            total_numbers = 10
        
        # 按期号、彩种、玩法分组
        grouped = df_target.groupby(['期号', '彩种', '玩法'])
        
        for (period, lottery, position), group in grouped:
            if len(group) >= 2:
                # 调用原有的按位置分析方法
                result = self.analyze_period_lottery_position(
                    group, period, lottery, position,
                    min_number_count,
                    min_avg_amount,
                    max_amount_ratio  # 新增参数
                )
                if result:
                    key = (period, lottery, position)
                    all_period_results[key] = result
        
        return all_period_results
    
    def analyze_by_period_merge(self, df_target, params, lottery_category, max_amount_ratio=10):
        """按期号合并分析 - 专门用于PK10/时时彩/赛车"""
        all_period_results = {}
        
        # 获取参数
        min_number_count = params['min_number_count']
        min_avg_amount = params['min_avg_amount']
        
        # 获取所有唯一的期号
        all_unique_periods = df_target['期号'].unique()
        
        # 分析每个期号
        for period in all_unique_periods:
            # 获取该期号的所有彩票类型
            period_lotteries = df_target[df_target['期号'] == period]['彩种'].unique()
            
            for lottery in period_lotteries:
                # 使用专门的PK10按期号合并分析方法
                result = self.analyze_pk10_period_merge(
                    df_target, period, lottery,
                    min_number_count,
                    min_avg_amount,
                    max_amount_ratio  # 新增参数
                )
                
                if result:
                    key = (period, lottery, '按期号合并')
                    all_period_results[key] = result
        
        return all_period_results
    
    def analyze_pk10_period_merge(self, df_target, period, lottery, min_number_count, min_avg_amount, max_amount_ratio=10):
        """PK10按期号合并分析 - 专门用于PK10系列彩票，包含金额平衡检查"""
        # 筛选该期号的所有数据
        period_data = df_target[
            (df_target['期号'] == period) & 
            (df_target['彩种'] == lottery)
        ]
        
        if len(period_data) < 2:
            return None
        
        # 按账户分组，合并所有号码
        account_numbers = {}
        account_amount_stats = {}
        account_bet_contents = {}
        
        for account in period_data['会员账号'].unique():
            account_data = period_data[period_data['会员账号'] == account]
            
            all_numbers = set()
            total_amount = 0
            
            for _, row in account_data.iterrows():
                numbers = row['提取号码'] if '提取号码' in row else self.cached_extract_numbers(row['内容'], '10_number', row['玩法'])
                all_numbers.update(numbers)
                
                # 提取金额
                if '投注金额' in row:
                    amount = row['投注金额']
                elif '金额' in row:
                    amount = self.extract_bet_amount(row['金额'])
                else:
                    amount = 0
                total_amount += amount
            
            if all_numbers:
                account_numbers[account] = sorted(all_numbers)
                account_bet_contents[account] = ", ".join([f"{num:02d}" for num in sorted(all_numbers)])
                
                number_count = len(all_numbers)
                avg_amount_per_number = total_amount / number_count if number_count > 0 else 0
                
                account_amount_stats[account] = {
                    'number_count': number_count,
                    'total_amount': total_amount,
                    'avg_amount_per_number': avg_amount_per_number
                }
        
        if len(account_numbers) < 2:
            return None
        
        # PK10总号码数是10
        total_numbers = 10
        
        # 尝试所有可能的2账户组合
        all_accounts = list(account_numbers.keys())
        perfect_combinations = []
        
        for i in range(len(all_accounts)):
            for j in range(i+1, len(all_accounts)):
                acc1 = all_accounts[i]
                acc2 = all_accounts[j]
                
                set1 = set(account_numbers[acc1])
                set2 = set(account_numbers[acc2])
                combined_set = set1 | set2
                
                # 检查是否覆盖1-10 且 没有重复号码
                if len(combined_set) == total_numbers and set1.isdisjoint(set2):
                    # 检查金额匹配度
                    avg1 = account_amount_stats[acc1]['avg_amount_per_number']
                    avg2 = account_amount_stats[acc2]['avg_amount_per_number']
                    similarity = self.calculate_similarity([avg1, avg2])
                    
                    # 检查金额平衡
                    amount1 = account_amount_stats[acc1]['total_amount']
                    amount2 = account_amount_stats[acc2]['total_amount']
                    max_amount = max(amount1, amount2)
                    min_amount = min(amount1, amount2)
                    
                    # 检查金额阈值和金额平衡
                    if (avg1 >= float(min_avg_amount) and avg2 >= float(min_avg_amount) and
                        min_amount > 0 and max_amount / min_amount <= max_amount_ratio):
                        
                        result_data = {
                            'accounts': sorted([acc1, acc2]),
                            'account_count': 2,
                            'total_amount': account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount'],
                            'avg_amount_per_number': (account_amount_stats[acc1]['total_amount'] + account_amount_stats[acc2]['total_amount']) / 10,
                            'similarity': similarity,
                            'similarity_indicator': self.get_similarity_indicator(similarity),
                            'individual_amounts': {
                                acc1: account_amount_stats[acc1]['total_amount'],
                                acc2: account_amount_stats[acc2]['total_amount']
                            },
                            'individual_avg_per_number': {
                                acc1: account_amount_stats[acc1]['avg_amount_per_number'],
                                acc2: account_amount_stats[acc2]['avg_amount_per_number']
                            },
                            'bet_contents': {
                                acc1: account_bet_contents[acc1],
                                acc2: account_bet_contents[acc2]
                            },
                            'merged_numbers': sorted(combined_set)
                        }
                        
                        perfect_combinations.append(result_data)
        
        if perfect_combinations:
            return {
                'period': period,
                'lottery': lottery,
                'position': '按期号合并',
                'lottery_category': '10_number',
                'total_combinations': len(perfect_combinations),
                'all_combinations': perfect_combinations,
                'filtered_accounts': len(account_numbers),
                'total_numbers': total_numbers
            }
        
        return None

    def display_enhanced_results(self, all_period_results, analysis_mode, df_target=None):
        """增强结果展示 - 保留统计信息版本，传入df_target用于计算总投注期数"""
        if not all_period_results:
            st.info("🎉 未发现完美覆盖组合")
            return
    
        # 按账户组合和彩种分组
        account_pair_groups = defaultdict(lambda: defaultdict(list))
        
        for group_key, result in all_period_results.items():
            lottery = result['lottery']
            position = result.get('position', None)
            
            for combo in result['all_combinations']:
                # 创建账户组合键
                accounts = combo['accounts']
                account_pair = " ↔ ".join(sorted(accounts))
                
                # 创建彩种键
                if position:
                    lottery_key = f"{lottery} - {position}"
                else:
                    lottery_key = lottery
                
                # 存储组合信息
                combo_info = {
                    'period': result['period'],
                    'combo': combo,
                    'lottery_category': result['lottery_category'],
                    'total_numbers': result['total_numbers']
                }
                
                account_pair_groups[account_pair][lottery_key].append(combo_info)
    
        # 显示彩种类型统计
        st.subheader("🎲 组合类型统计")
        col1, col2, col3, col4 = st.columns(4)
        
        # 计算各类型组合数量
        combo_type_stats = {2: 0, 3: 0, 4: 0}
        for result in all_period_results.values():
            for combo in result['all_combinations']:
                combo_type_stats[combo['account_count']] += 1
        
        with col1:
            st.metric("2账户组合", f"{combo_type_stats[2]}组")
        with col2:
            st.metric("3账户组合", f"{combo_type_stats[3]}组")
        with col3:
            st.metric("4账户组合", f"{combo_type_stats[4]}组")
        with col4:
            total_combinations = sum(combo_type_stats.values())
            st.metric("总组合数", f"{total_combinations}组")
        
        # 显示汇总统计
        st.subheader("📊 检测汇总")
        total_combinations = sum(result['total_combinations'] for result in all_period_results.values())
        total_filtered_accounts = sum(result['filtered_accounts'] for result in all_period_results.values())
        total_periods = len(set(result['period'] for result in all_period_results.values()))
        total_lotteries = len(set(result['lottery'] for result in all_period_results.values()))
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总完美组合数", total_combinations)
        with col2:
            st.metric("分析期数", total_periods)
        with col3:
            st.metric("有效账户数", total_filtered_accounts)
        with col4:
            st.metric("涉及彩种", total_lotteries)
        
        # 参与账户详细统计 - 使用新的统计函数
        st.subheader("👥 参与账户详细统计")
        account_stats = self._calculate_detailed_account_stats(all_period_results, df_target)
        
        if account_stats:
            df_stats = pd.DataFrame(account_stats)
            
            # 重新排序列顺序，将彩种期数放在涉及期数前面
            columns_order = ['账户', '参与组合数', '彩种期数', '涉及期数', 
                            '涉及彩种', '组合类型', '总投注金额', '平均每期金额', '涉及位置']
            # 只保留存在的列
            existing_columns = [col for col in columns_order if col in df_stats.columns]
            # 添加其他列
            other_columns = [col for col in df_stats.columns if col not in existing_columns]
            final_columns = existing_columns + other_columns
            
            df_stats = df_stats[final_columns]
            
            st.dataframe(
                df_stats,
                use_container_width=True,
                hide_index=True,
                height=min(400, len(df_stats) * 35 + 38)
            )
        
        # 显示详细组合分析 - 传入账户统计信息
        st.subheader("📈 详细组合分析")
        self._display_by_account_pair_lottery(account_pair_groups, analysis_mode, account_stats)

    def _calculate_detailed_account_stats(self, all_period_results, df_target):
        """详细账户统计 - 改进彩种名称匹配逻辑"""
        account_stats = []
        account_participation = defaultdict(lambda: {
            'periods': set(),
            'lotteries': set(),
            'positions': set(),
            'total_combinations': 0,
            'total_bet_amount': 0,
            'combo_types': set(),
            'violation_lottery_periods': defaultdict(set)
        })
        
        # 首先计算每个账户在各彩种的总投注期数（从原始数据df_target）
        account_lottery_periods = defaultdict(lambda: defaultdict(set))
        
        # 遍历原始数据，统计每个账户在各彩种的投注期数
        if df_target is not None and not df_target.empty:
            for idx, row in df_target.iterrows():
                account = row['会员账号']
                lottery = row['彩种']
                period = row['期号']
                
                if account and lottery and period:
                    # 统一彩种名称：去除前后空格，保留完整名称
                    lottery_clean = lottery.strip()
                    account_lottery_periods[account][lottery_clean].add(period)
        
        # 统计违规信息
        for result_key, result in all_period_results.items():
            lottery = result['lottery'].strip()  # 清理彩种名称
            
            for combo in result['all_combinations']:
                for account in combo['accounts']:
                    account_info = account_participation[account]
                    account_info['periods'].add(result['period'])
                    account_info['lotteries'].add(lottery)
                    
                    # 记录该彩种的违规期数
                    account_info['violation_lottery_periods'][lottery].add(result['period'])
                    
                    if 'position' in result and result['position']:
                        account_info['positions'].add(result['position'])
                        
                    account_info['total_combinations'] += 1
                    account_info['total_bet_amount'] += combo['individual_amounts'][account]
                    account_info['combo_types'].add(combo['account_count'])
        
        # 生成统计记录
        for account, info in account_participation.items():
            # 计算违规彩种的总投注期数
            violation_lottery_periods_summary = []
            
            for lottery in info['lotteries']:
                # 获取该彩种的总投注期数
                total_periods = 0
                if account in account_lottery_periods:
                    # 尝试多种匹配方式
                    matched_lottery = None
                    for stored_lottery in account_lottery_periods[account].keys():
                        # 精确匹配或包含匹配
                        if (stored_lottery == lottery or 
                            lottery in stored_lottery or 
                            stored_lottery in lottery):
                            matched_lottery = stored_lottery
                            break
                    
                    if matched_lottery:
                        total_periods = len(account_lottery_periods[account][matched_lottery])
                
                violation_lottery_periods_summary.append(f"{lottery}:{total_periods}期")
            
            # 计算总违规期数（所有彩种去重）
            total_violation_periods = len(info['periods'])
            
            stat_record = {
                '账户': account,
                '参与组合数': info['total_combinations'],
                '彩种期数': ' | '.join(violation_lottery_periods_summary) if violation_lottery_periods_summary else '无数据',
                '涉及期数': total_violation_periods,
                '涉及彩种': len(info['lotteries']),
                '组合类型': ', '.join([f"{t}账户" for t in sorted(info['combo_types'])]),
                '总投注金额': info['total_bet_amount'],
                '平均每期金额': info['total_bet_amount'] / total_violation_periods if total_violation_periods > 0 else 0
            }
            
            if info['positions']:
                stat_record['涉及位置'] = ', '.join(sorted(info['positions']))
            
            account_stats.append(stat_record)
        
        return sorted(account_stats, key=lambda x: x['参与组合数'], reverse=True)

    def _display_by_account_pair_lottery(self, account_pair_groups, analysis_mode, account_stats):
        """按账户组合和彩种展示 - 优化投注统计显示格式"""
        category_display = {
            'six_mark': '六合彩',
            'six_mark_tail': '六合彩尾数',
            '10_number': '时时彩/PK10/赛车',
            'fast_three': '快三'
        }
        
        if not account_pair_groups:
            st.info("❌ 没有找到要展示的组合")
            return
        
        # 将account_stats转换为字典，便于查找
        account_stats_dict = {}
        for stat in account_stats:
            account = stat['账户']
            account_stats_dict[account] = stat
        
        # 遍历每个账户组合
        for account_pair, lottery_groups in account_pair_groups.items():
            # 分解账户对
            accounts = account_pair.split(' ↔ ')
            
            # 遍历每个彩种
            for lottery_key, combos in lottery_groups.items():
                # 按期号排序
                combos.sort(key=lambda x: x['period'])
                
                # 创建折叠框标题
                combo_count = len(combos)
                title = f"**{account_pair}** - {lottery_key}（{combo_count}个组合）"
                
                with st.expander(title, expanded=True):
                    # 显示每个组合
                    for idx, combo_info in enumerate(combos, 1):
                        combo = combo_info['combo']
                        period = combo_info['period']
                        lottery_category = combo_info['lottery_category']
                        
                        # 组合标题
                        st.markdown(f"**完美组合 {idx}:** {account_pair}")
                        
                        # 组合信息 - 使用4列布局
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.write(f"**账户数量:** {combo['account_count']}个")
                        with col2:
                            st.write(f"**期号:** {period}")
                        with col3:
                            st.write(f"**总金额:** ¥{combo['total_amount']:,.2f}")
                        with col4:
                            similarity = combo['similarity']
                            indicator = combo['similarity_indicator']
                            st.write(f"**金额匹配度:** {similarity:.1f}% {indicator}")
                        
                        # 彩种类型信息
                        category_name = category_display.get(lottery_category, lottery_category)
                        st.write(f"**彩种类型:** {category_name}")
                        
                        # 获取当前彩种的基本名称（去掉位置信息）
                        current_lottery = lottery_key.split(' - ')[0].strip() if ' - ' in lottery_key else lottery_key
                        
                        # 各账户投注统计 - 改进显示格式
                        st.write("**投注统计:**")
                        
                        # 为每个账户构建投注统计信息
                        accounts_info_lines = []
                        
                        for account in combo['accounts']:
                            # 获取该账户的统计信息
                            account_periods = "未知"
                            violation_count = 0
                            
                            if account in account_stats_dict:
                                stat_info = account_stats_dict[account]
                                # 从彩种期数中提取当前彩种的期数
                                lottery_periods_info = stat_info.get('彩种期数', '')
                                
                                # 改进：更精确地匹配彩种名称
                                if lottery_periods_info and lottery_periods_info != '无数据':
                                    # 分割多个彩种信息
                                    items = lottery_periods_info.split('|')
                                    for item in items:
                                        item = item.strip()
                                        if ':' in item:
                                            lottery_name, periods = item.split(':', 1)
                                            lottery_name = lottery_name.strip()
                                            periods = periods.strip()
                                            
                                            # 改进匹配逻辑：检查彩种名称是否匹配
                                            if (lottery_name == current_lottery or 
                                                current_lottery in lottery_name or 
                                                lottery_name in current_lottery):
                                                account_periods = periods.replace('期', '').strip()
                                                break
                                
                                # 计算该账户在当前彩种的违规期数
                                violation_periods = []
                                for c_info in combos:
                                    if account in c_info['combo']['accounts']:
                                        violation_periods.append(c_info['period'])
                                violation_count = len(set(violation_periods))
                            
                            # 使用Markdown格式创建加粗效果
                            account_info = f"**{account}:**   **投注期数:**{account_periods}   **违规期数:**{violation_count}"
                            accounts_info_lines.append(account_info)
                        
                        # 用" ↔ "分隔各账户信息
                        st.markdown(" ↔ ".join(accounts_info_lines))
                        
                        # 各账户详情
                        st.write("**各账户详情:**")
                        
                        for account in combo['accounts']:
                            amount_info = combo['individual_amounts'][account]
                            avg_info = combo['individual_avg_per_number'][account]
                            numbers = combo['bet_contents'][account]
                            numbers_count = len(numbers.split(', '))
                            
                            st.write(f"- **{account}**: {numbers_count}个数字")
                            st.write(f"  - 总投注: ¥{amount_info:,.2f}")
                            st.write(f"  - 平均每号: ¥{avg_info:,.2f}")
                            st.write(f"  - 投注内容: {numbers}")
                        
                        # 添加分隔线（除了最后一个组合）
                        if idx < len(combos):
                            st.markdown("---")

    def enhanced_export(self, all_period_results, analysis_mode):
        """增强导出功能 - 支持4账户组合"""
        export_data = []
        
        category_display = {
            'six_mark': '六合彩',
            '10_number': '时时彩/PK10/赛车',
            'fast_three': '快三'
        }
        
        # 修复：确保正确遍历 all_period_results
        for result_key, result in all_period_results.items():
            lottery_category = result['lottery_category']
            total_numbers = result['total_numbers']
            
            for combo in result['all_combinations']:
                # 基础信息
                export_record = {
                    '期号': result['period'],
                    '彩种': result['lottery'],
                    '彩种类型': category_display.get(lottery_category, lottery_category),
                    '号码总数': total_numbers,
                    '组合类型': f"{combo['account_count']}账户组合",
                    '账户组合': ' ↔ '.join(combo['accounts']),
                    '总投注金额': combo['total_amount'],
                    '平均每号金额': combo['avg_amount_per_number'],
                    '金额匹配度': f"{combo['similarity']:.1f}%",
                    '匹配度等级': combo['similarity_indicator']
                }
                
                # 添加位置信息
                if 'position' in result and result['position']:
                    export_record['投注位置'] = result['position']
                
                # 各账户详情 - 现在最多支持4个账户
                for i, account in enumerate(combo['accounts'], 1):
                    export_record[f'账户{i}'] = account
                    export_record[f'账户{i}总金额'] = combo['individual_amounts'][account]
                    export_record[f'账户{i}平均每号'] = combo['individual_avg_per_number'][account]
                    export_record[f'账户{i}号码数量'] = len(combo['bet_contents'][account].split(', '))
                    export_record[f'账户{i}投注内容'] = combo['bet_contents'][account]
                
                export_data.append(export_record)
        
        return pd.DataFrame(export_data)

# ==================== Streamlit界面 ====================
def main():
    st.title("🎯 🎈彩票完美覆盖分析系统🎈")
    st.markdown("### 支持六合彩、时时彩、PK10、赛车、快三等多种彩票的智能对刷检测")
    
    analyzer = MultiLotteryCoverageAnalyzer()
    
    # 侧边栏设置 - 分别设置不同彩种的阈值
    st.sidebar.header("⚙️ 分析参数设置")
    
    # 文件上传
    st.sidebar.header("📁 数据上传")
    uploaded_file = st.sidebar.file_uploader(
        "上传投注数据文件", 
        type=['csv', 'xlsx', 'xls'],
        help="请上传包含彩票投注数据的Excel或CSV文件"
    )
    
    # 添加彩种类型选择
    analysis_mode = st.sidebar.radio(
        "分析模式:",
        ["自动识别所有彩种", "仅分析六合彩", "仅分析时时彩/PK10/赛车", "仅分析快三"],
        help="选择要分析的彩种类型"
    )
    
    # ========== 金额平衡设置 ==========
    st.sidebar.subheader("💰 金额平衡设置")
    
    # 金额平衡倍数设置
    max_amount_ratio = st.sidebar.slider(
        "组内最大金额与最小金额的允许倍数", 
        min_value=1, 
        max_value=50, 
        value=10,
        help="例如：10表示最大金额与最小金额的差距不超过10倍。设置为1则要求金额完全相等。"
    )
    
    # ========== 六合彩参数设置 ==========
    st.sidebar.subheader("🎯 六合彩参数设置")
    
    # 六合彩特码、正码等基础玩法
    six_mark_min_number_count = st.sidebar.slider(
        "六合彩基础-号码数量阈值", 
        min_value=1, 
        max_value=30, 
        value=11,
        help="六合彩特码、正码等：只分析投注号码数量大于等于此值的账户"
    )
    
    six_mark_min_avg_amount = st.sidebar.slider(
        "六合彩基础-平均金额阈值", 
        min_value=0, 
        max_value=50,
        value=10,
        step=1,
        help="六合彩特码、正码等：只分析平均每号金额大于等于此值的账户"
    )
    
    # 六合彩尾数专用阈值设置
    st.sidebar.subheader("🔢 六合彩尾数参数设置")
    
    six_mark_tail_min_number_count = st.sidebar.slider(
        "六合彩尾数-号码数量阈值", 
        min_value=1, 
        max_value=10, 
        value=3,
        help="六合彩尾数：只分析投注号码数量大于等于此值的账户"
    )
    
    six_mark_tail_min_avg_amount = st.sidebar.slider(
        "六合彩尾数-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="六合彩尾数：只分析平均每号金额大于等于此值的账户"
    )
    
    # ========== 时时彩/PK10/赛车参数设置 ==========
    st.sidebar.subheader("🏎️ 时时彩/PK10/赛车参数设置")
    
    # 时时彩基础玩法（定位胆、名次等）
    ten_number_min_number_count = st.sidebar.slider(
        "赛车类基础-号码数量阈值", 
        min_value=1, 
        max_value=10, 
        value=3,
        help="时时彩/PK10/赛车基础玩法：只分析投注号码数量大于等于此值的账户"
    )
    
    ten_number_min_avg_amount = st.sidebar.slider(
        "赛车类基础-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="时时彩/PK10/赛车基础玩法：只分析平均每号金额大于等于此值的账户"
    )
    
    # 🆕 新增：冠亚和专用阈值设置
    st.sidebar.subheader("🥇 冠亚和参数设置")
    
    ten_number_sum_min_number_count = st.sidebar.slider(
        "冠亚和-号码数量阈值", 
        min_value=1, 
        max_value=17, 
        value=5,
        help="冠亚和玩法：只分析投注号码数量大于等于此值的账户"
    )
    
    ten_number_sum_min_avg_amount = st.sidebar.slider(
        "冠亚和-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="冠亚和玩法：只分析平均每号金额大于等于此值的账户"
    )
    
    # ========== 快三参数设置 ==========
    st.sidebar.subheader("🎲 快三参数设置")
    
    # 快三和值玩法
    fast_three_sum_min_number_count = st.sidebar.slider(
        "快三和值-号码数量阈值", 
        min_value=1, 
        max_value=16, 
        value=4,
        help="快三和值玩法：只分析投注号码数量大于等于此值的账户"
    )
    
    fast_three_sum_min_avg_amount = st.sidebar.slider(
        "快三和值-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="快三和值玩法：只分析平均每号金额大于等于此值的账户"
    )
    
    # 🆕 新增：快三基础玩法专用阈值设置
    st.sidebar.subheader("🎯 快三基础玩法参数设置")
    
    fast_three_base_min_number_count = st.sidebar.slider(
        "快三基础-号码数量阈值", 
        min_value=1, 
        max_value=6, 
        value=2,
        help="快三基础玩法（三军、独胆等）：只分析投注号码数量大于等于此值的账户"
    )
    
    fast_three_base_min_avg_amount = st.sidebar.slider(
        "快三基础-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="快三基础玩法（三军、独胆等）：只分析平均每号金额大于等于此值的账户"
    )
    
    # ========== 时时彩/3D参数设置 ==========
    st.sidebar.subheader("🎰 时时彩/3D参数设置")
    
    ssc_3d_min_number_count = st.sidebar.slider(
        "时时彩/3D-号码数量阈值", 
        min_value=1, 
        max_value=10, 
        value=3,
        help="时时彩/3D系列：只分析投注号码数量大于等于此值的账户"
    )
    
    ssc_3d_min_avg_amount = st.sidebar.slider(
        "时时彩/3D-平均金额阈值", 
        min_value=0, 
        max_value=20,
        value=5,
        step=1,
        help="时时彩/3D系列：只分析平均每号金额大于等于此值的账户"
    )

    if uploaded_file is not None:
        try:
            # 读取文件 - 增强编码处理
            if uploaded_file.name.endswith('.csv'):
                try:
                    # 先尝试UTF-8
                    df = pd.read_csv(uploaded_file)
                except UnicodeDecodeError:
                    # 如果UTF-8失败，尝试其他编码
                    uploaded_file.seek(0)  # 重置文件指针
                    try:
                        df = pd.read_csv(uploaded_file, encoding='gbk')
                    except:
                        uploaded_file.seek(0)
                        try:
                            df = pd.read_csv(uploaded_file, encoding='gb2312')
                        except:
                            uploaded_file.seek(0)
                            # 最后尝试忽略错误
                            df = pd.read_csv(uploaded_file, encoding_errors='ignore')
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ 成功读取文件，共 {len(df):,} 条记录")
            
            # 🆕 关键修复：保留列名映射步骤，但隐藏显示
            # 增强版列名映射
            column_mapping = analyzer.enhanced_column_mapping(df)
            
            if column_mapping is None:
                st.error("❌ 列名映射失败，无法继续分析")
                return
            
            # 重命名列
            df = df.rename(columns=column_mapping)
            
            # 🆕 关键修复：确保列名正确
            # 数据质量验证
            quality_issues = analyzer.validate_data_quality(df)
            
            # 数据清理
            required_columns = ['会员账号', '彩种', '期号', '玩法', '内容']
            
            # 检查必要列是否存在
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.error(f"❌ 缺少必要列: {missing_columns}")
                st.info(f"当前列名: {list(df.columns)}")
                return
            
            # 检查是否有金额列
            has_amount_column = '金额' in df.columns
            
            # 创建干净的DataFrame
            df_clean = df[required_columns].copy()
            if has_amount_column:
                df_clean['金额'] = df['金额']
            
            # 清理数据
            for col in required_columns:
                df_clean[col] = df_clean[col].astype(str).str.strip()
    
            # 🆕 关键修复：执行数据预处理，但不显示过程
            with st.spinner("正在处理数据..."):
                df_clean, _, _ = analyzer.enhanced_data_preprocessing(df_clean)
            
            # 从投注内容中提取具体位置信息
            if '彩种类型' in df_clean.columns:
                df_clean['提取位置'] = df_clean.apply(
                    lambda row: analyzer.enhanced_extract_position_from_content(
                        row['玩法'], row['内容'], row['彩种类型']
                    ), 
                    axis=1
                )
                
                # 对于成功提取到具体位置的记录，更新玩法列为提取的位置
                mask = df_clean['提取位置'] != df_clean['玩法']
                if mask.any():
                    df_clean.loc[mask, '玩法'] = df_clean.loc[mask, '提取位置']
                
                # 删除临时列
                df_clean = df_clean.drop('提取位置', axis=1)
            
            # 应用金额提取
            if has_amount_column:
                df_clean['投注金额'] = df_clean['金额'].apply(analyzer.extract_bet_amount)
            
            # 筛选有效玩法数据
            if analysis_mode == "仅分析六合彩":
                valid_plays = ['特码', '正码一', '正码二', '正码三', '正码四', '正码五', '正码六', 
                             '正一特', '正二特', '正三特', '正四特', '正五特', '正六特', '平码', '平特',
                             '尾数', '全尾', '特尾']
                df_target = df_clean[df_clean['玩法'].isin(valid_plays)]
                if '彩种类型' in df_clean.columns:
                    df_target = df_target[df_target['彩种类型'] == 'six_mark']
            elif analysis_mode == "仅分析时时彩/PK10/赛车":
                valid_plays = ['冠军', '亚军', '季军', '第四名', '第五名', '第六名', '第七名', '第八名', '第九名', '第十名', 
                             '定位胆', '前一', '1-5名', '6-10名']
                df_target = df_clean[df_clean['玩法'].isin(valid_plays)]
                if '彩种类型' in df_clean.columns:
                    df_target = df_target[df_target['彩种类型'] == '10_number']
            elif analysis_mode == "仅分析快三":
                valid_plays = ['和值']
                df_target = df_clean[df_clean['玩法'].isin(valid_plays)]
                if '彩种类型' in df_clean.columns:
                    df_target = df_target[df_target['彩种类型'] == 'fast_three']
            else:
                valid_plays = ['特码', '正码一', '正码二', '正码三', '正码四', '正码五', '正码六', 
                             '正一特', '正二特', '正三特', '正四特', '正五特', '正六特', '平码', '平特',
                             '尾数', '全尾', '特尾',
                             '冠军', '亚军', '季军', '第四名', '第五名', '第六名', '第七名', '第八名', '第九名', '第十名', 
                             '定位胆', '前一', '和值', '1-5名', '6-10名']
                df_target = df_clean[df_clean['玩法'].isin(valid_plays)]
                if '彩种类型' in df_clean.columns:
                    df_target = df_target[df_target['彩种类型'].notna()]
    
            if len(df_target) == 0:
                st.error("❌ 未找到符合条件的有效玩法数据")
                return
    
            # 分析数据
            with st.spinner("正在分析数据..."):
                six_mark_params = {
                    'min_number_count': six_mark_min_number_count,
                    'min_avg_amount': six_mark_min_avg_amount,
                    'tail_min_number_count': six_mark_tail_min_number_count,
                    'tail_min_avg_amount': six_mark_tail_min_avg_amount
                }
                ten_number_params = {
                    'min_number_count': ten_number_min_number_count,
                    'min_avg_amount': ten_number_min_avg_amount,
                    'sum_min_number_count': ten_number_sum_min_number_count,
                    'sum_min_avg_amount': ten_number_sum_min_avg_amount
                }
                fast_three_params = {
                    'sum_min_number_count': fast_three_sum_min_number_count,
                    'sum_min_avg_amount': fast_three_sum_min_avg_amount,
                    'base_min_number_count': fast_three_base_min_number_count,
                    'base_min_avg_amount': fast_three_base_min_avg_amount
                }
                ssc_3d_params = {
                    'min_number_count': ssc_3d_min_number_count,
                    'min_avg_amount': ssc_3d_min_avg_amount
                }
                
                all_period_results = analyzer.analyze_with_progress(
                    df_target, six_mark_params, ten_number_params, fast_three_params, ssc_3d_params, analysis_mode, max_amount_ratio
                )
            
            # 显示最终结果
            if all_period_results:
                total_combinations = sum(result['total_combinations'] for result in all_period_results.values())
                st.success(f"✅ 分析完成，共发现 {total_combinations} 个完美覆盖组合")
                analyzer.display_enhanced_results(all_period_results, analysis_mode, df_target)
                
                # 导出功能
                st.markdown("---")
                st.subheader("📥 数据导出")
                
                if st.button("📊 生成完美组合数据报告"):
                    download_df = analyzer.enhanced_export(all_period_results, analysis_mode)
                    
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        download_df.to_excel(writer, index=False, sheet_name='完美组合数据')
                        
                        account_stats = analyzer._calculate_detailed_account_stats(all_period_results)
                        if account_stats:
                            df_account_stats = pd.DataFrame(account_stats)
                            df_account_stats.to_excel(writer, index=False, sheet_name='账户参与统计')
                    
                    st.download_button(
                        label="📥 下载完整分析报告",
                        data=output.getvalue(),
                        file_name=f"全彩种完美组合分析报告_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.success("✅ 数据导出准备完成!")
            else:
                st.info("📊 分析完成: 未发现完美覆盖组合")
            
        except Exception as e:
            st.error(f"❌ 处理文件时出错: {str(e)}")
            logger.error(f"文件处理错误: {str(e)}", exc_info=True)
            
            # 提供更详细的错误信息
            with st.expander("🔍 查看详细错误信息", expanded=False):
                st.code(f"""
        错误类型: {type(e).__name__}
        错误信息: {str(e)}
                
        可能的原因:
        1. 文件编码问题 - 尝试将文件另存为UTF-8编码
        2. 文件格式问题 - 确保文件是有效的CSV或Excel格式
        3. 内存不足 - 尝试分析较小的数据文件
        4. 列名不匹配 - 检查文件是否包含必要的列
                
        如果问题持续存在，请联系技术支持。
                """)
    
    else:
        st.info("💡 **彩票完美覆盖分析系统**")
        st.markdown("""
        ### 🚀 系统特色功能:

        **🎲 全彩种支持**
        - ✅ **六合彩**: 1-49个号码，支持特码、正码、正特、平码等多种玩法
        - ✅ **时时彩/PK10/赛车**: 1-10共10个号码，**按位置精准分析**  
        - ✅ **快三**: 3-18共16个号码，和值玩法
        - 🔄 **自动识别**: 智能识别彩种类型

        **📍 位置精准分析**
        - ✅ **六合彩位置**: 特码、正码一至正码六、正一特至正六特、平码、平特
        - ✅ **PK10/赛车位置**: 冠军、亚军、季军、第四名到第十名、前一
        - ✅ **快三位置**: 和值
        - ✅ **位置统计**: 按位置统计完美组合数量

        **🔍 智能数据识别**
        - ✅ 增强列名识别：支持多种列名变体
        - 📊 数据质量验证：完整的数据检查流程
        - 🎯 玩法分类统一：智能识别各彩种玩法
        - 💰 金额提取优化：支持多种金额格式

        **⚡ 性能优化**
        - 🔄 缓存机制：号码和金额提取缓存
        - 📈 进度显示：实时分析进度
        - 🎨 界面优化：现代化Streamlit界面

        **📊 分析增强**
        - 👥 账户聚合视图：按账户统计参与情况和总投注金额
        - 📋 详细组合分析：完整的组合信息展示
        - 📊 汇总统计：多维度数据统计

        ### 🎯 各彩种分析原理:

        **六合彩 (49个号码)**
        - 检测同一期号、同一位置内不同账户的投注号码是否形成完美覆盖（1-49全部覆盖）
        - 分析各账户的投注金额匹配度，识别可疑的协同投注行为
        - 支持特码、正码、正特、平码等多种玩法

        **时时彩/PK10/赛车 (10个号码)**  
        - **按位置精准分析**: 冠军、亚军、季军等每个位置独立分析
        - 检测同一位置内，不同账户是否覆盖全部10个号码（1-10）
        - 识别对刷行为：多个账户在同一位置合作覆盖所有号码

        **快三 (16个号码)**
        - **和值玩法**: 检测同一期号内不同账户是否覆盖全部16个和值（3-18）
        - 分析各账户的投注金额匹配度，识别可疑的协同投注行为

        ### 📝 支持的列名格式:
        """)
        
        for standard_col, possible_names in analyzer.column_mappings.items():
            st.write(f"- **{standard_col}**: {', '.join(possible_names[:3])}{'...' if len(possible_names) > 3 else ''}")
        
        st.markdown("""
        ### 🎯 数据要求:
        - ✅ 必须包含: 会员账号, 彩种, 期号, 玩法, 内容
        - ✅ 玩法必须为支持的类型
        - ✅ 彩种必须是支持的彩票类型
        - 💰 可选包含金额列进行深度分析
        """)

if __name__ == "__main__":
    main()
