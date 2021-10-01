# coding=utf-8
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from source import NacosInstance,Beat


def s_time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


app = FastAPI(title='NacosInstance.beating Test',
              description='Test method "beating_start" for class "NacosInstance"')
ni = NacosInstance('localhost', 'nacos', 'nacos')
beat = Beat(serviceName='test-beat', ip='127.0.0.1', port=7333,
            metadata={'starttime': s_time_now(), 'lasttime': s_time_now})


@app.router.get('/')
def default():
    return 'Nacos 心跳测试页面'

@app.router.get('/up')
def up():
    try:
        ni.register('test-beat', '127.0.0.1', 7333,
                    metadata={'starttime': s_time_now(),
                              'lasttime': s_time_now()})
        ni.beating_start(beat)
        ok=True
    except (BaseException,):
        ok=False
    return ok

@app.router.get('/down')
def down():
    try:
        ni.delete('test-beat', '127.0.0.1', 7333)
        ni.beating_stop(beat)
        ok=True
    except (BaseException,):
        ok=False
    return ok

ni.beating_start(beat)
uvicorn.run(app = app,
            host = '127.0.0.1',
            port = 7333,
            )
ni.beating_stop(beat)