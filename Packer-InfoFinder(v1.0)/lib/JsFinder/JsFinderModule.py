#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import re
import os
import json
import html # 修复: 导入 html 模块
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Set
from lib.common.CreatLog import creatLog
from lib.common.utils import Utils
from lib.Database import DatabaseType
import multiprocessing

class JsFinderModule:
    def __init__(self, projectTag, options):
        self.projectTag = projectTag
        self.options = options
        self.log = creatLog().get_logger()
        
        # --- 修复：确保每个项目的输出目录是唯一的 ---
        self.output_directory = os.path.join(DatabaseType(self.projectTag).getPathfromDB(), 'finder_results')
        
        self.regex_patterns = self.load_regex_patterns()
        
        self.compiled_regex_patterns = {name: re.compile(pattern, re.MULTILINE | re.DOTALL)
                                       for name, pattern in self.regex_patterns.items()}
    
    def load_regex_patterns(self):
        """加载正则表达式模式"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get('regex_patterns', {})
        except Exception as e:
            self.log.error(f"加载配置文件失败: {e}")
        
        return {
            'Oss云存储桶': r"(?i)(?:[A|a]ccess[K|k]ey(?:[I|i]d|[S|s]ecret)|[A|a]ccess[-_]?[Kk]ey)\s*[:=]\s*['\"]?([0-9a-fA-F\-_=]{6,128})['\"]?",
            "aliyun_oss_url": r"(?<!\w)[a-zA-Z0-9-]+\.oss[-\w]*\.aliyuncs\.com(?!\w)",
            'json_web_token': r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}\.?[A-Za-z0-9-_.+/=]*',
            'Basic Auth Credentials': r'(?<=://)[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}',
            'Cloudinary Basic Auth': r'cloudinary://[0-9]{15}:[0-9A-Za-z]+@[a-z]+',
            "Github": r"(?i)github(?:[-_]?token)?\s*[:=]\s*['\"]?(gh[psuro]_[0-9a-zA-Z]{36})['\"]?",
            "LinkedIn Secret Key": r"(?i)linkedin[-_]?secret\s*[:=]\s*['\"][0-9a-zA-Z]{16}['\"]",
            'Mailchamp API Key': r'(?i)[0-9a-f]{32}-us\d{1,2}',
            'Mailgun API Key': r'(?i)key-[0-9a-zA-Z]{32}',
            'Slack Webhook': r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8}/[a-zA-Z0-9_]{24}',
            'Stripe API Key': r'(?i) [rs]k_(?:live|test)_[0-9a-zA-Z]{24}',
            "国内手机号码": r'(?<!\d)((?:\+86|0086)?1[3-9]\d{9})(?!\d)',
            "身份证号码": r'(?<!\d)(?!0{6,}|1{6,})([1-6]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dxX])(?!\d)',
            '敏感配置信息': r"(?:[\{\,]\s*)((appkey)|(secret)|(token)|(auth)|(access)|(admin)|(VideoWebPlugin)|(playMode)|(snapDir)|(SnapDir)|(videoDir))([\w]{0,10})\s*:\s*([^,\}\s]+|['\"].*?['\"])",
            "Password": r"(?i)(?:['\"]?[\w]{0,10}[p](?:ass|wd|asswd|assword)[\w]{0,10}['\"]?)[:=]\s*['\"](?!null|undefined)(.*?)['\"]",
            "Username/Account": r'((|\'|")(|[\w]{1,10})(([u](ser|name|sername))|(account)|((((create|update)((d|r)|(by|on|at)))|(creator))))(|[\w]{1,10})(|\'|")(:|=)( |)(\'|")(.*?)(\'|")(|,))'
        }
    
    def find_matches(self, content: str, filename: str) -> Dict[str, List[Tuple[str, str, str]]]:
        """在JavaScript内容中查找匹配的敏感信息"""
        matches = {}
        lines = content.splitlines()
        
        for pattern_name, compiled_pattern in self.compiled_regex_patterns.items():
            pattern_matches = set()
            try:
                for match in compiled_pattern.finditer(content):
                    matched_text = match.group(0)
                    start_pos = match.start()
                    
                    line_num = content[:start_pos].count('\n') + 1
                    
                    context_start = max(0, start_pos - 300)
                    context_end = min(len(content), start_pos + len(matched_text) + 300)
                    context = content[context_start:context_end].strip()
                    
                    context = context.replace('\n', ' ').replace('\r', ' ')
                    
                    pattern_matches.add((
                        matched_text,
                        f"{filename}:Line {line_num}",
                        context
                    ))
            except re.error as e:
                self.log.error(f"正则表达式 '{pattern_name}' 无效: {e}")
                continue
            
            if pattern_matches:
                matches[pattern_name] = list(pattern_matches)
        
        return matches
    
    def extract_paths(self, content: str, filename: str) -> Tuple[List[str], List[str]]:
        """从JavaScript内容中提取路径"""
        paths = set()
        path_to_file_mapping = []
        
        path_patterns = [
            r'''['"](?:/|(?:https?:) ?//)[^\s'"]+?['"]''',
            r'''(?:src|href|url)\s*[:=]\s*['"][^'"]+['"]''',
            r'''(?:path|route)\s*[:=]\s*['"][^'"]+['"]'''
        ]
        
        for pattern in path_patterns:
            for match in re.finditer(pattern, content):
                path = match.group(0).strip('\'"')
                if path.startswith(('/', 'http://', 'https://') ) and not path.endswith(('.js', '.css')):
                    paths.add(path)
                    path_to_file_mapping.append(f"{filename}----{path}")
        
        return sorted(paths), path_to_file_mapping
    
    def process_js_file(self, file_path: str) -> Tuple[Dict, List, List]:
        """处理单个JavaScript文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
        except Exception as e:
            self.log.error(f"无法读取文件 {file_path}: {e}")
            return {}, [], []
        
        filename = os.path.basename(file_path)
        matches = self.find_matches(content, filename)
        unique_paths, path_mappings = self.extract_paths(content, filename)
        return matches, unique_paths, path_mappings
    
    def process_js_files(self, js_files_dir: str) -> None:
        """处理目录中的所有JavaScript文件"""
        if not os.path.exists(js_files_dir):
            self.log.error(f"目录不存在: {js_files_dir}")
            return False
        
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)
        
        file_paths = []
        for root, _, files in os.walk(js_files_dir):
            for file in files:
                if file.endswith('.js'):
                    file_paths.append(os.path.join(root, file))
        
        if not file_paths:
            self.log.info("未找到JavaScript文件")
            return False
        
        self.log.info(f"找到 {len(file_paths)} 个JavaScript文件，开始扫描敏感信息...")
        
        all_matches = {}
        all_unique_paths = set()
        all_path_mappings = []
        
        max_threads = min(4, multiprocessing.cpu_count())
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(self.process_js_file, fp) for fp in file_paths]
            
            for future in futures:
                matches, unique_paths, path_mappings = future.result()
                for pattern_name, pattern_matches in matches.items():
                    if pattern_name not in all_matches:
                        all_matches[pattern_name] = []
                    all_matches[pattern_name].extend(pattern_matches)
                all_unique_paths.update(unique_paths)
                all_path_mappings.extend(path_mappings)
        
        self.save_results(all_matches, sorted(all_unique_paths), sorted(all_path_mappings))
        
        total_matches = sum(len(m) for m in all_matches.values())
        self.log.info(f"敏感信息扫描完成，共发现 {total_matches} 个匹配项")
        for pattern_name, pattern_matches in all_matches.items():
            if pattern_matches:
                self.log.info(f"- {pattern_name}: {len(pattern_matches)} 个匹配")
        
        return True
    
    def generate_html_output(self, matches: Dict[str, List[Tuple[str, str, str]]]) -> str:
        """生成HTML格式的输出，包含侧边栏显示关键字"""
        html_path = os.path.join(self.output_directory, 'sensitive_info.html')
        
        scan_time = Utils().tellTime()
        
        sidebar_items = []
        total_matches = sum(len(pattern_matches) for pattern_matches in matches.values())
        
        sorted_patterns = sorted(matches.items(), key=lambda x: len(x[1]), reverse=True)
        
        # ###################### START: MODIFICATION 1 ######################
        # 修复: 为每个模式类型创建一个从0开始的索引，用于生成唯一的锚点ID
        for index, (pattern_name, pattern_matches) in enumerate(sorted_patterns):
            if pattern_matches:
                match_count = len(pattern_matches)
                # 修复: 使用索引生成唯一的锚点ID，例如 "pattern-0", "pattern-1"
                anchor_id = f"pattern-{index}"
                # 修复: 对显示在侧边栏的 pattern_name 进行HTML转义，防止特殊字符破坏HTML结构
                safe_pattern_name = html.escape(pattern_name)
                sidebar_items.append(f'<li><a href="#{anchor_id}">{safe_pattern_name} <span class="count">{match_count}</span></a></li>')
        # ####################### END: MODIFICATION 1 #######################
        
        html_content = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>JavaScript敏感信息扫描结果</title>
            <style>
                * { box-sizing: border-box; }
                body { 
                    font-family: "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
                    line-height: 1.6; 
                    margin: 0; 
                    padding: 0; 
                    color: #333;
                    display: flex;
                    min-height: 100vh;
                    background-color: #f8f9fa;
                }
                
                /* 侧边栏样式 */
                .sidebar {
                    width: 320px;
                    background-color: #2c3e50;
                    color: #fff;
                    padding: 20px;
                    position: fixed;
                    height: 100vh;
                    overflow-y: auto;
                    box-shadow: 0 0 20px rgba(0,0,0,0.1);
                    z-index: 100;
                    transition: all 0.3s;
                }
                
                .sidebar h3 {
                    margin-top: 0;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #4a6278;
                    color: #ecf0f1;
                    font-size: 18px;
                    letter-spacing: 1px;
                }
                
                .sidebar ul {
                    list-style: none;
                    padding: 0;
                    margin: 0;
                }
                
                .sidebar ul li {
                    margin-bottom: 8px;
                }
                
                .sidebar ul li a {
                    color: #ecf0f1;
                    text-decoration: none;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 10px 12px;
                    border-radius: 6px;
                    transition: all 0.2s ease;
                }
                
                .sidebar ul li a:hover {
                    background-color: #3498db;
                }
                
                .sidebar ul li a .count {
                    background-color: #e74c3c;
                    color: white;
                    border-radius: 12px;
                    padding: 2px 8px;
                    font-size: 12px;
                    font-weight: bold;
                }
                
                .sidebar-toggle {
                    position: fixed;
                    top: 20px;
                    left: 20px;
                    z-index: 101;
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 15px;
                    cursor: pointer;
                    display: none;
                }
                
                /* 主内容区样式 */
                .main-content {
                    flex-grow: 1;
                    padding: 30px;
                    margin-left: 320px;  /* 匹配sidebar宽度 */
                    width: calc(100% - 320px);
                    max-width: 1200px;
                    background-color: white;
                    box-shadow: 0 0 20px rgba(0,0,0,0.05);
                    border-radius: 0 0 8px 8px;
                }
                
                h1 { 
                    color: #2c3e50; 
                    border-bottom: 2px solid #3498db; 
                    padding-bottom: 15px; 
                    margin-top: 0;
                    font-size: 28px;
                    position: relative;
                }
                
                h1::after {
                    content: '';
                    display: block;
                    width: 80px;
                    height: 5px;
                    background: #e74c3c;
                    position: absolute;
                    bottom: -3px;
                    left: 0;
                }
                
                h2 { 
                    color: #2980b9; 
                    margin-top: 40px; 
                    padding: 10px 15px;
                    background-color: #eaf2f8;
                    border-radius: 6px;
                    position: relative;
                    font-size: 22px;
                    scroll-margin-top: 30px; /* 锚点定位时的顶部边距 */
                }
                
                h2 .pattern-count {
                    position: absolute;
                    right: 15px;
                    top: 50%;
                    transform: translateY(-50%);
                    background-color: #e74c3c;
                    color: white;
                    border-radius: 15px;
                    padding: 3px 10px;
                    font-size: 14px;
                    font-weight: bold;
                }
                
                .match-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                
                .match-item { 
                    background-color: #f9f9f9; 
                    border-left: 4px solid #e74c3c; 
                    padding: 15px; 
                    border-radius: 6px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.05);
                    transition: all 0.2s ease;
                    overflow: hidden;
                }
                
                .match-item:hover {
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                    transform: translateY(-2px);
                }
                
                .match-text { 
                    font-weight: bold; 
                    color: #c0392b; 
                    word-break: break-all;
                    background-color: #ffe6e6;
                    padding: 8px;
                    border-radius: 4px;
                    margin-bottom: 10px;
                    font-family: monospace;
                    font-size: 14px;
                }
                
                .match-source { 
                    color: #7f8c8d; 
                    font-size: 0.9em; 
                    margin: 10px 0;
                    border-top: 1px solid #ecf0f1;
                    border-bottom: 1px solid #ecf0f1;
                    padding: 8px 0;
                }
                
                .match-context { 
                    background-color: #f1f1f1; 
                    padding: 12px; 
                    border-radius: 4px; 
                    font-family: monospace; 
                    white-space: pre-wrap; 
                    word-break: break-all;
                    font-size: 13px;
                    max-height: 150px;
                    overflow-y: auto;
                    position: relative;
                }
                
                .match-context.expanded {
                    max-height: none;
                }
                
                .context-toggle {
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    margin-top: 5px;
                    cursor: pointer;
                    font-size: 12px;
                }
                
                .highlight { 
                    background-color: #ff9999; 
                    padding: 2px 0; 
                    border-radius: 2px; 
                    font-weight: bold;
                }
                
                .summary { 
                    background: linear-gradient(135deg, #3498db, #2c3e50);
                    color: white;
                    padding: 20px; 
                    border-radius: 8px; 
                    margin-bottom: 30px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    flex-wrap: wrap;
                }
                
                .summary-item {
                    flex: 1;
                    min-width: 200px;
                    margin: 10px;
                    text-align: center;
                }
                
                .summary-value {
                    font-size: 32px;
                    font-weight: bold;
                    display: block;
                }
                
                .summary-label {
                    font-size: 14px;
                    opacity: 0.8;
                }
                
                .no-results { 
                    color: #7f8c8d; 
                    font-style: italic;
                    text-align: center;
                    margin: 50px 0;
                    font-size: 18px;
                }
                
                .chart-container {
                    margin: 30px 0;
                    height: 300px;
                }
                
                .filters {
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f8f9fa;
                    border-radius: 6px;
                    display: flex;
                    align-items: center;
                    flex-wrap: wrap;
                }
                
                .filter-input {
                    flex: 1;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    margin-right: 10px;
                    min-width: 200px;
                }
                
                .clear-filter {
                    background: #e74c3c;
                    color: white;
                    border: none;
                    padding: 10px 15px;
                    border-radius: 4px;
                    cursor: pointer;
                }
                
                /* 移动设备适配 */
                @media (max-width: 1024px) {
                    .sidebar {
                        width: 280px;
                    }
                    .main-content {
                        margin-left: 280px;
                        width: calc(100% - 280px);
                        padding: 20px;
                    }
                    .match-grid {
                        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    }
                }
                
                @media (max-width: 768px) {
                    body {
                        flex-direction: column;
                    }
                    .sidebar {
                        width: 100%;
                        height: auto;
                        max-height: 100vh;
                        position: fixed;
                        transform: translateX(-100%);
                    }
                    .sidebar.active {
                        transform: translateX(0);
                    }
                    .main-content {
                        margin-left: 0;
                        width: 100%;
                        padding: 15px;
                    }
                    .sidebar-toggle {
                        display: block;
                    }
                    .match-grid {
                        grid-template-columns: 1fr;
                    }
                }
                
                /* 工具栏样式 */
                .toolbar {
                    position: sticky;
                    top: 0;
                    z-index: 90;
                    background: white;
                    padding: 10px 0;
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #eee;
                }
                
                .view-options {
                    display: flex;
                    gap: 10px;
                }
                
                .view-option {
                    background: #f8f9fa;
                    border: 1px solid #ddd;
                    padding: 8px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                }
                
                .view-option.active {
                    background: #3498db;
                    color: white;
                    border-color: #3498db;
                }
                
                /* 表格视图样式 */
                .table-view {
                    overflow-x: auto;
                    margin-top: 20px;
                    display: none;
                }
                
                .table-view.active {
                    display: block;
                }
                
                .sensitive-table {
                    width: 100%;
                    border-collapse: collapse;
                }
                
                .sensitive-table th,
                .sensitive-table td {
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                
                .sensitive-table th {
                    background-color: #f8f9fa;
                    font-weight: bold;
                }
                
                .sensitive-table tr:hover {
                    background-color: #f1f1f1;
                }
                
                .card-view.active {
                    display: block;
                }
                
                .card-view {
                    display: none;
                }
                
                /* 返回顶部按钮 */
                .back-to-top {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: #3498db;
                    color: white;
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    opacity: 0;
                    transition: opacity 0.3s;
                    z-index: 99;
                }
                
                .back-to-top.visible {
                    opacity: 1;
                }
                
                .back-to-top:hover {
                    background: #2980b9;
                }
                
                /* 加载动画 */
                .loader {
                    display: none;
                    text-align: center;
                    padding: 20px;
                }
            </style>
        </head>
        <body>
            <button class="sidebar-toggle">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="3" y1="12" x2="21" y2="12"></line>
                    <line x1="3" y1="6" x2="21" y2="6"></line>
                    <line x1="3" y1="18" x2="21" y2="18"></line>
                </svg>
            </button>
            
            <div class="sidebar">
                <h3>敏感信息扫描结果</h3>
                <ul>
                    """ + '\n'.join(sidebar_items) + """
                </ul>
            </div>
            
            <div class="main-content">
                <h1>JavaScript敏感信息扫描结果</h1>
                <div class="summary">
                    <div class="summary-item">
                        <span class="summary-value">""" + str(total_matches) + """</span>
                        <span class="summary-label">总匹配项</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">""" + str(len([p for p in matches.keys() if matches[p]])) + """</span>
                        <span class="summary-label">匹配的模式类型</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">""" + scan_time + """</span>
                        <span class="summary-label">扫描时间</span>
                    </div>
                </div>
                
                <div class="toolbar">
                    <div class="search-container">
                        <input type="text" id="filterInput" class="filter-input" placeholder="输入关键词过滤敏感信息...">
                        <button id="clearFilter" class="clear-filter">清除</button>
                    </div>
                    <div class="view-options">
                        <span class="view-option active" data-view="card">卡片视图</span>
                        <span class="view-option" data-view="table">表格视图</span>
                    </div>
                </div>
                
                <div id="filterStatus" style="margin: 10px 0; display: none;">
                    正在显示过滤结果: <span id="filterKeyword"></span>
                    <button id="resetFilter" style="margin-left: 10px; cursor: pointer;">重置</button>
                </div>
                
                <div class="loader">
                    <p>正在加载数据...</p>
                </div>
        """
        
        if not matches:
            html_content += '<p class="no-results">未发现敏感信息</p>'
        
        html_content += """
                <div class="table-view">
                    <table class="sensitive-table">
                        <thead>
                            <tr>
                                <th>敏感信息类型</th>
                                <th>匹配内容</th>
                                <th>来源</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        # ###################### START: MODIFICATION 2 ######################
        # 修复: 遍历已排序的列表，并全面使用 html.escape()
        for pattern_name, pattern_matches in sorted_patterns:
            if not pattern_matches:
                continue
            
            # 修复: 对所有输出到HTML的内容使用 html.escape()
            safe_pattern_name = html.escape(pattern_name)
            safe_pattern_name_attr = html.escape(pattern_name, quote=True)

            for match_text, source, context in pattern_matches:
                safe_match = html.escape(match_text)
                safe_source = html.escape(source)
                # 修复: 对 data-context 属性进行完整的转义，确保JS安全
                safe_context_attr = html.escape(context, quote=True)
                
                html_content += f'''
                            <tr data-type="{safe_pattern_name_attr}">
                                <td>{safe_pattern_name}</td>
                                <td class="match-text-cell">{safe_match}</td>
                                <td>{safe_source}</td>
                                <td>
                                    <button class="context-btn" data-context="{safe_context_attr}">
                                        查看上下文
                                    </button>
                                </td>
                            </tr>
                '''
        # ####################### END: MODIFICATION 2 #######################

        html_content += """
                        </tbody>
                    </table>
                </div>
                
                <div class="card-view active">
        """
        
        # ###################### START: MODIFICATION 3 ######################
        # 修复: 使用带索引的循环来生成唯一的ID，并全面使用 html.escape()
        for index, (pattern_name, pattern_matches) in enumerate(sorted_patterns):
            if not pattern_matches:
                continue

            # 修复: 使用索引生成唯一的锚点ID
            anchor_id = f"pattern-{index}"
            safe_pattern_name = html.escape(pattern_name)
            safe_pattern_name_attr = html.escape(pattern_name, quote=True)
            
            html_content += f'<h2 id="{anchor_id}" data-pattern-name="{safe_pattern_name_attr}">{safe_pattern_name} <span class="pattern-count">{len(pattern_matches)}</span></h2>'
            
            html_content += '<div class="match-grid">'
            
            for match_text, source, context in pattern_matches:
                safe_match = html.escape(match_text)
                safe_source = html.escape(source)
                safe_context = html.escape(context)
                
                highlighted_context = safe_context.replace(
                    safe_match, 
                    f'<span class="highlight">{safe_match}</span>'
                )
                
                html_content += f'''
                <div class="match-item" data-type="{safe_pattern_name_attr}">
                    <div class="match-text">{safe_match}</div>
                    <div class="match-source">来源: {safe_source}</div>
                    <div class="match-context">{highlighted_context}</div>
                    <button class="context-toggle">展开全文</button>
                </div>
                '''
            
            html_content += '</div>'
        # ####################### END: MODIFICATION 3 #######################

        html_content += """
                </div>
            </div>
            
            <div class="back-to-top">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5"></line>
                    <polyline points="5 12 12 5 19 12"></polyline>
                </svg>
            </div>
            
            <div id="contextModal" style="display:none; position:fixed; z-index:1000; left:0; top:0; width:100%; height:100%; overflow:auto; background-color:rgba(0,0,0,0.5);">
                <div style="background-color:white; margin:10% auto; padding:20px; border-radius:5px; width:80%; max-width:800px; position:relative;">
                    <span style="position:absolute; right:10px; top:5px; font-size:24px; cursor:pointer;" onclick="document.getElementById('contextModal').style.display='none'">&times;</span>
                    <h3>上下文内容</h3>
                    <div id="modalContext" style="white-space:pre-wrap; background:#f8f9fa; padding:15px; border-radius:5px; margin-top:15px; max-height:400px; overflow-y:auto;"></div>
                </div>
            </div>
            
            <script>
                // 侧边栏切换功能
                const sidebarToggle = document.querySelector('.sidebar-toggle');
                const sidebar = document.querySelector('.sidebar');
                
                sidebarToggle.addEventListener('click', () => {
                    sidebar.classList.toggle('active');
                });
                
                // 为侧边栏添加平滑滚动效果
                document.querySelectorAll('.sidebar a').forEach(anchor => {
                    anchor.addEventListener('click', function(e) {
                        e.preventDefault();
                        const targetId = this.getAttribute('href');
                        const targetElement = document.querySelector(targetId);
                        
                        if (targetElement) {
                            window.scrollTo({
                                top: targetElement.offsetTop - 20,
                                behavior: 'smooth'
                            });
                            
                            // 在小屏幕上点击后关闭侧边栏
                            if (window.innerWidth <= 768) {
                                sidebar.classList.remove('active');
                            }
                        }
                    });
                });
                
                // 展开/收起上下文
                document.addEventListener('click', function(e) {
                    if (e.target.classList.contains('context-toggle')) {
                        const contextDiv = e.target.previousElementSibling;
                        contextDiv.classList.toggle('expanded');
                        e.target.textContent = contextDiv.classList.contains('expanded') ? '收起' : '展开全文';
                    }
                    
                    // 显示上下文模态框
                    if (e.target.classList.contains('context-btn')) {
                        const context = e.target.getAttribute('data-context');
                        // 修复: 模态框内容应直接使用HTML，因为Python端已正确转义
                        document.getElementById('modalContext').textContent = context;
                        document.getElementById('contextModal').style.display = 'block';
                    }
                });
                
                // 返回顶部功能
                const backToTop = document.querySelector('.back-to-top');
                
                window.addEventListener('scroll', () => {
                    if (window.scrollY > 300) {
                        backToTop.classList.add('visible');
                    } else {
                        backToTop.classList.remove('visible');
                    }
                });
                
                backToTop.addEventListener('click', () => {
                    window.scrollTo({
                        top: 0,
                        behavior: 'smooth'
                    });
                });
                
                // 视图切换功能
                const viewOptions = document.querySelectorAll('.view-option');
                const cardView = document.querySelector('.card-view');
                const tableView = document.querySelector('.table-view');
                
                viewOptions.forEach(option => {
                    option.addEventListener('click', () => {
                        viewOptions.forEach(opt => opt.classList.remove('active'));
                        option.classList.add('active');
                        
                        const viewType = option.getAttribute('data-view');
                        if (viewType === 'card') {
                            cardView.classList.add('active');
                            tableView.classList.remove('active');
                        } else {
                            tableView.classList.add('active');
                            cardView.classList.remove('active');
                        }
                    });
                });
                
                // 过滤功能
                const filterInput = document.getElementById('filterInput');
                const clearFilterBtn = document.getElementById('clearFilter');
                const resetFilterBtn = document.getElementById('resetFilter');
                const filterStatus = document.getElementById('filterStatus');
                const filterKeyword = document.getElementById('filterKeyword');
                const matchItems = document.querySelectorAll('.match-item');
                const tableRows = document.querySelectorAll('.sensitive-table tbody tr');
                
                filterInput.addEventListener('input', filterItems);
                clearFilterBtn.addEventListener('click', clearFilter);
                resetFilterBtn.addEventListener('click', clearFilter);
                
                function filterItems() {
                    const keyword = filterInput.value.toLowerCase().trim();
                    
                    if (keyword) {
                        filterStatus.style.display = 'block';
                        filterKeyword.textContent = keyword;
                        
                        // 过滤卡片视图
                        matchItems.forEach(item => {
                            const matchText = item.querySelector('.match-text').textContent.toLowerCase();
                            const matchSource = item.querySelector('.match-source').textContent.toLowerCase();
                            const matchContext = item.querySelector('.match-context').textContent.toLowerCase();
                            const matchType = item.getAttribute('data-type').toLowerCase();
                            
                            if (matchText.includes(keyword) || matchSource.includes(keyword) || 
                                matchContext.includes(keyword) || matchType.includes(keyword)) {
                                item.style.display = '';
                            } else {
                                item.style.display = 'none';
                            }
                        });
                        
                        // 过滤表格视图
                        tableRows.forEach(row => {
                            const type = row.cells[0].textContent.toLowerCase();
                            const matchText = row.cells[1].textContent.toLowerCase();
                            const source = row.cells[2].textContent.toLowerCase();
                            
                            if (type.includes(keyword) || matchText.includes(keyword) || source.includes(keyword)) {
                                row.style.display = '';
                            } else {
                                row.style.display = 'none';
                            }
                        });
                        
                        updateVisibleCounts();
                    } else {
                        clearFilter();
                    }
                }
                
                function clearFilter() {
                    filterInput.value = '';
                    filterStatus.style.display = 'none';
                    
                    matchItems.forEach(item => {
                        item.style.display = '';
                    });
                    
                    tableRows.forEach(row => {
                        row.style.display = '';
                    });
                    
                    updateVisibleCounts(true);
                }
                
                function updateVisibleCounts(reset = false) {
                    const headers = document.querySelectorAll('h2');
                    
                    headers.forEach(header => {
                        const patternName = header.dataset.patternName;
                        if (!patternName) return;
                        const countSpan = header.querySelector('.pattern-count');
                        
                        // 修复: 选择器中的属性值也需要被正确处理，特别是当patternName包含特殊字符时
                        // 使用CSS.escape()可以实现，但为了兼容性，我们依赖于Python端生成的可靠属性值
                        const safePatternSelector = `[data-type="${patternName.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"]`;
                        
                        if (reset) {
                            const originalItems = document.querySelectorAll('.match-item' + safePatternSelector);
                            countSpan.textContent = originalItems.length;
                        } else {
                            const visibleItems = Array.from(document.querySelectorAll('.match-item' + safePatternSelector))
                                .filter(item => item.style.display !== 'none');
                            countSpan.textContent = visibleItems.length;
                        }
                    });
                }
                
                document.addEventListener('DOMContentLoaded', () => {
                    const noResults = document.querySelector('.no-results');
                    const toolbar = document.querySelector('.toolbar');
                    
                    if (noResults) {
                        toolbar.style.display = 'none';
                    }
                });
            </script>
        </body>
        </html>
        """
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_path
    
    def save_results(self, matches: Dict, unique_paths: List, path_mappings: List) -> None:
        """保存扫描结果到文件"""
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)
        
        html_path = self.generate_html_output(matches)
        
        text_path = os.path.join(self.output_directory, 'sensitive_info.txt')
        with open(text_path, 'w', encoding='utf-8') as output_file:
            output_file.write(f"=== JavaScript敏感信息扫描结果 ===\n")
            output_file.write(f"扫描时间: {Utils().tellTime()}\n\n")
            
            for pattern_name, pattern_matches in matches.items():
                if pattern_matches:
                    output_file.write(f"\n=== {pattern_name.upper()} ===\n")
                    for match_text, source, _ in pattern_matches:
                        output_file.write(f"[+] {match_text}\n")
                        output_file.write(f"    来源: {source}\n")
        
        path_output_file = os.path.join(self.output_directory, 'paths.txt')
        with open(path_output_file, 'w', encoding='utf-8') as path_file:
            path_file.write("[--------------------独立路径列表-----------------------]\n")
            for path in unique_paths:
                path_file.write(f"{path}\n")
            path_file.write("\n[------------------文件路径对应关系-----------------------]\n")
            for mapping in path_mappings:
                path_file.write(f"{mapping}\n")
        
        self.log.info(f"HTML格式结果已保存到: {html_path}")
        self.log.info(f"文本格式结果已保存到: {text_path}")
        self.log.info(f"路径信息已保存到: {path_output_file}")
    
    def start_scan(self) -> bool:
        """开始扫描JavaScript文件中的敏感信息"""
        self.log.info("开始JavaScript敏感信息扫描...")
        
        try:
            project_path = DatabaseType(self.projectTag).getPathfromDB()
            if not project_path:
                self.log.error("无法获取项目路径")
                return False
            
            result = self.process_js_files(project_path)
            
            if result:
                self.log.info(f"JavaScript敏感信息扫描完成，结果保存在: {self.output_directory}")
                return True
            else:
                self.log.error("JavaScript敏感信息扫描失败")
                return False
                
        except Exception as e:
            self.log.error(f"JavaScript敏感信息扫描过程中出错: {e}")
            return False