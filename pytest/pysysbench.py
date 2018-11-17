#!/usr/bin/python
#coding=utf-8
import time
from common import ssh,LOG
from prettytable import PrettyTable

def install_sysbench(hosts):

    cmd = "yum -y install make automake libtool pkgconfig libaio-devel"

    cmd = "yum -y install mariadb-devel openssl-devel"

    cmd = "git clone https://github.com/akopytov/sysbench.git"

    '''
    ./autogen.sh
    # Add --with-pgsql to build with PostgreSQL support
    ./configure
    make -j
    make install
    '''
    pass

def sysbench_prepare(hosts):
    for hostinfo in hosts:
        cmd ="nohup sysbench /root/sysbench/src/lua/oltp_read_write.lua --mysql-host=%s --mysql-port=3306 --mysql-db=test --mysql-user=root --mysql-password=root --table_size=10000000 --tables=10 --threads=30 --time=60 --report-interval=10 --db-driver=mysql  prepare &"%(hostinfo[0])
        os.system(cmd)

def sysbench_run(param):
    dbhost = param[0]
    sbhost = param[1]
    threads = param[2]
    times = param[3]
    ip = dbhost.ip
    uuid = time.strftime('%m%d_%H%M')
    sarlog = '/opt/huawei/%s_%d_%d_%s_sar.log'%(ip,threads,times,uuid)
    sblog = '/opt/huawei/%s_%d_%d_%s_sysbench.log'%(ip,threads,times,uuid)
    local_sarlog = '/opt/huawei/%s/'%(uuid)
    local_sblog = ''
    LOG('GREEN','='*60)
    LOG('GREEN','Target MySQL Host:%s'%(ip))
    rssh = ssh(dbhost.ip,user=dbhost.user,passwd=dbhost.passwd)

    # 启动sar监控命令
    LOG('GREEN','Start sar to collect cpu statistic data')
    cmd = "sar 1 %s >%s &"%(times,sarlog)
    rssh.ssh_run(cmd)

    # 执行sysbench测试命令
    LOG('GREEN','Start sysbench')
    rssh_sb = ssh(sbhost.ip,user=sbhost.user,passwd=sbhost.passwd)
    cmd = "sysbench /root/sysbench/src/lua/oltp_read_write.lua --mysql-host=%s \
--mysql-port=3306 --mysql-db=test --mysql-user=root --mysql-password=root --table_size=10000000 --tables=10 --threads=%s --time=%s --report-interval=10 --db-driver=mysql run > %s "%(ip,threads,times,sblog)
    print cmd
    rssh_sb.ssh_run(cmd)
    print(time.strftime('%m%d_%H%M%S'))
    time.sleep(10)

    # 收集sysbench日志
    LOG('GREEN','Download sysbench log file')
    rssh_sb.sftp_download_file(sblog,sblog)

    # 收集sar日志
    LOG('GREEN','Download sar log file')
    rssh.sftp_download_file(sarlog,sarlog)

    return sysbench_metric(sblog) + cpu_metric(sarlog)


def sysbench_run_job(param):
    # ips,threads,times,numberoftest,interval
    sbjob = param[0]
    dbhosts= sbjob.dbhosts
    sbhost = sbjob.sbhost
    threads=eval(sbjob.threads)
    times=int(sbjob.times)
    numberoftest=int(sbjob.numberoftest)
    interval=int(sbjob.interval)
    f = open("job1.txt","w")

    x = PrettyTable(["ip", "threads", "times", "No.", "tps","qps","avgLatency","%%user","%%nice","%%system","%%iowait","%%steal","%%idle"])
    for ip in dbhosts.keys():
        for t in threads:
            for i in xrange(1,numberoftest + 1):
                LOG('GREEN','Perform %dth/%s test(ip=%s,threads=%d,times=%d)'%(i,numberoftest,ip,t,times))
                param=(dbhosts[ip],sbhost,t,times)
                result = sysbench_run(param)
                print result
                row= [ip,t,times,i] + list(result)
                print row
                x.add_row(row)
                f.write(str(row))

            LOG('GREEN','Sleep %d seconds'%(interval))
            time.sleep(interval)
    print x
    f.close()

def sysbench_metric(fname):
    with open(fname) as f:
        for line in f.readlines():
            if line.strip().startswith("transactions:"):
                tps = line.split("(")[1].split("per")[0].strip()
            elif line.strip().startswith("queries:"):
                qps = line.split("(")[1].split("per")[0].strip()
            elif line.strip().startswith("avg:"):
                avgLatency=line.split(":")[1].strip().replace('\n','')
    return tps,qps,avgLatency

def cpu_metric(fname):
    with open(fname) as f:
        lines = f.readlines()
        lastline = lines[len(lines) - 1]
        if lastline.startswith("Average:"):
            fields = lastline.strip().split()
            user= fields[2]
            nice= fields[3]
            system= fields[4]
            iowait= fields[5]
            steal= fields[6]
            idle= fields[7]
            return user,nice,system,iowait,steal,idle
        else:
            LOG('RED','%s content is incomplete or corrupt'%(fname))
            return ""
