# -*- coding: utf-8 -*-
from xml.dom import minidom


class Xml2Dict(object):
    """XML数据转为字典
    >>> s = '''
    ... <a title="aaa">
    ...   <b title="Enemy"><type>Thriller</type></b>
    ...   <b title="Trans"><type>Action</type></b>
    ... </a>'''
    >>> x=Xml2Dict.loads(s)
    >>> x['b'][1]['type']=='Action'
    True
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
    def value2list(_dict, name):
        if not isinstance(_dict[name], list):
            _dict[name] = [_dict[name]]
    @staticmethod
    def get_dict(node)->dict:
        if node.nodeType == 1 and \
                node.firstChild == node.lastChild and \
                isinstance(node.firstChild, minidom.Text):
            return node.firstChild.data
        else:
            obj = dict(node.attributes.items())
            for child in node.childNodes:
                if child.localName:
                    name, value = child.nodeName, Xml2Dict.get_dict(child)
                    if name in obj.keys():
                        if not isinstance(obj[name], list):
                            obj[name] = [obj[name]]
                            obj[name].append(value)
                    else:
                        obj[name] = value
            return obj


class Properties(object):
    @staticmethod
    def load(file):
        with open(file, 'r') as f:
            Properties.loads(f.read())

    @staticmethod
    def loads(data):
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