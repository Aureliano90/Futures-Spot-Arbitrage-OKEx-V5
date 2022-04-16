from typing import List
import collections
import functools
import inspect
import multiprocessing
from datetime import datetime, timedelta, timezone
import math
import time
import asyncio
import httpx
import src.lang as lang

logfile = open("./log.txt", "a", encoding="utf-8")


def rtruncate(string, n):
    """Truncate `n` chars in the `string` from the right

    :param string: string
    :param n: number of chars to be truncated
    """
    return string[:-n]


def datetime_str(d: datetime) -> str:
    """Format datetime
    """
    return rtruncate(d.strftime("%Y-%m-%d, %H:%M:%S.%f"), 4)


def utc_to_local(d: datetime) -> datetime:
    """Convert utc datetime to local
    """
    return d.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def fprint(*args, **kwargs):
    print(*args, **kwargs)
    kwargs['file'], kwargs['flush'] = logfile, True
    print(datetime_str(datetime.now()), *args, **kwargs)


def apy(apr: float):
    return math.exp(apr) - 1


def utcfrommillisecs(millisecs: str):
    return datetime.utcfromtimestamp(int(millisecs) / 1000)


def num_decimals(f: str):
    """Number of decimals
    """
    return len(f[f.find('.'):]) - 1


def float_str(f: float, decimals: int):
    """String of float up to certain decimals
    """
    return f'{f:.{decimals}f}'


def round_to(number, fraction) -> float:
    """Return the quotient of `number` and `fraction`
    """
    fs = f'{fraction:.18f}'.rstrip('0')
    decimals = num_decimals(fs)
    if decimals > 0:
        return round(number / fraction // 1 * fraction, decimals)
    else:
        return round(number / fraction // 1 * fraction)


class REST_Semaphore:
    """A custom semaphore to be used with REST API with velocity limit in asyncio
    """

    def __init__(self, value: int, interval: int):
        """控制REST API并发连接

        :param value: API limit
        :param interval: Reset interval
        """
        if value <= 0:
            raise ValueError("Semaphore initial value must be > 0")
        # Queue of inquiry timestamps
        self._inquiries = collections.deque(maxlen=value)
        self._value = value
        self._waiters = collections.deque()
        self._loop = asyncio.get_event_loop()
        self._count = 0
        self._interval = interval

    def __repr__(self):
        return f'API velocity: {self._value} inquiries/{self._interval}s'

    def _wake_up_next(self):
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                return

    async def acquire(self):
        if self._count < self._value:
            self._count += 1
        else:
            # Reached max inquiries during interval. But none of them have returned.
            # See the similar code in asyncio.Semaphore.
            while not self._inquiries:
                fut = self._loop.create_future()
                self._waiters.append(fut)
                try:
                    await fut
                except:
                    fut.cancel()
                    if self._inquiries and not fut.cancelled():
                        self._wake_up_next()
                    raise
            timelapse = time.monotonic() - self._inquiries.popleft()
            # Wait until interval has passed since the first inquiry in queue returned.
            if timelapse < self._interval:
                await asyncio.sleep(self._interval - timelapse)
        return True

    def release(self):
        self._inquiries.append(time.monotonic())
        if self._waiters:
            self._wake_up_next()

    async def __aenter__(self):
        await self.acquire()
        return None

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


class p_Semaphore:
    """A custom semaphore to be used with REST API with velocity limit by processes
    """

    def __init__(self, value: int, interval: int):
        """控制REST API并发连接

        :param value: API limit
        :param interval: Reset interval
        """
        if value <= 0:
            raise ValueError("Semaphore initial value must be > 0")
        # Queue of inquiry timestamps
        self._inquiries = multiprocessing.Queue()
        self._value = value
        self._count = multiprocessing.Value('I', lock=True)
        self._count.value = 0
        self._interval = interval

    def __repr__(self):
        return f'API velocity: {self._value} inquiries/{self._interval}s'

    def acquire(self):
        with self._count.get_lock():
            if self._count.value < self._value:
                self._count.value += 1
                return True
        timelapse = time.monotonic() - self._inquiries.get()
        # Wait until interval has passed since the first inquiry in queue returned.
        if timelapse < self._interval:
            time.sleep(self._interval - timelapse)
        return True

    def release(self):
        self._inquiries.put(time.monotonic())

    def __enter__(self):
        self.acquire()
        return None

    def __exit__(self, *args):
        self.release()


def columned_output(res: List, header: str, ncols: int, form):
    len1 = len(res)
    nrows = len1 // ncols + 1
    headers = ''
    for j in range(ncols):
        headers += header
        if j < ncols - 1:
            headers += '\t'
    fprint(headers)
    for i in range(nrows):
        line = ''
        for j in range(ncols):
            if i + j * nrows < len1:
                n = res[i + j * nrows]
                line += form(n)
                if j < ncols - 1:
                    line += '\t'
        fprint(line)


async def get_with_limit(api, tag, max, limit=0, **kwargs):
    """Loop `api` until `limit` is reached

    :param api: api coroutine
    :param tag: tag used by after argument
    :param max: max number of results in a single request
    :param limit: number of entries
    :param kwargs: other arguments
    :return: List
    """
    # Number of entries is known.
    if limit > 0:
        res = temp = []
        while limit > 0:
            if limit <= max:
                if len(temp) == max:
                    # Last time
                    temp = await api(**kwargs, after=temp[max - 1][tag], limit=limit)
                else:
                    # First time
                    temp = await api(**kwargs, limit=limit)
            else:
                if len(temp) == max:
                    # Last time
                    temp = await api(**kwargs, after=temp[max - 1][tag], limit=max)
                else:
                    # First time
                    temp = await api(**kwargs, limit=max)
            res.extend(temp)
            limit -= max
    else:
        # First time
        res = temp = await api(**kwargs)
        # print(datetime_str(datetime.now()))
        # Results not exhausted
        while len(temp) == max:
            temp = await api(**kwargs, after=temp[max - 1][tag])
            # print(datetime_str(datetime.now()))
            res.extend(temp)
    return res


def debug_timer(cls):
    """Decorator for debug and timing
    """
    if isinstance(cls, type):
        # print(f'{cls.__name__} is class')
        old_init = getattr(cls, '__init__')

        @functools.wraps(old_init)
        def __init__(self, *args, **kwargs):
            print(f"{self.__name__} init started")
            begin = time.monotonic()
            old_init(self, *args, **kwargs)
            print(f"{self.__name__}({self.coin}) init finished")
            end = time.monotonic()
            print(f"{self.__name__} init takes {end - begin} s")

        cls.__init__ = __init__

        if old_await := getattr(cls, '__await__', False):
            @functools.wraps(old_await)
            def __await__(self):
                print(f"{self.__name__}__await__ started")
                begin = time.monotonic()
                result = yield from old_await(self)
                print(f"{self.__name__}__await__ finished")
                end = time.monotonic()
                print(f"{self.__name__}__await__ takes {end - begin} s")
                return result

            cls.__await__ = __await__

        if old_del := getattr(cls, '__del__', False):
            @functools.wraps(old_del)
            def __del__(self):
                print(f"{self.__name__} del started")
                old_del(self)
                print(f"{self.__name__} del finished")

            cls.__del__ = __del__
        return cls
    elif asyncio.iscoroutinefunction(cls):
        # print(f"{cls.__name__} is coroutine function")

        @functools.wraps(cls)
        async def wrapper(*args, **kwargs):
            begin = time.monotonic()
            res = await cls(*args, **kwargs)
            end = time.monotonic()
            print(f"{cls.__name__} takes {end - begin} s")
            return res

        return wrapper
    elif inspect.isroutine(cls):
        # print(f"{cls.__name__} is function")

        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            begin = time.monotonic()
            res = cls(*args, **kwargs)
            end = time.monotonic()
            print(f"{cls.__name__} takes {end - begin} s")
            return res

        return wrapper
    else:
        # print(f"{cls.__name__} is nothing")
        return cls


def call_coroutine(cls):
    """Decorator to call `coro(*args, **kwargs)` in normal context
    and `await coro(*args, **kwargs)` in async context.
    """
    if asyncio.iscoroutinefunction(cls):
        # cls is a coroutine function.
        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            # coro is a coroutine object.
            coro = cls(*args, **kwargs)
            # print(f"{cls.__name__} {asyncio.iscoroutine(coro)=}")
            if loop.is_running():
                # print("loop is running")
                # Return the coroutine object to be awaited.
                return coro
            else:
                # print("loop is not running")
                # Execute the coroutine object and return its result.
                return loop.run_until_complete(coro)

        return wrapper
    elif isinstance(cls, type):
        # cls is a class.
        if hasattr(cls, '__await__'):
            # Decorate the class into a construction function which cannot be inherited.
            # @functools.wraps(cls)
            # def wrapper(*args, **kwargs):
            #     # class instance
            #     ins = cls(*args, **kwargs)
            #
            #     loop = asyncio.get_event_loop()
            #     if loop.is_running():
            #         # Return the class instance to be awaited.
            #         pass
            #     else:
            #         # Initiate the class instance asynchronously.
            #         loop.run_until_complete(ins.__await__())
            #     return ins
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
        # Do not iterate stdin while it is still waiting.
        while not written:
            # print('sinput waiting_input')
            time.sleep(1)
        # print('leaving sinput', input_buffer, 'received')
        return input_buffer
    else:
        waiting_input = True
        try:
            # Read from stdin
            input_buffer = input(*args)
        except EOFError:
            # Handle exception in child processes
            input_buffer = ''
    # Received stdin
    waiting_input = False
    written = True
    # print('leaving sinput', input_buffer, 'written')
    return input_buffer


def ainput(*args):
    """Return a future to wait for stdin asynchronously.
    """
    global input_future, future_cancelled
    if waiting_input:
        # Previous input future was cancelled by a completed task but stdin is still waiting.
        # Schedule a new future for a new task to capture the last stdin.
        if future_cancelled:
            loop = asyncio.get_event_loop()
            input_future = asyncio.ensure_future(loop.run_in_executor(None, functools.partial(sinput, *args)))
            future_cancelled = False
    else:
        # Schedule a future to wait for stdin asynchronously.
        loop = asyncio.get_event_loop()
        input_future = asyncio.ensure_future(loop.run_in_executor(None, functools.partial(sinput, *args)))
        future_cancelled = False
    return input_future


def input_cancel(t: asyncio.Task, r, c: asyncio.Task):
    """Cancel task `t` if the result of `c` is `r`
    """
    try:
        if not t.done():
            if r:
                # Input future cancels the running task.
                if not c.cancelled():
                    if c.result() == r:
                        t.cancel()
                        # print(f'{r=}', c)
            else:
                # Completed task cancels the input future.
                t.cancel()
                global future_cancelled
                future_cancelled = True
                # print(f'{r=}', c)
    except asyncio.exceptions.CancelledError:
        pass


def run_with_cancel(cls):
    """Decorator to run a function and schedule a future to interrupt it
    by waiting for stdin signal asynchronously.
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
                # print("loop is running")
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
                # print("loop is not running")
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
