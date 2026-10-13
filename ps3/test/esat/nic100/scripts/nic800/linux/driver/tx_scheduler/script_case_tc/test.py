import concurrent.futures
import time
from scripts.script_libs.log import log
from scripts.script_libs.enums import CmdExecuteAdressEnum

def run_iperf_task(task_config: dict) -> tuple:
    """单个打流任务函数，供线程池异步调度执行"""
    port = task_config["port"]
    priority = task_config["priority"]
    log_path = task_config["log_path"]

    try:
        iperf_runner = IperfOperation(
            case_cls=task_config.get("case_cls", "AsyncIperfTest"),
            iperf_version=task_config.get("iperf_version", 3),
            test_device_name=task_config.get("test_device_name", "ens4f0"),
            cmd_execute_address=task_config.get("cmd_execute_address", CmdExecuteAdressEnum.SERVER.value),
            dct_device_name=task_config.get("dct_device_name", "ens4f1"),
            dct_cmd_execute_address=task_config.get("dct_cmd_execute_address", CmdExecuteAdressEnum.CLIENT.value),
            send_time=task_config.get("send_time", 15),
            time_sleep=1,
            parallel_num=task_config.get("parallel_num", 2),
            port_num=port,
            priority=priority,
            use_tcp=False,
            iperf_log_file=log_path
        )

        # 1. 服务端后台启动守护进程
        iperf_runner.set_iperf_demon(
            iperf_version=iperf_runner.iperf_version,
            connect_port=str(port),
            cmd_execute_address=iperf_runner.dct_cmd_execute_address
        )
        time.sleep(1)  # 等待端口监听成功

        # 2. 客户端发起 UDP 打流
        rtn_code, rtn_stdout = iperf_runner.udp_flow_bandwidth(
            dst_address=task_config["target_ip"],
            bandwidth=task_config.get("bandwidth", "100"),
            parallel_num=iperf_runner.parallel_num,
            cmd_execute_address=iperf_runner.cmd_execute_address,
            iperf_log_file=log_path
        )
        return port, rtn_code, rtn_stdout

    except Exception as exc:
        log.error(f"[Port {port}] 打流任务发生异常: {exc}")
        return port, -1, str(exc)


if __name__ == "__main__":
    target_ip = "192.168.10.100"

    # 支持配置多条不同 Priority 与 Port 的并发打流任务
    tasks_config = [
        {"priority": 3, "port": 5201, "target_ip": target_ip, "bandwidth": "100", "log_path": "/tmp/iperf_p3_5201.log"},
        {"priority": 6, "port": 5202, "target_ip": target_ip, "bandwidth": "200", "log_path": "/tmp/iperf_p6_5202.log"},
        {"priority": 1, "port": 5203, "target_ip": target_ip, "bandwidth": "50",  "log_path": "/tmp/iperf_p1_5203.log"},
    ]

    max_workers = min(len(tasks_config), 8)

    # 建立异步线程池并提交任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 使用字典映射 Future 对象与端口，便于结果追踪
        future_to_port = {
            executor.submit(run_iperf_task, config): config["port"]
            for config in tasks_config
        }

        # as_completed 按照任务完成的顺序异步获取结果
        for future in concurrent.futures.as_completed(future_to_port):
            port = future_to_port[future]
            try:
                res_port, status_code, stdout = future.result()
                log.info_caller(f"端口 [{res_port}] 打流任务执行完毕，退出码: {status_code}")
            except Exception as exc:
                log.error(f"端口 [{port}] 任务产生未捕获异常: {exc}")