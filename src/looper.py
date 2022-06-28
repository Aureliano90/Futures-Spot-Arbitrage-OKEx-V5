import asyncio
from datetime import datetime, timedelta
from typing import AsyncIterable
from aiostream import stream


class Looper:
    def __init__(self, when: float = 0., interval: float = 0., *, loop=None):
        """Event emitter that yields at `when` and every `interval` thereafter

        :param when: Time as in the event loop’s internal monotonic clock
        :param interval: Yields every `interval` seconds unless 0
        :param loop: The event loop
        """
        self.loop = loop or asyncio.get_event_loop()
        self.when = when or self.loop.time()
        self.interval = interval
        self.waiter = self.loop.create_future()

    def awake(self):
        self.waiter.set_result(None)

    async def __aiter__(self):
        self.loop.call_at(self.when, self.awake)
        while self.interval:
            await self.waiter
            if self.when - self.loop.time() >= 0 or self.loop.time() - self.when < self.interval:
                yield self
            self.waiter = self.loop.create_future()
            self.when = self.when + self.interval
            self.loop.call_at(self.when, self.awake)
        else:
            await self.waiter
            yield self


class UTCLooper(Looper):
    def __init__(self, when: datetime, interval: timedelta = timedelta(), *, loop=None):
        """Event emitter that yields at `when` and every `interval` thereafter

        :param when: UTC `datetime`
        :param interval: Yields every `timedelta` unless None
        :param loop: The event loop
        """
        loop = loop or asyncio.get_event_loop()
        now = datetime.utcnow()
        super().__init__(loop.time() + (when - now).total_seconds(), interval.total_seconds(), loop=loop)


class FundingTime(UTCLooper):
    """Yields when funding rates update
    """

    def __init__(self, *, offset: timedelta = timedelta(minutes=1), loop=None):
        loop = loop or asyncio.get_event_loop()
        now = datetime.utcnow()
        when = now + timedelta(hours=8 - now.hour % 8)
        super().__init__(when + offset, timedelta(hours=8), loop=loop)


class EventChain:
    def __init__(self, *async_generators: AsyncIterable):
        """Chaining AsyncGenerators"""
        self.async_generators = async_generators

    async def __aiter__(self):
        xs = stream.merge(*self.async_generators)
        async with xs.stream() as streamer:
            async for x in streamer:
                yield x


async def test():
    loop = asyncio.get_event_loop()
    async for _ in EventChain(Looper(interval=1), Looper(interval=2), Looper(interval=3), ):
        print(loop.time(), _)


if __name__ == '__main__':
    asyncio.run(test())
