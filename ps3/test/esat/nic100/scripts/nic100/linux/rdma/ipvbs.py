# coding=utf-8
"""
version: 1.0.0
date: 2024.08.28

使用说明：
1. 每次启动时创建文件，当文件大小超过200M时创建新文件
1. 所有创建的对象需要以obj_开头
2. 调用接口方式与pyverbs相同，工具不记录对象由哪个设备创建，需要脚本自行维护
3. 通过mem_alloc.malloc申请的内存对象需要以obj_buf开头
4. exit退出交互式工具，并释放所有资源

eg.
obj_ctx = device.Context(name='mlx5_0')
obj_pd1 = pd.PD(creator=obj_ctx)
obj_buf = mem_alloc.malloc(100)
obj_mr1 =  mr.MR(creator=obj_pd1, length=100, access=enums.ibv_access_flags.IBV_ACCESS_LOCAL_WRITE.value, address=obj_buf, implicit=False)
obj_mr1.length
obj_mr1.write(data='asdfghjkl', length=10)
obj_mr1.read(10, 0).decode()
obj_mr1.close()
mem_alloc.free(obj_buf)
"""
import re
import subprocess
from re import findall
from traceback import format_exc
from string import *
from random import *
from pyverbs import device, pyverbs_error, pd, mem_alloc, addr, mr, cq, wr, qp, srq
from pyverbs import *
import datetime
import os
import concurrent.futures
import time
import signal
import readline

rc_59 = False
rc_51 = False
status, result = subprocess.getstatusoutput('echo $PYTHONPATH')
if 'rdma-core-59.0' in result:
    rc_59 = True
elif 'rdma-core-51.0' in result:
    rc_51 = True
else:
    pass
if rc_59:
    from pyverbs import libibverbs_enums
    from pyverbs.libibverbs_enums import *
elif rc_51:
    from pyverbs import enums
    from pyverbs.enums import *
else:
    from pyverbs import enums
    from pyverbs.enums import *

rdma_dict = {}
sge_list = []
timeout = 0

# dev_lst = device.rdma_get_devices()
# dev_name_lst = [dev.name.decode('utf-8') for dev in dev_lst]

VERSION = '2025.0908.1'

close_lst = [
    "<class 'pyverbs.addr.AH'>",
    "<class 'pyverbs.base.PyverbsCM'>",
    "<class 'pyverbs.cmid.AddrInfo'>",
    "<class 'pyverbs.cmid.CMEvent'>",
    "<class 'pyverbs.cmid.CMEventChannel'>",
    "<class 'pyverbs.cmid.CMID'>",
    "<class 'pyverbs.cq.CompChannel'>",
    "<class 'pyverbs.cq.CQ'>",
    "<class 'pyverbs.cq.CQEX'>",
    "<class 'pyverbs.device.Context'>",
    "<class 'pyverbs.device.DM'>",
    "<class 'pyverbs.dmabuf.DmaBuf'>",
    "<class 'pyverbs.flow.Flow'>",
    "<class 'pyverbs.mr.MR'>",
    "<class 'pyverbs.mr.MW'>",
    "<class 'pyverbs.mr.DmaBufMR'>",
    "<class 'pyverbs.pd.PD'>",
    "<class 'pyverbs.pd.ParentDomain'>",
    "<class 'pyverbs.qp.QP'>",
    "<class 'pyverbs.srq.SRQ'>",
    "<class 'pyverbs.srq.OpsWr'>",
    "<class 'pyverbs.wq.WQ'>",
    "<class 'pyverbs.wq.RwqIndTable'>",
    "<class 'pyverbs.wr.SendWR'>",
    "<class 'pyverbs.wr.RecvWR'>",
    "<class 'pyverbs.wr.SGE'>",
    "<class 'pyverbs.xrcd.XRCD'>",
]
free_lst = [
    "<class 'pyverbs.mem_alloc.malloc'>",
]

# def get_log_filename():
#     """生成日志文件名，包含当前日期和时间"""
#     now = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
#     return f"pyverbs_log_{now}.log"

directory_path = '/home/pyverbs_log'
result_folder = '/root/result_log'

# 检查目录是否存在
if not os.path.exists(directory_path):
    # 如果目录不存在，则创建它
    try:
        os.makedirs(directory_path)
        os.makedirs(result_folder)
        print(f"目录 {directory_path} 已创建。")
    except PermissionError:
        # 如果遇到权限错误，打印一条消息
        print(f"没有权限在 {directory_path} 创建目录。请以root用户身份运行此脚本或使用sudo。")
    except Exception as e:
        # 捕获其他可能的异常
        print(f"创建目录时发生错误：{e}")

now = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
file_path = directory_path + f"/pyverbs_log_{now}.log"
result_path = result_folder + f"/pyverbs_log_{now}.log"


# 定义信号处理函数
def ignore_sigint(signum, frame):
    pass

# 捕获 SIGINT 信号
signal.signal(signal.SIGINT, ignore_sigint)


def split_string(input_cmd):
    cmd_lst = []
    d_quot = False
    s_quot = False
    start = 0
    input_cmd = input_cmd.strip()
    length = len(input_cmd)
    index = 0
    while index < length:
        s = input_cmd[index]
        # for index, s in enumerate(input_cmd):
        if s == '"' and not d_quot:
            d_quot = True
        elif s == '"' and d_quot:
            d_quot = False

        if s == "'" and not s_quot:
            s_quot = True
        elif s == "'" and s_quot:
            s_quot = False
        if s == ';' and d_quot is False and s_quot is False:
            cmd_lst.append(input_cmd[start:index].strip())
            start = index + 1
            index += 1
        elif index == len(input_cmd) - 1:
            cmd_lst.append(input_cmd[start:index + 1].strip())

        index += 1

    return cmd_lst


def custom_print(*args):
    """
    自定义print函数，将消息打印到控制台和文件。
    如果文件大小超过max_file_size，则创建新文件。
    """
    # 获取当前时间
    # max_file_size = 200 * 1024 * 1024
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 构造带时间戳的消息
    timed_message = f'[{now}] '
    for arg in args:
        timed_message += f'{arg}'

    # 刚启动时创建文件，打印文件路径
    if 'log_file_path: ' in timed_message:
        # file_path = get_log_filename()
        timed_message += file_path
    if findall('\[.*] execute:', timed_message):
        timed_message += '\n'
    else:
        timed_message += '#####RESULTEND######\n'

    # 打印到控制台
    print(timed_message, end='')

    # 写入文件
    with open(file_path, 'a') as file:
        file.write(timed_message)

    with open(result_path, 'a') as file:
        file.write(timed_message)

    # if findall(fr'\[\d+-\d+-\d+ \d+:\d+:\d+]\s+status:', timed_message):
    #     with open(result_path, 'a') as file:
    #         file.write(timed_message)

def eval_with_timeout(expression, timeout=5):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"代码执行超时({timeout})")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)  # 设置超时时间

    try:
        result = eval(expression)  # 执行eval
        signal.alarm(0)  # 取消超时
        return result
    except TimeoutError:
        # print(f"超时({timeout})!")
        return 'timeout'

def exec_with_timeout(expression, timeout=5):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"代码执行超时({timeout})")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)  # 设置超时时间

    try:
        result = exec(expression)  # 执行exec
        signal.alarm(0)  # 取消超时
        return result
    except TimeoutError:
        # print(f"超时({timeout})!")
        return 'timeout'


def call_function(input_cmd):
    try:
        # 如果输入的指令是：对象名=类名.方法名(para1=**, para2=**), 则执行方法并将新创建的对象存到字典rdma_dict中, 输出返回结果
        if findall(r'^[a-zA-Z0-9_.]+\s*=.*\)$', input_cmd):
            obj_name = input_cmd.split('=')[0].strip()
            func_str = input_cmd[input_cmd.find('=') + 1:].strip()
            test_obj_names = findall(rf'(obj_\w+)', func_str)
            if test_obj_names:
                test_cmd = func_str
                replace_set = set(test_obj_names)
                for test_obj_name in replace_set:
                    test_cmd = test_cmd.replace(test_obj_name, f"rdma_dict['{test_obj_name}']")
            else:
                test_cmd = func_str
            custom_print(f'execute:', input_cmd)
            rdma_dict[obj_name] = eval_with_timeout(test_cmd, timeout)
            if len(str(rdma_dict[obj_name])) > 10000:
                custom_print(f'status: success\nresult length exceed 10000, skip print\n')
            else:
                custom_print(f'status: success\n{str(rdma_dict[obj_name])}\n')
        # 如果输入的指令是：类名.方法名(para1=**, para2=**), 则执行方法并输出返回结果
        else:
            test_obj_names = findall(rf'(obj_\w+)', input_cmd)
            if test_obj_names:
                test_cmd = input_cmd
                replace_set = set(test_obj_names)
                for test_obj_name in replace_set:
                    test_cmd = test_cmd.replace(test_obj_name, f"rdma_dict['{test_obj_name}']")
            else:
                test_cmd = input_cmd
            custom_print(f'execute:{input_cmd}')
            result = eval_with_timeout(test_cmd, timeout)
            custom_print(f'status: success\n{result}\n')
            del_lst = ['free', 'close']
            if any(word in test_cmd for word in del_lst):
                # rdma_dict[test_obj_names[0]] = None
                rdma_dict.pop(test_obj_names[0], '')

    except pyverbs_error.PyverbsUserError:
        custom_print('status: failure\nPyverbsUserError:', format_exc(), '\n')
    except pyverbs_error.PyverbsRDMAError:
        custom_print('status: failure\nPyverbsError', format_exc(), '\n')
    except AttributeError:
        custom_print("status: failure\nAttributeError:", format_exc(), '\n')
    except Exception:
        custom_print("status: failure\nException:", format_exc(), '\n')


custom_print('log_file_path: ')
print("""
使用说明：
1. 每次启动时创建文件
1. 所有创建的对象需要以obj_开头
2. 调用接口方式与pyverbs相同，工具不记录对象由哪个设备创建，需要脚本自行维护
3. 通过mem_alloc.malloc申请的内存对象需要以obj_buf开头
4. exit退出交互式工具，并释放所有资源
""")
while True:
    try:
        input_cmd = input(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] > ')
        if 'timeout' in input_cmd and '.timeout' not in input_cmd and 'timeout=' not in input_cmd:
            res = re.findall(r'timeout(\d+)s', input_cmd)
            if res:
                timeout = int(res[0])
                input_cmd = input_cmd.replace(f'timeout{timeout}s ', '')
            else:
                custom_print('status: failure\ntimeout format error', format_exc(), '\n')
                continue
        # exit时释放所有资源并退出
        if input_cmd in ['exit', 'clear']:
            custom_print(f'== {input_cmd} ==')
            for obj_name, test_obj in rdma_dict.items():
                obj_type = str(type(test_obj))
                obj_cmd = None
                if obj_type == "<class 'int'>" and 'buf' in obj_name:
                    custom_print(f'execute: mem_alloc.free({obj_name})')
                    obj_cmd = f"mem_alloc.free(rdma_dict['{obj_name}'])"
                    result = eval_with_timeout(obj_cmd, timeout)
                    custom_print(f'status: success\n{result}\n')
                elif obj_type in close_lst:
                    custom_print(f'execute: {obj_name}.close')
                    obj_cmd = f"rdma_dict['{obj_name}'].close()"
                    result = eval_with_timeout(obj_cmd, timeout)
                    custom_print(f'status: success\n{result}\n')
                elif obj_type in free_lst:
                    custom_print(f'execute: mem_alloc.free({obj_name})')
                    obj_cmd = f"mem_alloc.free(rdma_dict['{obj_name}'])"
                    result = eval_with_timeout(obj_cmd, timeout)
                    custom_print(f'status: success\n{result}\n')
            if input_cmd == 'exit':
                break
            else:
                continue

        if len(input_cmd) < 4:
            continue
        cmd_lst = split_string(input_cmd)
        for cmd in cmd_lst:
            if findall(r'\(.*\)', cmd):
                call_function(cmd)
            # 如果输入的指令是：类名.对象名, 则执行方法并输出返回结果
            else:
                try:
                    test_obj_names = findall(rf'(obj_\w+)', cmd)
                    if test_obj_names:
                        replace_set = set(test_obj_names)
                        test_cmd = cmd
                        for test_obj_name in replace_set:
                            test_cmd = test_cmd.replace(test_obj_name, f"rdma_dict['{test_obj_name}']")
                    else:
                        test_cmd = cmd
                    custom_print(f'execute:', cmd)
                    if "=" in test_cmd:
                        result = exec_with_timeout(test_cmd, timeout)
                    else:
                        result = eval_with_timeout(test_cmd, timeout)
                    custom_print(f'status: success\n{result}\n')
                except pyverbs_error.PyverbsUserError as e:
                    custom_print('status: failure\nPyverbsUserError:', format_exc(), '\n')
                except pyverbs_error.PyverbsRDMAError as e:
                    custom_print('status: failure\nPyverbsRDMAError:', format_exc(), '\n')
                except AttributeError as e:
                    custom_print("status: failure\nAttributeError:", format_exc(), '\n')
                except Exception as e:
                    custom_print("status: failure\nException:", format_exc(), '\n')
    except SyntaxError:
        custom_print('status: failure\nSyntaxError:', format_exc(), '\n')
    except Exception:
        custom_print("status: failure\nException:", format_exc(), '\n')
