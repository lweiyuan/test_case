"""
author: peibao.wang
date: 2021.02.23
description: 根据符合标准的用例Excel文件，生成所有的子类模板脚本文件
"""

import os
import time

import xlrd
import copy
import logging
from datetime import datetime

# 需要自定义修改的参数
# 必填，测试用例Excel，需要复制到当前目录下
filename = "架构融合分流测试用例-20260409.xlsx"
# 必填，作者名，用于替换脚本中的author: ****.**
author = "haibin.xu"
# 选填，模板文件，基于scripts目录的相对路径，例如：expander/simu/simu_f_01_01_001_001_qemu_excute_path_check.py
template_filename = 'nic100/linux/dpdk/rte_flow/case_leagcy/dpdk_switch_patten_template.py'
# template_filename = None
# 必填，需要生成的行号限制，注意为Excel表中的左侧行号
start_row_num = 2  # 包含行号为start_row_num的行
end_row_num = 29  # 包含行号为end_row_num的行
# sheet_name, 表格名称
sheet_name_list = ["测试用例", "Worksheet"]
# 行长度
line_length = 120
new_dir_num = 0
new_script_num = 0
exist_script_num = 0
non_auto_case_num = 0
new_dir_list = []
new_script_list = []
exist_script_list = []
non_auto_script_list = []

script_steps_list = []
script_steps_result_list = []

# 设置log输出级别
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(funcName)s %(lineno)d [%(levelname)s] %(message)s')


# 读取用例Excel文件，获取对应的信息，包括脚本名称，用例编号，测试对象，测试步骤等信息
def get_case_info() -> list:
    try:
        workbook = xlrd.open_workbook(filename)
        logging.info('Excel文件：{}，打开正常'.format(filename))
        for i, sheet_name in enumerate(sheet_name_list):
            try:
                table = workbook.sheet_by_name(sheet_name)
                logging.info('Excel文件：{}，的sheet页：{}，打开正常'.format(filename, sheet_name))
                break
            except Exception as e:
                logging.exception("打开测试用例Excel文件[{}]的sheet页[{}]异常:\n{}".format(filename, sheet_name, e))
                if i == (len(sheet_name_list) - 1):
                    logging.error('Excel文件：{}，的sheet列表：{}，中任一项都未成功打开，不再继续解析'.format(
                        filename, sheet_name_list))
                    return []
    except Exception as e:
        logging.exception("打开用例Excel文件异常:\n{}".format(e))
        return []

    # 处理读取的文件信息
    # 找到用例开始的一行
    row_index = 0
    while True:
        if table.cell(row_index, 0).value in ["测试编号", "脚本名称", "用例标题", "所属产品"]:
            logging.info("找到用例表头行，解析用例标题对应索引")
            break
        row_index += 1
    # 将用例标题行解析成对应的索引
    # 需要用到的标题名称
    case_num_index = 0       # 测试编号
    case_name_index = 1      # 脚本名称
    case_title_index = 2     # 用例标题
    test_object_index = 3    # 测试对象
    check_point_index = 4    # 检查点
    steps_index = 5          # 检查步骤
    test_platform_index = 6  # 测试平台
    case_author_index = 7          # 作者
    test_platform_auto_index = 8  # 测试平台是否实现自动化
    step_result_index = 9    # 预期结果
    case_test_condition_index = 10  # 测试场景

    col_index = 0
    while col_index < table.ncols:
        title = table.cell(row_index, col_index).value
        if title == "测试编号":
            case_num_index = col_index
        elif title == "脚本名称":
            case_name_index = col_index
        elif title == "用例标题":
            case_title_index = col_index
        elif title == "需求点/测试对象":
            test_object_index = col_index
        elif title == "检查项/测试点":
            check_point_index = col_index
        elif title == "测试步骤":
            steps_index = col_index
        elif title == "物理环境":
            test_platform_index = col_index
        elif title == "作者":
            case_author_index = col_index
        elif title == "测试平台实现自动化":
            test_platform_auto_index = col_index
        elif title == "预期结果":
            step_result_index = col_index
        elif title == "测试场景":
            case_test_condition_index = col_index

        col_index += 1
    # 打印不同标题对应的索引
    # 读取用例的必要信息
    row_index += 1
    case_info_l = []
    while row_index < table.nrows and row_index <= (end_row_num - 1):
        if row_index < start_row_num - 1:
            row_index += 1
            continue

        case_test_platform_auto = table.cell(row_index, test_platform_auto_index).value
        case_num = table.cell(row_index, case_num_index).value
        case_name = table.cell(row_index, case_name_index).value
        case_title = table.cell(row_index, case_title_index).value
        case_author = table.cell(row_index, case_author_index).value
        case_test_condition = table.cell(row_index, case_test_condition_index).value

        # 处理case_title过长的问题
        if '\r\n' in case_test_condition:
            cm = '\r\n'
        elif '\r' in case_test_condition:
            cm = '\r'
        else:
            cm = '\n'
        case_test_condition_list = case_test_condition.split(cm)
        for index in range(len(case_test_condition_list)):
            test_cd = case_test_condition_list[index]
            test_cd_copy_list = []
            while len(test_cd) > line_length:  # 如果长度超过70，则插入换行符
                test_cd_copy_list.append(test_cd[:line_length].strip())
                test_cd = test_cd[line_length:]
            test_cd_copy_list.append(test_cd.strip())
            case_test_condition_list[index] = "\n                  ".join(test_cd_copy_list)
        case_test_condition = "\n               ".join(case_test_condition_list)

        # 处理case_title过长的问题
        case_title_list = []
        while len(case_title) > line_length:  # 如果长度超过70，插入一个换行符
            case_title_list.append(case_title[:line_length].strip())
            case_title = case_title[line_length:]
        case_title_list.append(case_title.strip())
        case_title = "\n   ".join(case_title_list)
        # test_object = table.cell(row_index, test_object_index).value
        # 检查点有可能超出长度限制，中文最多放73个，每70个长度，插入一个换行符
        check_point = table.cell(row_index, check_point_index).value
        check_point_list = []
        while len(check_point) > line_length:  # 如果长度超过70，插入一个换行符
            check_point_list.append(check_point[:line_length].strip())
            check_point = check_point[line_length:]
        check_point_list.append(check_point.strip())
        check_point = "\n   ".join(check_point_list)

        steps = table.cell(row_index, steps_index).value
        test_platform = table.cell(row_index, test_platform_index).value
        # steps单行可能超出长度限制，中文最多只能放73个，所以每70个长度，插入一个换行符
        steps_list = steps.split("\n")
        global script_steps_list
        sub_script_steps_list = copy.deepcopy(steps_list)
        script_steps_list.append(sub_script_steps_list)
        for index in range(len(steps_list)):
            step = steps_list[index]
            step_copy_list = []
            while len(step) > line_length:  # 如果长度超过70，则插入换行符
                step_copy_list.append(step[:line_length].strip())
                step = step[line_length:]
            step_copy_list.append(step.strip())
            steps_list[index] = "\n   ".join(step_copy_list)
        steps = "\n".join(steps_list)

        # steps expect result单行可能超出长度限制，中文最多只能放73个，所以每70个长度，插入一个换行符
        case_steps_result = table.cell(row_index, step_result_index).value
        steps_result_list = case_steps_result.split("\n")
        global script_steps_result_list
        sub_script_steps_result_list = copy.deepcopy(steps_result_list)
        script_steps_result_list.append(sub_script_steps_result_list)
        for index in range(len(steps_result_list)):
            step_result = steps_result_list[index]
            step_copy_list = []
            while len(step_result) > line_length:  # 如果长度超过70，则插入换行符
                step_copy_list.append(step_result[:line_length].strip())
                step_result = step_result[line_length:]
            step_copy_list.append(step_result.strip())
            steps_result_list[index] = "\n   ".join(step_copy_list)
        case_steps_result = "\n".join(steps_result_list)

        # if all([case_num, case_name, case_title, check_point, steps, test_platform]):
        case_info_l.append({
            "case_num": case_num,
            "case_name": case_name,
            "case_title": case_title,
            "case_author": case_author,
            "check_point": check_point,
            "steps": steps,
            "steps_expect_result": case_steps_result,
            "author": author,
            "test_platform": test_platform,
            "test_platform_automation": case_test_platform_auto,
            "test_condition": case_test_condition
        })

        row_index += 1

    return case_info_l


def write_template_file(case_info_dict: dict, case_idx: int) -> None:
    global new_script_num, new_dir_num, exist_script_num, new_script_list, new_dir_list, exist_script_list,\
        non_auto_case_num, non_auto_script_list, script_steps_list, script_steps_result_list, line_length
    # 首先回退到scripts目录下
    scripts_dir = os.path.abspath(__file__)
    while True:
        if scripts_dir.endswith('test/esat/nic100/scripts') or scripts_dir.endswith('test\\esat\\nic100\\scripts'):
            break
        scripts_dir = os.path.dirname(scripts_dir)

    tf_name = ""
    if template_filename:
        tf_name = os.path.join(scripts_dir, template_filename)

    script_name = os.path.join(scripts_dir, case_info_dict['case_name'])

    auto_test = case_info_dict.get('test_platform_automation')
    if 'SNPN' == auto_test:
        logging.warning('当前测试用例[测试平台实现自动化]: {}, 为手动测试用例，不再创建脚本'.format(auto_test))
        non_auto_case_num += 1
        non_auto_script_list.append(script_name)
        return

    tmp_dir = os.path.dirname(script_name)
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
        new_dir_list.append(tmp_dir)
        new_dir_num += 1

    cur_script_steps_list = script_steps_list[case_idx]
    cur_script_steps_result_list = script_steps_result_list[case_idx]

    # 区分是否有指定模板
    if not os.path.exists(script_name):
        with open(script_name, mode="w", encoding="utf-8") as f:
            # 写入文件头注释信息
            f.write("#!/usr/bin/env python3\n# -*- encoding=utf8 -*-\n\n")
            f.write('"""\n')
            f.write("case author:   {}\n".format(case_info_dict["case_author"]))
            f.write("script author: {}\n".format(author))
            f.write("date:          {}\n".format(datetime.now().strftime("%Y.%m.%d")))
            f.write("description:\n\n")
            f.write("case number:   {}\n".format(case_info_dict["case_num"]))
            f.write("case title:    {}\n".format(case_info_dict["case_title"]))
            # f.write("test object:   {}\n".format(case_info_dict["test_object"]))
            f.write("check point:   {}\n".format(case_info_dict["check_point"]))
            f.write("test condition:{}\n".format(case_info_dict["test_condition"])
                    if case_info_dict.get("test_condition") else "test condition:\n")
            f.write("test platform: {}\n\n".format(case_info_dict["test_platform"])
                    if case_info_dict.get("test_platform") else "test platform:\n\n")
            f.write("@steps:\n")
            f.write("{}\n\n".format(case_info_dict["steps"]))
            f.write("@steps expect result:\n")
            f.write("{}\n".format(case_info_dict["steps_expect_result"]))
            f.write("\n@changelog:\n\n")
            f.write('"""\n')
            if not tf_name:  # 如果没有指定文件，写入默认的格式内容
                f.write("import add_syspath\n\n")

                f.write("from scripts.script_libs import log\n")
                f.write("from scripts.script_libs.script_base import ScriptBase\n")
                f.write("from scripts.script_libs.common_operation import CommonOperation\n")
                f.write('\n\n')

                f.write("class Script(ScriptBase):\n")
                f.write("    @classmethod\n")
                f.write("    def set_parameters(cls) -> None:\n")
                f.write('        """\n')
                f.write("        author: {}\n".format(author))
                f.write("        date: {}\n".format(datetime.now().strftime("%Y.%m.%d")))
                f.write("        descriptor: 设置需要调用的变量\n")
                f.write('        :return: 无返回值\n        """\n')
                f.write('        super().set_parameters()\n\n')
                f.write("    @classmethod\n")
                f.write("    def check_own_environment(cls) -> None:\n")
                f.write('        """\n')
                f.write("        author: {}\n".format(author))
                f.write("        date: {}\n".format(datetime.now().strftime("%Y.%m.%d")))
                f.write("        descriptor: 检测当前脚本运行所需的局部环境是否具备，该方法只检测，不报bug,\n")
                f.write("                    函数内需要设定类变量local_enviroment_enabled的值，\n")
                f.write("                    局部环境检测正常，类变量local_enviroment_enabled设置为True\n")
                f.write('        :return: 无返回值\n        """\n')
                f.write('        super().check_own_environment()\n')
                f.write("        log.info('脚本尚未实现，暂时跳过')\n")
                f.write('        cls.own_environment_enabled = False\n\n')
                f.write("    @classmethod\n")
                f.write("    def prepare(cls) -> None:\n")
                f.write('        """\n')
                f.write("        author: {}\n".format(author))
                f.write("        date: {}\n".format(datetime.now().strftime("%Y.%m.%d")))
                f.write("        descriptor: 准备环境\n")
                f.write('        :return: 无返回值\n        """\n')
                f.write('        super().prepare()\n\n')
                f.write("    @classmethod\n")
                f.write("    def do(cls) -> None:\n")
                f.write('        """\n')
                f.write("        author: {}\n".format(author))
                f.write("        date: {}\n".format(datetime.now().strftime("%Y.%m.%d")))
                f.write("        descriptor: 执行测试环境\n")
                f.write('        :return: 无返回值\n        """\n')
                f.write('        super().do()\n\n')
                for sub_step, sub_step_result in zip(cur_script_steps_list, cur_script_steps_result_list):
                    p_str_list = ["        CommonOperation.concat_test_steps(\n"]
                    tmp_p_str = "            'step{}; expect result: {}')\n\n".format(sub_step, sub_step_result)
                    space_str = ' ' * 12
                    while len(tmp_p_str) > line_length:  # 如果长度超过70，则插入换行符
                        p_str_list.append(tmp_p_str[:line_length] + '\'\n')
                        tmp_p_str = space_str + '\'' + tmp_p_str[line_length:]
                    p_str_list.append(tmp_p_str)
                    for sub_str in p_str_list:
                        f.write(sub_str)
                f.write("    @classmethod\n")
                f.write("    def post(cls) -> None:\n")
                f.write('        """\n')
                f.write("        author: {}\n".format(author))
                f.write("        date: {}\n".format(datetime.now().strftime("%Y.%m.%d")))
                f.write("        descriptor: 整理环境及结果信息相关信息\n")
                f.write('        :return: 无返回值\n        """\n')
                f.write('        super().post()\n\n\n')
                f.write("def main() -> None:\n    Script.run()\n\n\n")
                f.write('if __name__ == "__main__":\n    main()\n')
            else:  # 如果有模板文件，逐行读取模板文件，将对应内容替换
                with open(tf_name, mode="r", encoding="utf8") as tf:
                    contents = tf.readlines()
                    # 从第一个import/from开始
                    start_write = False
                    for content in contents:
                        if content.startswith("import ") or content.startswith("from "):
                            start_write = True
                        if start_write:
                            if "        author:" in content:
                                content = "        author: {}\n".format(author)
                            elif "        date:" in content:
                                content = "        date: {}\n".format(datetime.now().strftime("%Y.%m.%d"))
                            f.write(content)

        logging.info("创建脚本文件：{}，成功".format(script_name))
        new_script_num += 1
        new_script_list.append(script_name)
    else:
        logging.info("存在脚本文件：{}，不再创建".format(script_name))
        exist_script_num += 1
        exist_script_list.append(script_name)


if __name__ == "__main__":
    case_info_list = get_case_info()
    for i, case_info in enumerate(case_info_list):
        write_template_file(case_info, i)

    logging.info('本次操作执行测试用例数：{}'.format(end_row_num - start_row_num + 1))
    logging.info('新创建的目录个数：{}，目录列表：\n{}\n'.format(new_dir_num, '\n'.join(new_dir_list)))
    logging.info('已存在的脚本个数：{}，脚本文件列表：\n{}\n'.format(exist_script_num, '\n'.join(exist_script_list)))
    logging.info('新创建的脚本个数：{}，脚本文件列表：\n{}\n'.format(new_script_num, '\n'.join(new_script_list)))
