# coding=utf-8
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from py_nacos import NacosInstance,NacosConfig,Beat


def s_time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


app = FastAPI(title='NacosInstance.beating Test',
              description='Test method "beating_start" for class "NacosInstance"')
CONST_NACOS_LOGON = ('localhost', 'nacos', 'nacos')
ni = NacosInstance(*CONST_NACOS_LOGON)
nc = NacosConfig(*CONST_NACOS_LOGON)
beat = Beat(serviceName='test-beat', ip='127.0.0.1', port=7333,
            metadata={'starttime': s_time_now(), 'lasttime': s_time_now})


@app.router.get('/')
def default():
    return 'Nacos 心跳测试页面'


@app.router.get('/up')
def up():
    """如果服务自动心跳已经停止,这将重新开始该服务的自动心跳"""
    ni.register('test-beat', '127.0.0.1', 7333,
                metadata={'starttime': s_time_now(),
                          'lasttime': s_time_now()})
    ni.beating_start(beat)
    return 'ok'


@app.router.get('/down')
def down():
    """停止该服务的自动心跳"""
    ni.delete('test-beat', '127.0.0.1', 7333)
    ni.beating_stop(beat)
    return 'ok'

@app.router.get('/testjson')
def testjson():
    """返回该配置的当前值"""
    return nc.get('test_json').data


ni.beating_start(beat)  # 这将开始并保持 test-beat 服务的自动心跳
nc.listening('test_json')  # 这将开始对配置 test_json 的监听
uvicorn.run(app = app,
            host = '127.0.0.1',
            port = 7333,
            )
ni.beating_stop(beat)
