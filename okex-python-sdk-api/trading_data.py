from math import sqrt
from typing import List
import okex.asset as asset
import okex.public as public
from datetime import datetime, timedelta, timezone
import statistics
import record
import matplotlib.pyplot as plt
from log import fprint
from lang import *
import asyncio
from asyncio import create_task, gather


def high(candle: list):
    """最高价

    :param candle: K线
    """
    return float(candle[2])


def low(candle: list):
    """最低价

    :param candle: K线
    """
    return float(candle[3])


def close(candle: list):
    """收盘价

    :param candle: K线
    """
    return float(candle[4])


def true_range(candle: list, previous: list):
    """相对振幅

    :param candle: 当前K线
    :param previous: 上一K线
    """
    return max(high(candle) - low(candle), abs(high(candle) - close(previous)),
               abs(low(candle) - close(previous))) / close(previous)


def average_true_range(candles: list, days=7):
    """平均相对振幅

    :param candles: K线列表
    :param days:最近几天
    """
    tr = []
    # Use 4h candles
    if days * 6 > 1440:
        days = 240
    if days * 6 <= len(candles) + 1:
        num_candles = days * 6
    else:
        num_candles = len(candles) - 1
    for n in range(num_candles):
        tr.append(true_range(candles[n], candles[n + 1]))
    return statistics.mean(tr)


class Stat:
    """交易数据统计功能类
    """

    def __init__(self, coin: str = None):
        # print('Stat init started')
        self.assetAPI = asset.AssetAPI(api_key='', api_secret_key='', passphrase='')
        self.publicAPI = public.PublicAPI()

        self.coin = coin
        if coin:
            self.coin = coin
            self.spot_ID = coin + '-USDT'
            self.swap_ID = coin + '-USDT-SWAP'
            self.exist = True

            try:
                # begin = time.monotonic()
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在async上下文内呼叫构造函数，不能再run
                    # print('Event loop is running. Call with await.')
                    pass
                else:
                    # 在async上下文外呼叫构造函数
                    self.spot_info = loop.create_task(
                        self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                    self.swap_info = loop.create_task(
                        self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                    loop.run_until_complete(gather(self.spot_info, self.swap_info))
                    self.spot_info = self.spot_info.result()
                    self.swap_info = self.swap_info.result()
                # print(f'Stat({self.coin}) init finished')
                # end = time.monotonic()
                # print(f'Stat init takes {end-begin} s')
            except Exception as e:
                fprint(f'Stat({self.coin}) init error')
                fprint(e)
                self.exist = False
                fprint(nonexistent_crypto.format(self.coin))
        else:
            self.exist = False

    def __await__(self):
        """异步构造函数\n
        await Stat()先召唤__init__()，然后是awaitable __await__()。

        :return:Stat
        """
        if self.coin:
            try:
                # print('Stat__await__ started')
                # begin = time.monotonic()
                self.spot_info = create_task(self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                self.swap_info = create_task(self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                yield from gather(self.spot_info, self.swap_info)
                self.spot_info = self.spot_info.result()
                self.swap_info = self.swap_info.result()
                # print('Stat__await__ finished')
                # end = time.monotonic()
                # print('Stat__await__ takes {:f} s'.format(end-begin))
            except Exception as e:
                fprint(f'Stat__async__init__({self.coin}) error')
                fprint(e)
                self.exist = False
                fprint(nonexistent_crypto.format(self.coin))
        else:
            self.exist = False
        return self
        # return self.__async__init__().__await__()

    async def __async__init__(self):
        if self.coin:
            try:
                # print('Stat__async__init__ started')
                # begin = time.monotonic()
                self.spot_info = create_task(self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                self.swap_info = create_task(self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                await self.spot_info
                await self.swap_info
                self.spot_info = self.spot_info.result()
                self.swap_info = self.swap_info.result()
                # print(f'Stat__async__init__({self.coin}) finished')
                # end = time.monotonic()
                # print(f'Stat__async__init__ takes {end - begin} s')
            except Exception as e:
                fprint(f'Stat__async__init__({self.coin}) error')
                fprint(e)
                self.exist = False
                fprint(nonexistent_crypto.format(self.coin))
        else:
            self.exist = False
        return self

    def __del__(self):
        # print("Stat del started")
        self.assetAPI.__del__()
        self.publicAPI.__del__()
        # print("Stat del finished")

    async def get_candles(self, sem, instId, bar='4H') -> dict:
        """获取4小时K线

        :param sem: Semaphore
        :param instId: 产品ID
        :param bar: 时间粒度，默认值1m，如 [1m/3m/5m/15m/30m/1H/2H/4H]
        """
        async with sem:
            candles = await self.assetAPI.get_kline(instId=instId, bar=bar, limit='300')
            await asyncio.sleep(1)
            temp = candles
            while len(temp) == 300:
                temp = await self.assetAPI.get_kline(instId=instId, bar=bar, after=temp[299][0], limit='300')
                await asyncio.sleep(1)
                candles.extend(temp)
            return {'instId': instId, 'candles': candles}

    async def profitability(self, funding_rate_list, days=7) -> List[dict]:
        """显示各币种资金费率除以波动率
        """
        # begin = time.monotonic()
        task_list = []
        sem = asyncio.Semaphore(10)
        for n in funding_rate_list:
            task_list.append(self.get_candles(sem, n['instrument'] + '-USDT'))
        gather_result = await gather(*task_list)
        # end = time.monotonic()
        # print("get_candles takes %f s" % (end - begin))

        for n in range(len(funding_rate_list)):
            atr = average_true_range(gather_result[n]['candles'], days)
            funding_rate_list[n]['profitability'] = int(funding_rate_list[n]['funding_rate'] / sqrt(atr) * 10000)
        funding_rate_list.sort(key=lambda x: x['profitability'], reverse=True)
        funding_rate_list = funding_rate_list[:10]
        fprint(coin_funding_value)
        for n in funding_rate_list:
            fprint('{:9s}{:7.3%}{:6d}'.format(n['instrument'], n['funding_rate'], n['profitability']))
        return funding_rate_list

    def open_dist(self):
        """开仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')

        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=4))
        # print(timestamp)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$open_pd'}, 'std': {'$stdDevSamp': '$open_pd'},
                                'max': {'$max': '$open_pd'}, 'min': {'$min': '$open_pd'}, 'count': {'$sum': 1}}}]
        result = {}
        for x in Record.mycol.aggregate(pipeline):
            result = x
        # print(result)
        avg = result['avg']
        std = result['std']
        total = result['count']
        p1sigma = avg + std
        m1sigma = avg - std
        p15sigma = avg + 1.5 * std
        m15sigma = avg - 1.5 * std
        p2sigma = avg + 2 * std
        m2sigma = avg - 2 * std
        p3sigma = avg + 3 * std
        m3sigma = avg - 3 * std

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p1sigma, '$gt': m1sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p15sigma, '$gt': m15sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p2sigma, '$gt': m2sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p3sigma, '$gt': m3sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count3 = result['count']
        frequency3 = count3 / total
        print("开仓", self.coin, '{:.2%}'.format(p2sigma))
        print('{:.2%}'.format(frequency1), '{:.2%}'.format(frequency15), '{:.2%}'.format(frequency2),
              '{:.2%}'.format(frequency3))

    def close_dist(self):
        """平仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')

        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=4))
        # print(timestamp)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$close_pd'}, 'std': {'$stdDevSamp': '$close_pd'},
                                'max': {'$max': '$close_pd'}, 'min': {'$min': '$close_pd'}, 'count': {'$sum': 1}}}]
        result = {}
        for x in Record.mycol.aggregate(pipeline):
            result = x
        # print(result)
        avg = result['avg']
        std = result['std']
        total = result['count']
        p1sigma = avg + std
        m1sigma = avg - std
        p15sigma = avg + 1.5 * std
        m15sigma = avg - 1.5 * std
        p2sigma = avg + 2 * std
        m2sigma = avg - 2 * std
        p3sigma = avg + 3 * std
        m3sigma = avg - 3 * std

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p1sigma, '$gt': m1sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p15sigma, '$gt': m15sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p2sigma, '$gt': m2sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p3sigma, '$gt': m3sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count3 = result['count']
        frequency3 = count3 / total
        print("平仓", self.coin, '{:.2%}'.format(m2sigma))
        print('{:.2%}'.format(frequency1), '{:.2%}'.format(frequency15), '{:.2%}'.format(frequency2),
              '{:.2%}'.format(frequency3))

    def recent_ticker(self, hours=4):
        """返回近期期现差价列表

        :param hours: 最近几小时
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=hours))
        # print(timestamp)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}}]
        timelist: List[datetime] = []
        open_pd: List[float] = []
        close_pd: List[float] = []
        for x in Record.mycol.aggregate(pipeline):
            utctime: datetime = x['timestamp']
            localtime = utctime.replace(tzinfo=timezone.utc).astimezone(tz=None)
            timelist.append(localtime)
            open_pd.append(x['open_pd'])
            close_pd.append(x['close_pd'])
        return {'instrument': self.coin, 'timestamp': timelist, 'open_pd': open_pd, 'close_pd': close_pd}

    def recent_open_stat(self, hours=4):
        """返回近期开仓期现差价统计值

        :param hours: 最近几小时
        :rtype: dict
        """
        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=hours))
        # print(timestamp)

        Record = record.Record('Ticker')
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$open_pd'}, 'std': {'$stdDevSamp': '$open_pd'},
                                'max': {'$max': '$open_pd'}, 'min': {'$min': '$open_pd'}}}]
        for x in Record.mycol.aggregate(pipeline):
            return x

    def recent_close_stat(self, hours=4):
        """返回近期平仓期现差价统计值

        :param hours: 最近几小时
        :rtype: dict
        """
        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=hours))
        # print(timestamp)

        Record = record.Record('Ticker')
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$close_pd'}, 'std': {'$stdDevSamp': '$close_pd'},
                                'max': {'$max': '$close_pd'}, 'min': {'$min': '$close_pd'}}}]
        for x in Record.mycol.aggregate(pipeline):
            return x

    def open_time(self, account):
        """返回开仓时间

        :param account: 账号id
        :rtype: datetime
        """
        Record = record.Record('Ledger')
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'title': "开仓"}},
                    {'$sort': {'_id': -1}}, {'$limit': 1}]
        open_time = 0
        for x in Record.mycol.aggregate(pipeline):
            # 开仓时间
            open_time = x['timestamp']
        if open_time:
            return open_time
        else:
            return datetime(2021, 4, 1)

    def history_funding(self, account, days=0):
        """最近累计资金费

        :param account: 账号id
        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Record = record.Record('Ledger')
        if days == 0:
            open_time = self.open_time(account)
        else:
            open_time = datetime.utcnow().__sub__(timedelta(days=days))
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'timestamp': {'$gt': open_time}}},
                    {'$group': {'_id': '$instrument', 'sum': {'$sum': '$funding'}}}]
        for x in Record.mycol.aggregate(pipeline):
            # 累计资金费
            return x['sum']
        return 0.

    def history_cost(self, account, days=0):
        """最近累计成本

        :param account: 账号id
        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Record = record.Record('Ledger')
        if days == 0:
            open_time = self.open_time(account)
        else:
            open_time = datetime.utcnow().__sub__(timedelta(days=days))
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'timestamp': {'$gt': open_time}}},
                    {'$group': {'_id': '$instrument', 'spot_notional': {'$sum': '$spot_notional'},
                                'swap_notional': {'$sum': '$swap_notional'}, 'fee': {'$sum': '$fee'}}}]
        for x in Record.mycol.aggregate(pipeline):
            return x['spot_notional'] + x['swap_notional'] + x['fee']
        return 0.

    def plot(self, hours=4):
        """画出最近期现差价散点图

        :param hours: 最近几小时
        """
        recent = self.recent_open_stat(hours)
        open_pd = recent['avg'] + 2 * recent['std']
        recent = self.recent_close_stat(hours)
        close_pd = recent['avg'] - 2 * recent['std']
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        mylist = self.recent_ticker(hours)
        plt.figure(figsize=(16, 8))
        # plt.axhline(y=open_pd, color='g', linestyle='-')
        # plt.axhline(y=close_pd, color='r', linestyle='-')
        plt.plot(mylist['timestamp'], mylist['open_pd'], '.', color='g', label=pd_open)
        plt.plot(mylist['timestamp'], [open_pd] * len(mylist['timestamp']), '-', color='g', label=two_std)
        plt.plot(mylist['timestamp'], mylist['close_pd'], '.', color='r', label=pd_close)
        plt.plot(mylist['timestamp'], [close_pd] * len(mylist['timestamp']), '-', color='r', label=two_std)
        # plt.xticks(rotation=45)
        plt.xlabel(plot_time)
        plt.ylabel(plot_premium)
        plt.legend(loc="best")
        plt.title(plot_title.format(self.coin, hours))
        plt.show()
