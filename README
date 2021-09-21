# Nacos客户端

### NacosConfig提供两个装饰器
* value:作为属性Get方法的装饰器使用
    * 相应的属性总是返回配置项的值
* values:作为类装饰器使用
    * 相应的类如果有与配置项的子项同名的属性,则它们被赋值
    * 包括类属性与实例属性

例子:
配置`test_json`:
```
{
  "group": "02",
  "keys": {
    "accessKey": "aaa",
    "secretKey": "bbb"
  }
}
```

以下代码:

```
ncs = NacosConfig('localhost', 'nacos', 'nacos')
@ncs.values('test_json', 'keys')
class Test(object):
    secretKey = None
    def __init__(self):
        self.accessKey = None

    @property
    @ncs.value('test_json','group')
    def group(self):
        pass


e = Test()
print(e.accessKey)  # 'aaa'
print(e.secretKey)  # 'bbb'
print(e.group)  # '02'
```

其它`NacosConfig`、`NacosService`、`NacosInstance`、`NacosNameSpace`的使用方法可参考相应类中的测试脚本