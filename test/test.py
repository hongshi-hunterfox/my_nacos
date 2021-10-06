# coding=utf-8

from py_nacos import NacosConfig, ConfigBufferMode

# 这个 Nacos 服务启用了 auth
ncs = NacosConfig('localhost', 'nacos', 'nacos',
                  buffer_mode=ConfigBufferMode.memory)
def_config_data = [
    {'data_id': 'test_json', 'type': 'yaml', 'data': '''# 测试数据
keys:
    accessKey: <<accessKey>>
    secretKey: <<secretKey>>
group: <<group>>'''},
    {'data_id': 'xml_data', 'type': 'xml', 'data': '''<collection shelf="New Arrivals">
<movie title="Enemy Behind">
   <type>War, Thriller</type>
   <format>DVD</format>
   <year>2003</year>
   <rating>PG</rating>
   <stars>10</stars>
   <description>Talk about a US-Japan war</description>
</movie>
<movie title="Transformers">
   <type>Anime, Science Fiction</type>
   <format>DVD</format>
   <year>1989</year>
   <rating>R</rating>
   <stars>8</stars>
   <description>A schientific fiction</description>
</movie>
   <movie title="Trigun">
   <type>Anime, Action</type>
   <format>DVD</format>
   <episodes>4</episodes>
   <rating>PG</rating>
   <stars>10</stars>
   <description>Vash the Stampede!</description>
</movie>
<movie title="Ishtar">
   <type>Comedy</type>
   <format>VHS</format>
   <rating>PG</rating>
   <stars>2</stars>
   <description>Viewable boredom</description>
</movie>
</collection>'''},
    {'data_id': 'Properties-config', 'type': 'properties', 'data': '''a.b.d=v1
a.c=v2
d.e=v3
f=v4'''}]
for item in def_config_data:
    ncs.post(item['data_id'], item['data'], data_type=item['type'])


# 类装饰器 values
#   类被访问时类属性被赋值
#   实例化时类属性与实例属性被赋值
#   实例call时类属性与实例属性被赋值
@ncs.values('test_json', 'keys')
class Test(object):
    OtherField = ['--OtherField--']
    secretKey = '--secretKey--'

    def __init__(self, other_field=None):
        self.accessKey = None
        if other_field:
            self.OtherField = other_field

    def __call__(self, *args, **kwargs):
        return f'{self.accessKey},{self.secretKey}'

    @property
    @ncs.value('test_json', 'group')  # value装饰器只能在@property装饰器之后
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
b = Test('new instance')
print(f'b.OtherField:{b.OtherField}')
config_value = ncs.get('Properties-config').value('a.b.d')
print(f'Properties-config.a.b.d:{config_value}')
