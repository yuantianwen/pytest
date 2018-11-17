#!/usr/bin/python
#coding=utf-8
import mysql.connector
import curses,time
import sys

from prettytable import PrettyTable
from common import LOG,ssh,_mess_part,TextColor

def install_mysql(hosts):
    for hostinfo in hosts:
        ip = hostinfo[0]
        ser_id = ip[ip.rfind('.')+1:]
        LOG('GREEN','='*60)
        LOG('GREEN','Target Host:%s'%(ip))
        rssh = ssh(hostinfo,ROOT_USER,passwd=ROOT_USER_PASSWORD)

        # 创建work目录
        LOG('GREEN','1/9: Create MySQL Directory')
        rssh.ssh_run('mkdir -p /root/source')

        # 上传mysql文件
        LOG('GREEN','2/9: Upload MySQL RPM Install Package')
        rssh.sftp_upload_file('/root/source/MySQL-server-5.6.38-1.el7.x86_64.rpm','/root/source/MySQL-server-5.6.38-1.el7.x86_64.rpm')
        rssh.sftp_upload_file('/root/source/MySQL-client-5.6.38-1.el7.x86_64.rpm','/root/source/MySQL-client-5.6.38-1.el7.x86_64.rpm')

        # 上传my.cnf文件
        LOG('GREEN','3/9: Upload MySQL Configure File:/etc/my.cnf')
        rssh.sftp_upload_file('/root/my.cnf','/etc/my.cnf')
        # 修改my.cnf文件中的server-id
        rssh.ssh_run("sudo sed -i 's/18224/%s/g' %s"%(ip[ip.rfind('.')+1:],'/etc/my.cnf'))

        # 安装MySQL软件
        for pkg in mysqlInstallPkgs:
            LOG('GREEN','4/9: Install MySQL Package: %s'%pkg)
            rtn = rssh.ssh_run('rpm -ivh %s%s'%(SoftDir,pkg))

        # 创建目录和授权
        LOG('GREEN','5/9: Create MySQL Data Dir: /opt/huawei/db')
        rssh.ssh_run("mkdir -p /opt/huawei/db/data")
        rssh.ssh_run("mkdir -p /opt/huawei/db/mysql_temp")
        rssh.ssh_run("chown mysql:mysql /opt/huawei/db -R")
        rssh.ssh_run("chmod 777 /opt/huawei/db -R")
        rssh.ssh_run("chown mysql:mysql /etc/my.cnf")

        # 执行建库脚本:
        LOG('GREEN','6/9: Run Install DB Script：/usr/bin/mysql_install_db')
        rssh.ssh_run("/usr/bin/mysql_install_db --user=mysql")

        # 启动mysql服务
        LOG('GREEN','7/9: start mysql service')
        rtn = rssh.ssh_run('service mysql start')

        # 设置root密码
        LOG('GREEN','8/9: Set the password of root user')
        rtn = rssh.ssh_run('/usr/bin/mysqladmin -u root password "root"')

        # 创建root账号
        # grant all on *.* to 'root'@'%' identified by 'root';
        # flush privileges;
        LOG('GREEN','9/9: Add new root user account')
        print('mysql -uroot -proot -e "%s"'%("grant all on *.* to 'root'@'%' identified by 'root';flush privileges;"))
        rtn = rssh.ssh_run('mysql -uroot -proot -e "%s"'%("grant all on *.* to 'root'@'%' identified by 'root';flush privileges;"))
        print(rtn)


def uninstall_mysql(hosts):
    for hostinfo in hosts:
        LOG('GREEN','Target Host:%s'%(hostinfo[0]))
        rssh = ssh(hostinfo,ROOT_USER,passwd=ROOT_USER_PASSWORD)
        # 关闭mysql数据库
        rssh.ssh_run("pkill -9 mysql")

        # 卸载MySQL软件
        for pkg in mysqlInstallPkgs:
            LOG('GREEN','UnInstall MySQL Package: %s'%pkg)
            rtn = rssh.ssh_run('rpm -e %s'%pkg[:-4])

        # 删除数据文件和配置文件
        rssh.ssh_run("rm -rf /opt/huawei/db")
        rssh.ssh_run("rm /etc/my.cnf")

        # 删除mysql安装文件
        rssh.ssh_run("rm -rf /root/source")


def create_replication(srcip,destip):
    # CHANGE MASTER TO MASTER_HOST='10.60.0.59',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1;
    # CHANGE MASTER TO MASTER_HOST='10.60.0.13',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1;
    # CHANGE MASTER TO MASTER_HOST='10.60.0.88',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1;
    # CHANGE MASTER TO MASTER_HOST='10.60.0.113',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1;
    # CHANGE MASTER TO MASTER_HOST='10.60.0.110',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1;

    cmd = "CHANGE MASTER TO MASTER_HOST='%s',MASTER_USER='root',MASTER_PASSWORD='root',MASTER_AUTO_POSITION=1"%(srcip)

    cmd = "start slave"
    cmd = "show slave status \\G"

def backup_mysql(hosts):
    for hostinfo in hosts:
        ip = hostinfo[0]
        role = "M" if hostinfo[1] == "" else "S"

        LOG('GREEN','='*60)
        LOG('GREEN','Target Host:%s'%(ip))
        rssh = ssh(hostinfo,user=ROOT_USER,passwd=ROOT_USER_PASSWORD)

        # 停止mysql数据库
        LOG('GREEN','Stop MySQL service')
        rssh.ssh_run("service mysql stop")

        # 物理拷贝文件
        LOG('GREEN','Backup MySQL Datafile')
        todir = time.strftime('/opt/huawei/db%Y%m%d_%H%M')
        rssh.ssh_run("cp /opt/huawei/db %s -R"%(todir))

        # 重启mysql数据库
        LOG('GREEN','Restart MySQL service')
        rssh.ssh_run("service mysql start")

        # 启动MySQL内部的slave进程
        if role == "S":
            LOG('GREEN','Restart slave process')
            rssh.ssh_run("mysql -uroot -proot -e 'start slave'")

def start_slave_process(param):
    dbhosts = param[0]
    for h in dbhosts.values():
        cnx = mysql.connector.connect(user=h.user, password=h.passwd,host=h.ip,database='test')
        cur = cnx.cursor()
        query = "show slave status"
        cur.execute(query)
        for (f1) in cur:
            Slave_IO_Running = f1[10]
            Slave_SQL_Running = f1[11]
        if Slave_IO_Running == "No" and Slave_SQL_Running == "No":
            # 启动MySQL的slave进程
            LOG('GREEN','Start MySQL Slave Process:%s'%(h.ip))
            cur.execute("start slave")
        elif Slave_IO_Running != "Yes" and Slave_SQL_Running != "Yes":
            # 重新启动MySQL的slave进程
            LOG('GREEN','Restart MySQL Slave Process:%s'%(h.ip))
            cur.execute("stop slave")
            cur.execute("start slave")
def mon_mysql(param):
   while True:
        cnx = None
        cur = None
        dbhosts = param[0]
        #print dbhosts
        x = PrettyTable(["Slave Host", "Master Host", "Slave IO", "Slave SQL", "Delay","Master Log File","Master log Pos","Slave Log File","Slave Log Pos"])
        for h in dbhosts.values():
            try:
                cnx = mysql.connector.connect(user=h.user, password=h.passwd,host=h.ip,database='test')
                cur = cnx.cursor()
                query = "show slave status"
                cur.execute(query)            
                for (f1) in cur:
                    #print f1
                    Master_Host = f1[1]
                    Slave_IO_Running = f1[10] if f1[10]=="Yes" else TextColor.red(f1[10])
                    Slave_SQL_Running = f1[11] if f1[11]=="Yes" else TextColor.red(f1[11])
                    #print f1[32],len(f1[32])
                    Seconds_Behind_Master = f1[32] if f1[32]==0 else TextColor.green(f1[32])
                    Master_Log_File = f1[5]
                    Read_Master_Log_Pos= f1[6]
                    Relay_Master_Log_File = f1[9]
                    Exec_Master_Log_Pos = f1[21]
                    x.align["Slave Host"] = "l"
                    x.align["Master Host"] = "l"
                    x.padding_width = 1 
                    x.add_row([h.ip,Master_Host,Slave_IO_Running,Slave_SQL_Running,Seconds_Behind_Master,Master_Log_File,Read_Master_Log_Pos,Relay_Master_Log_File,Exec_Master_Log_Pos])
                cur.close()
                cnx.close()
            except Exception as e:
                print e
            finally:
                cur.close()
                cnx.close()
        print x
        time.sleep(1)
        sys.stdout.flush()


