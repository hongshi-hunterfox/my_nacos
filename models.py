# coding=utf-8
from pydantic import BaseModel
from typing import Optional,List,Any


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
    instanceHeartBeatInterval: int
    ipDeleteTimeout: int
    instanceHeartBeatTimeOut: int


class InstanceList(BaseModel):
    name: str
    groupName: str
    clusters: str
    cacheMillis: int
    hosts: List[InstanceItem]
    lastRefTime: int
    checksum: Optional[str]
    allIPs: bool
    reachProtectionThreshold: bool
    valid: bool


class Beat(BaseModel):
    serviceName: str
    ip: str
    port: int
    cluster: str = 'public'
    scheduled: bool = True
    metadata: dict = {}
    weight: int = 1


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
