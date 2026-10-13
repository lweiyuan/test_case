#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
author: junfeng.he
date  : 2021.3.6
description:
    该脚本用于统计脚本数量，代码行数 [必须在linux下执行]
    ******使用方法：必须放在/home/test/ps3test/pms/pmxxx路径执行******
    ******注意事项：修改git log统计时间******
    执行方法：
        python3 countscripts_owner.py
        python3 countscripts_owner.py ./../../pcie_switch

        update:
        在代码机10.22.67.4:/home/测试YF/changjsh/debug-branch/ps3/test/esat/scripts/system_test/mgr/utils/group_tools下执行
"""

import os
import sys
import subprocess
import platform

# os.chdir("./ps3/test/esat/scripts/system_test/mgr/")
os.chdir("../../nic100/")
print(os.getcwd())


def find_all_file(base):
    for root, ds, fs in os.walk(base):
        for f in fs:
            fullname = os.path.join(root, f)
            yield fullname


def main():
    if len(sys.argv) >= 2:
        base = sys.argv[1]
    else:
        # base = './../' # expander目录下
        # base = './../../pcie_switch' # pcies_witch目录下
        base = './'  # mgr目录下
    base = os.path.abspath(base)
    system = platform.system()
    if system == "Windows":
        print("OS is Windows!")
    else:
        print("OS is Linux!")

    if not os.path.exists(base):
        print("base path:{},not exists!!".format(base))
        return
    print("base path:{}".format(base))

    commit = []
    commit_pull = "git pull"
    # --------修改git log统计时间-------
    commit_cmdend = "git log --until ='2025-12-31' |grep 'commit' |head -1"
    commit_cmdstart = "git log --until ='2025-01-01' |grep 'commit' |head -1"

    status, res = subprocess.getstatusoutput(commit_pull)
    if status != 0:
        print("error -> status:{},res:{}".format(status, res))
    status, res = subprocess.getstatusoutput(commit_cmdend)
    if status != 0:
        print("error -> status:{},res:{}".format(status, res))
    else:
        # commit_start = res.split()[1]
        commit.append(res.split()[1])
    status, res = subprocess.getstatusoutput(commit_cmdstart)
    if status != 0:
        print("error -> status:{},res:{}".format(status, res))
    else:
        # commit_start = res.split()[1]
        commit.append(res.split()[1])
    print("commits:{}".format(commit))
    file_map = {}  # .py文件dict
    code_map = {}  # code dict
    base_code_map = {}  # script_base dict
    scripts_num = [0, 0]
    code_lines = [0, 0]
    mark_lines = [0, 0]
    base_code_lines = [0, 0]
    base_mark_lines = [0, 0]
    scripts_ignore = []

    for j in range(len(commit)):
        # 回退版本
        git_reset = "git reset --hard " + commit[j]
        status, res = subprocess.getstatusoutput(git_reset)
        if status != 0:
            print("error -> status:{},res:{}".format(status, res))
        else:
            print('git reset success! %s', commit[j])

        for i in find_all_file(base):
            if i.endswith('.py') and 'script_base' not in i:
                if '_f_' in i or '_r_' in i or '_sta_' in i or '_p_' in i or '_c_' in i or '_str_' in i:
                    if ' ' in i:
                        continue
                    cmd = "cat " + i + " | grep 'author:' | head -1"
                    status, res = subprocess.getstatusoutput(cmd)
                    if status != 0:
                        print("error -> status:{},res:{}".format(status, res))
                    else:
                        if res == ' ' or res is None:
                            res = 'anonyn'
                        res = res.replace("\n", "").replace(" ", "")
                        if res in file_map.keys():
                            file_map[res][j] += 1
                        else:
                            # print('i:{}'.format(i))
                            if j > 0:
                                file_map[res] = {0: 0, 1: 1}
                            file_map[res] = {0: 1, 1: 0}
        # print("格式说明-> 脚本：[统计commit_end，统计commit_start]")
        # print("commit:{},脚本数量统计结果:\n{}".format(commit[j], file_map))

        for key in file_map.keys():
            scripts_num[j] += file_map[key][j]  # ???

        for i in find_all_file(base):
            if i.endswith('.py'):
                if ' ' in i:
                    continue
                cmd = "cat " + i + " | grep 'author:' | head -1"
                try:
                    status, res = subprocess.getstatusoutput(cmd)
                except Exception as e:
                    print(f'scripts:{i};;exception:{e}')
                    continue
                if status != 0:
                    print("error -> status:{},res:{}".format(status, res))
                else:
                    res = res.replace("\n", "").replace(" ", "")
                    if res == ' ' or res is None:
                        res = 'anonyn'
                    cmd = "cat " + i + " | wc -l"
                    status, total = subprocess.getstatusoutput(cmd)
                    if status != 0:
                        total = 0
                    cmd = "cat " + i + " | grep '#' | wc -l"
                    status, mark = subprocess.getstatusoutput(cmd)
                    if status != 0:
                        mark = 0

                    if res in code_map.keys():
                        code_map[res][2 * j] += int(total)
                        code_map[res][2 * j + 1] += int(mark)
                    else:
                        # print ('res:{}'.format(res))
                        if j > 0:
                            code_map[res] = {0: 0, 1: 0, 2: int(total), 3: int(mark)}  # 第一个commit统计没有，置0
                        code_map[res] = {0: int(total), 1: int(mark), 2: 0, 3: 0}

                    if 'script_base' in i:
                        if res in base_code_map.keys():
                            base_code_map[res][2 * j] += int(total)
                            base_code_map[res][2 * j + 1] += int(mark)
                        else:
                            if j > 0:
                                base_code_map[res] = {0: 0, 1: 0, 2: int(total), 3: int(mark)}  # 第一个commit统计没有，置0
                            base_code_map[res] = {0: int(total), 1: int(mark), 2: 0, 3: 0}
        # print("格式说明-> 作者：[commit_end总行数，commit_end注释行数,commit_start总行数，commit_start注释行数]")
        # print("代码行数统计结果:\n{}".format(code_map))
        # print("基类代码行数统计结果:\n{}".format(base_code_map))

        for key in code_map.keys():
            code_lines[j] += code_map[key][2 * j]
            mark_lines[j] += code_map[key][2 * j + 1]

        for key in base_code_map.keys():
            base_code_lines[j] += base_code_map[key][2 * j]
            base_mark_lines[j] += base_code_map[key][2 * j + 1]

    print("脚本总数[commit_end,commit_start]:{}".format(scripts_num))
    print("代码总行数[commit_end,commit_start]:{}".format(code_lines))
    print("注释总行数[commit_end,commit_start]:{}".format(mark_lines))
    print("基类代码总行数[commit_end,commit_start]:{}".format(base_code_lines))
    print("基类注释总行数[commit_end,commit_start]:{}".format(base_mark_lines))
    print("------------------------------------------")
    print("------------------------------------------")
    print("格式说明-> 脚本：[统计commit_end，统计commit_start]")
    print("commit:{},脚本数量统计结果:\n{}".format(commit, file_map))
    print("格式说明-> 作者：[commit_end总行数，commit_end注释行数,commit_start总行数，commit_start注释行数]")
    print("代码行数统计结果:\n{}".format(code_map))
    print("基类代码行数统计结果:\n{}".format(base_code_map))
    tmp = scripts_num[0] - scripts_num[1]
    print("脚本总数[commitend-->commitstart]:{}".format(tmp))
    tmp = code_lines[0] - code_lines[1]
    print("代码总行数[commitend-->commitstart]:{}".format(tmp))
    tmp = mark_lines[0] - mark_lines[1]
    print("注释总行数[commitend-->commitstart]:{}".format(tmp))
    tmp = base_code_lines[0] - base_code_lines[1]
    print("基类代码总行数[commitend-->commitstart]:{}".format(tmp))
    tmp = base_mark_lines[0] - base_mark_lines[1]
    print("基类注释总行数[commitend-->commitstart]:{}".format(tmp))
    status, res = subprocess.getstatusoutput(commit_pull)
    if status != 0:
        print("error -> status:{},res:{}".format(status, res))


if __name__ == '__main__':
    main()
