# coding=utf-8
from enum import Enum


# 默认分组名
DEFAULT_GROUP_NAME = 'DEFAULT_GROUP'


class ConfigBufferMode(Enum):
    """配置信息缓存模式"""
    nothing = 0  # 不缓存
    memory = 1  # 在内存为缓存
    storage = 2  # 在本地文件中缓存