import socket
import json
from source import NacosNameSpace,NacosService,NacosInstance,NacosConfig,\
    InstanceItem,Switches
from typing import List


class TestNacosClient(object):
    """这个 Nacose 服务是无验证的
    使用了命名空间对配置和服务进行分组
    包含了较多测试数据"""
    server_addr = '10.126.8.80:8001'
    user=None
    pwd=None
    tenant = 'dev'  # 默认命名空间
    service_list = ['ces-ois','ces-post-loan']
    configs = {
        'ces-post-loan-dev.yaml': [
            'outbound.ai.jobclasses'
        ]
    }

    @property
    def local_ips(self) ->List[str]:
        addresses = socket.getaddrinfo(socket.gethostname(), None)
        return list(filter(lambda _: ':' not in _,
                           [item[4][0] for item in addresses]))

    def __init__(self):
        self.nn = NacosNameSpace(self.server_addr, self.user, self.pwd)
        self.ns = NacosService(self.server_addr, self.user, self.pwd)
        self.ni = NacosInstance(self.server_addr, self.user, self.pwd)
        self.nc = NacosConfig(self.server_addr, self.user, self.pwd)
        print("本机IP地址:\n\t" + '\n\t'.join(self.local_ips))
        print(f'连接到 Nacos Server: {self.server_addr}')

    def iter_instances(self, services: list=None, name_space=None) ->InstanceItem:
        name_space = name_space if name_space else self.tenant
        for service in self.ns.list(page_size=100, name_space=name_space).doms:
            if services and service not in services:
                continue
            for instance in self.ni.list(service, name_space=name_space).hosts:
                yield instance

    def show_switches(self):
        print('系统设置:')
        switches = self.ns.get_switches()
        for fld in switches.__fields__.keys():
            print(f'\t{fld}: {getattr(switches,fld)}')

    def show_service_at_local(self):
        print('本机启动的服务:')
        for ins in self.iter_instances():
            if ins.ip in self.local_ips:
                print(f'\t{ins.serviceName}\t\t{ins.ip}:{ins.port}')


    def show_service_by_list(self):
        print('监控的服务:')
        for ins in self.iter_instances(self.service_list):
            print(f'\t{ins.serviceName}\t\t{ins.ip}:{ins.port}')

    def show_configs(self):
        print('配置信息:')
        for data_id, paths in self.configs.items():
            print(f'\t{data_id}')
            for path in paths:
                data = self.nc.get(data_id, path, tenant=self.tenant)
                print(f'\t\t{path}: {data}')


t = TestNacosClient()
t.show_switches()
t.show_service_at_local()
t.show_service_by_list()
t.show_configs()
