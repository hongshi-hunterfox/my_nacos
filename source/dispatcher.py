# coding=utf-8
"""Nacos API 调用"""
import re, yaml, json
from copy import deepcopy
from random import randint
from functools import wraps
from datetime import datetime
from urllib.parse import urlencode
from requests import Response, request
from typing import Union,Callable,Any,List
from threading import Timer

from .exceptions import NacosException, NacosClientException
from .consts import DEFAULT_GROUP_NAME
from .models import Service, ServicesList, Switches, Metrics, Server, InstanceInfo, \
    InstanceList, Beat, BeatInfo, NameSpace, InstanceItem, ConfigData


class Token(object):
    def __init__(self, server,user,pwd):
        self.server = server
        self.token = None
        self.ttl = 0  # 失效时间
        self.user = user
        self.pwd = pwd
        self.refresh()

    def refresh(self):
        if self.user and self.pwd:
            ttl = datetime.now().timestamp()  # 失效时间自请求开始前计算
            url = self.server + '/nacos/v1/auth/login'
            data = f'username={self.user}&password={self.pwd}'
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            res = request('POST', url, data=data, headers=headers)
            if res.status_code != 200:
                self.token = None
            else:
                d_body = res.json()
                self.token = d_body['accessToken']
                self.ttl = ttl + (d_body['tokenTtl'])

    def dict(self) -> dict:
        if self.token is None or self.ttl > datetime.now().timestamp():
            self.refresh()
        return {'accessToken': self.token} if self.token else {}


class NacosClient(object):
    """API封装"""
    @staticmethod
    def _parse_server_addr(url: str) -> str:
        """为服务地址补全协议头、端口"""
        if not re.match(r'https?://.+', url):
            url = 'http://' + url
        if not re.match(r'.+:\d+$', url):
            return url + ':8848'
        elif not re.match(r'.+:\d{2,5}$', url):
            return re.sub(r':\d+$', ':8848', url)
        return url

    @staticmethod
    def _kwargs2dict(**kwargs) -> dict:
        """将所有命名参数整合为一个字典,排除值为None的"""
        d_result = {}
        for k,v in kwargs.items():
            if k in ['group', 'groupName'] and v is None:
                v = DEFAULT_GROUP_NAME
            if v:
                d_result[k] = v
        return d_result

    @staticmethod
    def _paras_body(res: Response) -> Any:
        if 'json' in res.headers['content-type']:
            return json.loads(res.text)
        else:  # 'text' in res.headers['content-type']:
            return res.text

    def __init__(self, server: str, user:str=None,pwd:str=None):
        self.server = self._parse_server_addr(server)
        self.token = Token(self.server, user, pwd) if user and pwd else None

    def _get_full_path(self, *args, params:dict=None) -> str:
        """生成请求地址
        params:需要附加到url中的参数
        """
        url = '/'.join(filter(lambda _:_, '/'.join(args).split('/')))
        url = url.replace(':/', '://')
        if self.token:
            params = params if params else {}
            token = self.token.dict() if self.token else {}
            assert token, NacosException('Authentication failed')
            params.update(token)
        if params:
            url = url + '?' + urlencode(params)
        return url

    def _get_response(self,path:str, params:dict=None, method:str='GET'
                      ) -> Response:
        """各种请求方式实现"""
        assert method in['POST', 'GET','PUT','DELETE'],\
            NacosClientException('不支持的请求方法')
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = None
        if method == 'POST':
            url = self._get_full_path(self.server, path)
            data = urlencode(params)
        else:  # GET,PUT,DELETE
            url = self._get_full_path(self.server, path, params=params)
        rsp = request(method, url, data=data, headers=headers)
        if rsp is None or rsp.status_code != 200:
            raise NacosException(rsp.status_code, rsp.text)
        return rsp


class NacosConfig(NacosClient):
    """配置
    >>> nc = NacosConfig('localhost', 'nacos', 'nacos')
    >>> nc.get('test_yaml').value('spring.datasource.dynamic.enabled')
    False
    >>> nc.get('test_json').value('keys.secretKey')
    'iGNddHce42LNtOc0sc58p94ayRxZNR'
    >>> data = {"serviceName":"ces-ois","healthyOnly":True,"namespaceId":"dev","groupName":"DEFAULT_GROUP"}
    >>> nc.post('test_update',data,data_type='JSON')
    True
    >>> data = 'serviceName: ces-ois\\nhealthyOnly: true\\nnamespaceId: dev\\ngroupName: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    >>> nc.post('test_update', data, data_type='yaml')
    True
    >>> nc.delete('test_update')
    True
    >>> history = nc.history('test_yaml')
    >>> history['totalCount']
    2
    >>> [_['id'] for _ in history['pageItems']]
    ['52', '4']
    >>> history = nc.history('test_yaml', nid=history['pageItems'][0]['id'])
    >>> history is not None
    True
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 配置缓存
        #   监听配置,当变更发生时,重新获取配置值
        #   get时优先读取缓存，缓存未命中添加相应监听
        self.config_buffer = {}  # {dataid^group^tenant, md5, obj}

    @classmethod
    def _paras(cls, rsp: Response) -> ConfigData:
        """从 Response 生产 ConfigData"""
        config = ConfigData(config_type=rsp.headers['config-type'],
                            config_md5=rsp.headers['content-md5'],
                            data=rsp.text)
        if config.config_type == 'yaml':
            config.data = yaml.load(config.data, Loader=yaml.SafeLoader)
        elif config.config_type == 'json':
            config.data = json.loads(config.data)
        return config

    def listener(self, data_id, group=None, tenant=None):
        """监听配置
        这需要建立一个线程池来管理:
            每个data_id对应一个异步请求
            建立迅步请求并等待回复
            得到回复后更新config_buffer并重建请求
            线程池销毁时要清理所有异步请求
        """
        raise NacosException('此功能尚未实现')

    def get(self, data_id, group=None, tenant=None) -> ConfigData:
        """取配置值"""
        api = '/nacos/v1/cs/configs'
        params = self._kwargs2dict(dataId=data_id, group=group, tenant=tenant)
        rsp = self._get_response(api, params)
        return self._paras(rsp)

    def post(self, data_id, data, group=None, tenant=None, data_type=None
             ) -> bool:
        """发布配置
        发布配置时,data_id必需是已存在于Nacos服务中的"""
        api = '/nacos/v1/cs/configs'
        params = self._kwargs2dict(dataId=data_id, content=data, group=group,
                                   tenant=tenant,type=data_type)
        rsp = self._get_response(api, params, method='POST')
        return self._paras_body(rsp)

    def delete(self, data_id, group=None, tenant=None) -> bool:
        """删除配置"""
        api = '/nacos/v1/cs/configs'
        params = self._kwargs2dict(dataId=data_id, group=group, tenant=tenant)
        rsp = self._get_response(api, params, method='DELETE')
        return self._paras_body(rsp)

    def history(self, data_id,
                group=None, tenant=None, page_no=None, page_size=None, nid=None
                ) -> dict:
        """查询配置历史"""
        api = '/nacos/v1/cs/history'
        if nid is None:
            params = self._kwargs2dict(search='accurate',
                                       dataId=data_id, group=group,
                                       tenant=tenant,
                                       pageNo=page_no, pageSize=page_size)
        else:
            params = self._kwargs2dict(dataId=data_id, group=group,
                                       tenant=tenant,
                                       nid=nid)
        rsp = self._get_response(api, params)
        return self._paras_body(rsp)

    def previous(self,  nid, data_id, group=None, tenant=None):
        """查询配置上一版本信息
        此API未调通: 无有效的nid
        """
        raise NacosException('此功能尚未实现')
        # api = '/nacos/v1/cs/history/previous'
        # params = self._kwargs2dict(id=nid,
        #                            dataId=data_id, group=group, tenant=tenant)
        # rsp = self._get_response(api, params)
        # return self._paras_body(rsp)

    def value(self, data_id, path, group=None, tenant=None):
        """属性方法装饰器
        被装饰的属性总是返回nacos相应配置项的值
        """
        def func_wrapper(func):
            @wraps(func)
            def call_func(*args, **kwargs):
                try:
                    e_return = self.get(data_id, group, tenant).value(path)
                except (NacosException,):
                    e_return = func(*args, **kwargs)
                return e_return
            return call_func
        return func_wrapper

    @staticmethod
    def _fetch_attrs(instance:object, data:dict):
        """为对象实例填充属性"""
        _class = instance.__class__
        for key in data.keys():
            if key.startswith('__') and key.endswith('__'):
                continue
            if key in instance.__dict__.keys() and instance.__dict__[key] is Callable:
                continue
            if key in _class.__dict__.keys() and _class.__dict__[key] is Callable:
                continue
            setattr(instance, key, data.get(key))

    def values(self, data_id, path, group=None, tenant=None,
               only_class=False):
        """类装饰器
        被装饰的类中与指定配置的子项同名的属性将得到相应的值
        only_class: 为 True 时,对象的__init__/__call__方法也将被装饰,
            当创建新实例或调用实例时,实例属性与类属性将被更新
        """
        def class_wrapper(_class):
            """读取配置值作为类的属性"""
            def wrap_class_init(func):
                @wraps(func)
                def call_func(*args, **kwargs):
                    func(*args, **kwargs)
                    data = self.get(data_id, group, tenant).value(path)
                    NacosConfig._fetch_attrs(args[0], data)
                return call_func

            def wrap_class_call(func):
                @wraps(func)
                def call_func(*args, **kwargs):
                    data = self.get(data_id, group, tenant).value(path)
                    NacosConfig._fetch_attrs(args[0], data)
                    return func(*args, **kwargs)
                return call_func

            try:
                cfg = self.get(data_id, group, tenant).value(path)
                for key in cfg.keys():
                    if not key.startswith('__') and \
                            not key.endswith('__') and \
                            key in _class.__dict__.keys() and \
                            _class.__dict__[key] is not Callable:
                        setattr(_class, key, cfg.get(key))
                if not only_class:
                    _class.__init__ = wrap_class_init(_class.__init__)
                    _class.__call__= wrap_class_call(_class.__call__)
            except (NacosException,):
                pass
            return _class
        return class_wrapper


class NacosService(NacosClient):
    """服务
    >>> ns = NacosService('localhost', 'nacos', 'nacos')
    >>> ns.create('new.Service')
    True
    >>> ns.update('new.Service',0.8,metadata={'starttime':datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    True
    >>> service = ns.query('new.Service')
    >>> type(service)
    <class 'models.Service'>
    >>> service.groupName == DEFAULT_GROUP_NAME
    True
    >>> type(ns.list())
    <class 'models.ServicesList'>
    >>> ns.delete('new.Service')
    True
    >>> ns.switches('defaultPushCacheMillis', 9999)
    True
    >>> type(ns.switches())
    <class 'models.Switches'>
    >>> type(ns.metrics())
    <class 'models.Metrics'>
    >>> type(ns.servers())
    <class 'list'>
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create(self, service,
               group=None, name_space=None, protect_threshold=None,
               metadata=None, selector=None
               ) -> bool:
        """创建服务"""
        api = '/nacos/v1/ns/service'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        if selector and not isinstance(selector, str):
            selector = json.dumps(selector)
        params = self._kwargs2dict(serviceName=service,
                                   groupName=group,
                                   namespaceId=name_space,
                                   protectThreshold=protect_threshold,
                                   metadata=metadata,
                                   selector=selector)
        rsp = self._get_response(api, params, 'POST')
        return self._paras_body(rsp) == 'ok'

    def query(self, service, group=None, name_space=None) -> Service:
        """查询服务
        不能以该接口是否返回值来判断服务是否存在"""
        api = '/nacos/v1/ns/service'
        params = self._kwargs2dict(serviceName=service,
                                   groupName=group,
                                   namespaceId=name_space)
        rsp = self._get_response(api, params)
        return Service(**self._paras_body(rsp))

    def update(self, service, protect_threshold:float,
               group=None, name_space=None, metadata=None, selector=None
               ) -> bool:
        """修改服务"""
        api = '/nacos/v1/ns/service'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        if selector and not isinstance(selector, str):
            selector = json.dumps(selector)
        params = self._kwargs2dict(serviceName=service,
                                   groupName=group,
                                   namespaceId=name_space,
                                   protectThreshold=protect_threshold,
                                   metadata=metadata,
                                   selector=selector)
        rsp = self._get_response(api, params, 'PUT')
        return self._paras_body(rsp) == 'ok'

    def delete(self, service, group=None, name_space=None) -> bool:
        """删除服务"""
        api = '/nacos/v1/ns/service'
        params = self._kwargs2dict(serviceName=service,
                                   groupName=group,
                                   namespaceId=name_space)
        rsp = self._get_response(api, params, 'DELETE')
        return self._paras_body(rsp) == 'ok'

    def list(self, page_no:int=1, page_size:int=10,
             group=None, name_space=None) -> ServicesList:
        """服务列表"""
        api = '/nacos/v1/ns/service/list'
        params = self._kwargs2dict(pageNo=page_no,
                                   pageSize=page_size,
                                   groupName=group,
                                   namespaceId=name_space)
        rsp = self._get_response(api, params)
        return ServicesList(**self._paras_body(rsp))

    def get_switches(self) -> Switches:
        """获取系统开关状态"""
        api = '/nacos/v1/ns/operator/switches'
        rsp = self._get_response(api)
        return Switches(**self._paras_body(rsp))

    def set_switches(self, entry, value, debug=False
                 ) -> Union[bool, Switches]:
        """设置系统开关"""
        api = '/nacos/v1/ns/operator/switches'
        params = self._kwargs2dict(entry=entry,
                                   value=value,
                                   debug=debug)
        rsp = self._get_response(api, params, 'PUT')
        return self._paras_body(rsp) == 'ok'

    def metrics(self) ->Metrics:
        """当前数据指标"""
        api = '/nacos/v1/ns/operator/metrics'
        rsp = self._get_response(api)
        return Metrics(**self._paras_body(rsp))

    def servers(self, healthy:bool=None)-> List[Server]:
        """集群Server列表"""
        api = '/nacos/v1/ns/operator/servers'
        params = self._kwargs2dict(healthy=healthy)
        rsp = self._get_response(api, params)
        return [Server(**item) for item in self._paras_body(rsp)['servers']]

    def leader(self):
        """当前集群的leader"""
        raise NacosException('此协议已失效')
        # api = '/nacos/v1/ns/raft/leader'
        # rsp = self._get_response(api)
        # return self._paras_body(rsp)


class ThreadBeat(object):
    def __init__(self, nc, beat):
        self.nc = nc
        self.beat = beat
        self.__thread = None
        self.start()

    def start(self):
        if self.__thread is None:
            self.__loop_beat__()

    def __loop_beat__(self):
        if self.nc:
            beat_info = self.nc.beating(beat=self.beat)
            interval = float(beat_info.clientBeatInterval / 1000)
            self.__thread = Timer(interval, self.__loop_beat__)
            self.__thread.start()

    def stop(self):
        if self.__thread:
            self.__thread.cancel()
            self.__thread = None

    def __del__(self):
        if self.__thread:
            self.stop()


class NacosInstance(NacosClient):
    """实例
    >>> ns = NacosService('localhost', 'nacos', 'nacos')
    >>> ns.create('new.Service')
    True
    >>> ni = NacosInstance('localhost', 'nacos', 'nacos')
    >>> ni.register('new.Service', '127.0.0.1', 8081)
    True
    >>> ni.update('new.Service', '127.0.0.1', 8081, metadata={'description':'this is test data.'})
    True
    >>> type(ni.list('new.Service'))
    <class 'models.InstanceList'>
    >>> ni.list('new.Service').hosts[0].serviceName
    'DEFAULT_GROUP@@new.Service'
    >>> type(ni.query('new.Service', '127.0.0.1', 8081))
    <class 'models.InstanceInfo'>
    >>> type(ni.beating('new.Service', ip='127.0.0.1', port=8081))
    <class 'models.BeatInfo'>
    >>> type(ni.beating('new.Service', Beat(serviceName='DEFAULT_GROUP@@new.Service', ip='127.0.0.1', port=8081)))
    <class 'models.BeatInfo'>
    >>> ni.delete('new.Service', '127.0.0.1', 8081)
    True
    >>> ns.delete('new.Service')
    True
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__thread_beats__ = {}  # {(service,ip,port): Timer()}

    def register(self, service, ip, port,
                 name_space=None,weight=None,enabled=None,healthy=None,
                 metadata=None,cluster=None,group=None,ephemeral=None
                 ) ->bool:
        """注册实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self._kwargs2dict(serviceName=service, ip=ip, port=port,
                                   groupName=group,
                                   namespaceId=name_space,
                                   weight=weight,
                                   enabled=enabled,
                                   healthy=healthy,
                                   metadata=metadata,
                                   clusterName=cluster,
                                   ephemeral=ephemeral)
        rsp = self._get_response(api, params, 'POST')
        return self._paras_body(rsp) == 'ok'

    def delete(self, service, ip, port,
               group=None, cluster=None, name_space=None, ephemeral=None
               )->bool:
        """删除实例"""
        api = '/nacos/v1/ns/instance'
        params = self._kwargs2dict(serviceName=service, ip=ip, port=port,
                                   groupName=group,
                                   clusterName=cluster,
                                   namespaceId=name_space,
                                   ephemeral=ephemeral)
        rsp = self._get_response(api, params, 'DELETE')
        return self._paras_body(rsp) == 'ok'

    def update(self, service, ip, port,
               group=None,cluster=None,name_space=None,weight=None,
               metadata=None,enabled=None,ephemeral=None)->bool:
        """更新实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self._kwargs2dict(serviceName=service, ip=ip, port=port,
                                   groupName=group,
                                   namespaceId=name_space,
                                   weight=weight,
                                   enabled=enabled,
                                   metadata=metadata,
                                   clusterName=cluster,
                                   ephemeral=ephemeral)
        rsp = self._get_response(api, params, 'PUT')
        return self._paras_body(rsp) == 'ok'

    def query(self, service, ip, port,
              group=None, name_space=None, cluster=None,
              healthy_only=False, ephemeral=None) ->InstanceInfo:
        """获取实例信息"""
        api = '/nacos/v1/ns/instance'
        params = self._kwargs2dict(serviceName=service, ip=ip, port=port,
                                   groupName=group,
                                   namespaceId=name_space,
                                   clusterName=cluster,
                                   healthyOnly=healthy_only,
                                   ephemeral=ephemeral)
        rsp = self._get_response(api, params)
        return InstanceInfo(**self._paras_body(rsp))

    def list(self, service,
             group=None,name_space=None,cluster=None,healthy_only=False
             )->InstanceList:
        """查询实例列表"""
        api = '/nacos/v1/ns/instance/list'
        params = self._kwargs2dict(serviceName=service,
                                   groupName=group,
                                   namespaceId=name_space,
                                   clusters=cluster,
                                   healthyOnly=healthy_only)
        rsp = self._get_response(api, params)
        return InstanceList(**self._paras_body(rsp))

    def select_one(self, service, cluster=None)->InstanceItem:
        """随机选取一名幸运观众 :)"""
        instances = self.list(service, cluster=cluster, healthy_only=True).hosts
        if len(instances) < 1:
            raise NacosClientException(f'no healthy instances for service {service}')
        sel = randint(0, len(instances)-1)
        return instances[sel]

    @staticmethod
    def get_beat(service=None, ip=None, port=None, group=None,
                 cluster:str=None, scheduled:bool=None, weight:int=None,
                 metadata:dict=None, beat:Beat=None)-> Beat:
        assert beat or (service and ip and port)
        if beat is None:
            group = group if group else DEFAULT_GROUP_NAME
            beat = Beat(serviceName=f'{group}@@{service}',
                        ip=ip,
                        port=port)
        if cluster: beat.cluster = cluster
        if scheduled: beat.scheduled = scheduled
        if weight: beat.weight = weight
        if metadata: beat.metadata = metadata
        return beat

    def calc_item(self, d: Union[dict, list, tuple]):
        """如果字典值、列表项是函数,使它们的值为函数的返回值"""
        for k, v in d.items():
            if callable(v):
                d[k] = v()
            elif isinstance(v, (list, tuple)):
                self.calc_item(d[k])

    def beating(self, beat:Beat=None, service=None, ip=None, port=None,
                group=None, cluster:str=None, scheduled:bool=None,
                weight: int = None, metadata:dict=None, ephemeral=None,
                )->BeatInfo:
        """实例心跳"""
        api = '/nacos/v1/ns/instance/beat'
        beat = self.get_beat(service=service, ip=ip, port=port, group=group,
                             cluster=cluster, scheduled=scheduled,
                             weight=weight, metadata=metadata, beat=beat)
        new_beat = deepcopy(beat)
        self.calc_item(new_beat.metadata)
        print(f'NacosInstance.beating:{new_beat}')
        if service is None:
            service = beat.serviceName.split('@')[-1]
        group = group if group else DEFAULT_GROUP_NAME
        params = self._kwargs2dict(serviceName=service,
                                   beat=new_beat.json(separators=(',',':')),
                                   groupName=group,
                                   ephemeral=ephemeral)
        rsp = self._get_response(api, params, 'PUT')
        return BeatInfo(**self._paras_body(rsp))

    def beating_start(self, beat: Beat):
        """开始自动心跳
        for example:
            if not ni.register(service,ip,port):
                raise NacosException('无法注册服务')

            self.beat = ni.get_beat(service, ip, port,
                                    metadata={'starttime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

            if not ni.beating_start(self.beat):
                raise NacosException('开始自动心跳失败')
        """
        if beat:
            s_beat = beat.json(separators=(',',':'),exclude={'metadata'})
            if s_beat not in self.__thread_beats__.keys():
                self.__thread_beats__[s_beat] = ThreadBeat(self, beat)

    def beating_stop(self, beat:Beat):
        """停止自动心跳
        """
        if beat:
            s_beat = beat.json(separators=(',',':'),exclude={'metadata'})
            if s_beat in self.__thread_beats__.keys():
                self.__thread_beats__.pop(s_beat)


class NacosNameSpace(NacosClient):
    """命名空间
    >>> nn = NacosNameSpace('localhost', 'nacos', 'nacos')
    >>> nn.create('test', 'test.c1')
    True
    >>> nn.update('test', 'test.c2','modify name')
    True
    >>> for item in nn.query():
    ...     print(f'{item.namespace}({item.namespaceShowName}):{item.quota},{item.configCount},{item.type}')
    (public)...
    test(test.c2)...
    >>> nn.delete('test')
    True
    """
    api = '/nacos/v1/console/namespaces'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def query(self) -> List[NameSpace]:
        """查询命名空间"""
        rsp = self._get_response(self.api)
        result = self._paras_body(rsp)
        if result['code'] != 200:
            raise NacosException(result['message'])
        return [NameSpace(**item) for item in result['data']]

    def create(self, name_space:str, show_name: str, desc: str=None)->bool:
        paras = self._kwargs2dict(customNamespaceId=name_space,
                                  namespaceName=show_name,
                                  namespaceDesc=desc)
        rsp = self._get_response(self.api, paras, 'POST')
        return self._paras_body(rsp)

    def update(self, name_space:str, show_name: str, desc: str)->bool:
        """修改命名空间"""
        paras = self._kwargs2dict(namespace=name_space,
                                  namespaceShowName=show_name,
                                  namespaceDesc=desc)
        rsp = self._get_response(self.api, paras, 'PUT')
        return self._paras_body(rsp)

    def delete(self, name_space:str)->bool:
        paras = self._kwargs2dict(namespaceId=name_space)
        rsp = self._get_response(self.api, paras, 'DELETE')
        return self._paras_body(rsp)


__note__ = '''
if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
'''
