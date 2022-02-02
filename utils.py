import functools
import inspect
from datetime import datetime, timedelta, timezone
import math
import time
import asyncio
import lang

logfile = open("log.txt", "a", encoding="utf-8")


def rtruncate(s, n):
    """Truncate n chars from string on the right

    :param s: string
    :param n: number of chars to be truncated
    """
    return s[:len(s) - n]


def datetime_str(d: datetime) -> str:
    """Format datetime
    """
    return rtruncate(d.strftime("%Y-%m-%d, %H:%M:%S.%f"), 4)


def utc_to_local(d: datetime) -> datetime:
    """Convert utc datetime to local
    """
    return d.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def fprint(*args):
    print(*args)
    print(datetime_str(datetime.now()), *args, file=logfile, flush=True)


def apy(apr: float):
    return math.exp(apr) - 1


def utcfrommillisecs(millisecs: str):
    return datetime.utcfromtimestamp(int(millisecs) / 1000)


def num_decimals(f: str):
    """Number of decimals
    """
    return len(f[f.find('.'):]) - 1


def float_str(f: float, decimals: int):
    """String of float with certain decimals
    """
    return f'{f:.{decimals}f}'


def round_to(number, fraction) -> float:
    """Return the quotient of number and fraction
    """
    fs = f'{fraction:.18f}'.rstrip('0')
    decimals = num_decimals(fs)
    if decimals > 0:
        return round(number / fraction // 1 * fraction, decimals)
    else:
        return round(number / fraction // 1 * fraction)


async def get_with_limit(api, tag, max, limit=0, sem=None, sleep=0., **kwargs):
    """Loop api until limit is reached

    :param api: api coroutine
    :param tag: tag used in after argument
    :param max: max number of results in a single call
    :param limit: number of entries
    :param sem: semaphore
    :param sleep: interval between calls
    :param kwargs: other arguments
    :return: List
    """
    if not sem: sem = asyncio.Semaphore(1)
    async with sem:
        if limit > 0:
            res = temp = []
            while limit > 0:
                if limit <= max:
                    if len(temp) == max:
                        # 最后一次
                        temp = await api(**kwargs, after=temp[max-1][tag], limit=limit)
                    else:
                        # 第一次
                        temp = await api(**kwargs, limit=limit)
                else:
                    if len(temp) == max:
                        temp = await api(**kwargs, after=temp[max-1][tag], limit=max)
                    else:
                        temp = await api(**kwargs, limit=max)
                await asyncio.sleep(sleep)
                res.extend(temp)
                limit -= max
        else:
            res = temp = await api(**kwargs)
            await asyncio.sleep(sleep)
            while len(temp) == max:
                temp = await api(**kwargs, after=temp[max-1][tag])
                await asyncio.sleep(sleep)
                res.extend(temp)
        return res


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
        # print(f'{cls.__name__} is coroutine function')

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
            # print(f'{cls.__name__} {asyncio.iscoroutine(coro)=}')
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


waiting_input = False
written = False
input_buffer = None
input_future = None
future_cancelled = False


def minput(*args):
    global waiting_input, written
    if waiting_input:
        print(*args, end='')
        while not written:
            time.sleep(1)
        return input_buffer
    else:
        return input(*args)


def sinput(*args):
    global written, waiting_input, input_buffer
    written = False
    if waiting_input:
        print(*args, end='')
        while not written:
            # print('sinput waiting_input')
            time.sleep(1)
        # print('leaving sinput', input_buffer, 'received')
        return input_buffer
    else:
        waiting_input = True
        try:
            input_buffer = input(*args)
        except EOFError:
            input_buffer = ''
    waiting_input = False
    written = True
    # print('leaving sinput', input_buffer, 'written')
    return input_buffer


def ainput(*args):
    global input_future, future_cancelled
    if waiting_input:
        if future_cancelled:
            loop = asyncio.get_event_loop()
            input_future = asyncio.ensure_future(loop.run_in_executor(None, functools.partial(sinput, *args)))
            future_cancelled = False
        return input_future
    else:
        loop = asyncio.get_event_loop()
        input_future = asyncio.ensure_future(loop.run_in_executor(None, functools.partial(sinput, *args)))
        future_cancelled = False
        return input_future


def input_cancel(t, r, c):
    """Cancel task t if the result of c is r
    """
    try:
        if not t.done():
            if r:
                if not c.cancelled():
                    if c.result() == r:
                        t.cancel()
                        # print(f'{r=}', c)
            else:
                t.cancel()
                global future_cancelled
                # sinput future cancelled
                future_cancelled = True
                # print(f'{r=}', c)
    except asyncio.exceptions.CancelledError:
        pass


def run_with_cancel(cls):
    if asyncio.iscoroutinefunction(cls):
        # cls is a coroutine function.
        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            # coro is a coroutine object.
            coro = cls(*args, **kwargs)
            # print(f'{cls.__name__} {asyncio.iscoroutine(coro)=}')
            if loop.is_running():
                # print('loop is running')
                # Return the coroutine object to be awaited.
                async def _coro():
                    _t = loop.create_task(coro)
                    _c = ainput(lang.input_q_abort)
                    _g = asyncio.gather(_t, _c, return_exceptions=True)
                    _t.add_done_callback(functools.partial(input_cancel, _c, ''))
                    _c.add_done_callback(functools.partial(input_cancel, _t, 'q'))
                    try:
                        await _g
                    except asyncio.exceptions.CancelledError:
                        pass
                    finally:
                        if not _t.cancelled():
                            return _t.result()

                return _coro()
            else:
                # print('loop is not running')
                # Execute the coroutine object and return its result.
                t = loop.create_task(coro)
                c = ainput(lang.input_q_abort)
                g = asyncio.gather(t, c, return_exceptions=True)
                t.add_done_callback(functools.partial(input_cancel, c, ''))
                c.add_done_callback(functools.partial(input_cancel, t, 'q'))
                try:
                    loop.run_until_complete(g)
                except asyncio.exceptions.CancelledError:
                    pass
                finally:
                    if not t.cancelled():
                        return t.result()

        return wrapper
    return cls
