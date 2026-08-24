# -*- coding: utf-8 -*-
"""对比 translations/zh-CN 下的 md 笔记与网站实际收录情况"""
import os
import re
import json

disk = set()
for dirpath, dirnames, filenames in os.walk("translations/zh-CN"):
    for fn in filenames:
        if fn.endswith(".md") and fn != "LICENSE.md":
            p = os.path.join(dirpath, fn).replace(os.sep, "/")
            disk.add(p.replace("translations/zh-CN/", "", 1))

html = open("course-site/index.html", encoding="utf-8").read()
m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
data = json.loads(m.group(1))
site = set(data["docs"].keys())

print("文件夹 md 总数:", len(disk))
print("网站已收录:", len(site))
print()
print("=== 网站漏掉的 ===")
for p in sorted(disk - site):
    print(" ", p)
print()
print("=== 网站多出的（应为空）===")
for p in sorted(site - disk):
    print(" ", p)
