#!/usr/bin/python
#coding=utf-8
import os
import sys

import paramiko
import logging
import time
from pyfiglet import Figlet

''' 消息返回分隔符,应尽量复杂''' 
_mess_part='''|+|'''
class TextColor(object):
    @staticmethod
    def black(s):
        return '\033[32;1m%s\033[0m'%(s)
    @staticmethod
    def green(s):
        return '\033[32;1m%s\033[0m'%(s)
    @staticmethod
    def red(s):
        return '\033[31;1m%s\033[0m'%(s) 
    @staticmethod
    def yellow(s):
        return '\033[33;1m%s\033[0m'%(s)

class ArtFont(object):
    @staticmethod
    def renderText(s):
        f = Figlet(font='slant')
        return f.renderText(s)

def LOG(type,msg):
    date_detail = time.strftime('%Y-%m-%d %H:%M:%S')
    logtext = '[%s] %s'%(date_detail,msg)

    if type == 'NORMAL':
        print '\033[32;1m%s\033[0m'%(msg)
    elif type == 'GREEN':
        print '\033[32;1m[INFO ] %s\033[0m'%(logtext)
    elif type == 'RED':
        print '\033[31;1m[ERROR] %s\033[0m'%(logtext) 
    elif type == 'YELLOW':
        print '\033[33;1m[WARN] %s\033[0m'%(logtext)


class ssh(object):
    """docstring for ssh"""
    def __init__(self, ip,user,passwd=None,pem=None):
        self.ip = ip
        self.username = user
        self.password = passwd
        self.userpem = pem
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if pem == None:
            self.connect_mode = 1
        else:
            self.connect_mode = 2
            self.key_file = paramiko.RSAKey.from_private_key_file(self.userpem)

    def ssh_run(self,cmd):
        try:
            if self.connect_mode == 1:
                self.client.connect(self.ip, 22, username=self.username,password=self.password, timeout=20)                
            elif self.connect_mode == 2:
                self.client.connect(self.ip, 22, username=self.username,pkey=self.key_file, timeout=20)
            stdin, stdout, stderr = self.client.exec_command(cmd)
            return '%s%s%s'%(self.ip,_mess_part,stdout.read().replace('/n',''))
        except Exception as e:
            LOG('RED','[%s]:[%s] %s'%(self.ip,cmd, str(e)))
            return '%s%s%s'%(self.ip,_mess_part,'error')

    def sftp_upload_file(self,local_path,remote_path):
        # 判断本地文件是否存在
        testCmd = "test -f %s && echo true || echo false"%(local_path)
        ret = os.system(testCmd)
        if ret == 'false':
            LOG('RED','[%s]:[source file (%s) do not exist]'%(self.ip,local_path))
            return('%s%s%s'%(self.ip,_mess_part,'error'))

        # 判断目标文件是否存在
        testCmd = "test -f %s && echo true || echo false"%(remote_path)
        ret = self.ssh_run(testCmd)
        if ret == 'true':
            LOG('YELLOW','[%s]:[remote file(%s) has been existed]'%(self.ip,remote_path))

        # 上传文件
        try:
            t = paramiko.Transport(self.ip,22)
            t.connect(username=self.username,password = self.password)
            sftp = paramiko.SFTPClient.from_transport(t)
            sftp.put(local_path,remote_path)
            t.close()
        except Exception as e:
            LOG('RED','[%s]:[tranport file from %s to %s] %s'%(self.ip,local_path,remote_path,str(e)))
            return '%s%s%s'%(self.ip,_mess_part,'error')

    def sftp_download_file(self,remote_path,local_path):
        # 判断目标文件是否存在
        testCmd = "test -f %s && echo true || echo false"%(remote_path)
        ret = self.ssh_run(testCmd)
        if ret == 'true':
            LOG('YELLOW','[%s]:[remote file(%s) has been existed]'%(self.ip,remote_path))
        # 下载文件
        try:
            t = paramiko.Transport(self.ip,22)
            t.connect(username=self.username,password = self.password)
            sftp = paramiko.SFTPClient.from_transport(t)
            sftp.get(remote_path,local_path)
            t.close()
        except Exception as e:
            LOG('RED','[%s]:[download file from %s to %s] %s'%(self.ip,remote_path,str(e)),local_path)
            return '%s%s%s'%(self.ip,_mess_part,'error')
