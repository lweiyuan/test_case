#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载曙光 OA 登录相关 JS 文件, 用于分析滑动验证码的签名算法。
在【能访问公司内网】的机器上运行:
    python fetch_login_js.py
运行后把 output/js/ 目录下的文件内容发回给我。
"""
import os
import sys
import requests
import urllib3

urllib3.disable_warnings()

OUTPUT_DIR = os.path.join("output", "js")

# 需要抓取的文件(相对 soa.com.cn 或 oastatic.sugon.com)
URLS = [
    "https://soa.com.cn/login/cooacloudlogin/login.js",
    "https://oastatic.sugon.com/OA/signature.js",
    "https://oastatic.sugon.com/OA/login/jquery-1.7.2.min.js",
    "https://soa.com.cn/login/cooacloudlogin/login.css",
]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://soa.com.cn/oaataticsv/attendance/index.html",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

for url in URLS:
    fname = url.rsplit("/", 1)[-1]
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        if r.status_code == 200:
            path = os.path.join(OUTPUT_DIR, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
            print("[OK] {}  ->  {} ({} 字符)".format(url, path, len(r.text)))
        else:
            print("[{}] {}  状态码 {}".format("跳过", url, r.status_code))
    except Exception as e:
        print("[失败] {}  错误: {}".format(url, e))

print("\n完成。请把 {} 目录下的文件内容发回给我。".format(os.path.abspath(OUTPUT_DIR)))
