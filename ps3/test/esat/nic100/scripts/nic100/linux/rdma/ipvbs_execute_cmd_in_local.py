#!/usr/bin/python3
# -*- encoding=utf8 -*-
import argparse
import re
import subprocess
import time

parser = argparse.ArgumentParser(description="Sxe Test.")
parser.add_argument('-s', '--screen', default='', type=str, help='screen名称')
parser.add_argument('-c', '--cmd', default='', type=str, help=r'待执行的cmd')
parser.add_argument('-t', '--timeout', default=30, type=int, help=r'获取cmd执行结果超时时间')
parser.add_argument('-l', '--log_path', default='', type=str, help=r'ipvbs临时log文件名称')
args = parser.parse_args()

screen = args.screen
cmd = args.cmd
cmd_new = [int(cmd[i*2: i*2+2], 16) for i in range(0, len(cmd) // 2)]
cmd_new = bytes(cmd_new)
cmd_new = cmd_new.decode('utf-8')
# cmd = args.cmd.replace('\\', '').replace("@", "\"").replace("#", "\'")
# print('cmd:', args.cmd)\
timeout = args.timeout
log_path = args.log_path
# print("log_path:", log_path)

# exec_command = f'ls /root/result_log/'
# rtn_code, rtn_outputs = subprocess.getstatusoutput(exec_command)
# log_lst = re.findall(r'(pyverbs_log_\S+log)', rtn_outputs)
# log_path = '/root/result_log/' + max(log_lst, key=lambda x: int(''.join(re.findall(r'(\d+)', x))))

exec_1 = "screen -x -S {} -p 0 -X stuff \"{}\"".format(screen, cmd_new)
status, res = subprocess.getstatusoutput(exec_1)
# print('exec_1: ', exec_1)
# print(exec_1)
exec_2 = "screen -x -S {} -p 0 -X stuff '^M'".format(screen)
status, res = subprocess.getstatusoutput(exec_2)
# print(exec_2)

rtn_outputs = ''
ori_time = time.time()
check_lst = cmd_new.split(';')
check_wrd = check_lst[-1].strip()
check_wrd = re.sub(r'timeout(\d+)s ', '', check_wrd)
while time.time() - ori_time < timeout:
    exec_command = f'cat {log_path}'
    # print('exec_command: ', exec_command)
    rtn_code, rtn_outputs = subprocess.getstatusoutput(exec_command)
    pattern = rf'execute:{check_wrd}\n.*status' \
        .replace('+', '\+') \
        .replace('(', '\(').replace(')', '\)') \
        .replace('[', '\[').replace(']', '\]') \
        .replace(' * ', ' \* ')
    check = re.findall(pattern, rtn_outputs, re.S)
    # print('rtn_outputs: ', rtn_outputs)
    # print('pattern: ', pattern)
    # print('check: ', check)
    if check:
        break
    elif cmd_new.strip() == 'exit':
        break
status, res = subprocess.getstatusoutput(f"echo '' > {log_path}")
print(rtn_outputs)
