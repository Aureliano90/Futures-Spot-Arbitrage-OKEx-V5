import inspect
from datetime import datetime, timedelta, timezone
import time
import asyncio

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
    if isinstance(cls, type):
        # print(f'{cls.__name__} is class')
        old_init = getattr(cls, '__init__')

        def __init__(self, **kwargs):
            print(f'{self.__name__} init started')
            begin = time.monotonic()
            old_init(self, **kwargs)
            print(f'{self.__name__}({self.coin}) init finished')
            end = time.monotonic()
            print(f'{self.__name__} init takes {end - begin} s')

        cls.__init__ = __init__

        if old_await := getattr(cls, '__await__', False):
            def __await__(self):
                print(f'{self.__name__}__await__ started')
                begin = time.monotonic()
                result = yield from old_await(self)
                print(f'{self.__name__}__await__ finished')
                end = time.monotonic()
                print(f'{self.__name__}__await__ takes {end - begin} s')
                return result

            cls.__await__ = __await__

        if old_del := getattr(cls, '__del__', False):
            def __del__(self):
                print(f'{self.__name__} del started')
                old_del(self)
                print(f'{self.__name__} del finished')

            cls.__del__ = __del__
        return cls
    elif asyncio.iscoroutinefunction(cls):
        # print(f'{cls.__name__} is coroutine')

        async def wrapper(*args, **kwargs):
            begin = time.monotonic()
            res = await cls(*args, **kwargs)
            end = time.monotonic()
            print(f"{cls.__name__} takes {end - begin} s")
            return res

        return wrapper
    elif inspect.isroutine(cls):
        # print(f'{cls.__name__} is function')

        def wrapper(*args, **kwargs):
            begin = time.monotonic()
            res = cls(*args, **kwargs)
            end = time.monotonic()
            print(f"{cls.__name__} takes {end - begin} s")
            return res

        return wrapper
    else:
        # print(f'{cls.__name__} is nothing')
        return cls
