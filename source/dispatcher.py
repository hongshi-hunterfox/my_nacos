# -*- coding: utf-8 -*-
"""Nacos API 调用"""
import re, json, hashlib
from copy import deepcopy
from random import randint
from functools import wraps
from datetime import datetime
from urllib.parse import urlencode,unquote
from requests import Response, request
from typing import Union,Callable,Any,List,Dict

from .buffer import new_buffer
from .threads import ThreadBeat, ConfigListener
from .exceptions import NacosException, NacosClientException
from .consts import DEFAULT_GROUP_NAME, ConfigBufferMode
from .models import Service, ServicesList, Switches, Metrics, Server, \
    InstanceInfo, InstanceList, Beat, BeatInfo, NameSpace, InstanceItem, \
    ConfigData


class Token(object):
    """在accessToken未过期时,它不会重复请求"""
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
    """API封装基础类
        这不是异步的,所有需要异步的请求,应当在新的线程中去执行
    """
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
    def params(**kwargs) -> dict:
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

    @staticmethod
    def _def_headers(headers=None):
        if headers is None:
            headers = {}
        has_content_type = False
        for key in headers.keys():
            if key.title() == 'Content-Type':
                has_content_type = True
                break
        if not has_content_type:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return headers

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

    def request(self, path:str, params:dict=None,
                method:str='GET',headers=None
                ) -> Response:
        """各种请求方式实现"""
        assert method in['POST', 'GET','PUT','DELETE'],\
            NacosClientException('不支持的请求方法')
        headers = self._def_headers(headers)
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
    def __init__(self, *args,
                 buffer_mode:ConfigBufferMode = ConfigBufferMode.nothing,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = None
        if buffer_mode and buffer_mode!=ConfigBufferMode.nothing:
            pattern = re.compile(r'http[s]?://([\w.]+):(\d+).*')
            ip, port = pattern.search(self.server).groups()
            self.buffer = new_buffer(buffer_mode, ip, eval(port))
        self.listen_thread = ConfigListener(self.listener)

    def __del__(self):
        self.listen_thread = None

    @classmethod
    def _paras(cls, rsp: Response) -> ConfigData:
        """从 Response 生产 ConfigData"""
        config = ConfigData(config_type=rsp.headers['config-type'],
                            config_md5=rsp.headers['content-md5'],
                            data=rsp.text)
        return config

    def set_buffer(self, data_id, group, tenant, config):
        try:
            self.buffer.set(config, data_id, group, tenant)
        except (BaseException,):
            pass

    def listening(self, data_id, group=None, tenant=None):
        """添加自动监听配置项"""
        self.listen_thread.add(data_id, group, tenant)

    def stop_listen(self, data_id=None, group=None, tenant=None):
        """停止对指定配置的监听"""
        if self.listen_thread:
            if data_id:
                self.listen_thread.delete(data_id, group, tenant)
            else:
                self.listen_thread = None

    def listener(self, listening):
        """监听配置"""
        api = '/nacos/v1/cs/configs/listener'
        params = {'Listening-Configs': listening}
        headers = {'Long-Pulling-Timeout': '30000'}
        rsp = self.request(api, params, method='POST', headers=headers)
        if rsp.text == '':
            return  # 配置未发生变更
        data = unquote(rsp.text).replace('\n','')
        # 逐个配置更新
        for listen in data[:-1].split(chr(1)):
            params = listen.split(chr(2))
            params[1] = None if params[1]==DEFAULT_GROUP_NAME else params[1]
            try:
                self.buffer.delete(params)
            except (BaseException,):
                pass
            self.get(*params)

    def get(self, data_id, group=None, tenant=None) -> ConfigData:
        """取配置值"""
        try:
            config = self.buffer.get(data_id, group, tenant)
        except (BaseException,):
            config = None
        if config is None:
            api = '/nacos/v1/cs/configs'
            params = self.params(dataId=data_id, group=group, tenant=tenant)
            rsp = self.request(api, params)
            config = self._paras(rsp)
            self.listen_thread.update(data_id, group, tenant, config.config_md5)
            self.set_buffer(data_id, group, tenant, config)
        return config

    def post(self, data_id, data, group=None, tenant=None, data_type=None
             ) -> bool:
        """发布配置
        发布配置时,data_id必需是已存在于Nacos服务中的"""
        api = '/nacos/v1/cs/configs'
        params = self.params(dataId=data_id, content=data, group=group,
                             tenant=tenant,type=data_type)
        rsp = self.request(api, params, method='POST')
        success = self._paras_body(rsp)
        if success:
            md5 = hashlib.md5(data.encode()).hexdigest()
            config = ConfigData(config_type=data_type,
                                config_md5=md5,
                                data=data)
            self.set_buffer(data_id, group, tenant, config)
        return success

    def delete(self, data_id, group=None, tenant=None) -> bool:
        """删除配置"""
        api = '/nacos/v1/cs/configs'
        params = self.params(dataId=data_id, group=group, tenant=tenant)
        rsp = self.request(api, params, method='DELETE')
        success = self._paras_body(rsp)
        if success:
            try:
                self.buffer.delete(data_id, group, tenant)
            except (BaseException,):
                pass
        return success

    def history(self, data_id,
                group=None, tenant=None, page_no=None, page_size=None, nid=None
                ) -> dict:
        """查询配置历史"""
        api = '/nacos/v1/cs/history'
        if nid is None:
            params = self.params(search='accurate',
                                 dataId=data_id, group=group,
                                 tenant=tenant,
                                 pageNo=page_no, pageSize=page_size)
        else:
            params = self.params(dataId=data_id, group=group,
                                 tenant=tenant, nid=nid)
        rsp = self.request(api, params)
        return self._paras_body(rsp)

    def previous(self,  nid, data_id, group=None, tenant=None):
        """查询配置上一版本信息
        此API未调通: 无有效的nid
        """
        raise NacosException('此功能尚未实现')
        # api = '/nacos/v1/cs/history/previous'
        # params = self.params(id=nid, dataId=data_id,
        #                      group=group, tenant=tenant)
        # rsp = self.request(api, params)
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
            if key in instance.__dict__.keys() and \
                    instance.__dict__[key] is Callable:
                continue
            if key in _class.__dict__.keys() and \
                    _class.__dict__[key] is Callable:
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
        params = self.params(serviceName=service,
                             groupName=group,
                             namespaceId=name_space,
                             protectThreshold=protect_threshold,
                             metadata=metadata,
                             selector=selector)
        rsp = self.request(api, params, method='POST')
        return self._paras_body(rsp) == 'ok'

    def query(self, service, group=None, name_space=None) -> Service:
        """查询服务
        不能以该接口是否返回值来判断服务是否存在"""
        api = '/nacos/v1/ns/service'
        params = self.params(serviceName=service,
                             groupName=group,
                             namespaceId=name_space)
        rsp = self.request(api, params)
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
        params = self.params(serviceName=service,
                             groupName=group,
                             namespaceId=name_space,
                             protectThreshold=protect_threshold,
                             metadata=metadata,
                             selector=selector)
        rsp = self.request(api, params, method='PUT')
        return self._paras_body(rsp) == 'ok'

    def delete(self, service, group=None, name_space=None) -> bool:
        """删除服务"""
        api = '/nacos/v1/ns/service'
        params = self.params(serviceName=service,
                             groupName=group,
                             namespaceId=name_space)
        rsp = self.request(api, params, method='DELETE')
        return self._paras_body(rsp) == 'ok'

    def list(self, page_no:int=1, page_size:int=10,
             group=None, name_space=None) -> ServicesList:
        """服务列表"""
        api = '/nacos/v1/ns/service/list'
        params = self.params(pageNo=page_no,
                             pageSize=page_size,
                             groupName=group,
                             namespaceId=name_space)
        rsp = self.request(api, params)
        return ServicesList(**self._paras_body(rsp))

    def get_switches(self) -> Switches:
        """获取系统开关状态"""
        api = '/nacos/v1/ns/operator/switches'
        rsp = self.request(api)
        return Switches(**self._paras_body(rsp))

    def set_switches(self, entry, value, debug=False
                 ) -> Union[bool, Switches]:
        """设置系统开关"""
        api = '/nacos/v1/ns/operator/switches'
        params = self.params(entry=entry,
                             value=value,
                             debug=debug)
        rsp = self.request(api, params, method='PUT')
        return self._paras_body(rsp) == 'ok'

    def metrics(self) ->Metrics:
        """当前数据指标"""
        api = '/nacos/v1/ns/operator/metrics'
        rsp = self.request(api)
        return Metrics(**self._paras_body(rsp))

    def servers(self, healthy:bool=None)-> List[Server]:
        """集群Server列表"""
        api = '/nacos/v1/ns/operator/servers'
        params = self.params(healthy=healthy)
        rsp = self.request(api, params)
        return [Server(**item) for item in self._paras_body(rsp)['servers']]

    def leader(self):
        """当前集群的leader"""
        raise NacosException('此协议已失效')
        # api = '/nacos/v1/ns/raft/leader'
        # rsp = self.request(api)
        # return self._paras_body(rsp)


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
    beat_threads: Dict[str, ThreadBeat]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.beat_threads = {}

    def __del__(self):
        self.beat_threads = {}

    def register(self, service, ip, port,
                 name_space=None,weight=None,enabled=None,healthy=None,
                 metadata=None,cluster=None,group=None,ephemeral=None
                 ) ->bool:
        """注册实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self.params(serviceName=service, ip=ip, port=port,
                             groupName=group,
                             namespaceId=name_space,
                             weight=weight,
                             enabled=enabled,
                             healthy=healthy,
                             metadata=metadata,
                             clusterName=cluster,
                             ephemeral=ephemeral)
        rsp = self.request(api, params, method='POST')
        return self._paras_body(rsp) == 'ok'

    def delete(self, service, ip, port,
               group=None, cluster=None, name_space=None, ephemeral=None
               )->bool:
        """删除实例"""
        api = '/nacos/v1/ns/instance'
        params = self.params(serviceName=service, ip=ip, port=port,
                             groupName=group,
                             clusterName=cluster,
                             namespaceId=name_space,
                             ephemeral=ephemeral)
        rsp = self.request(api, params, method='DELETE')
        return self._paras_body(rsp) == 'ok'

    def update(self, service, ip, port,
               group=None,cluster=None,name_space=None,weight=None,
               metadata=None,enabled=None,ephemeral=None)->bool:
        """更新实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self.params(serviceName=service, ip=ip, port=port,
                             groupName=group,
                             namespaceId=name_space,
                             weight=weight,
                             enabled=enabled,
                             metadata=metadata,
                             clusterName=cluster,
                             ephemeral=ephemeral)
        rsp = self.request(api, params, method='PUT')
        return self._paras_body(rsp) == 'ok'

    def query(self, service, ip, port,
              group=None, name_space=None, cluster=None,
              healthy_only=False, ephemeral=None) ->InstanceInfo:
        """获取实例信息"""
        api = '/nacos/v1/ns/instance'
        params = self.params(serviceName=service, ip=ip, port=port,
                             groupName=group,
                             namespaceId=name_space,
                             clusterName=cluster,
                             healthyOnly=healthy_only,
                             ephemeral=ephemeral)
        rsp = self.request(api, params)
        return InstanceInfo(**self._paras_body(rsp))

    def list(self, service,
             group=None,name_space=None,cluster=None,healthy_only=False
             )->InstanceList:
        """查询实例列表"""
        api = '/nacos/v1/ns/instance/list'
        params = self.params(serviceName=service,
                             groupName=group,
                             namespaceId=name_space,
                             clusters=cluster,
                             healthyOnly=healthy_only)
        rsp = self.request(api, params)
        return InstanceList(**self._paras_body(rsp))

    def select_one(self, service, cluster=None)->Union[None,InstanceItem]:
        """随机选取一名幸运观众 :)"""
        instances = self.list(service, cluster=cluster, healthy_only=True).hosts
        if len(instances) < 1:
            return None  # 'no healthy instances
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
        if service is None:
            service = beat.serviceName.split('@')[-1]
        group = group if group else DEFAULT_GROUP_NAME
        params = self.params(serviceName=service,
                             beat=new_beat.json(separators=',:'),
                             groupName=group,
                             ephemeral=ephemeral)
        rsp = self.request(api, params, method='PUT')
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
            s_beat = str(beat)
            if s_beat not in self.beat_threads.keys():
                self.beat_threads[s_beat] = ThreadBeat(self.beating, 0, beat)

    def beating_stop(self, beat:Beat):
        """停止自动心跳
        """
        if beat:
            s_beat = str(beat)
            if s_beat in self.beat_threads.keys():
                self.beat_threads[s_beat].stop()
                self.beat_threads.pop(s_beat)


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

    def query(self) -> List[NameSpace]:
        """查询命名空间"""
        rsp = self.request(self.api)
        result = self._paras_body(rsp)
        if result['code'] != 200:
            raise NacosException(result['message'])
        return [NameSpace(**item) for item in result['data']]

    def create(self, name_space:str, show_name: str, desc: str=None)->bool:
        paras = self.params(customNamespaceId=name_space,
                            namespaceName=show_name,
                            namespaceDesc=desc)
        rsp = self.request(self.api, paras, method='POST')
        return self._paras_body(rsp)

    def update(self, name_space:str, show_name: str, desc: str)->bool:
        """修改命名空间"""
        paras = self.params(namespace=name_space,
                            namespaceShowName=show_name,
                            namespaceDesc=desc)
        rsp = self.request(self.api, paras, method='PUT')
        return self._paras_body(rsp)

    def delete(self, name_space:str)->bool:
        paras = self.params(namespaceId=name_space)
        rsp = self.request(self.api, paras, method='DELETE')
        return self._paras_body(rsp)


__note__ = '''
if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
'''

