# Nacos客户端

### 支持启用/未启用 auth 的 Nacos

```
# 启用 auth 的 Nacos
ncs = NacosConfig('localhost', 'nacos', 'nacos')
# 未启用 auth 的 Nacos
ncs = NacosConfig('localhost')
```


### NacosConfig
* NacosConfig
   * `get()`
      * 它总是返回一个`ConfigData`对象
      * 想要得到配置中的一个具体的值,可以使用`ConfigData`的`value`方法:
         * `s = NacosConfig(...).get('Properties-config').value('a.b.d')`
   * `start_listen()`
      * 开始监听配置变更
      * 对同一个配置的监听请求只会生效一次
      * 当监听到配置的变更,会从Nacos服务获取相应的配置并更新本地缓存(如果有启用的话)
   * `stop_listen()`
      * 停止对某个配置的监听
      * 如果不传递参数`data_id`,则停止所有配置的监听
   * `@value`
      * 可以使用它装饰一个属性的Get方法
      * 相应的属性总是返回配置项的值
   * `@values`
      * 可以使用它来装饰一个类
      * 相应的类如果有与配置项的子项同名的属性,则它们被赋值
      * 包括类属性与实例属性
   * `@listening`
      * 可以使用它将函数与配置项监听绑定,当相应的配置项值变更时,会触发该函数
      * 该函数必需能接受两个位置参数的调用形式: `func(value, path)`

> 示例代码 `test/test.py`


* NacosInstance
   * `NacosInstance` 提供服务实例注册功能，同时，简化服务心跳处理，提供了`beating_start`和`beating_stop`
   * 一个`NacosInstance`实例同时最多维持一个自动心跳,当停止一个自动心跳后,可以使用同一个实例来维持一个新的自动心跳
   * `select_one`
      * 它将返回指定服务的一个健康实例的服务地址
      * 示例:
```
ni = NacosInstance(...)
...
host = ni.select_one('test-beat')
if host:
    url = 'http://{host}/testjson'
    res = request('GET', url)
    print(res.text)
```

   * `get_beat`
      * 它用来创建自动心跳需要的参数:
      * 参数`metadata`中的value可以引用无参数函数,它们将会在这里进行计算取值
   * `beating_start`
      * 开始服务心跳循环
      * 在`NacosInstance`实例未销毁期间，它将维持`beating`,直到:
         * 以合适的参数调用了`beating_stop` 或 该`NacosInstance`实例销毁
   * `beating_stop`
      * 停止相应服务的心跳循环


> 示例代码 `test/test_beating.py`


### 关于配置的格式
* `json`/`xml`/`yaml`/`properties`类型的配置文档将自动解析
   * 这类文档可以使用`key.key.key`的格式来访问相应的配置值
   * `xml`类配置的解析忽略所有的节点属性
   * `xml`最底层的值始终解析为字符串

### `test`中的示例
* `test/test.py`
   * 它假定在`localhost:8848`有一个启用了auth验证的Nacos服务
   * 它会改写配置`test_json`、`xml_data`,`Properties-config`
   * 它主要演示了装饰器`@values`和`@value`
   * 它还包含了`NacosConfig().get().value()`的使用演示
* `test/test_nacos.py`
    * 它假定在`localhost:8001`有一个未启用auth验证的Nacos服务
    * 它假定所有操作均是对命名空间`dev`的
    * 它假定该Nacos服务中有配置`ces-post-loan-dev.yaml`
       * 它假定该配置包含配置项`movie[0].format`
    * 它主要演示了`NacosService`、`NacosInstance`、'NacosConfig'的基本使用方式
* `test/test_beating.py`
    * 它需要`fastapi`和`uvicorn`环境
    * 它假定在`localhost:8848`有一个启用了auth验证的Nacos服务
    * 它假定Nacos服务中有配置`test_json`
    * 它使用一个简单的webapi服务演示了自动服务心跳和配置监听功能
    * 执行该示例后，在[http://127.0.0.1:7333/docs]()页面可以测试相关的功能:

