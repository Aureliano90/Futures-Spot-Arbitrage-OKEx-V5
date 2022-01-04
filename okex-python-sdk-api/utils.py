from datetime import datetime, timedelta, timezone
import time

logfile = open("log.txt", "a", encoding="utf-8")


def fprint(*args):
    print(*args)
    print(datetime.now(), end='    ', file=logfile)
    print(*args, file=logfile, flush=True)


def utcfrommillisecs(millisecs: str):
    return datetime.utcfromtimestamp(int(millisecs) / 1000)


def round_to(number, fraction):
    """返回fraction的倍数
    """
    # 小数点后位数
    ndigits = len('{:f}'.format(fraction - int(fraction))) - 2
    if ndigits > 0:
        return round(int(number / fraction) * fraction, ndigits)
    else:
        return round(int(number / fraction) * fraction)


def init_debug(cls):
    old_init = cls.__init__
    old_await = cls.__await__

    def __init__(self, **kwargs):
        print(f'{self.__str__()} init started')
        begin = time.monotonic()
        old_init(self, **kwargs)
        print(f'{self.__str__()}({self.coin}) init finished')
        end = time.monotonic()
        print(f'{self.__str__()} init takes {end - begin} s')
    cls.__init__ = __init__

    def __await__(self):
        print(f'{self.__str__()}__await__ started')
        begin = time.monotonic()
        result = yield from old_await(self)
        print(f'{self.__str__()}__await__ finished')
        end = time.monotonic()
        print(f'{self.__str__()}__await__ takes {end - begin} s')
        return result
    cls.__await__ = __await__
    return cls

