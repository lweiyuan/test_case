#!/bin/bash

# 定义变量
LSIP="10.17.22.134"
LSAC="framework"
# SIP="172.17.30.127"
# CIP="172.17.30.125"
SIP="10.22.66.227"
CIP="10.22.66.229"

# testcase_path="/home/helei/ty_nic100/test/esat/nic100/scripts/nic100/linux/rdma/kernel/io/nic_linux_rdma_kernel_io_r_06_16_001_001_read_inv_and_reg_wr.py"
testcase_path="
/home/ps3/test/esat/nic100/scripts/nic100/linux/rdma/kernel/io/nic_linux_rdma_kernel_io_f_06_16_002_001_vf_interface_ib_sge_length.py
"

# testcase_path="nic100/linux/rdma/kernel/io/nic_linux_rdma_kernel_io_f_06_16_001_001_interface_ib_sge_length.py"
# testcase_path="nic100/linux/rdma/kernel/mr/script_base_rdmak_mr.py"
# testcase_path="nic100/linux/rdma/kernel/qp/script_base_krdma_qp.py"

# testcase_path="nic100/linux/rdma/kernel/nvme/script_base_nvmeof_io.py"
# testcase_path="nic100/linux/rdma/kernel/pd/nic_linux_rdma_kernel_pd_f_06_11_001_008_same_pf_diff_vf_create_pd.py"
# testcase_path="/home/helei/ty_nic100/test/esat/nic100/scripts/nic100/linux/rdma/kernel/io/nic_linux_rdma_kernel_io_f_06_16_001_001_interface_ib_sge_length.py"


HC=0
TE=0
TO=10
TP=3322
TIMEOUT=1
LST=False
SNICM="centos"
CNICM="centos"
SBMCIP=None
SUNAME=None
SUPASSWD="None"
CBMCIP=None
CUNAME=None
CUPASSWD="None"

mkdir -p outputs/scripts

#打开被测服务器的ssh 的 3322端口
# echo "Opening SSH port 3322 on SIP server..."
# ssh $SIP "sudo firewall-cmd --zone=public --add-port=3322/tcp --permanent"
# ssh $SIP "sudo firewall-cmd --reload"

# echo "Opening SSH port 3322 on CIP server..."
# ssh $CIP "sudo firewall-cmd --zone=public --add-port=3322/tcp --permanent"
# ssh $CIP "sudo firewall-cmd --reload"

# 执行 Python 脚本并传递变量
echo "python3 $testcase_path \
    --lsip $LSIP --lsac $LSAC --sip $SIP --snicip $SIP --cip $CIP --cnicip $CIP \
    --hc $HC --te $TE --to $TO --tp $TP --timeout $TIMEOUT --lst $LST \
    --snicm $SNICM --cnicm $CNICM --sbmcip $SBMCIP --suname $SUNAME --supasswd $SUPASSWD \
    --cbmcip $CBMCIP --cuname $CUNAME --cupasswd $CUPASSWD"

python3 $testcase_path \
    --lsip $LSIP --lsac $LSAC --sip $SIP --snicip $SIP --cip $CIP --cnicip $CIP \
    --hc $HC --te $TE --to $TO --tp $TP --timeout $TIMEOUT --lst $LST \
    --snicm $SNICM --cnicm $CNICM --sbmcip $SBMCIP --suname $SUNAME --supasswd $SUPASSWD \
    --cbmcip $CBMCIP --cuname $CUNAME --cupasswd $CUPASSWD
