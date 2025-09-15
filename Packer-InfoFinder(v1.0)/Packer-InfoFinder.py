# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import sys
import re
import json
import html 
import base64 
import datetime
from urllib.parse import quote, urlparse
from collections import Counter, defaultdict
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[错误] 缺少 'BeautifulSoup' 模块，请先安装: pip install beautifulsoup4")
    sys.exit(1)

from lib.Controller import Project
from lib.TestProxy import testProxy
from lib.common.banner import RandomBanner
from lib.common.cmdline import CommandLines
from lib.common.utils import Utils
from lib.common.CreatLog import logs, log_name
import importlib

class Program():
    def __init__(self, options):
        self.options = options

    def check(self):
        url = self.options.url
        t = Project(url, self.options)
        t.parseStart()


def read_urls(file_path):
    """读取 URL 文件"""
    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件 {file_path} 不存在")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except (FileNotFoundError, IOError, PermissionError) as e:
        print(f"文件操作失败: {e}")
        exit(1)

def reset_project_tag():
    """重置全局projectTag变量，为每个URL创建唯一的projectTag"""
    import lib.common.CreatLog
    importlib.reload(lib.common.CreatLog)
    return lib.common.CreatLog.logs

# --- 功能升级：交互式总览报告生成逻辑 ---

def initialize_finder_overview_report(report_path):
    """初始化总览报告文件，写入HTML头部、样式和交互脚本"""
    report_title = "Finder 敏感信息扫描总览报告"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{report_title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 0 auto; max-width: 1600px; padding: 20px; background-color: #f8f9fa; color: #333; }}
        h1, h2 {{ text-align: center; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); background-color: #fff; }}
        th, td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: left; word-break: break-all; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        .data-row:nth-child(even) {{ background-color: #f9f9f9; }}
        .data-row:hover {{ background-color: #e9ecef; cursor: pointer; }}
        .data-row.active {{ background-color: #d1e7fd; }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .summary-found {{ color: #dc3545; font-weight: bold; }}
        .summary-not-found {{ color: #6c757d; }}
        .summary-error {{ color: #ffc107; }}
        .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 0.9em; }}
        .hidden {{ display: none; }}
        .detail-cell {{ padding: 0; }}
        .detail-container {{ padding: 20px; background-color: #fdfdfd; border-top: 2px solid #007bff; }}
        .tabs {{ display: flex; border-bottom: 1px solid #ccc; margin-bottom: 15px; flex-wrap: wrap; }}
        .tab-link {{ padding: 10px 15px; cursor: pointer; border: 1px solid transparent; border-bottom: none; margin-bottom: -1px; background: #f1f1f1; border-radius: 4px 4px 0 0; margin-right: 5px; }}
        .tab-link.active {{ background: #fff; border-color: #ccc #ccc #fff; }}
        .tab-content {{ padding: 10px; }}
        .match-list-item {{ list-style: none; padding: 10px; border: 1px solid #eee; margin-bottom: 8px; border-radius: 4px; background: #fff; }}
        .match-list-item:hover {{ background: #f7f7f7; }}
        .match-header {{ cursor: pointer; font-weight: bold; color: #c0392b; font-family: monospace; }}
        .match-source {{ font-size: 0.8em; color: #777; margin-left: 15px; }}
        .match-context {{ background-color: #f0f0f0; padding: 10px; border-radius: 4px; margin-top: 10px; font-family: monospace; white-space: pre-wrap; word-break: break-all; font-size: 0.9em; border-left: 3px solid #6c757d; }}
        .highlight {{ background-color: #ff9999; padding: 2px 0; border-radius: 2px; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>{report_title}</h1>
    <h2>报告生成时间: {timestamp}</h2>
    <table id="main-table">
        <thead>
            <tr>
                <th style="width:5%">序号</th>
                <th style="width:35%">目标URL (点击展开/折叠)</th>
                <th style="width:45%">结果摘要</th>
                <th style="width:15%">原始报告</th>
            </tr>
        </thead>
        <tbody>
        </tbody>
    </table>
    <div class="footer">
        <p>报告由 Packer-InfoFinder 工具生成</p>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const mainTableBody = document.querySelector('#main-table tbody');

            // --- BUG FIX: Unicode-safe Base64解码函数 ---
            function b64DecodeUnicode(str) {{
                try {{
                    return decodeURIComponent(atob(str).split('').map(function(c) {{
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }}).join(''));
                }} catch (e) {{
                    console.error("Base64 decoding failed:", e);
                    return '';
                }}
            }}

            mainTableBody.addEventListener('click', function(e) {{
                const dataRow = e.target.closest('.data-row');
                if (!dataRow) return;

                const detailRowId = `detail-${{dataRow.dataset.id}}`;
                let detailRow = document.getElementById(detailRowId);

                if (detailRow) {{
                    dataRow.classList.toggle('active');
                    detailRow.classList.toggle('hidden');
                }} else {{
                    dataRow.classList.add('active');
                    detailRow = document.createElement('tr');
                    detailRow.id = detailRowId;
                    const detailCell = detailRow.insertCell(0);
                    detailCell.colSpan = 4;
                    detailCell.classList.add('detail-cell');
                    dataRow.insertAdjacentElement('afterend', detailRow);
                    
                    const jsonDataScript = document.getElementById(`json-${{dataRow.dataset.id}}`);
                    try {{
                        const b64Data = jsonDataScript.textContent.trim();
                        if (!b64Data) throw new Error("No data found.");
                        
                        const jsonText = b64DecodeUnicode(b64Data);
                        if (!jsonText) throw new Error("Decoded data is empty.");

                        const findings = JSON.parse(jsonText);
                        detailCell.innerHTML = createDetailView(findings, dataRow.dataset.id);
                        attachDetailEventListeners(detailRow);
                    }} catch (err) {{
                        detailCell.innerHTML = `<div class="detail-container">无法加载详细信息: ${{err.message}}</div>`;
                    }}
                }}
            }});

            function createDetailView(findings, id) {{
                if (Object.keys(findings).length === 0) {{
                    return `<div class="detail-container">无详细信息</div>`;
                }}
                let tabsHtml = '<div class="tabs">';
                let contentHtml = '';
                let isFirstTab = true;
                let tabIndex = 0; // --- BUG FIX: 使用索引作为ID，更稳妥 ---

                for (const type in findings) {{
                    const safeId = `tab-${{id}}-${{tabIndex}}`;
                    tabsHtml += `<div class="tab-link ${{isFirstTab ? 'active' : ''}}" data-tab="${{safeId}}">${{escapeHtml(type)}} (${{findings[type].length}})</div>`;
                    
                    let matchesHtml = '<ul style="padding:0;">';
                    findings[type].forEach((item, index) => {{
                        const contextId = `context-${{id}}-${{tabIndex}}-${{index}}`;
                        
                        // --- 优化点: 在上下文中高亮显示匹配的敏感信息 ---
                        const safeMatch = escapeHtml(item.match);
                        const safeContext = escapeHtml(item.context);
                        // 使用 split 和 join 实现全局替换，比 replaceAll 兼容性更好
                        const highlightedContext = safeContext.split(safeMatch).join(`<span class="highlight">${{safeMatch}}</span>`);
                        
                        matchesHtml += `
                            <li class="match-list-item">
                                <div class="match-header" data-target="${{contextId}}">
                                    ${{safeMatch}}
                                    <span class="match-source">${{escapeHtml(item.source)}}</span>
                                </div>
                                <div id="${{contextId}}" class="match-context hidden">
                                    ${{highlightedContext}}
                                </div>
                            </li>`;
                    }});
                    matchesHtml += '</ul>';

                    contentHtml += `<div id="${{safeId}}" class="tab-content ${{isFirstTab ? '' : 'hidden'}}">${{matchesHtml}}</div>`;
                    isFirstTab = false;
                    tabIndex++;
                }}
                tabsHtml += '</div>';

                return `<div class="detail-container">${{tabsHtml}}${{contentHtml}}</div>`;
            }}

            function attachDetailEventListeners(detailRow) {{
                detailRow.addEventListener('click', function(e) {{
                    if (e.target.classList.contains('tab-link')) {{
                        const tabId = e.target.dataset.tab;
                        detailRow.querySelectorAll('.tab-link').forEach(t => t.classList.remove('active'));
                        e.target.classList.add('active');
                        detailRow.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
                        detailRow.querySelector(`#${{tabId}}`).classList.remove('hidden');
                    }} else if (e.target.closest('.match-header')) {{
                        const header = e.target.closest('.match-header');
                        const contextDiv = document.getElementById(header.dataset.target);
                        if (contextDiv) {{
                            contextDiv.classList.toggle('hidden');
                        }}
                    }}
                }});
            }}

            function escapeHtml(str) {{
                if (typeof str !== 'string') return '';
                const p = document.createElement("p");
                p.textContent = str;
                return p.innerHTML;
            }}
        }});
    </script>
</body>
</html>
"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_template)

def parse_detailed_report(report_path):
    """解析单个sensitive_info.html文件，提取摘要和所有详细信息"""
    summary = "已扫描，未发现敏感信息"
    details = defaultdict(list)
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "未发现敏感信息" in content:
                return summary, {}
            soup = BeautifulSoup(content, 'html.parser')

        findings_summary = Counter()
        sidebar_links = soup.select('.sidebar ul li a')
        for link in sidebar_links:
            match = re.match(r'^(.*?)(\d+)$', link.get_text(strip=True))
            if match:
                finding_type, count = match.groups()
                findings_summary[finding_type.strip()] = int(count)
        if findings_summary:
            summary_parts = [f"{ftype}: {count}" for ftype, count in findings_summary.most_common()]
            summary = ", ".join(summary_parts)

        sections = soup.find_all('h2')
        for section in sections:
            section_id = section.get('id')
            if not section_id: 
                continue
            section_title = section_id.replace("_", " ")

            match_grid = section.find_next_sibling('div', class_='match-grid')
            if not match_grid: 
                continue

            for item in match_grid.find_all('div', class_='match-item'):
                match_text = item.select_one('.match-text').get_text(strip=True) if item.select_one('.match-text') else ''
                match_source = item.select_one('.match-source').get_text(strip=True).replace('来源: ', '') if item.select_one('.match-source') else ''
                match_context = item.select_one('.match-context').get_text(strip=True) if item.select_one('.match-context') else ''
                details[section_title].append({
                    "match": match_text,
                    "source": match_source,
                    "context": match_context
                })

        return summary, dict(details)
    except Exception as e:
        return f"解析报告失败: {str(e)}", {}

def append_to_overview_report(index, url, summary, details, detailed_report_path):
    """向总览报告中追加一行记录及对应的Base64编码的JSON数据"""
    summary_class = "summary-not-found"
    if details and "失败" not in summary and "异常" not in summary:
        summary_class = "summary-found"
    elif "失败" in summary or "异常" in summary:
        summary_class = "summary-error"

    link = "无"
    if detailed_report_path and os.path.exists(detailed_report_path):
        relative_path = os.path.relpath(detailed_report_path, start=os.getcwd())
        link = f'<a href="{quote(relative_path.replace(os.sep, "/"))}" target="_blank" onclick="event.stopPropagation();">点击查看</a>'

    table_row = f"""
            <tr class="data-row" data-id="{index}">
                <td>{index}</td>
                <td><a href="{url}" target="_blank" onclick="event.stopPropagation();">{url}</a></td>
                <td class="{summary_class}">{summary}</td>
                <td>{link}</td>
            </tr>
    """
    
    try:
        json_string = json.dumps(details, ensure_ascii=False)
        json_bytes = json_string.encode('utf-8')
        b64_bytes = base64.b64encode(json_bytes)
        b64_string = b64_bytes.decode('ascii')
    except Exception:
        b64_string = ""

    json_script = f"""
            <script type="application/json-base64" id="json-{index}" class="hidden">
            {b64_string}
            </script>
    """
    return table_row + json_script


def finalize_overview_report(report_path, all_rows_html):
    """将所有行数据写入报告并添加结尾"""
    with open(report_path, 'r+', encoding='utf-8') as f:
        content = f.read()
        tbody_pos = content.find('</tbody>')
        if tbody_pos != -1:
            final_content = content[:tbody_pos] + all_rows_html + content[tbody_pos:]
            f.seek(0)
            f.write(final_content)
            f.truncate()

def PackerInfoFinder():
    options = CommandLines().cmd()
    
    overview_report_path = "Finder_敏感信息总览报告.html"
    is_batch_finder_scan = options.list and options.finder
    all_rows_html = [] 

    if is_batch_finder_scan:
        initialize_finder_overview_report(overview_report_path)
        print(f"[+] 批量Finder扫描模式已启用，将生成交互式总览报告: {os.path.abspath(overview_report_path)}")

    if options.url is None:
        urls = read_urls(options.list)
        total_urls = len(urls)

        if total_urls == 0:
            print("[错误] URL列表文件为空或无有效URL")
            exit(1)

        print(f"开始扫描 {total_urls} 个 URL...")

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{total_urls}] 开始扫描 URL: {url}")
            print("==================================================")
            
            new_tag = reset_project_tag()
            testProxy(options, 1)
            options.url = url
            InfoFinder = Program(options)
            try:
                InfoFinder.check()

                if is_batch_finder_scan:
                    host = urlparse(url).netloc.replace(":", "_")
                    report_dir = os.path.join("tmp", f"{new_tag}_{host}", "finder_results")
                    report_file = os.path.join(report_dir, "sensitive_info.html")
                    
                    summary_text = ""
                    details_data = {}
                    detailed_report_path = None

                    if os.path.exists(report_file):
                        detailed_report_path = report_file
                        summary_text, details_data = parse_detailed_report(detailed_report_path)
                    else:
                        summary_text = "未生成报告文件 (可能未发现JS或未找到敏感信息)"

                    row_html = append_to_overview_report(i, url, summary_text, details_data, detailed_report_path)
                    all_rows_html.append(row_html)
                    print(f"[+] 已处理 {url} 的扫描结果。")

            except Exception as e:
                print(f"[错误] 扫描URL {url} 时发生严重错误: {e}")
                if is_batch_finder_scan:
                    row_html = append_to_overview_report(i, url, f"扫描异常: {e}", {}, None)
                    all_rows_html.append(row_html)
                continue
        
        if is_batch_finder_scan:
            finalize_overview_report(overview_report_path, "\n".join(all_rows_html))
            print(f"\n[v] 所有URL扫描完毕。交互式总览报告已成功生成: {os.path.abspath(overview_report_path)}")
        else:
            print(f"\n所有 {total_urls} 个 URL 扫描完毕。")

    else:
        testProxy(options, 1)
        PackerFuzzer = Program(options)
        PackerFuzzer.check()

if __name__ == "__main__":
    RandomBanner()
    PackerInfoFinder()