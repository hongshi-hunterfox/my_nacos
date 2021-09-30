# Nacos客户端

### 支持启用/未启用 auth 的 Nacos

```buildoutcfg
# 启用 auth 的 Nacos
ncs = NacosConfig('localhost', 'nacos', 'nacos')
# 未启用 auth 的 Nacos
ncs = NacosConfig('localhost')
```


### NacosConfig
* NacosConfig 提供两个装饰器
   * value:作为属性Get方法的装饰器使用
      * 相应的属性总是返回配置项的值
   * values:作为类装饰器使用
      * 相应的类如果有与配置项的子项同名的属性,则它们被赋值
      * 包括类属性与实例属性

> 示例代码 `test/test.py`


### NacosInstance
* NacosInstance提供服务实例注册功能，同时，简化服务心跳处理，提供了`beating_start`和`beating_stop`
* `beating_start`将开始服务心跳循环，在NacosInstance实例未销毁期间，它将维持`beating`,直到以合适的参数调用了`beating_stop`或该NacosInstance实例销毁

> 示例代码 `test/test_beating.py`


### 其它类的使用示例
* `test/test_nacos.py`
   * 演示了`NacosService`,`NacosInstance`,`NacosConfig`中的一些功能的使用

