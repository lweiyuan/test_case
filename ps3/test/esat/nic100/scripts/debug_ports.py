import add_syspath
from scripts.script_libs.command_line_args_parse import CommandLineArgsParse

print("server_port:", CommandLineArgsParse.get_server_port())
print("client_port:", CommandLineArgsParse.get_client_port())
print("server_ip:", CommandLineArgsParse.get_server_ip())
print("client_ip:", CommandLineArgsParse.get_client_ip())
print("server_nic_ip:", CommandLineArgsParse.get_server_nic_ip())
print("client_nic_ip:", CommandLineArgsParse.get_client_nic_ip())
