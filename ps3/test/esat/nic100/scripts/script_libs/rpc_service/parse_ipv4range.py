import ipaddress


def ip4_a2n(ip: str) -> int:
    """将str的IP4地址转成int"""
    return int(ipaddress.IPv4Address(ip))


def sort_ip4list(ips: list[str], reverse=False) -> [str]:
    """将IP地址列表进行排序"""
    ip_set = set()
    for ip in ips:
        ip_set.add(ip4_a2n(ip))

    ip_list = list(ip_set)
    ip_list.sort(reverse=reverse)

    new_list = []
    for n in ip_list:
        new_list.append(ip4_n2a(n))

    return new_list


def ip4_n2a(num: int) -> str:
    """将int的IP4地址转成str"""
    return str(ipaddress.IPv4Address(num))


def _parse_ip4range_minus(s: str) -> list[str]:
    """解析字符串表示的IP地址范围为IP地址列表
        例如：
            192.168.1.1-25
            192.168.1.* (表示 192.168.1.1-254)
    """
    s = s.replace('*', '1-254')
    sections = s.split('-')
    if len(sections) != 2:
        return []

    ip_fields = sections[0].split('.')
    if len(ip_fields) != 4:
        return []

    ip_list = []

    sta, end = ip4_a2n(sections[0]), ip4_a2n('.'.join([ip_fields[0], ip_fields[1], ip_fields[2], sections[1]]))
    for n in range(sta, end + 1):
        ip_list.append(ip4_n2a(n))

    return ip_list


def _parse_ip4range_net(s: str) -> list[str]:
    """将IP地址网络转换成IP地址列表
        例如：
            192.168.1.0/24 （如果使用 192.168.1.1/24 则会报错，因为主机位必须为 0 ）
    """
    net = ipaddress.ip_network(s)

    ip_list = []
    for ip in net.hosts():
        ip_list.append(str(ip))
    return ip_list


def parse_ip4range(iprange: str) -> list[str]:
    """解析字符串表示的IP地址范围，多段用逗号分隔"""
    ips = []
    for section in iprange.split(','):
        if '-' in section or '*' in section:
            ips += _parse_ip4range_minus(section)
        else:
            ips += _parse_ip4range_net(section)

    return sort_ip4list(ips)
