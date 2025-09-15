# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
from lib.ParseJs import ParseJs
from lib.common.utils import Utils
from lib.Database import DatabaseType
from lib.FuzzParam import FuzzerParam
from lib.CheckPacker import CheckPacker
from lib.common.beautyJS import BeautyJs
from lib.Recoverspilt import RecoverSpilt
from lib.common.CreatLog import creatLog,log_name,logs
from lib.JsFinder.JsFinderModule import JsFinderModule  #引入js文件扫描模块

class Project():

    def __init__(self, url, options):
        self.url = url
        self.codes = {}
        self.options = options
        # 确保每个URL实例使用自己的projectTag
        from lib.common.CreatLog import logs
        self.projectTag = logs

    def parseStart(self):
        # --- 修复：移除所有关于finder_report_path的返回值逻辑 ---
        projectTag = self.projectTag
        if self.options.silent != None:
            print("[TAG]" + projectTag)
        DatabaseType(projectTag).createDatabase()
        ParseJs(projectTag, self.url, self.options).parseJsStart()
        path_log = os.path.abspath(log_name)
        path_db = os.path.abspath(DatabaseType(projectTag).getPathfromDB() + projectTag + ".db")
        creatLog().get_logger().info("[+] " + "缓存文件路径：" + path_db)  #显示数据库文件路径
        creatLog().get_logger().info("[+] " + "日志文件路径：" + path_log) #显示log文件路径
        checkResult = CheckPacker(projectTag, self.url, self.options).checkStart()
        if checkResult == 1 or checkResult == 777: #打包器检测模块
            if checkResult != 777: #确保检测报错也能运行
                creatLog().get_logger().info("[v] " + "恭喜，这个站点很可能是通过前端打包器构建的！")
            RecoverSpilt(projectTag, self.options).recoverStart()
        else:
            creatLog().get_logger().info("[!] " + "未检测到前端打包器特征，也有可能是现有规则不足...")
        
        # 如果启用了finder参数，执行JavaScript敏感信息扫描
        if hasattr(self.options, 'finder') and self.options.finder:
            creatLog().get_logger().info("[+] " + "已启用JavaScript敏感信息扫描...")
            js_finder = JsFinderModule(projectTag, self.options)
            
            # --- 修复：恢复原始的调用方式，不再关心返回值 ---
            scan_result = js_finder.start_scan()

            if scan_result:
                creatLog().get_logger().info("[v] " + "JavaScript敏感信息扫描完成")
            else:
                creatLog().get_logger().info("[!] " + "JavaScript敏感信息扫描过程中出现问题或未发现")
        
        creatLog().get_logger().info("[v] " + "感谢您的使用！")
        
        # --- 修复：函数末尾不再返回任何值 ---