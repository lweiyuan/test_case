import json
import re
import time
from random import *
from re import findall, finditer
from string import ascii_letters, digits, hexdigits

from scripts.script_libs.constants import (BMC_PWD, BMC_NAME,SXE2CLI64,
                                           BMC_TOOL_PATH, BMC_PWD_NET, BMC_NAME_NET)
from scripts.script_libs.enums import CmdExecuteAdressEnum
from temp_test import CommandOperation, log, CommonOperation
from threading import Thread


IP = '10.22.115.228'
EID = 'b'


class CommonTools:

    @classmethod
    def feed_log(cls):
        counter = 100
        while counter:
            CommandOperation.execute_command_with_error(
                cmd=f'{SXE2CLI64} show',
                cmd_execute_address=CmdExecuteAdressEnum.SERVER.value
            )
            counter -= 1
        print('success')

    @classmethod
    def get_bmc_ip(cls, execute_addr=CmdExecuteAdressEnum.SERVER.value):
        cmd = 'ipmitool lan print 1'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        bmc_ip = findall(r'IP Address\s*:\s*(\d+\.\d+\.\d+\.\d+)', rtn_output)
        print(rtn_output)
        if bmc_ip:
            return bmc_ip[0]
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='获取BMC IP',
                result_info='获取失败')

    @classmethod
    def get_bmc_eid(cls, ip=IP, execute_addr=CmdExecuteAdressEnum.SERVER):
        eid_dict = {}
        cmd = f'{BMC_TOOL_PATH} -m 0 -c 0xff --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'获取所有BMC EID 结果：\n{rtn_output}')
        if 'MCTP Device count' not in rtn_output:
            CommonOperation.create_bug_problem(cls,
                                               key_word='BMC',
                                               description_word='获取所有BMC EID',
                                               result_info='获取失败')
        info_lst = findall(r'Medium Type[\s\S]*?Is Static EID', rtn_output)
        for info in info_lst:
            msg_type = findall(r'Message Types\s*:\s*(\w*)', info)[0]
            if msg_type == 'None':
                continue
            else:
                eid = findall(r'Endpoint ID\s*:\s*(\w*)', info)[0]
                uuid_line = findall(r'UUID.*', info)[0]
                uuid_list = findall(r'0x(\w+)', uuid_line)
                uuid = ''.join([s.rjust(2, '0') for s in uuid_list])
                eid_dict[uuid] = eid
        return eid_dict

    @classmethod
    def reboot_bmc(cls, ip=IP, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd_reboot = f"sshpass -p {BMC_PWD} ssh {BMC_NAME}@{ip} 'reboot'"
        print(cmd_reboot)
        CommandOperation.execute_command_with_error(cmd=cmd_reboot, cmd_execute_address=CmdExecuteAdressEnum)
        time.sleep(15)
        counter = 10
        while counter > 0:
            cmd_ping = f'ping {ip} -c 1'
            _, rtn_output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd_ping, cmd_execute_address=execute_addr)
            if '0% packet loss' in rtn_output:
                return True
            else:
                time.sleep(10)
        return False

    @classmethod
    def send_bmc_command(cls, ip, msg_type, command, *args, pldm_type=None, eid=EID,
                         execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m {msg_type} -c {command} '
        if pldm_type:
            cmd += f'-t {pldm_type} '
        if args:
            cmd += ' '.join(args)
        cmd += f' --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            return status, rtn_output
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='',
                result_info='指令执行失败')

    @classmethod
    def check_sensor_reading_para(cls, sensor, exp_size=0, ip=IP, key_word='', eid=EID, execute_addr='', exp_op=0,
                                  exp_evt_enable=0, exp_pres=1, exp_prev=0, exp_evt_state=1) -> int:
        status, sensor_dict = PldmTool.get_sensor_reading(
            ip=ip, eid=eid, sensor=sensor, execute_addr=execute_addr)
        if status != '0':
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口status参数',
                expect_info='0',
                result_info=status)
        data_size = int(sensor_dict.get('sensor_data_size'), 16)
        op_state = int(sensor_dict.get('sensor_op_state'), 16)
        evt_enable = int(sensor_dict.get('sensor_evt_msg_enable'), 16)
        pres_state = int(sensor_dict.get('pres_state'), 16)
        prev_state = int(sensor_dict.get('pres_state'), 16)
        event_state = int(sensor_dict.get('pres_state'), 16)
        if data_size != exp_size:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_data_size参数',
                expect_info=str(exp_size),
                result_info=str(data_size))
        if op_state != exp_op:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_op_state参数',
                expect_info=str(exp_op),
                result_info=str(op_state))
        if evt_enable != exp_evt_enable:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口sensor_evt_msg_enable参数',
                expect_info=str(exp_evt_enable),
                result_info=str(evt_enable))
        if pres_state != exp_pres:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口pres_state参数',
                expect_info=str(exp_pres),
                result_info=str(pres_state))
        if prev_state != exp_prev:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口prev_state参数',
                expect_info=str(exp_prev),
                result_info=str(prev_state))
        if event_state != exp_evt_state:
            CommonOperation.create_bug_problem(
                cls,
                key_word=key_word,
                description_word='校验PLDM_GetSensorReading接口prev_state参数',
                expect_info=str(exp_evt_state),
                result_info=str(event_state))
        data = int(sensor_dict.get('data'))
        return data

    @classmethod
    def set_mfg_info(cls, px=0):
        pn = ''.join(choices(digits + ascii_letters, k=16))
        sn = ''.join(choices(digits + ascii_letters, k=16))
        mfg_date = str(randint(2000, 2100)) + '-' + str(randint(1, 12)) + '-' + str(randint(1, 28))
        revision = ''.join(choices(digits, k=4))
        rework_date = str(randint(2000, 2100)) + '-' + str(randint(1, 12)) + '-' + str(randint(1, 28))
        mac_addr0 = '9C' + ''.join(choices(hexdigits, k=10))
        mac_addr1 = '9C' + ''.join(choices(hexdigits, k=10))
        cli_cmd = (
            f'{SXE2CLI64} /p{px} set mfginfo PN={pn} SN={sn} mfgDate={mfg_date} '
            f'revision={revision} reworkDate={rework_date} macAddr0={mac_addr0} '
            f'macAddr1={mac_addr1}')
        print(cli_cmd)
        _, output, _ = CommandOperation.execute_command_with_error(
            cmd=cli_cmd, cmd_execute_address=111)
        return output

    @classmethod
    def close_monitor(cls, ip=IP, execute_addr=CmdExecuteAdressEnum.SERVER.value):
        cmd_stop_monitor = f'sshpass -p {BMC_PWD} ssh {BMC_NAME}@{ip} touch /var/FWmode'
        CommandOperation.execute_command_with_error(cmd=cmd_stop_monitor, cmd_execute_address=execute_addr)
        time.sleep(25)

    @classmethod
    def set_threshold_continuously(cls, execute_addr=None):
        while True:
            threshold = randint(80, 120)
            cmd = f'{SXE2CLI64} /p0 set soctemp hthreshold={threshold}'
            # print(cmd)
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=cmd,
                cmd_execute_address=execute_addr
            )
            time.sleep(0.01)
            if 'Success' in output:
                print(cmd, '设置成功')
            else:
                print(cmd, '设置失败')
            # log.info(f'指令执行结果：\n{output}')


class MctpTools:

    @classmethod
    def get_eid(cls, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 2 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'MCTP GetEid 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['eid'] = findall(r'eid:(\w+)', rtn_output)[0]
                value['eidType'] = findall(r'eidType:(\w+)', rtn_output)[0]
                value['endpointType'] = findall(r'endpointType:(\w+)', rtn_output)[0]
                value['mediumSpecificInfo'] = findall(r'mediumSpecificInfo:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='MCTP GetEid',
                result_info='指令执行失败')

    @classmethod
    def get_uuid(cls, ip=IP, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 3 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'MCTP GetUuid 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = ''
            if status == '0':
                uuid_list = findall(r'uuid:(\w+)\s+(\w+)', rtn_output)[0]
                value = uuid_list[0].rjust(16, '0') + uuid_list[1].rjust(16, '0')
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='MCTP GetUuid',
                result_info='指令执行失败')

    @classmethod
    def get_msgtype_support(cls, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 5 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'MCTP GetMsgTypeSupport 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = []
            if status == '0':
                value = findall(r'Type\[\d]:\s*(\w+)', rtn_output)
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='MCTP GetMsgTypeSupport',
                result_info='指令执行失败')

    @classmethod
    def get_version_support(cls, ip, mctpmsgtype, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 4 --mctpmsgtype={mctpmsgtype} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'MCTP GetVersionSupport 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = []
            if status == '0':
                value = findall(r'ver\[\d]:\s*(\w+)', rtn_output)
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='MCTP GetVersionSupport',
                result_info='指令执行失败')

    @classmethod
    def get_vdm_support(cls, ip, mctpidset, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 0 -c 6 --mctpIdSet={mctpidset} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'MCTP GetVdmSupport 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['vendorIdSetSelector'] = findall(r'vendorIdSetSelector:(\w+)', rtn_output)[0]
                value['vendorIdFormat'] = findall(r'vendorIdFormat:(\w+)', rtn_output)[0]
                value['vendorIdData'] = findall(r'vendorIdData:(\w+)', rtn_output)[0]
                value['vendorSpecificData'] = findall(r'vendorSpecificData:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='MCTP GetVdmSupport',
                result_info='指令执行失败')


class PldmTool:
    @classmethod
    def set_tid_code_0(cls, ip, tid, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 1 --tid={tid} --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM SetTid TypeCode:0 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM SetTid TypeCode:0',
                result_info='指令执行失败')

    @classmethod
    def get_tid_code_0(cls, ip=IP, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 2 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM GetTid TypeCode:0 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = ''
            if status == '0':
                value = findall(r'Tid:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetTid TypeCode:0',
                result_info='指令执行失败')

    @classmethod
    def get_pldm_version(cls, ip, pldmtype, transferflag, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 3 --pldmtype={pldmtype} --transferflag={transferflag}'
               f' --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM GetPldmVersion 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['transferFlag'] = findall(r'transferFlag:(\w+)', rtn_output)[0]
                value['nextTransferHandle'] = findall(r'nextTransferHandle:(\w+)', rtn_output)[0]
                value['version'] = findall(r'version:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetPldmVersion',
                result_info='指令执行失败')

    @classmethod
    def get_pldm_types(cls, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 4 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM GetPldmTypes 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = []
            if status == '0':
                ori_type_lst = list(re.findall(
                    r'type\s*:\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)\s*(\w+)', rtn_output)[0])
                ori_type_lst.reverse()
                ori_type_str = ''.join(format(int(i, 16), '08b') for i in ori_type_lst)
                value = [format(i.start(), '02x') for i in finditer('1', ori_type_str[::-1])]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetPldmTypes',
                result_info='指令执行失败')

    @classmethod
    def get_pldm_command(cls, ip, pldmtype, typever, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 0 -c 5 --pldmtype={pldmtype} --typever={typever} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetPldmCommand 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = []
            if status == '0':
                code_str = ''
                for i in range(8):
                    code_re = re.findall(f'cmd\[{i}]:(\w+)', rtn_output)
                    if code_re:
                        code_str = format(int(code_re[0], 16), '08b') + code_str
                    else:
                        code_str = '00000000' + code_str
                value = [format(i.start(), '02x') for i in finditer('1', code_str[::-1])]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetPldmCommand',
                result_info='指令执行失败')

    @classmethod
    def set_tid_code_2(cls, tid, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 1 --tid={tid} --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM SetTid TypeCode:2 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM SetTid TypeCode:2',
                result_info='指令执行失败')

    @classmethod
    def get_tid_code_2(cls, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 2 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetTid TypeCode:0 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            if status == '0':
                value = findall(r'Tid:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetTid TypeCode:0',
                result_info='指令执行失败')

    @classmethod
    def get_uuid(cls, ip=IP, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 3 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetUuid 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = ''
            if status == '0':
                uuid_list = findall(r'uuid:(\w+)\s+(\w+)', rtn_output)[0]
                value = uuid_list[0].rjust(16, '0') + uuid_list[1].rjust(16, '0')
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetUuid',
                result_info='指令执行失败')

    @classmethod
    def set_event_receiver(cls, ip, evt_enable, addr_info, transport, eid='b',
                           execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 4 --evt_msg_global_enable={evt_enable} --transport={transport}'
               f' --addr_info={addr_info} --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM SetEventReceiver 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM SetEventReceiver',
                result_info='指令执行失败')

    @classmethod
    def get_event_receiver(cls, ip, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 5 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM GetEventReceiver 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['transport_protocol_type'] = findall(r'transport_protocol_type:(\w+)', rtn_output)[0]
                value['evt_receiver_addr'] = findall(r'evt_receiver_addr:(\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetEventReceiver',
                result_info='指令执行失败')

    @classmethod
    def platform_event_message(cls, ip, pldmevtfile, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c a --pldmevtfile={pldmevtfile} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM PlatformEventMessage 指令执行结果：\n{rtn_output}')
        re_event = re.findall(r'\w{4}-\w+-\w+\s\w+:\w+:\w+\sEvtShow:.*?prev_evt_state:\w{3}', rtn_output, re.S)
        # print(re_event)
        if re_event:
            event = re_event[-1]
            evt_dict = dict()
            format_version = re.findall(r'format_version:(\w+)', event)[0]
            if int(format_version, 16) != 1:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word='BMC',
                    description_word='PLDM PlatformEventMessage 指令format_version参数错误',
                    expect_info='0x01', result_info=format_version)
            evt_class = re.findall(r'evtClass:(\w+)', event)[0]
            if int(evt_class) != 0:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word='BMC',
                    description_word='PLDM PlatformEventMessage 指令evt_class参数错误',
                    expect_info='0', result_info=evt_class)
            sensor_offset = re.findall(r'sensor_offset:(\w+)', event)[0]
            if int(sensor_offset, 16) != 1:
                CommonOperation.create_bug_problem(
                    cls,
                    key_word='BMC',
                    description_word='PLDM PlatformEventMessage 指令sensor_offset参数错误',
                    expect_info='0x01', result_info=sensor_offset)

            evt_dict['evt_time'] = re.findall(r'(\w{4}-\w+-\w+\s\w+:\w+:\w+)\sEvtShow', event)[0]
            evt_dict['tid'] = re.findall(r'tid:(\w+)', event)[0]
            evt_dict['sensor_id'] = re.findall(r'sensor_id:(\w+)', event)[0]
            evt_dict['enum_sensor_evt_class'] = re.findall(r'enum_sensor_evt_class:(\w+)', event)[0]
            evt_dict['evt_state'] = re.findall(r'evt_state:(\w+)', event)[0]
            print(evt_dict)

    @classmethod
    def get_sensor_reading(cls, ip, sensor, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 11 --sensor={sensor} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetSensorReading 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['sensor_data_size'] = findall(r'sensor_data_size:(-?\w+)', rtn_output)[0]
                value['sensor_op_state'] = findall(r'sensor_op_state:(-?\w+)', rtn_output)[0]
                value['sensor_evt_msg_enable'] = findall(r'sensor_evt_msg_enable:(-\w+|\w+)', rtn_output)[0]
                value['pres_state'] = findall(r'pres_state:(-\w+|\w+)', rtn_output)[0]
                value['prev_state'] = findall(r'prev_state:(-\w+|\w+)', rtn_output)[0]
                value['evt_state'] = findall(r'evt_state:(-\w+|\w+)', rtn_output)[0]
                value['data'] = findall(r'data:(-\w+|\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetSensorReading',
                result_info='指令执行失败')

    @classmethod
    def get_sensor_thres_holds(cls, sensor, ip=IP, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1  -t 2 -c 12 --sensor={sensor} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetSensorThresHolds 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['sensor_data_size'] = findall(r'sensor_data_size:(-?\w+)', rtn_output)[0]
                value['upper_thold_warning'] = findall(r'upper_thold_warning:(-?\w+)', rtn_output)[0]
                value['upper_thold_crit'] = findall(r'upper_thold_crit:(-?\w+)', rtn_output)[0]
                value['upper_thold_fatal'] = findall(r'upper_thold_fatal:(-?\w+)', rtn_output)[0]
                value['lower_thold_warning'] = findall(r'lower_thold_warning:(-?\w+)', rtn_output)[0]
                value['lower_thold_crit'] = findall(r'lower_thold_crit:(-?\w+)', rtn_output)[0]
                value['lower_thold_fatal'] = findall(r'lower_thold_fatal:(-?\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetSensorThresHolds',
                result_info='指令执行失败')

    @classmethod
    def set_sensor_thres_holds(cls, ip, sensor, fatal_h, fatal_l=None, warn_h=None, warn_l=None,
                               eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        para_fatal_h = f' --upper_fatal={fatal_h}'
        para_fatal_l = f' --lower_fatal={fatal_l}' if fatal_l else ''
        para_warn_h = f' --upper_warn={warn_h}' if warn_h else ''
        para_warn_l = f' --lower_warn={warn_l}' if warn_l else ''
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 13 --sensor={sensor}{para_fatal_h}{para_fatal_l}'
               f'{para_warn_h}{para_warn_l} --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM SetSensorThresHolds 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM SetSensorThresHolds',
                result_info='指令执行失败')

    @classmethod
    def get_state_sensor_reading(cls, ip, sensor, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 21 --sensor={sensor} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetStateSensorReading 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['sensor_op_state'] = findall(r'sensor_op_state:(-?\w+)', rtn_output)[0]
                value['pres_state'] = findall(r'pres_state:(-?\w+)', rtn_output)[0]
                value['prev_state'] = findall(r'prev_state:(-?\w+)', rtn_output)[0]
                value['evt_state'] = findall(r'evt_state:(-?\w+)', rtn_output)[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetStateSensorReading',
                result_info='指令执行失败')

    @classmethod
    def set_numeric_effector_value(cls, ip, effecter, numeric_value, eid=EID,
                                   execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 2 -c 31 --effecter={effecter} --numeric_value={numeric_value} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM SetNumericEffectorValue 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM SetNumericEffectorValue',
                result_info='指令执行失败')

    @classmethod
    def get_fru_record_table_metadata(cls, ip=IP, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 4 -c 1 --addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}'
        print(cmd)
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetFruRecordTableMetadata 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                value['fru_data_major_version'] = findall(r'fru_data_major_version:(\w+)', rtn_output)[0]
                value['fru_data_minor_version'] = findall(r'fru_data_minor_version:(\w+)', rtn_output)[0]
                value['fru_sbl_max_size'] = findall(r'fru_sbl_max_size:(\w+)', rtn_output)[0]
                value['fru_sbl_length'] = findall(r'fru_sbl_length:(\w+)', rtn_output)[0]
                value['total_number_of_record_set_ids_in_sbl'] = (
                    findall(r'total_number_of_record_set_ids_in_sbl:(\w+)', rtn_output))[0]
                value['total_number_of_records_in_sbl'] = (
                    findall(r'total_number_of_records_in_sbl:(\w+)', rtn_output))[0]
                value['fru_data_structure_sbl_integrity_checksum'] = (
                    findall(r'fru_data_structure_sbl_integrity_checksum:(-?\w+|\w+)', rtn_output))[0]
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetFruRecordTableMetadata',
                result_info='指令执行失败')

    @classmethod
    def get_fru_record_table(cls, frusize, transferflag, eid=EID, ip=IP,
                             execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 4 -c 2 --frusize={frusize} --transferflag={transferflag} '
               f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd, cmd_execute_address=execute_addr)
        print(cmd)
        log.info(f'PLDM GetFruRecordTable 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = {}
            if status == '0':
                line_lst = findall('.+', rtn_output)
                record_index = 0
                field_index = 0
                for line in line_lst:
                    re_record = re.findall(r'record\[(\w+)]', line)
                    if re_record:
                        record_index = 'record ' + re_record[0]
                        value[record_index] = {}
                        value[record_index]['Fields'] = {}
                        continue
                    re_record_set_id = re.findall(r'recordSetId::(\w+)', line)
                    if re_record_set_id:
                        value[record_index]['recordSetId'] = re_record_set_id[0]
                        continue
                    re_record_type = re.findall(r'recordType:(\w+)', line)
                    if re_record_type:
                        value[record_index]['recordType'] = re_record_type[0]
                        continue
                    re_fields_num = re.findall(r'fieldsNum:(\w+)', line)
                    if re_fields_num:
                        value[record_index]['fieldsNum'] = re_fields_num[0]
                        continue
                    re_encoding_type = re.findall(r'EncodingType:(\w+)', line)
                    if re_encoding_type:
                        value[record_index]['EncodingType'] = re_encoding_type[0]
                        continue
                    re_fields = re.findall(r'Fields\[(\w+)]', line)
                    if re_fields:
                        field_index = re_fields[0]
                        value[record_index]['Fields'][field_index] = {}
                        continue
                    re_field_type = re.findall(r'fieldType:(\w+)', line)
                    if re_field_type:
                        value[record_index]['Fields'][field_index]['fieldType'] = re_field_type[0]
                        continue
                    re_field_type = re.findall(r'fieldLength:(\w+)', line)
                    if re_field_type:
                        value[record_index]['Fields'][field_index]['fieldLength'] = re_field_type[0]
                        continue
                    re_field = re.findall(r'field:(.*)', line)
                    if re_field:
                        value[record_index]['Fields'][field_index]['field'] = re_field[0]
                        continue
            # return status, value
            return json.dumps(value, indent=2, separators=(',', ':'))

        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetFruRecordTable',
                result_info='指令执行失败')

    @classmethod
    def firmware_upgrade(cls, pkg_path, ip=IP, eid=EID, skip_ip='10.22.114.229',
                         execute_addr=CmdExecuteAdressEnum.SERVER):
        pkg_name = pkg_path.split('/')[-1]

        cmd_copy = f'sshpass -p {BMC_PWD} scp {pkg_path} {BMC_NAME}@{ip}:/var/'
        cmd_mv = f"sshpass -p {BMC_PWD} ssh {BMC_NAME}@{ip} 'cd /var/; mv {pkg_name} image.pldm'"
        CommandOperation.execute_command_with_error(cmd=cmd_copy, cmd_execute_address=execute_addr)
        CommandOperation.execute_command_with_error(cmd=cmd_mv, cmd_execute_address=execute_addr)

        if skip_ip:
            cmd_upgrade = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={ip} --name={BMC_NAME_NET} '
                           f'--passwd={BMC_PWD_NET} -d {skip_ip}')
        else:
            cmd_upgrade = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 5 -c 0 --addr={ip} --name={BMC_NAME_NET} '
                           f'--passwd={BMC_PWD_NET}')
        CommandOperation.execute_command_with_error(cmd=cmd_upgrade, cmd_execute_address=execute_addr)

    @classmethod
    def get_oem_log(cls, ip, log_type, eid=EID, execute_addr=CmdExecuteAdressEnum.SERVER):
        cmd_upgrade = (f'{BMC_TOOL_PATH} -e {eid} -m 1 -t 3f -c {log_type} '
                       f'--addr={ip} --name={BMC_NAME} --passwd={BMC_PWD}')
        _, rtn_output, _ = CommandOperation.execute_command_with_error(
            cmd=cmd_upgrade, cmd_execute_address=execute_addr)
        log.info(f'PLDM GetOemLog 指令执行结果：\n{rtn_output}')
        status_lst = findall(r'status:(\w+)', rtn_output)
        if status_lst:
            status = status_lst[0]
            value = None
            return status, value
        else:
            CommonOperation.create_bug_problem(
                cls,
                key_word='BMC',
                description_word='PLDM GetOemLog',
                result_info='指令执行失败')

    @classmethod
    def set_cli_threshold(cls):
        while True:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SXE2CLI64} /p0 set soctemp hthreshold={choice(range(66, 80))}',
                cmd_execute_address=CmdExecuteAdressEnum.SERVER
            )
            print(output)

    @classmethod
    def set_cli_lldp(cls):
        while True:
            _, output, _ = CommandOperation.execute_command_with_error(
                cmd=f'{SXE2CLI64} /p0 custom sxe lldpenable port=0 enable={choice([0, 1])}',
                cmd_execute_address=CmdExecuteAdressEnum.SERVER
            )
            print(output)






