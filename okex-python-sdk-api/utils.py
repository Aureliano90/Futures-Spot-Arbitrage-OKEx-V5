import functools
import inspect
from datetime import datetime, timedelta, timezone
import math
import time
import asyncio

logfile = open("log.txt", "a", encoding="utf-8")


def fprint(*args):
    print(*args)
    print(datetime.now(), end='    ', file=logfile)
    print(*args, file=logfile, flush=True)


def apy(apr: float):
    return math.exp(apr) - 1


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


def debug_timer(cls):
    if isinstance(cls, type):
        # print(f'{cls.__name__} is class')
        old_init = getattr(cls, '__init__')

        @functools.wraps(old_init)
        def __init__(self, *args, **kwargs):
            print(f'{self.__name__} init started')
            begin = time.monotonic()
            old_init(self, *args, **kwargs)
            print(f'{self.__name__}({self.coin}) init finished')
            end = time.monotonic()
            print(f'{self.__name__} init takes {end - begin} s')

        cls.__init__ = __init__

        if old_await := getattr(cls, '__await__', False):
            @functools.wraps(old_await)
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
            @functools.wraps(old_del)
            def __del__(self):
                print(f'{self.__name__} del started')
                old_del(self)
                print(f'{self.__name__} del finished')

            cls.__del__ = __del__
        return cls
    elif asyncio.iscoroutinefunction(cls):
        # print(f'{cls.__name__} is coroutine')

        @functools.wraps(cls)
        async def wrapper(*args, **kwargs):
            begin = time.monotonic()
            res = await cls(*args, **kwargs)
            end = time.monotonic()
            print(f"{cls.__name__} takes {end - begin} s")
            return res

        return wrapper
    elif inspect.isroutine(cls):
        # print(f'{cls.__name__} is function')

        @functools.wraps(cls)
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


def call_coroutine(cls):
    """Call coro(*args, **kwargs) in normal context and await coro(*args, **kwargs) in async context.
    """
    if asyncio.iscoroutinefunction(cls):
        # cls is a coroutine function.
        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            # coro is a coroutine object.
            coro = cls(*args, **kwargs)
            # print(f'{cls.__name__} {asyncio.iscoroutine(res)=}')
            if loop.is_running():
                # print('loop is running')
                # Return the coroutine object to be awaited.
                return coro
            else:
                # print('loop is not running')
                # Execute the coroutine object and return its result.
                return loop.run_until_complete(coro)

        return wrapper
    elif isinstance(cls, type):
        # cls is a class.
        if hasattr(cls, '__await__'):
            # Decorate the class into a construction function which cannot be inherited.
            # @functools.wraps(cls)
            # def wrapper(*args, **kwargs):
            #     obj = cls(*args, **kwargs)
            #
            #     loop = asyncio.get_event_loop()
            #     if loop.is_running():
            #         pass
            #     else:
            #         loop.run_until_complete(obj.__await__())
            #     # input class, output class object
            #     return obj
            # return wrapper

            # Decorate the class into a class.
            old_init = getattr(cls, '__init__')

            @functools.wraps(old_init)
            def __init__(self, *args, **kwargs):
                old_init(self, *args, **kwargs)
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    pass
                else:
                    loop.run_until_complete(self.__await__())

            cls.__init__ = __init__
    return cls
