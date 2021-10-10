# -*- coding: utf-8 -*-
import json
from typing import Dict, Callable, List, Optional
from threading import Timer

from models import Listening, ConfigData


def _no_do(_):
    pass


class MyThread(object):
    def __init__(self, executor, interval=0, *args):
        assert callable(executor)
        self.executor = executor
        self.args = args
        self.interval = interval
        self.thread = None
        self.daemon = repr(self).split()[-1][2:-1]
        self.start()

    @property  # 判断当前条件是否满足线程循环
    def premise(self):
        return True

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
        """线程循环"""
        if self.premise:
            self.action()
            self.thread = Timer(self.interval, self.loop)
            self.thread.daemon = self.daemon
            self.thread.start()

    def action(self):
        """线程动作
        它的核心是执行 executor
        如果有必要,在这里处理 executor 的参数与返回值"""
        self.executor(*self.args)


class ThreadBeat(MyThread):
    """自动心跳线程
    每个实例仅维持一个心跳
    """
    @property
    def premise(self):
        return callable(self.executor) and \
               self.interval >= 0 and \
               self.args

    def action(self):
        print('ThreadBeat.action')
        beat_info = self.executor(*self.args)
        self.interval = float(beat_info.clientBeatInterval / 1000)


class ListenPath(object):
    """监听的配置项
    value: 配置项最新值
    event: 当配置项值变化时,触发的方法函数,
            要想它正常动作,它必需能接受至少一个非命名参数
    >>> lstn = ListenPath('127.0.0.1')
    >>> lstn == '127.0.0.1'
    True
    >>> lstn == '192.168.0.1'
    False
    >>> from datetime import datetime
    >>> fn = lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    >>> lstn.add(fn)
    >>> len(lstn.events)
    1
    """
    hash: int  # hash of value
    events: List[Callable] = []  # if this hash chang, notify then

    def __init__(self, value, event: Callable = None):
        self.hash = hash(json.dumps(value)) if value else None
        self.add(event)

    def __eq__(self, other):
        if isinstance(other, ListenPath):
            return self.hash == other.hash
        else:
            return self.hash == hash(json.dumps(other))

    def _clean(self):
        """整理: 清除失效的事件"""
        self.events = list(filter(callable, self.events))

    @property  # 是否有可用的绑定事件
    def has_event(self) -> bool:
        self._clean()
        return len(self.events) > 0

    def add(self, event: Callable):
        if callable(event) and event not in self.events:
            self.events.append(event)
            self._clean()

    def remove(self, event):
        if event in self.events:
            self.events.remove(event)
        self._clean()

    def update(self, new_value=None, path=None):
        """更新配置项值
        如果配置项值与记录时不同,更新 hash 值并通知所有绑定事件"""
        if new_value is None or self == new_value:
            return
        self.hash = hash(json.dumps(new_value))
        self._clean()
        for event in self.events:
            try:
                if callable(event):
                    event(new_value, path)
            finally:
                pass


class ListenData(object):
    """监听的配置数据
    一个配置数据下可以有多个 ListenPath，
    """
    md5: str = ''  # ConfigData.config_md5
    listens: Dict[str, ListenPath] = {}  # key: path in config

    def __init__(self,
                 config: ConfigData = None,
                 **kwargs: Dict[str, Callable]):
        self.md5 = config.config_md5 if config else ''
        if kwargs:
            for path, event in kwargs.items():
                if callable(event):
                    self.add_listening(config, path, event)

    def _clean(self):
        keys = [key
                for key, val in self.listens.items()
                if not val.has_event]
        for key in keys:
            self.listens.pop(key)

    @property  # 该配置下是否还有监听需求
    def has_path(self) -> bool:
        return len(self.listens) > 0

    def update(self, config: ConfigData):
        """配置发生变化，通知到所有 listens """
        if self.md5 == config.config_md5:
            return
        self.md5 = config.config_md5
        for path, listen in self.listens.items():
            listen.update(config.value(path), path=path)

    def add_listening(self,
                      config: Optional[ConfigData],
                      path: Optional[str],
                      event: Optional[Callable]):
        path = path if path else ''
        value = config.value(path) if config else None
        if path not in self.listens.keys():
            self.listens[path] = ListenPath(value, event)
        else:
            self.listens[path].update(value)
            if event not in self.listens[path]:
                self.listens[path].add(event)
        self._clean()

    def del_listening(self, path: str = None, event: Callable = None):
        path = path if path else ''
        if path in self.listens.keys():
            if event:
                self.listens[path].remove(event)
            else:
                self.listens.pop(path)
        self._clean()


class ConfigListener(MyThread):
    """配置监听线程
    每次监听所有 listens 中记录的配置"""
    listens: Dict[Listening, ListenData] = {}

    @property
    def premise(self):
        if callable(self.executor) and len(self.listens.keys()) > 0:
            for listen in self.listens.values():
                if listen.has_path:
                    return True
        return False

    def action(self):
        print('ConfigListener.action')
        self.executor(self.listening)

    @property  # Parameter listening of NacosConfig.listener()
    def listening(self) -> str:
        """返回所有监听的 Listening-Configs"""
        return ''.join([str(key) for key in self.listens.keys()])

    def add(self,
            listen: Listening,
            config: ConfigData = None,
            path: str = None,
            event: Callable = None):
        """添加一个监听项"""
        # 来自对配置的监听而非配置值的监听,需要有一个替代事件使
        #   ListenPath.has_event 为 True
        path = path if path else ''
        event = _no_do if path in (None, '') and event is None else event
        self.listens[listen] = ListenData(config, **{path: event})
        self.start()

    def update(self,
               key: Listening,
               config: ConfigData):
        """更新监听项的值(MD5)"""
        if key in self.listens.keys():
            listen = self.listens[key]
            self.listens.pop(key)
            self.listens[key] = listen
            listen.update(config)

    def delete(self,
               listen: Listening,
               path: str = None,
               event: Callable = None):
        """删除一个监听项"""
        event = _no_do if path is None and event is None else event
        if listen in self.listens.keys():
            if event:
                self.listens[listen].del_listening(path, event)
                if not self.listens[listen].has_path:
                    self.listens.pop(listen)
            else:
                self.listens.pop(listen)
        if len(self.listens.keys()) == 0:
            self.stop()


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
