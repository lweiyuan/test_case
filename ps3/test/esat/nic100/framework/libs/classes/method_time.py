# -*- encoding=utf8 -*-
from libs import constants


class MethodTime(object):
    """
    author: luyafei
    date  : 2020.04.24
    descriptor: 记录脚本中主方法执行时长的字段信息
    """

    def __init__(self):
        """测试准备执行时长"""
        self.pre_duration = 0
        """测试执行时长"""
        self.do_duration = 0
        """测试执行后处理时长"""
        self.post_duration = 0

    """
    MethodTime类中记录脚本主方法执行时长的各变量的set方法
    """
    def set_pre_duration(self, pre_duration: int) -> None:
        """
        author: luyafei
        date  : 2020.04.24
        description: 设置测试环境准备时间
        :param pre_duration: 测试环境准备时间
        """
        self.pre_duration = pre_duration

    def set_do_duration(self, do_duration: int) -> None:
        """
        author: luyafei
        date  : 2020.04.24
        description: 设置测试执行时间
        :param do_duration: 测试执行时间
        """
        self.do_duration = do_duration

    def set_post_duration(self, post_duration: int) -> None:
        self.post_duration = post_duration

    def keys(self) -> tuple:
        """
        author: luyafei
        date  : 2020.04.24
        description: 当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了字典
                     的键,其对应的值将以obj['name']的形式取, 但是对象是不可以以这种方
                     式取值的, 为了支持这种取值, 可以为类增加一个方法
        :return: 该环境字段信息类的类变量
        """
        return constants.PRE_DURATION, constants.DO_DURATION, \
            constants.POST_DURATION

    def __getitem__(self, item: str) -> int:
        """
        author: luyafei
        date  : 2020.04.24
        description: 内置方法, 当使用obj['name']的形式的时候, 将调用这个方法,
                     这里返回的结果就是属性对应的值
        :param item: 属性名称
        :return: 属性对应的值
        """
        return getattr(self, item)
