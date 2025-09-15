#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import re
import requests
import warnings
import sqlite3
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from lib.common.utils import Utils
from lib.Database import DatabaseType
from lib.DownloadJs import DownloadJs
from lib.common.CreatLog import creatLog
from lib.common.cmdline import CommandLines


class ParseJs():
    def __init__(self, projectTag, url, options):
        warnings.filterwarnings('ignore')
        self.url = url
        self.jsPaths = []
        self.jsRealPaths = []
        self.jsPathList = []
        self.projectTag = projectTag
        self.options = options
        self.proxy_data = {'http': self.options.proxy, 'https': self.options.proxy}
        self.base_url = url  # 新增基路径变量
        self._init_headers()
        DatabaseType(self.projectTag).createProjectDatabase(self.url, 1, "0")
        self.log = creatLog().get_logger()

    def _init_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:78.0) Gecko/20100101 Firefox/78.0",
            self.options.head.split(':')[0]: self.options.head.split(':')[1]
        }
        if self.options.cookie:
            headers["Cookie"] = self.options.cookie
        self.header = headers

    def _extract_base_url(self, html_content):
        """从HTML中提取<base>标签修正基路径"""
        soup = BeautifulSoup(html_content, "html.parser")
        base_tag = soup.find("base")
        if base_tag and base_tag.get("href"):
            return urljoin(self.url, base_tag.get("href"))
        return self.url

    def _process_script_tags(self, soup):
        """处理script标签的通用逻辑"""
        for item in soup.find_all("script"):
            # 处理外部JS
            if js_path := item.get("src"):
                self.jsPaths.append(js_path)
            
            # 处理内联JS
            if js_code := item.text.encode():
                self._save_inline_js(js_code)

    def _save_inline_js(self, js_code):
        """保存内联JS到数据库"""
        js_tag = Utils().creatTag(6)
        res = urlparse(self.url)
        domain = res.netloc.replace(":", "_")
        db_path = os.path.join("tmp", f"{self.projectTag}_{domain}", f"{self.projectTag}.db")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO js_file(name, path, local) VALUES(?, ?, ?)",
                (f"{js_tag}.js", self.url, f"{js_tag}.js")
            )
            file_path = os.path.join("tmp", f"{self.projectTag}_{domain}", f"{js_tag}.js")
            with open(file_path, "wb") as f:
                f.write(js_code)
            cursor.execute("UPDATE js_file SET success = 1 WHERE local=?", (f"{js_tag}.js",))
            conn.commit()

    def requestUrl(self):
        try:
            response = self._fetch_url()
            self.base_url = self._extract_base_url(response.text)  # 更新基路径
            soup = BeautifulSoup(response.text.replace("", ""), "html.parser")
            
            self._process_script_tags(soup)
            self._process_link_tags(soup)
            self._process_dynamic_js(soup, response.text)
            
            self.dealJs(self.jsPaths)
        except Exception as e:
            self.log.error(f"[Critical Error] 主解析流程失败: {str(e)}")

    def _fetch_url(self):
        """封装请求逻辑"""
        ssl_flag = int(self.options.ssl_flag)
        kwargs = {
            "url": self.url,
            "headers": self.header,
            "proxies": self.proxy_data,
            "allow_redirects": True,
            # --- 优化：添加了健壮的超时设置 ---
            "timeout": (10, 30) # 10秒连接，30秒读取
        }
        if ssl_flag:
            kwargs["verify"] = False
        response = requests.get(**kwargs)
        
        # 处理重定向
        if response.url != self.url:
            self.log.info(f"{Utils().tellTime()} 重定向: {self.url} -> {response.url}")
            self.url = response.url
        return response

    def _process_link_tags(self, soup):
        """处理link标签"""
        for item in soup.find_all("link"):
            if (href := item.get("href")) and href.endswith(".js"):
                self.jsPaths.append(href)

    def _process_dynamic_js(self, soup, html_content):
        """处理动态生成的JS路径"""
        try:
            js_in_script = self.scriptCrawling(html_content)
            self.jsPaths.extend(js_in_script)
        except Exception as e:
            self.log.error(f"[Error] scriptCrawling失败: {str(e)}")

    def dealJs(self, js_paths):
        """生成JS绝对路径"""
        parsed = urlparse(self.base_url)
        
        for path in js_paths:
            path = path.strip()
            if not path:
                continue
            if path.startswith("http"):
                self.jsRealPaths.append(path)
            elif path.startswith("//"):
                self.jsRealPaths.append(f"{parsed.scheme}:{path}")
            else:
                self.jsRealPaths.append(urljoin(self.base_url, path))
        
        self.log.info(f"{Utils().tellTime()} 发现JS文件: {len(self.jsRealPaths)}个")
        domain = parsed.netloc.replace(":", "_")
        DownloadJs(self.jsRealPaths, self.options).downloadJs(self.projectTag, domain, 0)
        self._process_external_js(domain)

    def _process_external_js(self, domain):
        """处理外部输入的JS"""
        if hasattr(self.options, 'js') and self.options.js:
            ext_js = self.options.js
            DownloadJs(ext_js.split(','), self.options).downloadJs(self.projectTag, domain, 0)

    def scriptCrawling(self, demo):
        """从内联JS中提取路径"""
        soup = BeautifulSoup(demo, "html.parser")
        found_paths = []
        for script in soup.find_all("script"):
            if script_content := script.string:
                found_paths.extend(re.findall(r'src=["\'](.*?\.js)', str(script_content)))
        return list(set(found_paths))

    def parseJsStart(self):
        self.requestUrl()