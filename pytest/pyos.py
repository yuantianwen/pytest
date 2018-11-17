#!/usr/bin/python
#coding=utf-8
from common import LOG,ssh,_mess_part

testExistsCmd = "test -f /opt/huawei/db"
testMountCmd = "mount|grep '/opt/huawei'|wc -l"

def checkEnvReady(param):
    hosts = param[0]
    pkgs = param[1]
    for h in hosts.values():
        print h
        LOG('GREEN','Target Host:%s'%(h.ip))
        rssh = ssh(h.ip,h.user,passwd=h.passwd)
        # 检查安装环境是否具备
        # 1.检查目录是否挂载
        LOG('GREEN','Check whether mount point /opt/huawei is exists')
        rtn = rssh.ssh_run(testMountCmd)
        if int(rtn.split(_mess_part)[1]) < 1:
            LOG('RED','Failure')
        else:
            LOG('GREEN',"OK")
        # 2.检查相关包是否安装
        for pkg in pkgs:
            LOG('GREEN','Check whether OS Dependence Package is installed:%s'%(pkg))
            rtn = rssh.ssh_run('rpm -qa|grep %s|wc -l'%(pkg))
            if int(rtn.split(_mess_part)[1]) < 1:
                LOG('RED','Failure')
            else:
                LOG('GREEN',"OK")

def fixEnv(hosts):
    for hostinfo in hosts:
        LOG('GREEN','Target Host:%s'%(hostinfo[0]))
        rssh = ssh(hostinfo,ROOT_USER,passwd=ROOT_USER_PASSWORD)
        # 检查安装环境是否具备
        # 判断/opt/huawei目录是否挂载
        LOG('GREEN','Check if mount point /opt/huawei is exists')
        rtn = rssh.ssh_run(testMountCmd)
        if int(rtn.split(_mess_part)[1]) < 1:
            # 挂载磁盘/opt/huawei
            LOG('GREEN','Begin to Create Mount Point:/opt/huawei')
            rssh.ssh_run("mkfs.ext4 /dev/nvme1n1")
            rssh.ssh_run("mkdir -p /opt/huawei")
            rssh.ssh_run("mount /dev/nvme1n1 /opt/huawei")

        # 安装os相关包
        for pkg in osDependencePkgs:
            LOG('GREEN','Install OS Dependence Package:%s'%(pkg))
            rssh.ssh_run('yum -y install %s'%(pkg))


def set_root_passwd(hosts):
    for hostinfo in hosts:
        ip = hostinfo[0]
        LOG('GREEN','='*60)
        LOG('GREEN','Target Host:%s'%(ip))
        rssh = ssh(hostinfo,USER_NAME,pem=USER_PEM)

        # 修改root密码*
        LOG('GREEN','Set the root user password')
        rssh.ssh_run("echo '%s'|sudo passwd --stdin root"%(ROOT_USER_PASSWORD))

        # 修改ssh配置文件
        LOG('GREEN','Modify ssh configuration file:/etc/ssh/sshd_config')
        rssh.ssh_run("sudo sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/g' %s" % ("/etc/ssh/sshd_config"))

        # 重启sshd服务
        LOG('GREEN','Restart sshd service')
        rssh.ssh_run("sudo service sshd restart")

        # 本地ssh登录测试
        LOG('GREEN','Run a connection test using root user')
        rssh = ssh(hostinfo,user=ROOT_USER,passwd=ROOT_USER_PASSWORD)
        rssh.ssh_run("echo")

def change_root_passwd(param):
    hosts = param[0]
    new_pwd = param[1]
    for h in hosts.values():
        print h
        LOG('GREEN','Target Host:%s'%(h.ip))
        rssh = ssh(h.ip,h.user,passwd=h.passwd)
        # 修改root密码*
        LOG('GREEN','Set the root user password')
        rssh.ssh_run("echo '%s'|sudo passwd --stdin root"%(new_pwd))

def run_commander(param):
    hosts = param[0]
    cmd = param[1]
    for h in hosts.values():
        LOG('GREEN','='*60)
        LOG('GREEN','Target Host:%s'%(h.ip))
        rssh = ssh(h.ip,user=h.user,passwd=h.passwd)
        rssh.ssh_run(cmd)
