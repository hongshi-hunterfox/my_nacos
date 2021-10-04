# -*- coding: utf-8 -*-
from threading import Timer

from .buffer import IConfigBuffer
from .exceptions import NacosClientException


class Thread(object):
    def __init__(self, executor, interval=0, *args):
        assert callable(executor)
        self.executor = executor
        self.args = args
        self.interval = interval
        self.thread = None
        self.start()

    def start(self):
        if self.thread is None:
            self.loop()

    def stop(self):
        if self.thread:
            self.thread.cancel()
        self.thread = None

    def __del__(self):
        if self.thread:
            self.stop()

    def loop(self):
        """线程循环
        self.executor(*self.args)
        if self.interval:
            self.thread = Timer(self.interval, self.loop)
            self.thread.start()
        """
        raise NacosClientException('未定义loop')


class ThreadBeat(Thread):
    """自动心跳线程
    每个实例仅维持一个心跳
    """
    def loop(self):
        if callable(self.executor):
            beat_info = self.executor(*self.args)
            interval = float(beat_info.clientBeatInterval / 1000)
            self.thread = Timer(interval, self.loop)
            self.thread.start()


class ConfigListener(Thread):
    """配置监听线程"""
    listens = {}  # key:(data_id,group,tenant), value:md5

    @property
    def listening(self)->str:
        """返回所有监听的 Listening-Configs"""
        return ''.join([IConfigBuffer.get_listening(*k, v)
                        for k, v in self.listens.items()])

    def add(self, data_id, group=None, tenant=None, md5=''):
        """添加一个监听项"""
        key = (data_id, group, tenant)
        self.listens[key] = md5

    def update(self, data_id, group=None, tenant=None, md5=''):
        """更新监听项的值(MD5)"""
        key = (data_id, group, tenant)
        if key in self.listens.keys():
            self.listens[key] = md5

    def delete(self, data_id, group=None, tenant=None):
        """删除一个监听项"""
        key = (data_id, group, tenant)
        if key in self.listens.keys():
            self.listens.pop(key)

    def loop(self):
        listening = self.listening
        if callable(self.executor):
            if listening:
                self.executor(listening)
            self.thread = Timer(self.interval, self.loop)
            self.thread.start()


