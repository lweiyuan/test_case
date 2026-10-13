import socket
import time
import argparse

parser = argparse.ArgumentParser(description="Test.")
# 添加命令行参数中的protocol选项,用于指定TCP/UDP
parser.add_argument('--proto', type=str, help='指定TCP UDP')
# 添加命令行参数中的ipv选项，用于指定IPV4/IPV6,默认ipv4
parser.add_argument('--ipv', default=4, type=int, help='指定ipv4 ipv6')
# 添加命令行参数中的server node ip选项,这里就是本机的测试网卡
parser.add_argument('--snip', type=str, help='指定收端测试网卡的ip')
# 添加命令行参数中的server port选项，这里就是本机的测试端口号
parser.add_argument('--sp', type=int, help='指定 server port')
# 添加命令行参数中的数据选项，默认为空，与file二选一
parser.add_argument('--data', type=str, help='指定数据', default='None')
# 添加命令行参数中的文件选项，默认为空，与data二选一
parser.add_argument('--file', type=str, help='指定文件路径', default='None')
args = parser.parse_args()

udp_socket, tcp_socket = None, None

if args.ipv == 4 and args.proto.lower() == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
elif args.ipv == 6 and args.proto.lower == 'udp':
    udp_socket = socket.socket(family=socket.AF_INET6, type=socket.SOCK_DGRAM)
elif args.ipv == 4 and args.proto.lower() == 'tcp':
    tcp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
else:
    addrinfo = socket.getaddrinfo(args.snip, args.sp, 0, 0)[0]
    tcp_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

if udp_socket:
    udp_socket.bind((args.snip, args.sp))
    receive_data = ''
    begin_time = time.time()

    while True:
        buffer_size = 32 * 1024
        content, addr = udp_socket.recvfrom(buffer_size)
        now_time = time.time()

        if 'SXETESTEND' not in content.decode():
            receive_data += content.decode()
            continue

            # 如果收到结束标记，中断循环
        elif 'SXETESTEND' in content.decode():
            receive_data += content.decode().replace('SXETESTEND', '')
            break

        # 如果循环超过120s，中断循环，防止网卡问题导致死循环
        elif now_time - begin_time > 120:
            break

        # 其他情形
        else:
            continue

    udp_socket.close()
    print(receive_data)

if tcp_socket:
    buffer_size = 40960 * 100
    while True:
        try:
            if args.ipv == 4:
                tcp_socket.bind((args.snip, args.sp))
                tcp_socket.listen(128)
                break
            else:
                tcp_socket.bind(addrinfo[-1])
                tcp_socket.listen(128)
                break
        except Exception as e:
            print('recv', e)
            time.sleep(1)


    receive_data = ''
    begin_time = time.time()
    client_socket, clientAddr = tcp_socket.accept()

    while True:
        content = client_socket.recv(buffer_size)
        #content, addr = client_socket.recvfrom(buffer_size)
        now_time = time.time()

        # 如果没有看到结束标记，继续循环获取
        if 'SXETESTEND' not in content.decode():
            receive_data += content.decode()
            continue

        # 如果收到结束标记，中断循环
        elif 'SXETESTEND' in content.decode():
            receive_data += content.decode().replace('SXETESTEND', '')
            break

        # 如果循环超过60s，中断循环，防止网卡问题导致死循环
        elif now_time - begin_time > 60:
            break

        # 其他情形
        else:
            continue

    client_socket.close()
    tcp_socket.close()
    print(receive_data)
