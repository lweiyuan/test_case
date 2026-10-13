# -*- encoding=utf8 -*-
"""
author: luyafei
date  : 2020.05.05
description: 用于记录程序中使用的常量信息
"""
import os


# test/esat, test/esat/framework、test/esat/conf, test/esat/scripts目录的绝对路径
ESAT_DIRETCORY = os.path.dirname(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
ESAT_PATH_OUT_PUTS_PATH = os.path.join(ESAT_DIRETCORY, 'outputs')
ESAT_PATH_OUT_PUTS_SCRIPTS_PATH = os.path.join(ESAT_DIRETCORY, 'outputs', 'scripts')
FRAMEWORK_DIRECTORY = os.path.join(ESAT_DIRETCORY, 'framework')
ENV_CONF_DIRECTORY = os.path.join(FRAMEWORK_DIRECTORY, 'env_conf')
CONF_DIRECTORY = os.path.join(ESAT_DIRETCORY, 'conf')
RUN_ALL_TEST_LOG_FILE = os.path.join(ESAT_DIRETCORY, 'outputs', 'framework', 'run_all_test_ps3_{}.log')
OUTPUTS_DIRECTORY_PATH = os.path.join(ESAT_DIRETCORY, 'outputs', 'framework')
SCRIPTS_DIRECTORY = os.path.join(ESAT_DIRETCORY, 'scripts')
"""-----------------------------------测试脚本返回给测试框架的信息-------------------------"""
# 测试脚本中的问题信息
BUG = "bug"
# 问题标题
BUG_TITLE = "title"
# 问题类型
BUG_TYPE = "type"
# 问题属于的测试对象
BUG_OBJECT = "object"
# 问题属于的测试模块
BUG_MODULE = "module"
# 使用的测试工具
BUG_TOOL = "tool"
# 测试前置条件
BUG_PRECONDITION = "precondition"
# 测试步骤
BUG_STEPS = "steps"
# 默认值
DEFAULT_SIMULATOR_IOC_CORE_BUG_TITLE = "模拟平台ioc端出现Core"
DEFAULT_SIMULATOR_HOST_CRASH_BUG_TITLE = "模拟平台host端出现Crash"
DEFAULT_SIMULATOR_IOC_CRASH_BUG_TITLE = "模拟平台ioc端出现Crash"
DEFAULT_SIMULATOR_RTEMS_SOC_CORE_BUG_TITLE = "模拟平台RTEMS soc端出现Core"

DEFAULT_CORE_BUG_EXPECT = "不出现Core"
DEFAULT_CORE_BUG_RESULT = "出现Core文件"

DEFAULT_CRASH_BUG_EXPECT = "不出现Crash"
DEFAULT_CRASH_BUG_RESULT = "出现Crash文件"

DEFAULT_CORE_CRASH_BUG_TYPE = "功能问题"
DEFAULT_CORE_CRASH_BUG_EXPECT = "不出现Core、Crash"
DEFAULT_CORE_CRASH_BUG_RESULT = "出现Core、Crash文件"

# 超时BUG信息
DEFAULT_TIMEOUT_BUG_TITLE = "脚本运行超出预期时间"
DEFAULT_TIMEOUT_BUG_TYPE = "timeOut"
DEFAULT_TIMEOUT_BUG_STEPS = "步骤：\n执行测试脚本;\n测试结果：脚本运行超出预期时间\n预期结果：脚本在预期时间内执行完成"

# 框架运行出错BUG信息
DEFAULT_FRAMEWORK_BUG_TITLE = '框架运行出错'
DEFAULT_FRAMEWORK_BUG_TYPE = '稳定性问题'
DEFAULT_FRAMEWORK_BUG_STEPS = '步骤：\n1.配置参数获取；2.环境部署（如果需要部署环境）；3.脚本测试；4.测试数据收集汇总\n测试结果：' \
                              '框架运行出错\n预期结果：框架正常运行'

"""--------------------------------------问题的描述信息-----------------------------------"""
# 问题等级
BUG_SEVERITY_STR = "bug_severity"
# 测试脚本中主方法信息
METHODS = "methods"
# pre方法执行时长
PRE_DURATION = "pre_duration"
# do方法执行时长
DO_DURATION = "do_duration"
# post方法执行时长
POST_DURATION = "post_duration"
FM_IOPS = "iops"
FM_BW = "bw"
FM_RESP_TIME = "resp_time"
FM_RAW_PERF_DATA = "raw_perf_data"

# 测试问题结果
BUG_RESULT = "result"
# 预期结果
BUG_EXPECT = "expect"
# 脚本测试结果
TEST_RESULT = "test_result"
# 脚本执行清理环境结果
POST_RESULT = "post_result"
# core、crash检查结果
CORE_CRASH_RESULT = "core_crash_result"
# 脚本cli命令最大执行时间
CLI_RESULT_MAX_TIME = "cli_result_max_time"
TEST_PLATFORM = "test_platform"

# 脚本返回结果
# 脚本测试成功
RETURN_CODE_SUCCESS = 0
# 脚本测试环境不满足
RETURN_CODE_SKIP = 2
# 脚本测试失败
RETURN_CODE_FAIL = 1
# cli命令执行失败
RETURN_CODE_EXCEPTION = 6
# 脚本运行超时
RETURN_CODE_TIMEOUT = 124

"""----------------------------------------Bug类中属性信息-----------------------------------"""
# 问题类型名称
BUG_ATTR_BUG_TITLE = "title"
# 问题类型名称
BUG_ATTR_TYPE_NAME = "type_name"
# 测试对象
BUG_ATTR_CATEGORY = "test_category"
# 测试工具
BUG_ATTR_TOOL = "test_tool"
# 前置条件
BUG_ATTR_PRECONDITION = "precondition"
# 测试步骤
BUG_ATTR_STEPS = "steps"
# 问题发生频率
BUG_ATTR_FREQUENCY = "frequency"
# 测试用例标题
BUG_ATTR_CASE_ID = "case_id"
# 测试用例版本
BUG_ATTR_CASE_VERSION = "case_version"
# 测试脚本
BUG_ATTR_SCRIPT_NAME = "script_name"
# 测试模块ID
BUG_ATTR_MODULE = "module"
# 测试模块名称
BUG_ATTR_MODULE_NAME = "module_name"
# 问题的提交状态
BUG_ATTR_STATUS = "status"
# 问题提交人
BUG_ATTR_OPENED = "opened_by"
# 问题所属产品
BUG_ATTR_PRODUCT = "product"
# 问题分支/平台
BUG_ATTR_BRANCH = "branch"
# 问题影响版本
BUG_ATTR_OPENED_BUILD = "opened_build"
# 问题指派给
BUG_ATTR_ASSIGNED_TO = "assigned_to"
# 问题截止日期
BUG_ATTR_DEADLINE = "deadline"
# 问题的严重程度
BUG_ATTR_SEVERITY = "severity"
# 问题优先级
BUG_ATTR_PRIORITY = "priority"
# 问题日志在日志服务器的存放位置
BUG_ATTR_LOG_PATH = "log_path"
# 测试环境信息所在对象
BUG_ATTR_ENV = "test_env_object"
# 测试目标和测试任务信息所在对象
BUG_ATTR_CASE = "test_case_object"

# 默认值
DEFAULT_FREQUENCY = "always"
DEFAULT_STATUS = "draft"
DEFAULT_ASSIGNED_TO = ""
DEFAULT_SEVERITY = 2
DEFAULT_PRIORITY = 2

# 允许的最大线程数
MAX_ALLOW_THREADS = 100

"""--------------------------测试报告中的概要信息命名---------------------------"""
# 测试任务名称
REPORT_ATTR_TASK_NAME = "task_name"
# 代码分支
REPORT_ATTR_GIT_BRANCH = "git_branch"
# 测试安装包
REPORT_ATTR_PACKAGE_PATH = "package_path"
# 测试用例路径
REPORT_ATTR_CASE_PATH = "case_path"
# 测试用例等级
REPORT_ATTR_CASE_LEVEL = "case_level"
# 测试总时长
REPORT_ATTR_TOTAL_DURATION = "total_duration"
# 测试成功的脚本数据
REPORT_ATTR_PASS_NUM = "pass_num"
# 测试失败的脚本数目
REPORT_ATTR_FAIL_NUM = "fail_num"
# 跳过的测试测试脚本数据
REPORT_ATTR_SKIP_NUM = "skip_num"
# 不存在测试测试脚本数据
REPORT_ATTR_NOT_EXIST_NUM = "not_exist_num"
# 测试主机ip
REPORT_ATTR_HOST_IP = "host_ip"
# 测试ioc的ip
REPORT_ATTR_IOC_IP = "ioc_ip"
# 测试系统
REPORT_ATTR_HOST_OS = "host_os"
# 测试平台
REPORT_ATTR_TEST_PLATFORM = "test_platform"

"""-----------------------------测试结果Result类中属性信息的命名----------------"""
# 测试用例信息
RESULT_ATTR_TEST_CASE_OBJECT = "test_case_object"
# 脚本测试结果
RESULT_ATTR_SCRIPT_RESULT = "script_result"
# 脚本开始执行的时间
RESULT_ATTR_START_TIME = "start_time"
# 脚本执行时长
RESULT_ATTR_SCRIPT_DURATION = "script_duration"
# 脚本中主要方法执行时间信息对象
RESULT_ATTR_METHODS_TIME = "methods_time"

"""-------------------bug list columns即在问题列表excel表格中显示的列名称----------------"""
# bug标题
BUG_COL_BUG_TITLE = "title"
# bug类型
BUG_COL_BUG_TYPE = "type"
# 测试对象
BUG_COL_TEST_TYPE = "testType"
# 测试工具
BUG_COL_TEST_TOOL = "testTool"
# 测试前置条件
BUG_COL_PRECONDITION = "precondition"
# 测试步骤
BUG_COL_STEPS = "steps"
# 出现频率
BUG_COL_FREQUENCY = "frequency"
# 状态
BUG_COL_STATUS = "status"
# 测试问题指派给
BUG_COL_ASSIGNED_TO = "assignedTo"
# 测试问题截止日期
BUG_COL_DEADLINE = "deadline"
# 严重等级
BUG_COL_SEVERITY = "severity"
# 解决优先级
BUG_COL_PRIORITY = "pri"
# 问题日志在日志服务器上的路径
BUG_COL_LOG_PATH = "logPath"
# 用例名称
BUG_COL_CASE_ID = "case"
# 用例版本
BUG_COL_CASE_VERSION = "caseVersion"
# 测试脚本
BUG_COL_TEST_SCRIPT = "script"
# 分支平台id
BUG_COL_BRANCH_ID = "branch"
# 测试模块
BUG_COL_MODULE_ID = "module"
# 测试模块
BUG_COL_MODULE_NAME = "moduleName"
# 测试项目ID
BUG_COL_PROJECT_ID = "project"
# 测试分支
BUG_COL_GIT_BRANCH_ID = "gitBranch"
# 测试分支版本
BUG_COL_GIT_BRANCH_VERSION = "bitBranchVersion"
# 测试任务ID
BUG_COL_TASK_ID = "testTask"
# 测试任务名称
BUG_COL_TASK_NAME = "testTaskName"
# 测试问题影响版本
BUG_COL_OPENED_BUILD = "openedBuild"
# 问题提交人
BUG_COL_OPENED_BY = "openedBy"
# 测试阶段
BUG_COL_TEST_PHASE = "testPhase"
# 测试产品
BUG_COL_PRODUCT_ID = "product"
# host宿主机所在服务器IP
BUG_COL_HOST_IP = "hostIp"
# host节点所在服务器IP
BUG_COL_HOST_QEMU_IP = "hostNodeIp"
# IOC所在机器IP
BUG_COL_IOC_IP = "iocIp"
# IOC节点所在机器IP
BUG_COL_IOC_QEMU_IP = "iocNodeIp"
# 测试主机操作系统
BUG_COL_HOST_OS = "os"
# CPU架构
BUG_COL_CPU_ARCHITECTURE = "cpuArchitecture"
# 背板
BUG_COL_BACKPLANE = "backplane"
# 测试平台
BUG_COL_PLATFORM = "platform"
BUG_COL_PLATFORM_INFO = "testPlatformInfo"

"""---------------result list columns即在结果列表excel表格中显示的列名称--------------------"""
# 测试用例ID
RESULT_COL_CASE_ID = "caseId"
# 测试用例版本
RESULT_COL_CASE_VERSION = "caseVersion"
# 用例名称
RESULT_COL_CASE_TITLE = "caseTitle"
# 脚本路径
RESULT_COL_SCRIPT = "script"
# 脚本测试结果
RESULT_COL_SCRIPT_RESULT = "result"
# 脚本开始执行时间
RESULT_COL_SCRIPT_START_TIME = "startTime"
# 脚本执行时长
RESULT_COL_SCRIPT_DURATION = "duration(s)"
# 脚本中pre方法执行时长
RESULT_COL_PRE_DURATION = "preDuration(s)"
# 脚本中do方法执行时长
RESULT_COL_DO_DURATION = "doDuration(s)"
# 脚本中post方法执行时长
RESULT_COL_POST_DURATION = "postDuration(s)"
# 提交人
RESULT_COL_OPENED_BY = "openedBy"
# 当前脚本测试前与测试后的内存占用差值
RESULT_COL_MEMORY_DELTA = "memoryDelta(Byte)"
# 当前脚本测试期间iops统计数据
RESULT_COL_IOPS = "iops"
# 当前脚本测试期间带宽统计数据
RESULT_COL_BW = "bw(MB/s)"
# 当前脚本测试期间延迟统计数据
RESULT_COL_RESP_TIME = "respTime(msec)"
# 当前脚本测试期间性能原始数据
RESULT_COL_RAW_PERF_DATA = "rawPerfData"
# 脚本中pre方法执行时长
RESULT_COL_CLI_RESULT_MAX_TIME = "cli_result_max_time(s)"

RESULT_TEST_PLATFORM = "test_platform"
RESULT_TEST_PLATFORM_INFO = "test_platform_info"

""" -------------------------------excel文件相关信息-----------------------------------"""
# 问题excel文件名称中的关键字
BUG_EXCEL_KEY = "bugs"
# 结果excel文件名称中的关键字
RESULT_EXCEL_KEY = "results"
RESULT_JOB_KEY = "job_info"
ENV_PARAM_FROM_ZENTAO = "parameters_from_zentao"
ENV_DEBUG_MODE = "debug_mode"
# 测试脚本日志文件夹名称
TEST_SCRIPT_LOG_DIR = "test_script_logs"
EXCEL_SUFFIX_NAME = ".xlsx"
# 问题excel文件名称的后缀
BUG_EXCEL_SUFFIX = "_bugs.xlsx"
# 结果excel文件名称的后缀
RESULT_EXCEL_SUFFIX = "_results.xlsx"
# 测试报告相关的问题excel文件名称后缀
REPORT_BUG_EXCEL_SUFFIX = "_report_bug.xlsx"
# 测试报告相关的问题excel文件中sheet名称
REPORT_BUG_SHEET = "report bug"
# 测试报告excel文件名称后缀
REPORT_EXCEL_SUFFIX = "_report.xlsx"
# excel表格的列宽度
EXCEL_COL_WIDTH = 13
# 测试报告的sheet名称
REPORT_SHEET = "test report"
# 问题列表文件的sheet名称
BUG_SHEET = "bug list"
# 结果列表文件的sheet名称
RESULT_SHEET = "result list"
# 测试报告存储的文件夹名称
REPORT_FOLDER_NAME = "reports"
# 单元格的填充方式
CELL_FILL_TYPE = "solid"
# 单元格的颜色
CELL_COLOR = "BCEE68"

"""-------------------------------测试报告文件中的信息-----------------------------"""
# 测试任务名称
REPORT_COL_TASK_NAME = "testTaskName"
# 测试分支
REPORT_COL_GIT_BRANCH_ID = "gitBranch"
# 测试安装包
REPORT_COL_INSTALL_PACKAGE = "installPackage"
# 测试用例文件路径
REPORT_COL_CASE_LIST_PATH = "casePath"
# 测试总时长
REPORT_COL_TOTAL_DURATION = "totalDuration"
# 脚本测试结果为pass
REPORT_COL_SCRIPT_PASS = "pass"
# 脚本测试结果为fail
REPORT_COL_SCRIPT_FAIL = "fail"
# 脚本测试结果为skip
REPORT_COL_SCRIPT_SKIP = "skip"
# 脚本不存在
REPORT_COL_SCRIPT_NOT_EXIST = "not_exist"
# 脚本测试结果为exception
REPORT_COL_SCRIPT_EXCEPTION = "except"
# 脚本测试结果为超时
REPORT_COL_SCRIPT_TIMEOUT = "timeout"
# 测试报告中的测试用例等级
REPORT_COL_CASE_LEVEL = "caseLevel"
# 测试报告中测试主机IP
REPORT_COL_HOST_IP = "hostIp"
# 测试报告中测试IOC的IP
REPORT_COL_IOC_IP = "IocIp"
# 测试报告中os
REPORT_COL_HOST_OS = "os"
# 测试报告中的测试平台
REPORT_COL_TEST_PLATFORM = "testPlatform"

# ===代码结构中的文件夹名称===
# 测试框架中的模块文件夹名称


"""------------------------------安装openpyxl------------------------------------"""
# 压缩包名称
ET_XMLFILE_TAR_PACKAGE = "et_xmlfile-1.0.1.tar.gz"
JDCAL_TAR_PACKAGE = "jdcal-1.4.1.tar.gz"
OPENPYXL_TAR_PACKAGE = "openpyxl-3.0.3.tar.gz"

# 解压后安装包名称
ET_XMLFILE_PACKAGE = "et_xmlfile-1.0.1"
JDCAL_PACKAGE = "jdcal-1.4.1"
OPENPYXL_PACKAGE = "openpyxl-3.0.3"

# 安装后所在文件夹
ET_XMLFILE = "et_xmlfile-1.0.1-py3.8.egg"
JDCAL = "jdcal-1.4.1-py3.8.egg"
OPENPYXL = "openpyxl-3.0.3-py3.8.egg"

"""--------------------------------日志收集模块的------------------------------------"""
# 日志服务器存放日志根目录
LOG_ROOT = "root"
LOG_ROOT_PATH = "/home/framework/sagitta_log/"

LOG_COLLECT_PATH = "ps3_log_collect"
# ===日志子文件夹===
# 管理工具日志文件夹
LOG_DIR_MGT_NAME = "mgt_log"
# 驱动日志文件夹
LOG_DIR_DRIVER_NAME = "driver_log"
# 固件日志文件夹
LOG_DIR_FW_NAME = "fw_log"
# UEFI Driver日志文件夹
LOG_DIR_UEFI_DRIVER_NAME = "UEFI_Driver_log"
# 仿真平台日志文件夹
LOG_DIR_SIMULATOR_NAME = "simulator_log"
# 测试机日志文件夹
LOG_DIR_HOST_NAME = "host_log"
# core文件夹
LOG_DIR_CORE_NAME = "core_log"
# Crash文件夹
LOG_DIR_CRASH_NAME = "crash_log"
# 测试工具日志文件夹
LOG_DIR_TOOLS_NAME = "tools_log"

# 测试机日志目表文件夹名称
LOG_DIR_NAME_QEMU_HOST = "opt_ps3sim_bin_log"  # qemu_host_log
# 主机侧驱动日志文件夹
LOG_DIR_NAME_HOST_DRIVER = "var_log_ps3sas_drv_log"  # host_driver_log
# 主机侧管理工具日志文件夹
LOG_DIR_NAME_HOST_MGT = "ps3cli_log"  # host_mgt_log
# factory 工具日志文件夹
LOG_DIR_NAME_HOST_FACTORY = "ps3test_log"
# 模拟平台下主机侧Message文件夹
LOG_DIR_NAME_HOST_MESSAGE = "var_log_message"  # "host_message_log"
# host qemu侧dmesg文件夹
LOG_DIR_NAME_HOST_DMESG = 'var_log_dmesg'
# 主机侧Crash文件夹
LOG_DIR_NAME_HOST_CRASH = "host_var_crash"  # "host_crash_log"
# 主机侧Vdbench文件夹
LOG_DIR_NAME_HOST_VDBENCH = "root_ps3test_vdbench"
# 主机侧Fio文件夹
LOG_DIR_NAME_HOST_FIO = "root_ps3test_fio"
# 主机侧cli error文件夹
LOG_DIR_NAME_HOST_CLI_ERROR = "root_cli_error"
# 主机侧minicom_log文件夹
LOG_DIR_NAME_HOST_SERIAL_LOG = "minicom_log"
# expander 寄存器数据文件夹
LOG_DIR_NAME_EXP_REGISTER_LOG = "register_log"

# IOC侧core目标文件夹名称
LOG_DIR_NAME_IOC_CORE = "opt_ps3_core"  # "ioc_core_log"
# IOC侧log文件夹
LOG_DIR_NAME_IOC_LOG = "opt_ps3_log"  # "ioc_log"
# IOC侧ps3文件夹
LOG_DIR_NAME_IOC_PS3 = "var_log_ps3_log"  # ioc_ps3_log
# IOC侧cli文件夹
LOG_DIR_NAME_IOC_CLI = "var_log_cli_log"  # ioc_cli_log
# IOC侧Crash文件夹
LOG_DIR_NAME_IOC_CRASH = "ioc_var_crash"  # "ioc_crash_log"
# IOC侧top文件夹
LOG_DIR_NAME_IOC_TOP = "opt_ps3_top"
# 侧模拟平台下IOC的Message文件夹
LOG_DIR_NAME_IOC_MESSAGE = "var_log_message"  # "ioc_message_log"
# ioc qemu侧dmesg文件夹
LOG_DIR_NAME_IOC_DMESG = "var_log_dmesg"
# 侧模拟平台下IOC的Message文件夹
LOG_DIR_NAME_IOC_PSTACK = "var_log_pstack"  # "ioc_pstack_log"

LOG_DIR_NAME_IOC_PS3SIM_LOG = "etc_ps3sim_log"
LOG_DIR_NAME_IOC_PCIESWITCH_LOG = 'pcieswitch.log'
LOG_DIR_NAME_IOC_SIMUSWITCH_LOG = 'simuSwitch.log'

LOG_DIR_NAME_TEST_SERVER = "test_server_log"
LOG_DIR_NAME_TEST_SERVE_TAR = "test_server_log.tar.gz"

# Expander目标文件夹名称
LOG_DIR_NAME_EXP_LOG = "expander_log"
LOG_DIR_NAME_EXP_EXPORT = "expander_export_log"
LOG_DIR_NAME_EXP_SERVER_LOG = "expander_server_log"
LOG_DIR_NAME_EXP_LOG_TAR = "expander_log.tar.gz"
# 物理平台，expander主机侧串口日志路径
REAL_EXP_SERIAL_LOG_DIR = '/home/minicom_log*'

# Host宿主机收集的日志的源地址
SIMULATOR_HOST_SERVER_LOG_COLLECT_PATH = "/opt/ps3sim/bin/log"
# SIMULATOR_HOST_SERVER_LOG_CLEAR_PATH = "/opt/ps3sim/bin/log/ps3sas_hostNode*"
SIMULATOR_HOST_SERVER_LOG_CLEAR_PATH = "/opt/ps3sim/bin/log/"
SIMULATOR_HOST_SERVER_LOG_DELETE_PATH = \
    "`find /opt/ps3sim/bin/log -name 'ps3sas_hostNode1.log_*' |grep ps3sas_hostNode1.log_...`"

SIMULATOR_HOST_SERVER_PCIE_SWITCH_LOG_COLLECT_PATH = "/opt/ps3swsim/log"
SIMULATOR_HOST_SERVER_PCIE_SWITCH_LOG_CLEAR_PATH = "/opt/ps3swsim/log/pcieswitch.log"

SIMULATOR_IOC_SERVER_PCIESWITCH_LOG_CLEAR_PATH = '/opt/ps3swsim/{}/pcieswitch /opt/ps3swsim/{}/pcieswitch.log'
SIMULATOR_IOC_SERVER_SIMUSWITCH_LOG_CLEAR_PATH = '/opt/ps3swsim/{}/simuSwitch /opt/ps3swsim/{}/simuSwitch.log'
SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_DIR = 'ioc_pcieswitch_log'
SIMULATOR_QEMU_IOC_PCIESWITCH_LOG_COLLECT_TAR = "ioc_pcieswitch_log.tar.gz"

SIMULATOR_QEMU_HOST_LOG_COLLECT_DIR = "host_qemu_log"
SIMULATOR_QEMU_HOST_LOG_COLLECT_TAR = "host_qemu_log.tar.gz"

SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_DIR = "ioc_exp_log"
SIMULATOR_QEMU_IOC_EXP_LOG_COLLECT_TAR = "ioc_exp_log.tar.gz"

SIMULATOR_HOST_PCIE_SWITCH_LOG_COLLECT_DIR = 'host_pcieswitch_log'

# Host端需要收集的日志的源地址：
# SIMULATOR_HOST_DRIVER_LOG_COLLECT_PATH = "/var/log/ps3sas_drv.log"
SIMULATOR_HOST_DRIVER_LOG_COLLECT_PATH = "/var/log/ps3sas_drv.log*"
SIMULATOR_HOST_DRIVER_BIN_COLLECT_PATH = "/var/log/ps3sas_drv.bin*"
SIMULATOR_HOST_DRIVER_LOG_DELETE_PATH = "/var/log/ps3sas_*"

SIMULATOR_HOST_MGT_LOG_COLLECT_CLEAR_PATH = "/root/ps3cli.log*"
SIMULATOR_HOST_FACTORY_LOG_COLLECT_CLEAR_PATH = "/root/ps3test.log*"
SIMULATOR_HOST_DMESG_LOG_COLLECT_PATH = '/var/log/dmesg'

SIMULATOR_HOST_MESSAGE_LOG_COLLECT_PATH = "/var/log/message*"
SIMULATOR_HOST_MESSAGE_LOG_DELETE_PATH = "/var/log/messages-*"

SIMULATOR_HOST_CRASH_LOG_COLLECT_PATH = "/var/crash"
SIMULATOR_HOST_CRASH_LOG_DELETE_PATH = "/var/crash/*"

TEST_TOOL_HOST_VDBENCH_CONFIGURE_COLLECT_PATH = "/root/ps3test/vdbench/vdb_configure/*"
TEST_TOOL_HOST_VDBENCH_OUTPUT_COLLECT_PATH = "/root/ps3test/vdbench/vdb_output/*"
TEST_TOOL_HOST_VDBENCH_JRN_OUTPUT_COLLECT_PATH = "/root/ps3test/vdbench/vdb_jrn_output/*"
TEST_TOOL_HOST_VDBENCH_JN_OUTPUT_COLLECT_PATH = "/root/ps3test/vdbench/vdb_jn_output/*"
TEST_TOOL_HOST_VDBENCH_DELETE_PATH = "/root/ps3test/vdbench/*"

TEST_TOOL_HOST_FIO_COLLECT_PATH = "/root/ps3test/fio/*"
TEST_TOOL_HOST_FIO_DELETE_PATH = "/root/ps3test/fio/*"
TEST_TOOL_HOST_CLI_ERROR_PATH = "/root/cli_error.log"
SIMULATOR_HOST_LOG_COLLECT_DIR = "host_log"
SIMULATOR_HOST_LOG_COLLECT_TAR = "host_log.tar.gz"

# Windows Host端需要收集的日志的源地址：
WINDOWS_SIMULATOR_HOST_DRIVER_LOG_COLLECT_PATH = "C:/ps3sas_drv.log*"
WINDOWS_SIMULATOR_HOST_DRIVER_BIN_COLLECT_PATH = "C:/ps3sas_drv.bin*"
WINDOWS_SIMULATOR_HOST_DRIVER_LOG_DELETE_PATH = "C:/ps3sas_*"

WINDOWS_SIMULATOR_HOST_MGT_LOG_COLLECT_CLEAR_PATH = "C:/Users/Administrator/ps3cli.log*"
WINDOWS_SIMULATOR_HOST_FACTORY_LOG_COLLECT_CLEAR_PATH = "C:/Users/Administrator/ps3test.log*"
WINDOWS_TEST_TOOL_HOST_CLI_ERROR_PATH = "C:/Users/Administrator/cli_error.log"
WINDOWS_TEST_TOOL_HOST_VDBENCH_PATH = "C:/Users/Administrator/ps3test/vdbench/*"
WINDOWS_TEST_TOOL_HOST_FIO_PATH = "C:/Users/Administrator/ps3test/fio/*"

# Ioc宿主机需要收集的日志源地址：
SIMULATOR_IOC_SERVER_PS3_EXP_LOG = "expAdmin.log"
PS3_EXP_FW_FILE = 'expsimu.bin'

# Ioc端需要收集的日志的源地址：
SIMULATOR_IOC_COLLECT_PATH = "/opt/ps3/ioc"
SIMULATOR_IOC_CORE_LOG_ROOT_PATH = "/opt/ps3/"
SIMULATOR_IOC_CORE_LOG_PATH = "/opt/ps3/*core* /opt/ps3/ioc"

EXPANDER_CORE_LOG_PATH = '{0}core.* {0}expsimu.bin'

SIMULATOR_IOC_LOG_COLLECT_PATH = "/opt/ps3/log/*"
SIMULATOR_IOC_LOG_DELETE_PATH = "/opt/ps3/log/*"

SIMULATOR_IOC_PS3_LOG_COLLECT_PATH = "/var/log/ps3_log/*"
SIMULATOR_IOC_PS3_LOG_DELETE_PATH = "/var/log/ps3_log/*"

SIMULATOR_IOC_CLI_LOG_COLLECT_PATH = "/root/ps3cli.log*"

SIMULATOR_IOC_CRASH_LOG_COLLECT_PATH = "/var/crash"
SIMULATOR_IOC_CRASH_LOG_DELETE_PATH = "/var/crash/*"

SIMULATOR_IOC_MESSAGE_LOG_COLLECT_PATH = "/var/log/message*"
SIMULATOR_IOC_DMESG_LOG_COLLECT_PATH = '/var/log/dmesg'
SIMULATOR_IOC_MESSAGE_DELETE_PATH = "/var/log/messages-*"
SIMULATOR_IOC_PSTACK_LOG_COLLECT_PATH = "/var/log/pstack*"
SIMULATOR_IOC_PSTACK_DELETE_PATH = "/var/log/pstack*"

SIMULATOR_IOC_PS3SIM_LOG_COLLECT_PATH = "/etc/ps3sim/log/* /opt/ps3sim/os_release_version.txt"
SIMULATOR_IOC_PS3SIM_LOG_DELETE_PATH = "`find /etc/ps3sim/log -name 'iocNode.log_*' | grep iocNode.log_...$`"
SIMULATOR_IOC_PS3SIM_LOG_CLEAR_PATH = "/etc/ps3sim/log/"

SIMULATOR_IOC_LOG_COLLECT_DIR = "ioc_log"
SIMULATOR_IOC_LOG_COLLECT_TAR = "ioc_log.tar.gz"
SIMULATOR_IOC_QEMU_LOG_COLLECT_DIR = "ioc_qemu_log"
SIMULATOR_IOC_QEMU_LOG_COLLECT_TAR = "ioc_qemu_log.tar.gz"

SIMULATOR_IOC_TOP_LOG_COLLECT_PATH = "/opt/ps3/stats/*"

CORE_PATTERN = "^core"
CORE_FILES_NAME = "*core.*"

LOG_CLEAR_START = "=====================Start to clear logs====================="
LOG_CLEAR_SUCCEED = "=====================Clear logs succeed====================="
LOG_SCRIPTS = '====================={}=====================\n\n'
LOG_FUNCION_SCRIPTS = '--------------{}--------------\n'
# 收集模拟平台Expander上日志的相关路径

# expander cli 存放的根路径，子路径文件夹是ep端口号命名的，以区分不同环境
SIMULATOR_EXP_CLI_ROOT = "/root/exp_simu_cli/"
SIMULATOR_EXP_EXPANDER_LOG = "expAdmin*"
SIMULATOR_EXP_EXP_EXPORT_LOG = "simuExpander*"
# expander cli命令头
SIMULATOR_EXP_CLI_HEAD = "exp_simu_host.elf"
SIMULATOR_EXP_LOG = "ps3_log"


"""-------------------------后端及后端工具相关信息-----------------------------"""
BACKEND = "backend"
BACKEND_TOOL_LOG_PATH = "/bin/backEndTest"
# IOC侧后端工具日志目标文件夹名称
LOG_DIR_NAME_BACKEND_TOOL = "bin_backend_test"

"""-------------------------用例脚本关系集所需要的信息常量--------------------------------"""
# 用例脚本关系集中正式数据开始行（去除表头）
CASE_SCRIPT_READ_MIN_ROW = 2
DEFAULT_ZEN_CASE_SCRIPT_BRANCH_ID = 1
DEFAULT_ZEN_CASE_SCRIPT_MODULE_ID = 0
# 脚本用例关系集字段名
CASE_SCRIPT_CASE_ID = "caseId"
CASE_SCRIPT_CASE_TITLE = "caseTitle"
CASE_SCRIPT_CASE_VERSION = "caseVersion"
CASE_SCRIPT_CASE_TYPE = "caseType"
CASE_SCRIPT_CASE_LEVEL = "caseLevel"
CASE_SCRIPT_SCRIPT_LOCATION = "scriptLocation"
CASE_SCRIPT_BRANCH_ID = "branchId"
CASE_SCRIPT_MODULE_ID = "moduleId"
CASE_SCRIPT_MODULE_NAME = "moduleName"
CASE_SCRIPT_CASE_STEP = "caseStep"
CASE_SCRIPT_RUN_ID = "runId"
CASE_SCRIPT_NEED_RUN = "needRun"

# 禅道脚本用例关系集字段名
ZEN_CASE_SCRIPT_CASE_ID = "case_id"
ZEN_CASE_SCRIPT_CASE_TITLE = "case_title"
ZEN_CASE_SCRIPT_CASE_VERSION = "case_version"
ZEN_CASE_SCRIPT_CASE_TYPE = "case_type"
ZEN_CASE_SCRIPT_CASE_LEVEL = "case_level"
ZEN_CASE_SCRIPT_SCRIPT_LOCATION = "script_path"
ZEN_CASE_SCRIPT_BRANCH_ID = "branch_id"
ZEN_CASE_SCRIPT_MODULE_ID = "module_id"
ZEN_CASE_SCRIPT_MODULE_NAME = "module_name"
ZEN_CASE_SCRIPT_CASE_STEP = "case_step"
ZEN_CASE_SCRIPT_RUN_ID = "run_id"
ZEN_CASE_SCRIPT_NEED_RUN = "need_run"

CASE_SCRIPT_NEED_RUN_YES = "Y"

# 使用到的命名常量信息
CASE_SCRIPTS_DIR_NAME = "scripts"
CASE_SCRIPTS_HBA_DIR_NAME = "scripts_hba"
CASE_SCRIPT_FILE_NAME = "case_script_"
CASE_SCRIPT_PART_PATH_NAME = "scripts/case_script_lists/zentao_auto"
CASE_SCRIPT_SHEET_NAME = "case script list"
DEFAULT_SCRIPT_NAME = "script"
DEFAULT_OPEN_SIMULATOR_CASE_TITLE = "拉起模拟平台"
DEFAULT_CLOSE_SIMULATOR_CASE_TITLE = "关闭模拟平台"
DEFAULT_RESET_SIMULATOR_CASE_TITLE = "重启模拟平台"

"""-----------------------------------环境配置字段名----------------------------------"""
ENV_GIT_BRANCH = "git_branch"
ENV_GIT_BRANCH_VERSION = "git_branch_version"
ENV_PACKAGE_INSTALL = "package_install"
ENV_PROJECT_NAME = "project_name"
ENV_TEST_PROJECT = "test_project"
ENV_TEST_OBJECT = "test_object"
ENV_PACKAGE_PATH = "package_path"
ENV_CASE_SCRIPT_LIST_PATH = "case_script_list_path"
ENV_TASK_ID = "task_id"
ENV_TASK_NAME = "task_name"
ENV_JOB_ID = "job_id"
ENV_JOB_NAME = "job_name"
ENV_HOST_OS = "host_os"
ENV_HOST_TYPE = "host_type"
ENV_HOST_LABEL = "host_label"
ENV_HOST_CPU = "host_cpu"
ENV_DISK_INTERFACE = "disk_interface"
ENV_DISK_MEDIUM = "disk_medium"
ENV_BACKPLANE = "backplane"
ENV_TEST_PLATFORM = "test_platform"
ENV_CASE_LEVEL = "case_level"
ENV_TEST_ROUNDS = "test_rounds"
ENV_CHIP_TYPE = "chip_type"
ENV_JENKINS_IP = "jenkins_ip"
ENV_JOB_UUID = "job_uuid"
ENV_HOST_LOCATION = "host_location"
ENV_TEST_SCRIPT_LIST = "test_script_list"
ENV_TEST_CASE_LIST = "test_case_list"
ENV_PRODUCT_ID = "product_id"
ENV_PROJECT_ID = "project_id"
ENV_OPENED_BUILD = "opened_build"
ENV_OPENED_BY = "opened_by"
ENV_TEST_PHASE = "test_phase"
ENV_SCRIPT_TIMEOUT = "script_timeout"
ENV_TEST_ENTRY = "test_entry"
TEST_ENTRY_SINGLE_MODE = "single_mode"
TEST_ENTRY_UEFI_MODE = "uefi_mode"
TEST_ENTRY_DPDK_MODE = "dpdk_mode"
TEST_ENTRY_DPDK_AUTO_MODE = "dpdk_auto_mode"

ENV_BUG_STOP = "bug_stop"

ENV_COMPILE_OBJECT = "compile_object"

ENV_PACKAGE_COMPILE = "package_compile"


ENV_SHOW_CONSOLE_LOG = "show_console_log"

ENV_GCOVER_VERSION = "gcover_version"
# 是否片内发包（仅性能测试组使用），默认为no

# 是否长稳测试
ENV_LONG_STAB_TEST = "long_stab_test"

ENV_SWITCH_LABEL = "switch_label"
EVN_SERVER_NIC_MODEL = 'server_nic_model'
EVN_CLIENT_NIC_MODEL = 'client_nic_model'


ENV_CASE_LIST_ORDER = "case_list_order"
ENV_RANDOM_EXEC = "random_exec"

ENV_RPM_INSTALL = "rpm_install"
ENV_SKIP_QEMU_START = "skip_qemu_start"


ENV_PARAM_FROM_ZENTAO = "parameters_from_zentao"

ENV_RUN_MODE_WITH_KO = "nic"
ENV_RUN_MODE_WITH_SRC = "nic_with_src"
ENV_RUN_MODE_WITH_RPM = "nic_with_rpm"
ENV_RUN_MODE_WITH_SRC_KO = "nic_with_src_ko"
ENV_RUN_MODE_WITH_SRPM = "nic_with_srpm"
ENV_RUN_MODE_WITH_KMOD_SRPM = "nic_with_kmod_srpm"
ENV_RUN_MODE_WITH_BG_TRAFFIC = "nic_with_background_traffic"
ENV_TEST_PORT = "test_port"
ENV_HOST_IP = "server_ip"
ENV_HOST_PORT = "host_port"
ENV_SERVER_NIC_IP = 'server_nic_ip'
ENV_CLIENT_IP = 'client_ip'
ENV_CLIENT_PORT = "client_port"
ENV_CLIENT_NIC_IP = "client_nic_ip"
ENV_HOST_QEMU_IP = 'host_qemu_ip'
ENV_HOST_QEMU_PORT = 'host_qemu_port'
ENV_IOC_IP = "soc_ip"
ENV_IOC_PORT = "soc_port"
ENV_IOC_QEMU_IP = 'soc_qemu_ip'
ENV_IOC_QEMU_PORT = 'soc_qemu_port'

ENV_LOG_SERVER_IP = "log_server_ip"
ENV_PS3_SERVER_IP = "ps3_server_ip"
ENV_LOG_SERVER_PATH = "log_server_path"
ENV_ROOT_NODE_NAME = "env_config"
ENV_FIREWALLD = "firewalld"
ENV_CUSTOM_PARAMS = "custom_params"
CUSTOM_PARAMS_PF_CO_MODE = "pf_com_mode"
CUSTOM_PARAMS_VF_CO_MODE = "vf_com_mode"
# 打开日志超限检查
CUSTOM_PARAMS_LOG_CHECK = "log_check"
# 所有日志检查都关闭（日志超限检查、异常关键字检查）
CUSTOM_PARAMS_NOT_CHECK_LOG = "not_check_log"
CUSTOM_PARAMS_CORE_RESET_RECOVERY_LINK = "core_reset_recovery_link"
# 服务器ip配置节点
SERVER_COMMON_JENKINS = "jenkins"
SERVER_COMMON_JENKINS_SERVER_IP = "jenkins_server_ip"
ENV_LOG_SERVER_ACCOUNT = "log_server_account"

COM_LOG_DIR = "/home/framework/other/"
# 测试主机配置节点
TEST_CONFIG_SERVER_IP = "server_ip"
TEST_CONFIG_SERVER_NIC_IP = "server_nic_ip"
TEST_CONFIG_SERVER_BMC_IP = "server_bmc_ip"
TEST_CONFIG_SERVER_PORT = "server_port"
TEST_CONFIG_CLIENT_IP = "client_ip"
TEST_CONFIG_CLIENT_NIC_IP = "client_nic_ip"
TEST_CONFIG_CLIENT_BMC_IP = "client_bmc_ip"
TEST_CONFIG_DEFAULT_PORT = "22"

TEST_CONFIG_SUNAME = 'suname'
TEST_CONFIG_SUPASSWD = 'supasswd'
TEST_CONFIG_CUNAME = 'cuname'
TEST_CONFIG_CUPASSWD = 'cupasswd'

TEST_CONFIG_SERVER_COM_IP = "server_com_ip"
TEST_CONFIG_SERVER_COM_PORT = "server_com_port"
TEST_CONFIG_CLIENT_COM_IP = "client_com_ip"
TEST_CONFIG_CLIENT_COM_PORT = "client_com_port"

# 配置文件名称
TEST_HOST_CONFIG_NAME = "test_host_config.xml"
ENV_CONFIG_NAME = "env_config.xml"
SERVER_COMMON_CONFIG_NAME = "server_common_config.xml"
# 配置文件中主机类型取值
ENV_VIRTUAL_MACHINE = "virtual_machine"
ENV_PHYSICAL_MACHINE = "physical_machine"
ENV_PLATFORM_SIMU = "simu_platform"
ENV_PLATFORM_REAL = "real_platform"
# 配置文件test_host_config存放主机类型文件夹名称
CONFIG_DIR_VIRTUAL = "vms"
CONFIG_DIR_PHYSICAL = "pms"

# 默认值
DEFAULT_ENV_OPENED_BUILD = "1.0.0"
DEFAULT_ENV_OPENED_BY = "tester"
DEFAULT_ENV_TASK_ID = 0
DEFAULT_ENV_PRODUCT_ID = 1
DEFAULT_ENV_HOST_OS = "Linux"
# 取值
ENV_TEST_ENTRY_HOST = "host"
ENV_TEST_ENTRY_IOC = "soc"

ENV_BUG_STOP_YES = "yes"
ENV_BUG_STOP_NO = "no"
ENV_DEFAULT_ACCOUNT = "root"
ENV_LOG_SERVER_ACCOUNT_FRAMEWORK = "framework"


"""------------------------------------时间同步信息--------------------------------------"""
TIME_SERVER_IP = "10.22.132.10"
NTP_CONF_INFO_RE = "'^server 127.127.1.0$'"
NTP_CONF_INFO = "'server 127.127.1.0'"
NTP_TIME_ZONE = "CST"
NTP_TIME_ZONE_VALUE = "Asia/Shanghai"

"""-------------------------------文件夹、分隔符等常量------------------------------------"""
DEFAULT_TIME_FORMAT = "%Y%m%d%H%M%S"
DEFAULT_ENCODING = "utf-8"
# framework下tools文件夹
FRAMEWORK_DIR_TOOLS = "tools"
# 项目下的配置文件夹名称
PROJECT_DIR_CONF = "conf"
# framework下环境配置文件夹名称
FRAMEWORK_DIR_ENV_CONF = "env_conf"
# framework下环境文件夹名称
FW_MODULES = "biz"
# outputs文件夹名称
OUTPUTS = "outputs"
# output下framework存放的文件夹
OUTPUT_FRAMEWORK = "framework"
# 测试报告生成的日志文件名
REPORT_LOG_FILE_NAME = "report_log"
# 拉起模拟平台文件
HOST_IOC_OPEN_FILE_PATH = 'simulation/host_ioc_start.py'
EXPANDER_OPEN_FILE_PATH = 'simulation/exp_simu_open.py'
PCIE_SWITCH_OPEN_FILE_PATH = 'simulation/sw_simu_open.py'
# 关闭模拟平台文件
HOST_IOC_CLOSE_FILE_PATH = 'simulation/host_ioc_close.py'
EXPANDER_CLOSE_FILE_PATH = 'simulation/exp_simu_close.py'
# 重启模拟平台文件
HOST_IOC_RESET_FILE_PATH = 'simulation/host_ioc_reset.py'
# 修改文件权限路径‘
CHANGE_MODE_FILE_PATH = "/home/logfile_permission.py"

# 分隔符
FILE_NAME_CONNECTOR = "_"
INTENT_SPLITTER = "\t"
INTENT_CHARACTER = "\n"
WINDOWS_DIR_SPLITTER = "\\"
LINUX_DIR_SPLITTER = "/"
CASE_LEVEL_SPLIT_FLAG = ","
CASE_SCRIPT_LOCATIONS_SPLIT_FLAG = ","
# 脚本执行结果之间分隔
SCRIPT_RESULT_SPLIT_CHARACTER = "-"
# 用例类型字符串的分隔符
CASE_TYPE_STR_CONNECTOR = "-"
# 测试脚本返回结果关键字
OUTPUT_SPLIT_KEY = "result_dict:"
OUTPUT_END_SPLIT_KEY = "\n"
PATTERN_CH_NUM = "[^\u4e00-\u9fa5a-zA-Z0-9]"

"""------------------------------------run_all_test_ps3的提示信息--------------------------------------"""

SCRIPT_START_INFO = \
    "\n------------------Script start running. Script path: %s.------------------"
SCRIPT_NOT_EXIST_INFO = \
    "\n------------------Script not exists. Script path : %s.------------------"
SCRIPT_BUG_STOP_INFO = \
    "\n------------------A bug appears, or scripts timeout, or cli execute except, and the test stops: %s." \
    "------------------"
PING_CMD_FAIL_INFO = \
    "\n------------------Ping host ip fail. Script path : %s.------------------"
RESTART_SIMULATOR_FAILED = \
    "\n------------------Simulator restarting failed,test stop------------------"
REPORT_CREATE_START = \
    "\n****************************Start to create test report.*************************************"
REPORT_PATH_FAIL = \
    "\n**********************Create test report path failed. Report path: %s.**********************"
REPORT_CREATE_FAIL = \
    "\n*****************************Create test report failed.*************************************"
REPORT_CREATE_SUC = \
    "\n****************************Create test report success!!!***********************************"
TEST_START_INFO = \
    "\n***************************Framework run all test start*************************************"
TEST_FINISH_INFO = \
    "\n***************************Framework run all test finish************************************"
CASE_NOT_EXIST_INFO = \
    "\n------------------Script case not exists. Script path : %s.------------------"

"""----------------------------------others------------------------------------"""
NONE_STR = "None"
TRUE_STR_LIST = ['y', "Y", "yes", "YES", "Yes", "True", "TRUE", "true", True]
FALSE_STR_LIST = ['n', "N", "no", "NO", "No", "False", "FALSE", "false", False]
LOCATION_SUFFIX_PY = -3
LOCATION_SUFFIX_TAR = -4
# duration精确到小数点后3位
DURATION_ROUND_BIT = 3
# 程序暂停时间
SLEEP_TIME = 10
# 毫秒和秒的转换
TIME_RATIO = 1000
# 脚本指向时间限制单位-小时
SCRIPT_TIMEOUT_UNIT = 'h'
# 脚本不存在
SCRIPT_NON_EXIST = "not exist"
# 脚本对应用例不存在
SCRIPT_CASE_NON_EXIST = "case not exist"
# ping测试主机ip失败
PING_HOST_FAIL = "ping host ip failed"
# ping测试主机ip最大失败次数
PING_FAILED_MAX_TIMES = 5
# 执行脚本最多的次数
EXEC_SCRIPTS_MAX_TIMES = 1
# 脚本测试概览信息的标识
SCRIPT_SUMMARY_TAG = "summary"
# ioc版本
IOC_VERSION = "ioc_version"
LOG_WARN = "log_waring"
# ioc进程名称
IOC_PROCESS_NAME = 'ioc'
# run all test结果标识
RESULT_RUN_ALL_TEST = "run all test result"
# 问题类型的最大长度限制
BUG_TYPE_MAX_LEN = 30
# ip地址正则表达式
# IP_PATTERN = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
IP_PATTERN = r'(([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])\.){3}([01]{0,1}\d{0,1}\d|2[0-4]\d|25[0-5])'
HOST_OWNER = "owner"
HOST_CONFIG_FILE = "/home/test/ps3test/conf/sagitta_config_new.xlsx"

# 禅道host_cpu选项
HOST_CPU_X86 = 'x86'
HOST_CPU_ARM = 'arm'
HOST_CPU_MIPS = 'mips'


# 脚本文件头信息
class ScriptsHeader(object):
    header = {"0": "caseId",
              "1": "caseTitle",
              "2": "caseVersion",
              "3": "caseLevel",
              "4": "caseType",
              "5": "branchId",
              "6": "moduleId",
              "7": "moduleName",
              "8": "caseStep",
              "9": "scriptLocation",
              "10": "runId",
              "11": "needRun"}
