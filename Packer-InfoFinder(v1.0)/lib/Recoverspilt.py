#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os, re, sqlite3
from urllib.parse import urlparse, urljoin
from lib.common.utils import Utils
from lib.Database import DatabaseType
from lib.DownloadJs import DownloadJs
from lib.common.groupBy import GroupBy
from lib.common.CreatLog import creatLog
import deno_vm
import esprima

class RecoverSpilt():

    def __init__(self, projectTag, options):
        self.projectTag = projectTag
        self.options = options
        self.log = creatLog().get_logger()
        self.processed_files = set()
        self.pending_js_files = set()
        self.js_split_id_counter = 1

    def _get_db_connection(self):
        projectDBPath = DatabaseType(self.projectTag).getPathfromDB() + self.projectTag + ".db"
        conn = sqlite3.connect(os.sep.join(projectDBPath.split('/')))
        conn.isolation_level = None
        return conn

    def _execute_in_deno(self, js_code_func, name_list):
        filenames_found = set()
        with deno_vm.VM() as vm:
            vm.run(js_code_func)
            for name in name_list:
                try:
                    param = int(name) if name.isdigit() else name
                    result = vm.call("js_compile", param)
                    if result and "undefined" not in str(result):
                        filenames_found.add(str(result))
                except Exception:
                    continue
        return filenames_found

    def compile_from_ast(self, code_body, param_name, jsFilePath, parent_js_content):
        try:
            pattern1 = re.compile(r"\{(.*?)\:")
            pattern2 = re.compile(r"\,(.*?)\:")
            code_body_for_regex = re.sub(r'\s', '', code_body)
            nameList1 = pattern1.findall(code_body_for_regex)
            nameList2 = pattern2.findall(code_body_for_regex)
            nameList = list(set([name.replace('"', '').replace("'", "") for name in nameList1 + nameList2]))

            if not nameList:
                self.log.debug(f"在 {Utils().getFilename(jsFilePath)} 中未提取到有效的JS模块ID (AST)")
                return

            self.log.info(f"在 {Utils().getFilename(jsFilePath)} 中提取到 {len(nameList)} 个JS模块ID (AST)，正在解析...")
            js_code_func = f"function js_compile({param_name}){{ return {code_body} }}"
            filenames_found = self._execute_in_deno(js_code_func, nameList)
            
            if filenames_found:
                self.log.info(f"成功解析出 {len(filenames_found)} 个异步JS文件名 (AST)")
                self._add_to_pending_list(filenames_found, jsFilePath, parent_js_content, code_body)
        except Exception as e:
            self.log.error(f"[Err] AST代码编译过程中出错: {e}")
    
    def compile_from_regex(self, jsCode, jsFilePath, parent_js_content):
        try:
            variable = re.findall(r'\[.*?\]', jsCode)
            if not variable: return

            variable = variable[0].replace("[", "").replace("]", "")
            jsCodeFunc = "function js_compile(%s){js_url=" % (variable) + jsCode + "\nreturn js_url}"

            pattern1 = re.compile(r"\{(.*?)\:")
            pattern2 = re.compile(r"\,(.*?)\:")
            nameList1 = pattern1.findall(jsCode)
            nameList2 = pattern2.findall(jsCode)
            nameList = list(set([name.replace('"', '').replace("'", "") for name in nameList1 + nameList2]))

            if not nameList: return

            self.log.info(f"在 {Utils().getFilename(jsFilePath)} 中提取到 {len(nameList)} 个JS模块ID (Regex)，正在解析...")
            filenames_found = self._execute_in_deno(jsCodeFunc, nameList)

            if filenames_found:
                self.log.info(f"成功解析出 {len(filenames_found)} 个异步JS文件名 (Regex)")
                self._add_to_pending_list(filenames_found, jsFilePath, parent_js_content, jsCode)
        except Exception as e:
            self.log.error(f"[Err] Regex代码编译过程中出错: {e}")

    def _add_to_pending_list(self, filenames_found, jsFilePath, parent_js_content, code_snippet):
        conn = self._get_db_connection()
        cursor = conn.cursor()
        localFile = os.path.basename(jsFilePath)
        
        jsSplitId = self.js_split_id_counter
        self.js_split_id_counter += 1

        sql = "INSERT OR IGNORE INTO js_split_tree(id, jsCode, js_name) VALUES(?, ?, ?)"
        cursor.execute(sql, (jsSplitId, code_snippet, localFile))
        conn.commit()

        cursor.execute("SELECT path FROM js_file WHERE local=?", (localFile,))
        jsUrlPath = cursor.fetchone()[0]
        conn.close()

        self.pending_js_files.update(
            self.getRealFilePath(list(filenames_found), jsUrlPath, parent_js_content)
        )

    def _build_full_url(self, path, script_url):
        """
        参照 content.js 中 buildFullUrl 逻辑的 Python 实现，用于健壮地拼接URL并处理双重路径。
        """
        try:
            script_url_parts = urlparse(script_url)
            base_origin = f"{script_url_parts.scheme}://{script_url_parts.netloc}"

            if path.startswith(('http://', 'https://')):
                return path
            
            if path.startswith('/'):
                return urljoin(base_origin, path)

            # 核心：处理相对路径和路径重叠
            script_path = script_url_parts.path
            script_directory = script_path[:script_path.rfind('/') + 1]

            path_segments = [s for s in path.split('/') if s]
            dir_segments = [s for s in script_directory.split('/') if s]
            
            overlap_len = 0
            # 从后向前寻找最大重叠
            for i in range(min(len(path_segments), len(dir_segments)), 0, -1):
                if dir_segments[-i:] == path_segments[:i]:
                    overlap_len = i
                    break
            
            # 拼接最终路径
            final_segments = dir_segments + path_segments[overlap_len:]
            final_path = "/" + "/".join(final_segments)
            
            return urljoin(base_origin, final_path)

        except Exception as e:
            self.log.error(f"构建URL时出错: path='{path}', script_url='{script_url}', error='{e}'")
            return urljoin(script_url, path) # Fallback

    def getRealFilePath(self, jsFileNames, jsUrlpath, parent_js_content):
        jsRealPaths = []
        # 尝试提取 publicPath
        match = re.search(r'(__webpack_require__\.p|\w\.p)\s*=\s*["\'](.*?)["\']', parent_js_content)
        if match:
            public_path = match.group(2)
            self.log.info(f"成功提取到 publicPath: '{public_path}'，将基于父JS路径智能合并。")
            # 使用 urljoin 智能合并 publicPath 和父JS目录，结果作为新的基础URL
            base_url_for_build = urljoin(jsUrlpath, public_path)
        else:
            self.log.warning("未能在父JS中自动提取 publicPath，将使用父JS的URL作为基础。")
            base_url_for_build = jsUrlpath

        for jsFileName in jsFileNames:
            # 统一调用我们健壮的URL构建函数
            full_url = self._build_full_url(jsFileName, base_url_for_build)
            jsRealPaths.append(full_url)
        
        return jsRealPaths

    def checkCodeSpilting(self, jsFilePath):
        if jsFilePath in self.processed_files:
            return
        self.processed_files.add(jsFilePath)

        try:
            with open(jsFilePath, 'r', encoding='UTF-8', errors="ignore") as f:
                js_content = f.read()

            self.log.info(f"[{Utils().tellTime()}] 正在使用AST分析文件: {Utils().getFilename(jsFilePath)}")
            found_by_ast = self._analyze_with_ast(js_content, jsFilePath)

            if not found_by_ast:
                self.log.info(f"AST未能找到模式，在 {Utils().getFilename(jsFilePath)} 上尝试Regex回退方案...")
                self._analyze_with_regex(js_content, jsFilePath)

        except Exception as e:
            self.log.error(f"[Err] 分析文件 {Utils().getFilename(jsFilePath)} 时发生未知错误: {e}")
    
    def _analyze_with_ast(self, js_content, jsFilePath):
        try:
            ast = esprima.parseScript(js_content, {'range': True, 'tolerant': True})
            return self._traverse_ast(ast, js_content, jsFilePath)
        except Exception as e:
            self.log.debug(f"[Debug] AST解析文件 {Utils().getFilename(jsFilePath)} 时失败: {e}")
            return False

    def _traverse_ast(self, node, js_content, jsFilePath):
        if not node or not isinstance(node, esprima.nodes.Node):
            return False

        if node.type == 'AssignmentExpression' and node.operator == '=' and \
           getattr(node.left, 'type', None) == 'MemberExpression' and \
           getattr(node.right, 'type', None) == 'FunctionExpression':
            
            func_node = node.right
            if func_node.body and func_node.body.body:
                for statement in func_node.body.body:
                    if statement.type == 'ReturnStatement' and statement.argument:
                        if not func_node.params: continue
                        
                        param_name = func_node.params[0].name
                        start, end = statement.argument.range
                        code_body = js_content[start:end]
                        
                        if ".js" in code_body:
                            self.log.info(f"AST发现可能的异步加载函数: {Utils().getFilename(jsFilePath)}")
                            self.compile_from_ast(code_body, param_name, jsFilePath, js_content)
                            return True

        for key in dir(node):
            if not key.startswith('_'):
                child = getattr(node, key)
                if isinstance(child, esprima.nodes.Node):
                    if self._traverse_ast(child, js_content, jsFilePath):
                        return True
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, esprima.nodes.Node):
                            if self._traverse_ast(item, js_content, jsFilePath):
                                return True
        return False

    def _analyze_with_regex(self, js_content, jsFilePath):
        if "document.createElement(\"script\")" in js_content:
            pattern = re.compile(r"\w\.p\+\"(.*?)\.js\"")
            jsCodeList = pattern.findall(js_content)
            if jsCodeList:
                 self.log.info(f"Regex发现 {len(jsCodeList)} 个可能的异步加载片段: {Utils().getFilename(jsFilePath)}")
                 for jsCode in jsCodeList:
                    if len(jsCode) < 30000:
                        full_js_code = '"' + jsCode + '.js"'
                        self.compile_from_regex(full_js_code, jsFilePath, js_content)

    def recoverStart(self):
        projectPath = DatabaseType(self.projectTag).getPathfromDB()
        
        self.log.info("--- 开始混合模式分析 (AST为主, Regex为辅) ---")
        all_js_files = []
        for parent, _, filenames in os.walk(projectPath, followlinks=True):
            for filename in filenames:
                if filename.endswith(".js"):
                    all_js_files.append(os.path.join(parent, filename))
        
        for js_file_path in all_js_files:
            self.checkCodeSpilting(js_file_path)

        if self.pending_js_files:
            self.log.info(f"--- 共发现 {len(self.pending_js_files)} 个新的异步JS文件，开始下载 ---")
            domain = urlparse(self.options.url).netloc
            if ":" in domain:
                domain = domain.replace(":", "_")
            
            DownloadJs(list(self.pending_js_files), self.options).downloadJs(self.projectTag, domain, 999)
        else:
            self.log.info("--- 未发现新的异步JS文件 ---")