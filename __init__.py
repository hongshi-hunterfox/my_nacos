# coding=utf-8
"""
for example:
    from typing import Optional

    nacos = NacosProperty(server_addr = "127.0.0.1:8848",
                          data_id = "example",
                          auto_refreshed = True)


    @nacos.values('ocr')
    class Config(object):
        url: Optional[str]
        ak: Optional[str]
        sk: Optional[str]


    class Auth(object):
        @property
        def api_path(self) -> str:
            pass

        def __call__(self, *args, **kwargs):
            config = Config()
            uri = '/'.join(config.url.split('/') + self.api_path.split('/'))
            return f'{uri}?ak={config.ak}&sk={config.sk}'
"""
