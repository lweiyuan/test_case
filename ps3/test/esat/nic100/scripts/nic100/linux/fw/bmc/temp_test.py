import paramiko


class CommonOperation(object):

    @classmethod
    def create_bug_problem(cls, case_cls, key_word: str, description_word: str,
                           result_info: str = '', expect_info: str = ''):
        """
        author: weiyuan
        date: 2022年7月26日20:49:11
        description: 描述bug信息
        :param case_cls:
        :param key_word: 功能模块
        :param description_word: 异常描述信息
        :param result_info: 实际结果
        :param expect_info: 预期结果
        """
        print(description_word)


class CommandOperation:
    @classmethod
    def execute_command_with_error(cls, cmd, cmd_execute_address):
        # 创建SSH对象
        ssh = paramiko.SSHClient()
        # 允许连接不在know_hosts文件中的主机
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # 连接服务器
        ssh.connect(hostname='10.22.114.228', port=22, username='root', password='Tianjian;123')
        # ssh.connect(hostname='10.17.132.223', port=22, username='root', password='Tianjian;123')
        # 执行命令
        stdin, stdout, stderr = ssh.exec_command(cmd)
        # 获取命令结果
        #
        result = stdout.read()

        result_str = result.decode("utf-8")

        # 关闭连接
        ssh.close()
        return 0, result_str, 0


class log:
    @staticmethod
    def info(mess):
        print(mess)
