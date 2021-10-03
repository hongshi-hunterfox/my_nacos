# coding=utf-8
from datetime import datetime
from source import  NacosConfig, ConfigBufferMode


# 这个 Nacos 服务启用了 auth
ncs = NacosConfig('localhost', 'nacos', 'nacos',
                  buffer_mode=ConfigBufferMode.memory)
_data ="""# 测试数据
keys:
    accessKey: <<accessKey>>
    secretKey: <<secretKey>>
group: <<group>>"""
ncs.post('test_json',_data, data_type='yaml')


# 类装饰器 values
#   类被访问时类属性被赋值
#   实例化时类属性与实例属性被赋值
#   实例call时类属性与实例属性被赋值
@ncs.values('test_json', 'keys')
class Test(object):
    OtherField = ['--OtherField--']
    secretKey = '--secretKey--'
    def __init__(self,other_field=None):
        self.accessKey = None
        if other_field:
            self.OtherField = other_field

    def __call__(self, *args, **kwargs):
        return f'{self.accessKey},{self.secretKey}'

    @property
    @ncs.value('test_json','group') # value装饰器只能在@property装饰器之后
    def group_value(self):
        raise BaseException('不能读取配置信息')

    def keys(self):
        return f'{self.secretKey},{self.accessKey}'

    @classmethod
    def add_field(cls, field):
        cls.OtherField.append(field)


# 直接访问类属性,它已被赋值
print(f'Test.secretKey:{Test.secretKey}')
a = Test()
print('-----')
# 配置中没有的属性不被改变
print(f'a.OtherField:{a.OtherField}')
# 类属性被赋值
print(f'a.secretKey:{a.secretKey}')
# 实例属性被赋值
print(f'a.accessKey:{a.accessKey}')
# 属性方法装饰效果
print(f'a.group:{a.group_value}')
# 方法有效
print(f'a.keys():{a.keys()}')
# __call__ 装饰效果
print(f'a():{a()}')
print('-----------------------')
b=Test('new instance')
print(f'b.OtherField:{b.OtherField}')
print('-----------------------')
now = lambda : datetime.now().timestamp()
t = now()
print(f'-0--{now() - t}-')
ncs.listening('test_json')
print(f'-1--{now() - t}-')
