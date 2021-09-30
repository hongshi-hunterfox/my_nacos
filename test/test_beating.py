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


ni.beating_start(beat)
uvicorn.run(app = app,
            host = '127.0.0.1',
            port = 7333,
            )
