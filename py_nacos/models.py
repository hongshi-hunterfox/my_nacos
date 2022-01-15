# -*- coding: utf-8 -*-
import yaml
import json
import re
from pydantic import BaseModel
from typing import Optional, List, Any

from .consts import DEFAULT_GROUP_NAME
from .exceptions import NacosClientException
from .utils import Xml2Dict, Properties2Dict


class ConfigData(BaseModel):
    config_type: str
    config_md5: str
    data: str

    @property
    def data_obj(self):
        if self.config_type == 'yaml':
            return yaml.load(self.data, Loader=yaml.SafeLoader)
        elif self.config_type == 'json':
            return json.loads(self.data)
        elif self.config_type == 'xml':
            return Xml2Dict.loads(self.data)
        elif self.config_type == 'properties':
            return Properties2Dict.loads(self.data)
        else:  # text/html
            return self.data

    def value(self, path: str):
        re_idx = re.compile(r'(.+)\[(\d+)]')
        path = path if path else ''
        data = self.data_obj
        try:
            for key in path.split('.'):
                key_idx = re_idx.match(key)
                if key_idx:
                    key, idx = key_idx.groups()
                    data = data[key][eval(idx)]
                elif key not in ('', None):
                    data = data[key]
                else:
                    break
        except (BaseException,) as err:
            raise NacosClientException(err)
        return data


class ServicesList(BaseModel):
    count: int
    doms: List[str]


class Service(BaseModel):
    namespaceId: str
    groupName: str
    name: str
    protectThreshold: float
    metadata: dict
    selector: dict
    clusters: List[Any]


class Health(BaseModel):
    max: int
    min: int
    factor: float


class Switches(BaseModel):
    name: str
    masters: Optional[str]
    adWeightMap: dict
    defaultPushCacheMillis: int
    clientBeatInterval: int
    defaultCacheMillis: int
    distroThreshold: float
    healthCheckEnabled: bool
    distroEnabled: bool
    enableStandalone: bool
    pushEnabled: bool
    checkTimes: int
    httpHealthParams: Health
    tcpHealthParams: Health
    mysqlHealthParams: Health
    incrementalList: List[Any]
    serverStatusSynchronizationPeriodMillis: int
    serviceStatusSynchronizationPeriodMillis: int
    disableAddIP: bool
    sendBeatOnly: bool
    lightBeatEnabled: Optional[bool]
    doubleWriteEnabled: Optional[bool]
    limitedUrlMap: dict
    distroServerExpiredMillis: int
    pushGoVersion: str
    pushJavaVersion: str
    pushPythonVersion: str
    pushCVersion: str
    enableAuthentication: bool
    overriddenServerStatus: Optional[str]
    defaultInstanceEphemeral: bool
    healthCheckWhiteList: List[Any]
    checksum: Optional[str]


class Metrics(BaseModel):
    status: str
    serviceCount: Optional[int]
    load: Optional[float]
    mem: Optional[float]
    responsibleServiceCount: Optional[int]
    instanceCount: Optional[int]
    cpu: Optional[float]
    responsibleInstanceCount: Optional[int]


class Server(BaseModel):
    ip: str
    servePort: Optional[int]
    site: Optional[str]
    weight: Optional[int]
    adWeight: Optional[int]
    alive: Optional[bool]
    lastRefTime: Optional[int]
    lastRefTimeStr: Optional[str]
    key: Optional[str]


class InstanceInfo(BaseModel):
    service: str
    ip: str
    port: int
    clusterName: str
    weight: float
    healthy: bool
    instanceId: str
    metadata: dict


class InstanceItem(BaseModel):
    instanceId: str
    ip: str
    port: int
    weight: float
    healthy: bool
    enabled: bool
    ephemeral: bool
    clusterName: str
    serviceName: str
    metadata: dict
    instanceHeartBeatInterval: Optional[int]
    ipDeleteTimeout: Optional[int]
    instanceHeartBeatTimeOut: Optional[int]

    @property
    def host(self):
        return f'{self.ip}:{self.port}'


class InstanceList(BaseModel):
    name: str
    clusters: str
    hosts: List[InstanceItem]
    groupName: Optional[str]
    cacheMillis: Optional[int]
    lastRefTime: Optional[int]
    checksum: Optional[str]
    allIPs: Optional[bool]
    reachProtectionThreshold: Optional[bool]
    valid: Optional[bool]


class Beat(BaseModel):
    serviceName: str
    ip: str
    port: int
    cluster: str = 'public'
    scheduled: bool = True
    metadata: dict = {}
    weight: int = 1

    def __str__(self):
        return self.json(separators=',:', exclude={'metadata'})


class BeatInfo(BaseModel):
    clientBeatInterval: int
    code: int
    lightBeatEnabled: bool


class NameSpace(BaseModel):
    namespace: str
    namespaceShowName: str
    quota: int
    configCount: int
    type: int


class Listening(BaseModel):
    """监听项
    >>> a = Listening(data_id='xml_data')
    >>> b = Listening(data_id='xml_data')
    >>> a == b
    True
    >>> dit = {a:33}
    >>> dit[b]
    33
    """
    data_id: str
    group: Optional[str]
    tenant: Optional[str]
    md5: Optional[str]

    def __str__(self):
        lst = [self.data_id,
               self.group if self.group else DEFAULT_GROUP_NAME,
               self.md5 if self.md5 else '']
        if self.tenant:
            lst.append(self.tenant)
        s = chr(2).join(lst)
        return s + chr(1)

    def __eq__(self, other):
        return self.data_id == other.data_id and \
               self.group == other.group and \
               self.tenant == other.tenant

    def __hash__(self):
        return hash(self.json(exclude={'md5'}))


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
