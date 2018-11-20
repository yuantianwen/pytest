#!/usr/bin/python
# coding=utf-8
import os
import sys
import getopt
import time
from collections import namedtuple
import ConfigParser
import signal

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

# 主机字典信息
HOST_ALL={}
HOST_SYSBENCH_IP_LIST=[]

# Mysql字典信息
MYSQL_ALL={}
MYSQL_MASTER_IP_LIST=[]
MYSQL_SLAVE_IP_LIST=[]

SYSBENCH_JOBS={}


def help():
    helpinfo="Usage: \n\
    python main.py [-h][-o N][--threads=N][--times=N][--cmd=xxx][--jobname=xxx][--pwd=xxx] \n\
Option: \n\
    [-h]            help \n\
    [-o]            Command option \n\
    [--threads]     Sysbench Threads \n\
    [--times]       Sysbench times \n\
    [--cmd]         Command \n\
    [--jobname]     Jobname \n\
    [--pwd]         Set root user new password \n\
\n\
Example: \n\
    1) python main.py -h       \n\
    2) python main.py -o 1       \n\
    3) python main.py -o 2       \n\
"
    print helpinfo
def eexit(signum, frame):
    print("Exit By Manual")
    exit(0)

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
    signal.signal(signal.SIGINT,eexit)
    signal.signal(signal.SIGTERM,eexit)

    config = ConfigParser.ConfigParser()
    config.readfp(open("config.ini"))
    # 获取所有这次所有机器IP，用户，密码信息
    OsHost = namedtuple("OsHost","ip,user,passwd")
    hosts = eval(config.get("os","hosts"))
    os_user = config.get("os","os_user")
    os_passwd = config.get("os","os_passwd")
    for ip in hosts:
        h = OsHost(ip,os_user,os_passwd)
        HOST_ALL[ip]=h

    special_hosts=eval(config.get("os","special_hosts"))
    for sh in special_hosts:
        ip,os_user,os_passwd = sh
        h = OsHost(ip,os_user,os_passwd)
        HOST_ALL[ip]=h
    # print HOST_ALL

    # 获取所有mysql数据库主机信息
    DbHost = namedtuple("DbHost","ip,user,passwd")
    dbhosts = eval(config.get("mysql","hosts"))
    db_user = config.get("mysql","db_user")
    db_passwd = config.get("mysql","db_passwd")
    for host in dbhosts:
        master_ip,slave_ip = host
        mh = DbHost(master_ip,db_user,db_passwd)
        sh = DbHost(slave_ip,db_user,db_passwd)
        MYSQL_ALL[master_ip] =mh
        MYSQL_ALL[slave_ip] = sh
        MYSQL_MASTER_IP_LIST.append(master_ip)
        MYSQL_SLAVE_IP_LIST.append(slave_ip)
    special_hosts=eval(config.get("mysql","special_hosts"))
    for sh in special_hosts:
        ip,os_user,os_passwd = sh
        h = DbHost(ip,os_user,os_passwd)
        MYSQL_ALL[ip]=h

    # print MYSQL_MASTER_IP_LIST,MYSQL_SLAVE_IP_LIST,MYSQL_ALL

    # 获取所有sysbench主机
    HOST_SYSBENCH_IP_LIST = eval(config.get("sysbench","hosts"))
    # HOST_SYSBENCH_IP_LIST = {key:value for key,value in HOST_ALL.items() if key in eval(config.get("sysbench","hosts"))}
    # print HOST_SYSBENCH_IP_LIST

    # 获取其他配置
    os_depend_pkgs = eval(config.get("common","os_depend_pkgs"))

    # 获取sysbench测试任务
    SbJOB = namedtuple("SbJOB","dbhosts,sbhost,threads,times,numberoftest,interval")
    host_mysql_in_job={}
    for sec in config.sections():
        if sec.startswith('job') == True:
            for ip in eval(config.get(sec,"ips")):
                host_mysql_in_job[ip] = HOST_ALL[ip]
            SYSBENCH_JOBS[sec] = SbJOB(host_mysql_in_job,HOST_ALL["10.60.0.232"],config.get(sec,"threads"),config.get(sec,"times"),config.get(sec,"numberoftest"),config.get(sec,"interval"))        

    Func = namedtuple("Func","fn,params,desc")
    fns = {"1":Func("checkEnvReady",(HOST_ALL,os_depend_pkgs),"Deployment Environment check"),
            "2":Func("fixEnv",HOST_ALL,"Fix Environment"),
            "3":Func("install_mysql",MYSQL_ALL,"Install MySQL"),
            "4":Func("uninstall_mysql",MYSQL_ALL,"UnInstall MySQL"),
            "5":Func("set_root_passwd",HOST_ALL,"Set root user's password"),
            "6":Func("backup_mysql",MYSQL_ALL,"Backup mysql database"),
            "7":Func("sysbench_run",[],"Choose one of databases and run testing"),
            "8":Func("sysbench_run_job",[],"choose one of jobs and run testing"),
            "9":Func("run_commander",[HOST_ALL,],"Run command"),
            "10":Func("change_root_passwd",[HOST_ALL,],"Change the root user Password"),
            "11":Func("mon_mysql",[],"Monitor repliciation process status"),
            "12":Func("start_slave_process",[],"Start MySQL Slave Process"),
            "13":Func("sysbench_show_status",[],"Show sysbench process status"),   
           }
    idx = 0
    cmd = ""
    threads = "1"
    Times = "3"
    jobname="job1"
    dbhost=""
    sbhost=""

    opts,args = getopt.getopt(sys.argv[1:],"ho:",["threads=","times=","cmd=","jobname=","pwd="])
    opts={key:value for key,value in opts}
    #print type(opts),type(args),opts
    # 获取操作项
    if len(opts) == 0:
        displaymenu(fns)
        idx = input("Please choose one command:")
        if idx == 0:
            exit(0)
    else:
        if opts.has_key("-h"):
            help()
            exit(0)
        elif opts.has_key("-o"):
            idx = opts["-o"]
    if idx == 0:
        help()
        exit()

    f = fns[str(idx)]

    # 根据操作项判断
    if idx == 7:
        if opts.has_key("dbhost"):
            dbhost = HOST_ALL[opts["dbhost"]]
        else:
            # 选择测试哪台mysql
            for i in xrange(len(MYSQL_MASTER_IP_LIST)):
                print "%d. %s"%(i+1,MYSQL_MASTER_IP_LIST[i])
            i = input("Please enter the MySQL host number that needs to be tested[1-%s]:"%(len(MYSQL_MASTER_IP_LIST)))
            ip = MYSQL_MASTER_IP_LIST[i-1]
            print ip
            dbhost = HOST_ALL[ip]
        print dbhost

        if opts.has_key("sbhost"):
            sbhost = HOST_ALL[opts["sbhost"]]
        else:
            # 选择使用哪台压测机器
            for i in xrange(len(HOST_SYSBENCH_IP_LIST)):
                print "%d. %s"%(i+1,HOST_SYSBENCH_IP_LIST[i])
            i = input("Please enter the host number used to run sysbench[1-%s]:"%(len(HOST_SYSBENCH_IP_LIST)))
            sbip = HOST_SYSBENCH_IP_LIST[i-1]
            sbhost=HOST_ALL[sbip]

        if opts.has_key("threads"):
            threads = opts["threads"]
        else:
            # 设置压测线程数
            threads = input("Please enter th threads for sysbench [e.g:16/32/64/128 etc]:")

        if opts.has_key("times"):
            times= opts["times"]
        else:
            # 设置压测时间（单位：s)
            times = input("Please enter the times for sysbench [e.g:60/120/300 etc]:")

        print ip,sbip,threads,times
        f.params.append(dbhost)
        f.params.append(sbhost)
        f.params.append(threads)
        f.params.append(times)
        print f.params
    elif idx == 8:
        if opts.has_key("jobname"):
            jobname= opts["jobname"]
        else:
            # 选择执行的job任务
            jobid = 0
            m = {}
            for jobname in SYSBENCH_JOBS.keys():
                jobid = jobid + 1
                m[jobid] = jobname
                print "%d. %s(%s,%s,%s,%s,%s)"%(jobid,jobname,config.get(jobname,"ips"),config.get(jobname,"threads"),config.get(jobname,"times"),config.get(jobname,"numberoftest"),config.get(jobname,"interval"))
            jobid = input("Please select which job[e.g:1/2/3 etc]:")
            jobname = m[jobid]
        f.params.append(SYSBENCH_JOBS[jobname])
        print f.params
    elif idx == 9:
        if opts.has_key("cmd"):
            cmd= opts["cmd"]
        else:
            cmd = raw_input("Please input command to be executed:")
        f.params.append(cmd)
    elif idx == 10:
        if opts.has_key("pwd"):
            pwd= opts["pwd"]
        else:
            pwd = raw_input("Please input new root password:")
        f.params.append(pwd)
    elif idx == 11 or idx == 12:
        #slave_hosts={}
        #for ip in MYSQL_SLAVE_IP_LIST:
        #   slave_hosts[ip] = MYSQL_ALL[ip]
        #f.params.append(slave_hosts)
        f.params.append({key:value for key,value in MYSQL_ALL.items() if key in MYSQL_SLAVE_IP_LIST})
    elif idx == 13:
        #sys_hosts={}
        #for ip in HOST_SYSBENCH_IP_LIST:
        #    sys_hosts[ip] = HOST_ALL[ip]
        #f.params.append(sys_hosts)
        #print HOST_SYSBENCH_IP_LIST
        
        f.params.append({key:value for key,value in HOST_ALL.items() if key in MYSQL_MASTER_IP_LIST})
        f.params.append({key:value for key,value in HOST_ALL.items() if key in HOST_SYSBENCH_IP_LIST})
    # 执行命令
    eval(f.fn)(f.params)
    exit(0)

if __name__ == '__main__':
    main()
    exit(0)