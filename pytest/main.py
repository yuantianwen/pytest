#!/usr/bin/python
# coding=utf-8
import os
import sys
import getopt
import time
from collections import namedtuple
import ConfigParser

from pyos import *
from pymysql import *
from pysysbench import *

from common import LOG,ssh,_mess_part,ArtFont,TextColor


deployDir = "/root/"
SoftDir = "/root/source/"
mysqlDataDir = "/opt/huawei/"
os_depend_pkgs = ('numactl','autoconf','git')
mysqlInstallPkgs = ('MySQL-server-5.6.38-1.el7.x86_64.rpm','MySQL-client-5.6.38-1.el7.x86_64.rpm')
USER_NAME = "cloud-user"
USER_PEM = "/root/mysql.pem"
ROOT_USER="root"
ROOT_USER_PASSWORD = "Huawei@123"

ALL_HOSTS={}
MYSQL_HOSTS={}
MYSQL_HOSTS_MASTER=[]
MYSQL_HOSTS_SLAVE=[]
SYSBENCH_HOSTS=[]

SYSBENCH_JOBS={}


def help():
    helpinfo="Usage: python ssh.py"

def displaymenu(funcs):
    #print "="*60
    #print "="*4 + ArtFont.renderText("DB Test Tool").center(52) + "="*4
    #print "="*60
    print ArtFont.renderText("DB Test Tool")
    print TextColor.green("Welcome to use MySQL stress test tool:")
    for id in xrange(1,len(funcs)+1):
        f = funcs[str(id)]
        print "%s. %s"%(id,f.desc)
    print "%s. %s"%("0","Exit")

def main():
    config = ConfigParser.ConfigParser()
    config.readfp(open("config.ini"))
    # 获取所有这次所有机器IP，用户，密码信息
    OsHost = namedtuple("OsHost","ip,user,passwd")
    hosts = eval(config.get("os","hosts"))
    os_user = config.get("os","os_user")
    os_passwd = config.get("os","os_passwd")
    for ip in hosts:
        h = OsHost(ip,os_user,os_passwd)
        ALL_HOSTS[ip]=h

    special_hosts=eval(config.get("os","special_hosts"))
    for sh in special_hosts:
        ip,os_user,os_passwd = sh
        h = OsHost(ip,os_user,os_passwd)
        ALL_HOSTS[ip]=h
    # print ALL_HOSTS

    # 获取所有mysql数据库主机信息
    DbHost = namedtuple("DbHost","ip,user,passwd")
    dbhosts = eval(config.get("mysql","hosts"))
    db_user = config.get("mysql","db_user")
    db_passwd = config.get("mysql","db_passwd")
    for host in dbhosts:
        MYSQL_HOSTS_MASTER.append(host[0])
        MYSQL_HOSTS_SLAVE.append(host[1])
        h = DbHost(host[0],db_user,db_passwd)
        MYSQL_HOSTS[host[0]]=h
        h = DbHost(host[1],db_user,db_passwd)
        MYSQL_HOSTS[host[1]]= h
    special_hosts=eval(config.get("mysql","special_hosts"))
    for sh in special_hosts:
        ip,os_user,os_passwd = sh
        h = DbHost(ip,os_user,os_passwd)
        MYSQL_HOSTS[ip]=h
    # print MYSQL_HOSTS_MASTER,MYSQL_HOSTS_SLAVE,MYSQL_HOSTS

    # 获取所有sysbench主机
    SYSBENCH_HOSTS = eval(config.get("sysbench","hosts"))
    # print SYSBENCH_HOSTS

    # 获取其他配置
    os_depend_pkgs = eval(config.get("common","os_depend_pkgs"))


    # 获取sysbench测试任务
    SbJOB = namedtuple("SbJOB","dbhosts,sbhost,threads,times,numberoftest,interval")
    JOB_MYSQL_HOSTS={}
    for sec in config.sections():
        if sec.startswith('job') == True:
            for ip in eval(config.get(sec,"ips")):
                JOB_MYSQL_HOSTS[ip] = ALL_HOSTS[ip]
            SYSBENCH_JOBS[sec] = SbJOB(JOB_MYSQL_HOSTS,ALL_HOSTS[SYSBENCH_HOSTS[1]],config.get(sec,"threads"),config.get(sec,"times"),config.get(sec,"numberoftest"),config.get(sec,"interval"))        

    Func = namedtuple("Func","fn,params,desc")
    fns = {"1":Func("checkEnvReady",(ALL_HOSTS,os_depend_pkgs),"Deployment Environment check"),
            "2":Func("fixEnv",ALL_HOSTS,"Fix Environment"),
            "3":Func("install_mysql",MYSQL_HOSTS,"Install MySQL"),
            "4":Func("uninstall_mysql",MYSQL_HOSTS,"UnInstall MySQL"),
            "5":Func("set_root_passwd",ALL_HOSTS,"Set root user's password"),
            "6":Func("backup_mysql",MYSQL_HOSTS,"Backup mysql database file"),
            "7":Func("sysbench_run",[],"Run sysbench test for only one mysql"),
            "8":Func("sysbench_run_job",[],"Run sysbench test (3 times)"),
            "9":Func("run_commander",[ALL_HOSTS,],"Run command"),
            "10":Func("change_root_passwd",[ALL_HOSTS,],"Change the root user Password"),
            "11":Func("mon_mysql",[],"Check mysql repliciation status"),
            "12":Func("start_slave_process",[],"Start MySQL Slave Process"),            
           }

    opts,args = getopt.getopt(sys.argv[1:],"ho:",["threads=","times=","cmd="])
    if len(opts) == 0:
        # 交互模式执行
        displaymenu(fns)
        idx = input("Please choose operate Option:")
        f = fns[str(idx)]
        if idx == 7:
            # 选择测试哪台mysql
            for i in xrange(len(MYSQL_HOSTS_MASTER)):
                print "%d. %s"%(i+1,MYSQL_HOSTS_MASTER[i])
            i = input("Please select MySQL host sequence[1-%s]:"%(len(MYSQL_HOSTS_MASTER)))
            ip = MYSQL_HOSTS_MASTER[i-1]
            # 选择使用哪台压测机器
            for i in xrange(len(SYSBENCH_HOSTS)):
                print "%d. %s"%(i+1,SYSBENCH_HOSTS[i])
            i = input("Please select sysbench host sequence[1-%s]:"%(len(SYSBENCH_HOSTS)))
            sbip = SYSBENCH_HOSTS[i-1]
            # 设置压测线程数
            threads = input("Please input threads[e.g:16/32/64/128 etc]:")
            # 设置压测时间（单位：s)
            times = input("Please input times[e.g:60/120/300 etc]:")
            print ip,sbip,threads,times
            dbhost=ALL_HOSTS[ip]
            sbhost=ALL_HOSTS[sbip]
            f.params.append(dbhost)
            f.params.append(sbhost)
            f.params.append(threads)
            f.params.append(times)
            print f.params
        elif idx == 8:
            # 选择执行的job任务
            jobid = 0
            m = {}
            for jobname in SYSBENCH_JOBS.keys():
                jobid = jobid + 1
                m[jobid] = jobname
                print "%d. %s(%s)"%(jobid,jobname,config.get(jobname,"ips"))
            jobid = input("Please select which job[e.g:1/2/3 etc]:")
            jobname = m[jobid]
            f.params.append(SYSBENCH_JOBS[jobname])
            print f.params
        elif idx == 10:
            new_pwd = raw_input("Please input new root password:")
            f.params.append(new_pwd)
        elif idx == 11 or idx == 12:
            slave_hosts={}
            for ip in MYSQL_HOSTS_SLAVE:
                slave_hosts[ip] = MYSQL_HOSTS[ip]
            f.params.append(slave_hosts)

        # 执行命令
        eval(f.fn)(f.params)
        exit(0)
    else:
        #　静默模式执行
        idx = None
        cmd = None
        threads = None
        Times = None
        for op,value in opts:
            if op == "-h":
                help()
                exit(0)
            elif op == "-o":
                idx = value
            elif op == "cmd":
                cmd = value
            elif op == "threads":
                threads = value
            elif op == "times":
                times = value
        if idx != None:
            f = fns[idx]
            #print(f.params)
            if idx == "8":
                 # 选择执行的job任务
                jobname="job1"
                f.params.append(SYSBENCH_JOBS[jobname])
                print f.params
            elif idx == "11" or idx == "12":
                slave_hosts={}
                for ip in MYSQL_HOSTS_SLAVE:
                    slave_hosts[ip] = MYSQL_HOSTS[ip]
                f.params.append(slave_hosts)
                # print(f.params)
            eval(f.fn)(f.params)



if __name__ == '__main__':
    main()
    exit(0)