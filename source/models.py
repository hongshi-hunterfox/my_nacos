# -*- coding: utf-8 -*-
import yaml, json
from pydantic import BaseModel
from typing import Optional,List,Any
from .exceptions import NacosClientException
from .utils import Xml2Dict,Properties


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
            return Properties.loads(self.data)
        else:  # text/html
            return self.data

    def value(self, path: str):
        path = path if path else ''
        data = self.data_obj
        try:
            for key in path.split('.'):
                data = data[key]
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
        return self.json(separators=(',',':'), exclude={'metadata'})


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
