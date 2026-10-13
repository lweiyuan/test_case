import paramiko
import threading
import queue
import time
import socket
import logging
from scripts.script_libs import log


class SSHConnectionPool:
    def __init__(
            self,
            host,
            port=22,
            username='root',
            password=None,
            key_filename=None,
            key_password=None,
            max_connections=5,
            socket_timeout=10,
            cmd_timeout=30,
            pool_timeout=15,
            policy=paramiko.AutoAddPolicy  # 主机密钥验证策略
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.key_password = key_password
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.cmd_timeout = cmd_timeout
        self.pool_timeout = pool_timeout
        self.policy = policy
        self.pool = queue.Queue(max_connections)
        self.lock = threading.Lock()
        # 初始化连接池
        err = 0

        for i in range(2):
            try:
                log.info(f"开始实例化第{i}个ssh长连接对象")
                self.pool.put(self._create_connection())
                time.sleep(0.1)
            except Exception as e:
                err += 1

                log.error(e)
                time.sleep(3)

        if err > 2:
            raise Exception(f"SSH连接失败")

    def _create_connection(self):
        """创建 SSH 连接（支持多种认证方式）"""
        ssh = paramiko.SSHClient()
        paramiko.util.get_logger('paramiko.transport').setLevel(logging.WARNING)
        ssh.set_missing_host_key_policy(self.policy())
        try:
            # 构建连接参数
            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": self.socket_timeout
            }
            # 选择认证方式
            if self.key_filename:
                connect_kwargs["key_filename"] = self.key_filename
                if self.key_password:
                    connect_kwargs["password"] = self.key_password
            else:
                connect_kwargs["password"] = self.password
                # 建立连接
            ssh.connect(**connect_kwargs)
            transport = ssh.get_transport()
            transport.set_keepalive(30)
            log.info('实例化ssh连接对象成功')
            return transport
        except (socket.timeout, paramiko.SSHException) as e:
            raise Exception(f"SSH连接失败: {str(e)}")

    def get_connection(self):
        """获取连接（带超时和动态扩容）"""
        try:
            # 连接池中没有新连接时直接创建新的
            if self.pool.qsize() > 0:
                conn = self.pool.get(block=True, timeout=self.pool_timeout)
            else:
                return self._create_connection()

            if not conn.is_active():
                try:
                    conn.close()
                except:
                    pass
                log.error("发生错误: 从连接池中获取到了一个非活动状态的连接,开始重试")
                conn = self._create_connection()
            # log.debug('获取到ssh连接对象,连接池中剩余' + str(self.pool.qsize()))
            return conn
        except queue.Empty:
            with self.lock:  # 线程安全扩容
                if self.pool.qsize() < self.max_connections:
                    return self._create_connection()
            raise TimeoutError(f"获取连接超时 ({self.pool_timeout}s)")

    def release_connection(self, conn):
        """归还连接（自动检测有效性）"""
        if conn.is_active() and self.pool.qsize() < self.max_connections:
            self.pool.put(conn)
            # log.debug("连接归还成功")
        else:
            self.close_conn(conn)
            # log.info("检查到本次释放的连接对象已被关闭,开始重新实例化")
            # self.pool.put(self._create_connection())

    def close_conn(self, conn):
        """关闭"""
        try:
            conn.close()
        except Exception as e:
            log.info(e)

    def execute_command(self, conn, command, cmd_timeout=None):
        """
        执行SSH命令
        :param conn:
        :param command:
        :param cmd_timeout: 超时时间/秒
        :return: tuple
        """
        if not cmd_timeout:
            cmd_timeout = self.cmd_timeout

        """（带超时控制）"""
        ssh = paramiko.SSHClient()
        ssh._transport = conn
        stdin, cmd_output, cmd_stderr = ssh.exec_command(command, timeout=cmd_timeout)

        if cmd_output:
            # 当cmd_output有效时，获取返回错误码
            output = cmd_output.read()
            cmd_code = cmd_output.channel.recv_exit_status()
            cmd_output = output.decode(errors='ignore')
        if cmd_stderr:
            cmd_stderr = cmd_stderr.read()
        # 如果命令错误输出不为空，表明该指令执行失败，打印error信息
        if isinstance(cmd_stderr, bytes):
            cmd_stderr = cmd_stderr.decode().rstrip('\n').rstrip()
        if isinstance(cmd_output, str):
            # 此处去除命令返回结果中最后一个换行符
            cmd_output = cmd_output.rstrip('\n').rstrip()

        return cmd_code, cmd_output, cmd_stderr

    def close_all(self):
        """清理所有连接"""
        while not self.pool.empty():
            conn = self.pool.get()
            try:
                conn.close()
            except:
                pass


# ------------------- 使用示例 -------------------


def worker(pool, command, timeout):
    try:
        conn = pool.get_connection()
        stdout, stderr = pool.execute_command(conn, command, timeout)
        print(f"输出: {stdout}")
    except TimeoutError as e:
        print(f"操作失败: {str(e)}")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        pool.release_connection(conn)


if __name__ == "__main__":
    # 场景1：密钥登录 + 自动信任新主机
    pool_key = SSHConnectionPool(
        host="192.168.1.100",
        username="ubuntu",
        key_filename="/home/user/.ssh/id_rsa",
        max_connections=3
    )

    # 场景2：加密密钥登录
    pool_encrypted_key = SSHConnectionPool(
        host="192.168.1.101",
        username="admin",
        key_filename="/path/to/encrypted_key",
        key_password="mypassword",
        policy=paramiko.WarningPolicy  # 仅警告未知主机
    )

    # 场景3：密码登录 + 严格模式
    pool_password = SSHConnectionPool(
        host="192.168.1.102",
        username="root",
        password="ssh_password",
        policy=paramiko.RejectPolicy,  # 需预配置known_hosts
        socket_timeout=5
    )

    # 并发测试
    commands = ["hostname", "sleep 15", "df -h"] * 2  # 测试6个任务
    threads = []
    for cmd in commands:
        t = threading.Thread(target=worker, args=(pool_key, cmd))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    # 清理连接池
    pool_key.close_all()
    pool_encrypted_key.close_all()
    pool_password.close_all()
