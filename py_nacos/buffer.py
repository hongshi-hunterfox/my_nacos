# -*- coding: utf-8 -*-
"""Configured data cache"""
import os
import hashlib
from datetime import datetime
from abc import abstractmethod, ABCMeta
from typing import Dict, Union

from .consts import DEFAULT_GROUP_NAME, ConfigBufferMode
from .exceptions import NacosClientException
from .models import ConfigData


BUFFER_MODE = ConfigBufferMode.nothing


class BufferItem(object):
    update_time: datetime
    config: ConfigData


class IConfigBuffer(metaclass=ABCMeta):
    """缓存接口类"""
    buffer: Dict[str, BufferItem] = {}

    def __init__(self, *args, **kwargs):
        super().__init__()

    @staticmethod
    def get_listening(data_id: str, group=None, tenant=None, md5=None) -> str:
        """返回配置对应的监听数据报文
        safe: 如果为 True 则返回值中 chr(1)、chr(2) 替换为^1、^2
        """
        lst = [data_id,
               group if group else DEFAULT_GROUP_NAME,
               md5 if md5 else '']
        if tenant:
            lst.append(tenant)
        s = chr(2).join(lst)
        return s + chr(1)

    @abstractmethod
    def get_content_md5(self, data_id: str, group=None, tenant=None) -> str:
        pass  # 返回配置缓存数据的MD5值

    @abstractmethod
    def get(self, data_id: str, group=None, tenant=None
            ) -> Union[None, ConfigData]: pass

    @abstractmethod
    def set(self, config: ConfigData, data_id: str, group=None, tenant=None): pass

    def delete(self, data_id: str, group=None, tenant=None):
        listening = self.get_listening(data_id, group, tenant)
        if listening in self.buffer.keys():
            self.buffer.pop(listening)

    def clear(self):
        self.buffer = {}


class BufferMemory(IConfigBuffer):
    """在内存中的缓存:它们保存在一个字典中"""
    def get_content_md5(self, data_id: str, group=None, tenant=None) -> str:
        """返回相应缓存配置的 MD5 值
        如果没有缓存则返回''"""
        listening = self.get_listening(data_id, group, tenant)
        if listening not in self.buffer.keys():
            return ''
        return self.buffer[listening].config.config_md5

    def get(self, data_id: str, group=None, tenant=None
            ) -> Union[None, ConfigData]:
        """返回相应缓存配置的 ConfigData 对象
        如果没有缓存则返回 None"""
        listening = self.get_listening(data_id, group, tenant)
        if listening not in self.buffer.keys():
            return None
        return self.buffer[listening].config

    def set(self, config: ConfigData, data_id: str, group=None, tenant=None):
        """更新缓存"""
        assert config, '必需给出有效的配置数据'
        listening = self.get_listening(data_id, group, tenant)
        if listening not in self.buffer.keys():
            self.buffer[listening] = BufferItem()
        self.buffer[listening].update_time = datetime.now()
        self.buffer[listening].config = config


class BufferStorage(IConfigBuffer):
    """文件快照缓存
    缓存位置:{user.home}/nacos/config/fixed_{server_ip}_{server_port}-nacos
             /snapshot/{tenant}/{group}/{data_type}/{data_id}
    """
    def __init__(self, server_ip, server_port=8848, **kwargs):
        super().__init__(**kwargs)
        # 本地快照目录
        self.home = os.path.join(os.path.expanduser('~'),
                                 'nacos',
                                 'config',
                                 f'fixed-{server_ip}_{server_port}-nacos',
                                 'snapshot')
        self.load_snapshots()

    @classmethod
    def iter_file(cls, level, args):
        """迭代出目录下指定深度的文件
            文件本身是最后一层深度
        args: [homedir]
        return: [file_path, sub_dir1, ..., file_name]
        """
        for sub_dir in os.listdir(args[0]):
            path = os.path.join(args[0], sub_dir)
            if len(args) < level and os.path.isdir(path):
                for item in cls.iter_file(level, [path] + args[1:] + [sub_dir]):
                    yield item
            else:
                if os.path.isfile(path):
                    yield [path] + args[1:] + [sub_dir]

    @staticmethod
    def _file_md5(path):
        """计算文件 MD5 值"""
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def load_snapshots(self):
        """从本地快照加载配置"""
        for path, tenant, group, xtype, data_id in self.iter_file(4, [self.home]):
            tenant = tenant if tenant != 'default-tenant' else None
            item = BufferItem()
            item.update_time = os.path.getmtime(path)
            item.config = ConfigData(config_type=xtype,
                                     config_md5=self._file_md5(path),
                                     data=path)
            listening = self.get_listening(data_id, group, tenant)
            self.buffer[listening] = item

    def _get_path(self,
                  data_id: str, group=None, tenant=None,
                  data_type=None, new=False) -> str:
        """返回配置快照文件名(全路径)"""
        data_type = data_type if data_type else 'text'
        full_path = os.path.join(self.home,
                                 tenant if tenant else 'default-tenant',
                                 group if group else DEFAULT_GROUP_NAME,
                                 data_type,
                                 data_id)
        return full_path if os.path.isfile(full_path) or new else None

    def get_content_md5(self, data_id: str, group=None, tenant=None) -> str:
        listening = self.get_listening(data_id, group, tenant)
        if listening in self.buffer.keys():
            memory = self.buffer[listening]
            full_path = memory.config.data
            if os.path.getmtime(full_path) == memory.update_time and \
                    self._file_md5(full_path) == memory.config.config_md5:
                return memory.config.config_md5
        return ''

    def get(self, data_id: str, group=None, tenant=None
            ) -> Union[None, ConfigData]:
        listening = self.get_listening(data_id, group, tenant)
        if listening not in self.buffer.keys():
            return None
        memory = self.buffer[listening]
        full_path = memory.config.data
        if os.path.getmtime(full_path) != memory.update_time and \
                self._file_md5(full_path) != memory.config.config_md5:
            return None
        config = ConfigData(config_type=memory.config.config_type,
                            config_md5=memory.config.config_md5,
                            data='')
        with open(full_path, 'r', encoding='utf-8') as f:
            config.data = f.read()
        return config

    def set(self, config: ConfigData, data_id: str, group=None, tenant=None):
        assert config, '必需给出有效的配置数据'
        full_path = self._get_path(data_id, group, tenant, config.config_type, True)
        path = os.path.split(full_path)[0]
        if not os.path.isdir(path):
            if os.path.exists(path):
                raise NacosClientException('can not making dir(it is file)', path)
            os.makedirs(path)
        with open(full_path, 'w+', encoding='utf-8') as f:
            f.write(config.data)
        item = BufferItem()
        item.config = ConfigData(config_type=config.config_type,
                                 config_md5=config.config_md5,
                                 data=full_path)
        item.update_time = os.path.getmtime(full_path)
        listening = self.get_listening(data_id, group, tenant)
        self.buffer[listening] = item


def new_buffer(buffer_mode: ConfigBufferMode,
               *args, **kwargs
               ) -> Union[IConfigBuffer, None]:
    if buffer_mode is None:
        return None
    elif buffer_mode == ConfigBufferMode.memory:
        return BufferMemory(*args, **kwargs)
    elif buffer_mode == ConfigBufferMode.storage:
        return BufferStorage(*args, **kwargs)
    else:
        return None
