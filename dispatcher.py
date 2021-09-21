# coding=utf-8
"""Nacos API 调用"""
import re
from datetime import datetime
from urllib.parse import urlencode
from requests import Response, request
import yaml,json
from typing import Union
from models import *


DEFAULT_GROUP_NAME = 'DEFAULT_GROUP'


class NacosException(BaseException): pass
class NacosClientException(BaseException): pass

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
    def parse_server_addr(url: str) -> str:
        """为服务地址补全协议头、端口"""
        if not re.match(r'https?://.+', url):
            url = 'http://' + url
        if not re.match(r'.+:\d+$', url):
            return url + ':8848'
        elif not re.match(r'.+:\d{2,5}$', url):
            return re.sub(r':\d+$', ':8848', url)

    @staticmethod
    def kwargs2dict(**kwargs) -> dict:
        """将所有命名参数整合为一个字典,排除值为None的"""
        d_result = {}
        for k,v in kwargs.items():
            if k in ['group', 'groupName'] and v is None:
                v = DEFAULT_GROUP_NAME
            if v:
                d_result[k] = v
        return d_result

    @staticmethod
    def paras_body(res: Response) -> Any:
        if 'json' in res.headers['content-type']:
            return json.loads(res.text)
        else:  # 'text' in res.headers['content-type']:
            return res.text

    def __init__(self, server: str, user:str=None,pwd:str=None):
        self.server = self.parse_server_addr(server)
        self.token = Token(self.server, user, pwd) if user and pwd else None

    def get_full_path(self, *args, params:dict=None) -> str:
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

    def get_response(self,path:str, params:dict=None, method:str='GET') -> Response:
        """各种请求方式实现"""
        assert method in['POST', 'GET','PUT','DELETE'], NacosClientException('不支持的请求方法')
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = None
        if method == 'POST':
            url = self.get_full_path(self.server, path)
            data = urlencode(params)
        else:  # GET,PUT,DELETE
            url = self.get_full_path(self.server, path, params=params)
        # print('------------NacosClient.get_response------------')
        # print(f'{method} {url}')
        # print(f'headers:{headers}')
        # if data:
        #     print(f'data:{data}')
        rsp = request(method, url, data = data, headers=headers)
        if rsp is None or rsp.status_code != 200:
            raise NacosException(rsp.status_code, rsp.text)
        return rsp


class NacosConfig(NacosClient):
    """配置
    >>> nc = NacosConfig('localhost', 'nacos', 'nacos')
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

    @staticmethod
    def paras(source_type, source_data) -> dict:
        """将配置数据按格式转码为dict"""
        if source_type == 'yaml':
            return yaml.load(source_data, Loader=yaml.SafeLoader)
        elif source_type == 'json':
            return json.loads(source_data)

    def listener(self, data_id, group=None, tenant=None):
        """监听配置
        这需要建立一个线程池来管理:
            每个data_id对应一个异步请求
            建立迅步请求并等待回复
            得到回复后更新config_buffer并重建请求
            线程池销毁时要清理所有异步请求
        """
        raise NacosException('此功能尚未实现')

    def get(self, data_id, path, group=None, tenant=None) -> Any:
        """取配置值
        >>> nc = NacosConfig('localhost', 'nacos', 'nacos')
        >>> print(nc.get('test_yaml', 'spring.datasource.dynamic.enabled'))
        False
        >>> print(nc.get('test_json', 'keys.secretKey'))
        iGNddHce42LNtOc0sc58p94ayRxZNR
        """
        api = '/nacos/v1/cs/configs'
        params = self.kwargs2dict(dataId=data_id, group=group, tenant=tenant)
        rsp = self.get_response(api, params)
        cfg = self.paras(rsp.headers['config-type'], rsp.text)
        try:
            for key in path.split('.'):
                cfg = cfg[key]
            return cfg
        except (BaseException,) as err:
            raise NacosException(err)

    def post(self, data_id, data, group=None, tenant=None, data_type=None
             ) -> bool:
        """发布配置
        发布配置时,data_id必需是已存在于Nacos服务中的"""
        api = '/nacos/v1/cs/configs'
        params = self.kwargs2dict(dataId=data_id, content=data, group=group,
                                  tenant=tenant,type=data_type)
        rsp = self.get_response(api, params, method='POST')
        return self.paras_body(rsp)

    def delete(self, data_id, group=None, tenant=None) -> bool:
        """删除配置"""
        api = '/nacos/v1/cs/configs'
        params = self.kwargs2dict(dataId=data_id, group=group, tenant=tenant)
        rsp = self.get_response(api, params, method='DELETE')
        return self.paras_body(rsp)

    def history(self, data_id,
                group=None, tenant=None, page_no=None, page_size=None, nid=None
                ) -> dict:
        """查询配置历史"""
        api = '/nacos/v1/cs/history'
        if nid is None:
            params = self.kwargs2dict(search='accurate',
                                      dataId=data_id, group=group, tenant=tenant,
                                      pageNo=page_no, pageSize=page_size)
        else:
            params = self.kwargs2dict(dataId=data_id, group=group, tenant=tenant,
                                      nid=nid)
        rsp = self.get_response(api, params)
        return self.paras_body(rsp)

    def previous(self,  nid, data_id, group=None, tenant=None):
        """查询配置上一版本信息
        此API未调通: 无有效的nid
        """
        raise NacosException('此功能尚未实现')
        # api = '/nacos/v1/cs/history/previous'
        # params = self.kwargs2dict(id=nid,
        #                           dataId=data_id, group=group, tenant=tenant)
        # rsp = self.get_response(api, params)
        # return self.paras_body(rsp)

    def value(self, data_id, path, group=None, tenant=None):
        """这是一个装饰器,用于装饰属性的get方法
        被装饰的属性总是返回nacos相应配置项的值
        """
        def func_wrapper(func):
            def call_func(*args, **kwargs):
                return self.get(data_id, path, group, tenant)
            return call_func
        return func_wrapper

    def values(self, data_id, path, group=None, tenant=None):
        """这是一个类装饰器,用于装饰一个类
        被装饰的类中与指定配置的子项同名的属性将得到相应的值
        """
        def class_wrapper(_class):
            """读取配置值作为类的属性"""
            def call_class(*args,**kwargs):
                instance = _class(*args,**kwargs)
                # 为实例写入属性
                cfg = self.get(data_id, path, group, tenant)
                for key in cfg.keys():
                    if key in instance.__dict__.keys() \
                            or key in instance.__class__.__dict__:
                        instance.__dict__[key] = cfg.get(key)
                return instance
            return call_class
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
        params = self.kwargs2dict(serviceName=service,
                                  groupName=group,
                                  namespaceId=name_space,
                                  protectThreshold=protect_threshold,
                                  metadata=metadata,
                                  selector=selector)
        rsp = self.get_response(api, params, 'POST')
        return self.paras_body(rsp) == 'ok'

    def query(self, service, group=None, name_space=None) -> Service:
        """查询服务
        不能以该接口是否返回值来判断服务是否存在"""
        api = '/nacos/v1/ns/service'
        params = self.kwargs2dict(serviceName=service,
                                  groupName=group,
                                  namespaceId=name_space)
        rsp = self.get_response(api, params)
        return Service(**self.paras_body(rsp))

    def update(self, service, protect_threshold:float,
               group=None, name_space=None, metadata=None, selector=None
               ) -> bool:
        """修改服务"""
        api = '/nacos/v1/ns/service'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        if selector and not isinstance(selector, str):
            selector = json.dumps(selector)
        params = self.kwargs2dict(serviceName=service,
                                  groupName=group,
                                  namespaceId=name_space,
                                  protectThreshold=protect_threshold,
                                  metadata=metadata,
                                  selector=selector)
        rsp = self.get_response(api, params, 'PUT')
        return self.paras_body(rsp) == 'ok'

    def delete(self, service, group=None, name_space=None) -> bool:
        """删除服务"""
        api = '/nacos/v1/ns/service'
        params = self.kwargs2dict(serviceName=service,
                                  groupName=group,
                                  namespaceId=name_space)
        rsp = self.get_response(api, params, 'DELETE')
        return self.paras_body(rsp) == 'ok'

    def list(self, page_no:int=1, page_size:int=10,
             group=None, name_space=None) -> ServicesList:
        """服务列表"""
        api = '/nacos/v1/ns/service/list'
        params = self.kwargs2dict(pageNo=page_no,
                                  pageSize=page_size,
                                  groupName=group,
                                  namespaceId=name_space)
        rsp = self.get_response(api, params)
        return ServicesList(**self.paras_body(rsp))

    def switches(self, entry=None, value=None, debug=False
                 ) -> Union[bool, Switches]:
        """系统开关"""
        api = '/nacos/v1/ns/operator/switches'
        if entry and value:
            params = self.kwargs2dict(entry=entry,
                                      value=value,
                                      debug=debug)
            rsp = self.get_response(api, params, 'PUT')
            return self.paras_body(rsp) == 'ok'
        else:
            rsp = self.get_response(api)
            return Switches(**self.paras_body(rsp))

    def metrics(self) ->Metrics:
        """当前数据指标"""
        api = '/nacos/v1/ns/operator/metrics'
        rsp = self.get_response(api)
        return Metrics(**self.paras_body(rsp))

    def servers(self, healthy:bool=None)-> List[Server]:
        """集群Server列表"""
        api = '/nacos/v1/ns/operator/servers'
        params = self.kwargs2dict(healthy=healthy)
        rsp = self.get_response(api, params)
        return [Server(**item) for item in self.paras_body(rsp)['servers']]

    def leader(self):
        """当前集群的leader"""
        raise NacosException('此协议已失效')
        # api = '/nacos/v1/ns/raft/leader'
        # rsp = self.get_response(api)
        # return self.paras_body(rsp)


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

    def register(self, service, ip, port,
                 name_space=None,weight=None,enabled=None,healthy=None,
                 metadata=None,cluster=None,group=None,ephemeral=None) ->bool:
        """注册实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self.kwargs2dict(serviceName=service, ip=ip, port=port,
                                  groupName=group,
                                  namespaceId=name_space,
                                  weight=weight,
                                  enabled=enabled,
                                  healthy=healthy,
                                  metadata=metadata,
                                  clusterName=cluster,
                                  ephemeral=ephemeral)
        rsp = self.get_response(api, params, 'POST')
        return self.paras_body(rsp) == 'ok'

    def delete(self, service, ip, port,
               group=None, cluster=None, name_space=None, ephemeral=None)->bool:
        """删除实例"""
        api = '/nacos/v1/ns/instance'
        params = self.kwargs2dict(serviceName=service, ip=ip, port=port,
                                  groupName=group,
                                  clusterName=cluster,
                                  namespaceId=name_space,
                                  ephemeral=ephemeral)
        rsp = self.get_response(api, params, 'DELETE')
        return self.paras_body(rsp) == 'ok'

    def update(self, service, ip, port,
               group=None,cluster=None,name_space=None,weight=None,
               metadata=None,enabled=None,ephemeral=None)->bool:
        """更新实例"""
        api = '/nacos/v1/ns/instance'
        if metadata and not isinstance(metadata,str):
            metadata = json.dumps(metadata)
        params = self.kwargs2dict(serviceName=service, ip=ip, port=port,
                                  groupName=group,
                                  namespaceId=name_space,
                                  weight=weight,
                                  enabled=enabled,
                                  metadata=metadata,
                                  clusterName=cluster,
                                  ephemeral=ephemeral)
        rsp = self.get_response(api, params, 'PUT')
        return self.paras_body(rsp) == 'ok'

    def query(self, service, ip, port,
            group=None, name_space=None, cluster=None,
            healthy_only=False, ephemeral=None) ->InstanceInfo:
        """获取实例信息"""
        api = '/nacos/v1/ns/instance'
        params = self.kwargs2dict(serviceName=service, ip=ip, port=port,
                                  groupName=group,
                                  namespaceId=name_space,
                                  clusterName=cluster,
                                  healthyOnly=healthy_only,
                                  ephemeral=ephemeral)
        rsp = self.get_response(api, params)
        return InstanceInfo(**self.paras_body(rsp))

    def list(self, service,
             group=None,name_space=None,cluster=None,healthy_only=False
             )->InstanceList:
        """查询实例列表"""
        api = '/nacos/v1/ns/instance/list'
        params = self.kwargs2dict(serviceName=service,
                                  groupName=group,
                                  namespaceId=name_space,
                                  clusters=cluster,
                                  healthyOnly=healthy_only)
        rsp = self.get_response(api, params)
        return InstanceList(**self.paras_body(rsp))

    def beating(self, service, beat:Beat=None, group=None, ephemeral=None,
                ip=None, port=None, cluster:str=None, scheduled:bool=None,
                weight:int=None, metadata:dict=None
                )->BeatInfo:
        """实例心跳"""
        assert beat or (ip and port)
        api = '/nacos/v1/ns/instance/beat'
        if beat is None:
            beat = Beat(serviceName=f'{group if group else DEFAULT_GROUP_NAME}@@{service}',
                        ip=ip,
                        port=port)
            if cluster: beat.cluster = cluster
            if scheduled: beat.scheduled = scheduled
            if weight: beat.weight = weight
            if metadata: beat.metadata = metadata
        params = self.kwargs2dict(serviceName=service,beat=beat.json(),
                                  groupName=group,ephemeral=ephemeral)
        rsp = self.get_response(api, params, 'PUT')
        return BeatInfo(**self.paras_body(rsp))

    def autobeating(self):
        # TODO: 装饰器
        #   在对象存续期定时调用beating
        pass


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
        rsp = self.get_response(self.api)
        result = self.paras_body(rsp)
        if result['code'] != 200:
            raise NacosException(result['message'])
        return [NameSpace(**item) for item in result['data']]

    def create(self, id:str, show_name: str, desc: str=None)->bool:
        paras = self.kwargs2dict(customNamespaceId=id,
                                 namespaceName=show_name,
                                 namespaceDesc=desc)
        rsp = self.get_response(self.api, paras, 'POST')
        return self.paras_body(rsp)

    def update(self, id:str, show_name: str, desc: str)->bool:
        """修改命名空间"""
        paras = self.kwargs2dict(namespace=id,
                                 namespaceShowName=show_name,
                                 namespaceDesc=desc)
        rsp = self.get_response(self.api, paras, 'PUT')
        return self.paras_body(rsp)

    def delete(self, id:str)->bool:
        paras = self.kwargs2dict(namespaceId=id)
        rsp = self.get_response(self.api, paras, 'DELETE')
        return self.paras_body(rsp)


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)


