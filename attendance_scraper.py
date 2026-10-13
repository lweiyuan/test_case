#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
曙光(SOA)考勤系统 —— 自动登录 + 抓取脚本
============================================================
在【能访问公司内网】的机器上运行:
    pip install requests beautifulsoup4
    python attendance_scraper.py

脚本会:
  1. 访问登录页, 自动识别登录表单字段(用户名/密码/隐藏字段/CSRF token)
  2. 提交登录, 维持会话 Cookie
  3. 打开考勤页面, 抓取所有表格数据
  4. 输出到 ./output/ 目录(CSV + JSON + 原始 HTML, 便于人工核对)

说明:
  本脚本无法预知贵司 OA 的具体登录方式(表单字段名、是否走 AJAX/JSON 接口、
  是否有验证码、数据是否登录后异步加载)。脚本做了"自动探测 + 手动兜底"两套逻辑,
  并输出详细调试日志; 如果自动登录失败, 请把 ./output/debug_*.html 发回分析。
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    sys.exit("缺少依赖 requests, 请先运行: pip install requests beautifulsoup4")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("[提示] 未安装 beautifulsoup4, 将使用简化解析(建议安装以提升表格抓取质量):")
    print("       pip install beautifulsoup4")

# ============================================================
# 配置区 —— 按需修改
# ============================================================
USERNAME = "weiyuan1"
PASSWORD = "Sugon@1234"

LOGIN_URL = "https://soa.com.cn/oaataticsv/attendance/index.html"
ATTENDANCE_URL = "https://soa.com.cn/oaataticsv/attendance/index.html"  # 登录后要抓的数据页
BASE_URL = "https://soa.com.cn"

TIMEOUT = 30            # 单次请求超时(秒)
VERIFY_SSL = False      # 内网常见自签名证书, 设 False 跳过校验
OUTPUT_DIR = "output"

# 自动识别用户名/密码输入框时, 匹配这些 name/id 的关键词(按优先级)
USERNAME_KEYS = ["username", "username", "user_name", "loginname", "login_name",
                 "j_username", "account", "userid", "user_id", "user", "emp",
                 "empcode", "emp_code", "workno", "work_no", "jobnumber",
                 "job_number", "loginid", "login_id", "staff", "email"]
PASSWORD_KEYS = ["password", "passwd", "pwd", "j_password", "userpassword",
                 "user_password", "loginpwd", "login_pwd"]

# 手动兜底: 如果自动识别失败, 在这里填上正确的字段名(打开登录页 F12 查看)
# 例如: USERNAME_FIELD = "loginName"; PASSWORD_FIELD = "passWord"
USERNAME_FIELD = None
PASSWORD_FIELD = None

# 登录成功后, 抓取数据前等待的秒数(某些页面数据是异步加载)
WAIT_AFTER_LOGIN = 3

# ============================================================
# 工具函数
# ============================================================
def log(msg):
    print("[{}] {}".format(datetime.now().strftime("%H:%M:%S"), msg))


def save_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log("已保存: {}".format(path))


def find_input_by_keys(soup, keys):
    """在表单中按 name/id/placeholder 关键词查找输入框"""
    for inp in soup.find_all("input"):
        name = (inp.get("name") or "").lower()
        iid = (inp.get("id") or "").lower()
        placeholder = (inp.get("placeholder") or "").lower()
        blob = " ".join([name, iid, placeholder])
        for k in keys:
            if k in blob:
                return inp
    return None


def extract_hidden_fields(soup):
    """提取表单里的隐藏字段(含 CSRF token 之类)"""
    hidden = {}
    for inp in soup.find_all("input"):
        t = (inp.get("type") or "text").lower()
        if t == "hidden":
            name = inp.get("name")
            if name:
                hidden[name] = inp.get("value") or ""
    return hidden


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "*/*;q=0.8"),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


def parse_tables(html):
    """从 HTML 中解析所有 <table>, 返回 {标题: [行列表]}"""
    if not HAS_BS4:
        return None
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for i, t in enumerate(soup.find_all("table")):
        rows = []
        for tr in t.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"]):
                cells.append(td.get_text(" ", strip=True))
            if cells:
                rows.append(cells)
        if rows:
            # 用前面的标题元素或序号作为表名
            title = "table_{}".format(i + 1)
            tables.append({"title": title, "rows": rows})
    return tables


# ============================================================
# 主流程
# ============================================================
def main():
    log("开始访问登录页: {}".format(LOGIN_URL))
    session = make_session()

    # 1) 获取登录页(拿到 Cookie + 表单)
    try:
        resp = session.get(LOGIN_URL, timeout=TIMEOUT, verify=VERIFY_SSL)
    except requests.exceptions.SSLError as e:
        log("SSL 证书校验失败: {}. 已尝试 VERIFY_SSL=False 重试".format(e))
        resp = session.get(LOGIN_URL, timeout=TIMEOUT, verify=False)
    except Exception as e:
        sys.exit("无法访问登录页: {}".format(e))

    log("登录页状态码: {}".format(resp.status_code))
    html = resp.text
    save_text(os.path.join(OUTPUT_DIR, "debug_login_page.html"), html)

    if not HAS_BS4:
        sys.exit("需要 beautifulsoup4 才能解析表单, 请运行: pip install beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")

    # 2) 定位登录表单
    form = None
    for f in soup.find_all("form"):
        # 优先选含密码框的表单
        if find_input_by_keys(f, PASSWORD_KEYS):
            form = f
            break
    if form is None and soup.find_all("form"):
        form = soup.find_all("form")[0]
    if form is None:
        # 没有 <form>, 可能表单在 iframe 里
        log("[警告] 登录页未发现 <form>, 请检查 debug_login_page.html, 看是否有 iframe/JS 登录")
        iframe_urls = [i.get("src") for i in soup.find_all("iframe") if i.get("src")]
        log("[提示] 页面 iframe: {}".format(iframe_urls))
        form = soup

    # 3) 识别字段
    user_inp = find_input_by_keys(form, USERNAME_KEYS) if form is not soup else find_input_by_keys(soup, USERNAME_KEYS)
    pass_inp = find_input_by_keys(form, PASSWORD_KEYS) if form is not soup else find_input_by_keys(soup, PASSWORD_KEYS)

    if USERNAME_FIELD:
        user_field_name = USERNAME_FIELD
    elif user_inp is not None:
        user_field_name = user_inp.get("name") or user_inp.get("id")
    else:
        user_field_name = None

    if PASSWORD_FIELD:
        pass_field_name = PASSWORD_FIELD
    elif pass_inp is not None:
        pass_field_name = pass_inp.get("name") or pass_inp.get("id")
    else:
        pass_field_name = None

    log("识别到用户名字段: {}".format(user_field_name))
    log("识别到密码字段: {}".format(pass_field_name))

    if not user_field_name or not pass_field_name:
        sys.exit(
            "[失败] 无法自动识别登录字段。请打开登录页按 F12 查看 <input name=...>,\n"
            "       并在脚本顶部 USERNAME_FIELD / PASSWORD_FIELD 里手动填写字段名。"
        )

    # 4) 构造登录 POST
    if form is not soup:
        action = form.get("action") or ""
        login_post_url = urljoin(LOGIN_URL, action) if action else LOGIN_URL
    else:
        login_post_url = LOGIN_URL

    data = extract_hidden_fields(form if form is not soup else soup)
    data[user_field_name] = USERNAME
    data[pass_field_name] = PASSWORD
    log("登录 POST 地址: {}".format(login_post_url))
    log("提交字段(密码已脱敏): {}".format({k: ("***" if k == pass_field_name else v) for k, v in data.items()}))

    # 保留原始 Referer
    session.headers.update({"Referer": LOGIN_URL})

    try:
        login_resp = session.post(login_post_url, data=data, timeout=TIMEOUT,
                                  verify=VERIFY_SSL, allow_redirects=True)
    except requests.exceptions.SSLError:
        login_resp = session.post(login_post_url, data=data, timeout=TIMEOUT,
                                  verify=False, allow_redirects=True)
    except Exception as e:
        sys.exit("登录请求失败: {}".format(e))

    log("登录响应状态码: {}, 最终URL: {}".format(login_resp.status_code, login_resp.url))
    save_text(os.path.join(OUTPUT_DIR, "debug_login_response.html"), login_resp.text)

    # 5) 判断是否登录成功(简单启发式: 响应里是否还有"登录/密码"输入框)
    login_soup = BeautifulSoup(login_resp.text, "html.parser")
    still_has_login = find_input_by_keys(login_soup, PASSWORD_KEYS) is not None
    if still_has_login:
        log("[警告] 登录响应中仍检测到密码输入框, 可能登录失败(密码错误/需要验证码)。")
        log("       请检查 debug_login_response.html, 看是否有错误提示或验证码。")
        # 不直接退出, 继续尝试抓数据页, 让用户自行判断
    else:
        log("[成功] 未检测到密码框, 疑似登录成功。")

    # 6) 抓取考勤数据页
    time.sleep(WAIT_AFTER_LOGIN)
    log("抓取考勤页: {}".format(ATTENDANCE_URL))
    try:
        att_resp = session.get(ATTENDANCE_URL, timeout=TIMEOUT, verify=VERIFY_SSL)
    except requests.exceptions.SSLError:
        att_resp = session.get(ATTENDANCE_URL, timeout=TIMEOUT, verify=False)
    except Exception as e:
        sys.exit("抓取考勤页失败: {}".format(e))

    log("考勤页状态码: {}".format(att_resp.status_code))
    att_html = att_resp.text
    save_text(os.path.join(OUTPUT_DIR, "attendance_page.html"), att_html)

    # 7) 解析表格并导出
    tables = parse_tables(att_html)
    if tables:
        log("共解析到 {} 张表格".format(len(tables)))
        # 导出 CSV
        for t in tables:
            fname = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", t["title"]) + ".csv"
            csv_path = os.path.join(OUTPUT_DIR, fname)
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                for row in t["rows"]:
                    w.writerow(row)
            log("已导出: {} ({} 行)".format(csv_path, len(t["rows"])))
        # 导出 JSON
        json_path = os.path.join(OUTPUT_DIR, "attendance_tables.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(tables, f, ensure_ascii=False, indent=2)
        log("已导出: {}".format(json_path))
    else:
        log("[提示] 页面中未解析到 <table>, 数据可能是 JS 异步加载(见 attendance_page.html)。")
        log("       如需要, 可提供 attendance_page.html 内容, 我帮你进一步分析数据接口。")

    log("完成。输出目录: {}".format(os.path.abspath(OUTPUT_DIR)))


if __name__ == "__main__":
    main()
