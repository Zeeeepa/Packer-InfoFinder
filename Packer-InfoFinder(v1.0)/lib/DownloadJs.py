# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sqlite3
import warnings
import random
import re
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.common import readConfig
from lib.common.utils import Utils
from lib.common.CreatLog import creatLog


class DownloadJs():

    def __init__(self, jsRealPaths, options):
        warnings.filterwarnings('ignore')
        self.jsRealPaths = jsRealPaths
        self.blacklist_domains = readConfig.ReadConfig().getValue('blacklist', 'domain')[0]
        self.blacklistFilenames = readConfig.ReadConfig().getValue('blacklist', 'filename')[0]
        self.options = options
        self.proxy_data = {'http': self.options.proxy, 'https': self.options.proxy}
        self.UserAgent = [
            "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0",
            "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; en) Opera 9.50",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.57.2 (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11",
            "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.133 Safari/534.16",
            "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.11 TaoBrowser/2.0 Safari/536.11",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Maxthon/4.4.3.4000 Chrome/30.0.1599.101 Safari/537.36",
            "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; Trident/4.0; SV1; QQDownload 732; .NET4.0C; .NET4.0E; SE 2.X MetaSr 1.0)",
            "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; QQDownload 732; .NET4.0C; .NET4.0E; LBBROWSER)",
            "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50",
            "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0",
            "Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11",
            "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; TencentTraveler 4.0)"
        ]
        self.log = creatLog().get_logger()
        self.successful_path_patterns = {}
        self.webpack_public_path = None
        
        # --- 优化：初始化一个具备重试功能的 session ---
        self.session = requests.Session()
        # 定义重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1  # 重试之间的延迟因子
        )
        # ######################## START: 代码修改区域 ########################
        # 创建一个带有重试策略的适配器，并增大连接池大小以匹配线程数
        adapter = HTTPAdapter(
            pool_connections=100,      # 总连接池数量，可以设置得大一些
            pool_maxsize=30,           # 关键：每个连接池的最大连接数，使其等于或大于 max_workers (30)
            max_retries=retry_strategy
        )
        # ######################## END: 代码修改区域 ##########################

        # 为 http 和 https 协议挂载此适配器
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # ----------------------------------------------------------------

    def analyze_path_patterns(self, successful_path):
        try:
            parsed_url = urlparse(successful_path)
            path = parsed_url.path
            filename = path.split('/')[-1]
            if 'chunk' in filename:
                directory = '/'.join(path.split('/')[:-1]) + '/'
                if 'chunk' not in self.successful_path_patterns:
                    self.successful_path_patterns['chunk'] = []
                if directory not in self.successful_path_patterns['chunk']:
                    self.successful_path_patterns['chunk'].append(directory)
        except Exception as e:
            self.log.error(f"[Err] 分析路径模式时出错: {str(e)}")

    def extract_webpack_public_path(self, js_content):
        patterns = [
            r'__webpack_require__\.p\s*=\s*[\'"]([^\'"]+)[\'"]',
            r'\.p\s*=\s*[\'"]([^\'"]+)[\'"]',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, js_content)
            if matches:
                return matches[0]
        return None

    def infer_path(self, original_path):
        try:
            parsed_url = urlparse(original_path)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            filename = os.path.basename(parsed_url.path)
            possible_paths = {original_path} # 使用集合自动去重

            if 'chunk' in self.successful_path_patterns:
                for directory in self.successful_path_patterns['chunk']:
                    possible_paths.add(urljoin(base_url, f"{directory}{filename}"))
            
            return list(possible_paths)
        except Exception as e:
            self.log.error(f"[Err] 推断路径时出错: {str(e)}")
            return [original_path]

    def jsBlacklist(self):
        newList = self.jsRealPaths[:]
        for jsRealPath in newList:
            res = urlparse(jsRealPath)
            domain = res.netloc.lower()
            filename = Utils().getFilename(jsRealPath).lower()
            for d in self.blacklist_domains.split(","):
                if d in domain:
                    self.jsRealPaths.remove(jsRealPath)
                    break
            for f in self.blacklistFilenames.split(","):
                if f in filename:
                    if jsRealPath in self.jsRealPaths:
                        self.jsRealPaths.remove(jsRealPath)
                    break
        return self.jsRealPaths

    def download_single_js(self, jsRealPath, tag, host, spiltId):
        jsFilename = Utils().getFilename(jsRealPath)
        jsTag = Utils().creatTag(6)
        PATH = "tmp/" + tag + "_" + host + "/" + tag + ".db"
        db_path = os.sep.join(PATH.split('/'))
        
        conn = None  # 确保 conn 被定义
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            conn.isolation_level = None

            checkSql = f"SELECT * FROM js_file WHERE name='{jsFilename}'"
            cursor.execute(checkSql)
            if cursor.fetchall():
                self.log.info(Utils().tellTime() + f"文件已存在，跳过: {jsFilename}")
                return

            if spiltId == 0:
                sql = f"INSERT INTO js_file(name,path,local) VALUES('{jsFilename}', '{jsRealPath}', '{jsTag}.{jsFilename}')"
            else:
                sql = f"INSERT INTO js_file(name,path,local,spilt) VALUES('{jsFilename}', '{jsRealPath}', '{jsTag}.{jsFilename}', {spiltId})"
            cursor.execute(sql)
            conn.commit()

            sslFlag = int(self.options.ssl_flag)
            header = {
                'User-Agent': random.choice(self.UserAgent),
                'Accept': 'application/javascript, text/javascript, */*; q=0.01',
                self.options.head.split(':')[0]: self.options.head.split(':')[1],
            }
            if self.options.cookie:
                header['Cookie'] = self.options.cookie

            # 更新 session 的请求细节
            self.session.headers.update(header)
            self.session.proxies.update(self.proxy_data)
            self.session.verify = not sslFlag

            # --- 优化：使用 session 并配合健壮的超时和错误处理 ---
            # 超时：10秒连接，30秒读取响应。
            response = self.session.get(jsRealPath, stream=True, timeout=(10, 30))
            
            # 如果 HTTP 请求返回不成功的状态码，这将引发 HTTPError，并由重试机制处理。
            response.raise_for_status()

            self.analyze_path_patterns(jsRealPath)
            
            jsFileData = response.content
            if jsFileData.strip().lower().startswith((b'<!doctype html>', b'<html')):
                self.log.error(f"[Err] 下载内容为HTML，非JS: {jsFilename}")
                return

            if not self.webpack_public_path:
                self.webpack_public_path = self.extract_webpack_public_path(jsFileData.decode('utf-8', errors='ignore'))

            file_path = f"tmp{os.sep}{tag}_{host}{os.sep}{jsTag}.{jsFilename}"
            with open(file_path, "wb") as js_file:
                js_file.write(jsFileData)
                
            cursor.execute(f"UPDATE js_file SET success=1 WHERE local='{jsTag}.{jsFilename}'")
            conn.commit()
            self.log.info(Utils().tellTime() + f"下载成功: {jsFilename}")

        except requests.exceptions.RequestException as e:
            # 这将捕获所有重试失败后的错误。
            self.log.error(f"[Err] 所有重试均告失败: {jsFilename}, 错误: {str(e)}")
        except Exception as e:
            self.log.error(f"[Err] 下载或处理过程中发生未知错误: {jsFilename}, 错误: {str(e)}")
        finally:
            if conn:
                conn.close()

    def downloadJs(self, tag, host, spiltId):
        self.jsRealPaths = list(set(self.jsRealPaths))
        try:
            self.jsRealPaths = self.jsBlacklist()
        except Exception as e:
            self.log.error("[Err] %s" % e)

        filtered_urls = []
        for jsUrl in self.jsRealPaths:
            try:
                parsed_url = urlparse(jsUrl)
                if all([parsed_url.scheme, parsed_url.netloc]):
                    filtered_urls.append(jsUrl)
                else:
                    self.log.error(f"格式无效的URL，已忽略: {jsUrl}")
            except Exception as e:
                self.log.error(f"URL解析错误: {jsUrl}, {str(e)}")

        # --- 优化：增加并发工作线程数 ---
        # 对于像下载这样的I/O密集型任务，更多的线程可以显著提高速度。
        # 这个值可以根据网络状况和目标服务器的性能进行调整。
        max_workers = 30
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.download_single_js, jsRealPath, tag, host, spiltId) for jsRealPath in filtered_urls]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.error(f"[Err] 一个下载任务线程出现异常: {e}")

    def creatInsideJs(self, tag, host, scriptInside, url):
        try:
            jsRealPath = url
            jsFilename = "7777777.script.inside.html.js"
            jsTag = Utils().creatTag(6)
            PATH = "tmp/" + tag + "_" + host + "/" + tag + ".db"
            conn = sqlite3.connect(os.sep.join(PATH.split('/')))
            cursor = conn.cursor()
            conn.isolation_level = None
            sql = f"INSERT INTO js_file(name,path,local) VALUES('{jsFilename}','{jsRealPath}','{jsTag}.{jsFilename}')"
            cursor.execute(sql)
            conn.commit()
            self.log.info(Utils().tellTime() + "正在下载：" + jsFilename)
            file_path = f"tmp{os.sep}{tag}_{host}{os.sep}{jsTag}.{jsFilename}"
            with open(file_path, "wb") as js_file:
                js_file.write(str.encode(scriptInside))
            cursor.execute(f"UPDATE js_file SET success=1 WHERE local='{jsTag}.{jsFilename}'")
            conn.commit()
            conn.close()
        except Exception as e:
            self.log.error("[Err] %s" % e)