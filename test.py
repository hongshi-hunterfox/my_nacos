from dispatcher import  NacosConfig

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
print(e.accessKey)
print(e.secretKey)
print(e.group)

