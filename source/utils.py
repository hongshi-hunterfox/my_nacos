# -*- coding: utf-8 -*-
from xml.dom import minidom,Node


class Xml2Dict(object):
    """XML数据转为字典
        节点属性不处理,不输出
    >>> s = '''
    ... <a title="aaa">
    ...   <b title="Enemy"><type>Thriller
    ...             4444</type></b>
    ...   <b title="Trans"><type>Action</type></b>
    ...   <int_value type="integer">123</int_value>
    ...   <date_value type="datetime">2021-03-18</date_value>
    ... </a>'''
    >>> Xml2Dict.loads(s)
    {'b': [{'type': 'Thriller...'2021-03-18'}
    """
    @staticmethod
    def load(file)->dict:
        """从文件载入xml对象"""
        dom = minidom.parse(file)
        return Xml2Dict.get_dict(dom.documentElement)

    @staticmethod
    def loads(data:str) -> dict:
        """从文本载入xml对象"""
        dom = minidom.parseString(data)
        return Xml2Dict.get_dict(dom.documentElement)

    @staticmethod
    def get_dict(node: minidom.Node)->dict:
        """返回dom 节点对应的值"""
        if isinstance(node, minidom.Childless):
            return node.nodeValue
        obj = {}
        for child in node.childNodes:
            if child.nodeType in (Node.COMMENT_NODE,):
                continue
            name, value = child.nodeName, Xml2Dict.get_dict(child)
            if name not in obj.keys():
                obj[name] = value
            elif not isinstance(obj[name], list):
                obj[name] = [obj[name]]
                obj[name].append(value)
        if '#text' in obj.keys():
            if len(obj.keys())>1:
                obj.pop('#text')
            else:
                obj = obj['#text']
        return obj


class Properties2Dict(object):
    """properties格式配置数据转字典"""
    @staticmethod
    def load(file)->dict:
        """从文档载入"""
        with open(file, 'r') as f:
            return Properties2Dict.loads(f.read())

    @staticmethod
    def loads(data)->dict:
        """从文本载入"""
        def split_point(s):
            if ':' not in s:
                return s.index('=') if '=' in s else 0
            elif '=' not in s:
                return s.index(':')
            else:
                return min(s.index(':'), s.index('='))

        def set_key(_obj, _key: list, _data):
            if len(_key)==1:
                if _key[0] not in _obj.keys():
                    _obj[_key[0]] = _data
                elif isinstance(_obj[_key[0]], list):
                    _obj[_key[0]].append(_data)
                else:
                    _obj[_key[0]] = [_obj[_key[0]],_data]
            else:
                if _key[0] not in _obj.keys():
                    _obj[_key[0]] = {}
                set_key(_obj[_key[0]], _key[1:], _data)

        obj, buf={}, None
        for line in data.split('\n'):
            if line.startswith(('#','!')):
                continue  # discard comments
            if buf:
                buf = buf[:-1] + line.lstrip()
            elif not split_point(line):
                continue  # Error: missing delimiter
            else:
                buf = line
            if buf.endswith('\\'):
                continue  # multiline is not ended
            point = split_point(buf)
            attr, value = buf[:point],buf[point + 1:]
            print(f'{attr}:{value}')
            set_key(obj, attr.split('.'), value)
            buf=None
        return obj



if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)