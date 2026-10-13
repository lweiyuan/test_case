import os
import time
import re
# 要统计的目录
basedir = "/root/weiyuan1"
filelists = []
# PATTERN_SCRIPT_NAME = r".+_.{2}_.{2}_.{3}_.{3}_.+\.py"
PATTERN_SCRIPT_NAME = r"\.py"
whitelist = ["sh", "py", "xml"]


# 遍历文件，递归遍历文件夹中的所有
def getFile(basedir):
    global filelists
    for parent, dirname, filenames, in os.walk(basedir):
        for filename in filenames:
            ext = filename.split(".")[-1]
            print(filename)
            if ext in whitelist:
                if re.match(PATTERN_SCRIPT_NAME, filename):
                    continue
                filelists.append(os.path.join(parent, filename))


# 统计一个文件的行数
def countLine(fname):
    count = 0
    comment_flag = False
    for file_line in open(fname).readlines():
        file_line = file_line.strip()
        if not comment_flag and file_line.find('"""') != -1:
            comment_flag = True
            continue
        if comment_flag and file_line.find('"""') != -1:
            comment_flag = False
            continue
        if file_line == ' ' or file_line == "\n":
            pass
        elif file_line[0:1] == "#":
            pass
        elif comment_flag:
            pass
        else:
            count += 1
    print(f"{fname} 代码行数为---------- {count}")
    return count


def file_annotation(fname):
    count_annotation = 0
    comment_flag = False
    for file_line in open(fname).readlines():
        file_line = file_line.strip()
        if file_line == ' ' or file_line == "\n":
            pass
        else:
            count_annotation += 1
    print(f"{fname} 代码行数和注释总和为：---------- {count_annotation}")
    return count_annotation


if __name__ == '__main__':
    basedir = input("请输入绝对路径:")
    startTime = time.clock()
    getFile(basedir)
    totalline = 0
    total_annotation = 0
    print(filelists)
    for filelist in filelists:
        totalline = totalline + countLine(filelist)
        total_annotation = total_annotation + file_annotation(filelist)
    print(f"total lines:{totalline}")
    print(f"文件的总代码行数：{total_annotation}")
    print(f"代码的占比为：{totalline / total_annotation}")
