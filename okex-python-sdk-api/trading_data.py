from math import sqrt
from typing import List
import okex.asset as asset
import okex.public as public
import statistics
import record
import matplotlib.pyplot as plt
from utils import *
from lang import *
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


@call_coroutine
# @debug_timer
class Stat:
    """交易数据统计功能类
    """

    @property
    def __name__(self):
        return 'Stat'

    def __init__(self, coin: str = None):
        self.assetAPI = asset.AssetAPI(api_key='', api_secret_key='', passphrase='')
        self.publicAPI = public.PublicAPI()

        self.coin = coin
        if coin:
            self.coin = coin
            self.spot_ID = coin + '-USDT'
            self.swap_ID = coin + '-USDT-SWAP'
            self.exist = True
        else:
            self.exist = False

    def __await__(self):
        """异步构造函数\n
        await Stat()先召唤__init__()，然后是awaitable __await__()。

        :return: Stat
        """
        if self.coin:
            try:
                self.spot_info = create_task(self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                self.swap_info = create_task(self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                yield from gather(self.spot_info, self.swap_info)
                self.spot_info = self.spot_info.result()
                self.swap_info = self.swap_info.result()
            except Exception as e:
                fprint(f'{self.__name__}__await__({self.coin}) error')
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
                self.spot_info = create_task(self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                self.swap_info = create_task(self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                await self.spot_info
                await self.swap_info
                self.spot_info = self.spot_info.result()
                self.swap_info = self.swap_info.result()
            except Exception as e:
                fprint(f'{self.__name__}__async__init__({self.coin}) error')
                fprint(e)
                self.exist = False
                fprint(nonexistent_crypto.format(self.coin))
        else:
            self.exist = False
        return self

    def __del__(self):
        self.assetAPI.__del__()
        self.publicAPI.__del__()

    async def get_candles(self, sem, instId, days, bar='4H') -> dict:
        """获取4小时K线

        :param sem: Semaphore
        :param instId: 产品ID
        :param bar: 时间粒度，默认值1m，如 [1m/3m/5m/15m/30m/1H/2H/4H]
        """
        async with sem:
            limit = days * 6 + 1
            candles = temp = []
            while limit > 0:
                if limit <= 300:
                    if len(temp) == 300:
                        # 最后一次
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, after=temp[299][0], limit=limit)
                    else:
                        # 第一次
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, limit=limit)
                else:
                    if len(temp) == 300:
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, after=temp[299][0], limit='300')
                    else:
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, limit='300')
                await asyncio.sleep(2)
                candles.extend(temp)
                limit -= 300
            return {'instId': instId, 'candles': candles}

    async def profitability(self, funding_rate_list, days=7) -> List[dict]:
        """显示各币种资金费率除以波动率
        """
        # /api/v5/market/candles 限速： 20次/2s
        sem = asyncio.Semaphore(20)
        task_list = [self.get_candles(sem, n['instrument'] + '-USDT', days) for n in funding_rate_list]
        gather_result = await gather(*task_list)
        for n in range(len(funding_rate_list)):
            atr = average_true_range(gather_result[n]['candles'], days)
            funding_rate_list[n]['profitability'] = int(funding_rate_list[n]['funding_rate'] / sqrt(atr) * 10000)
        funding_rate_list.sort(key=lambda x: x['profitability'], reverse=True)
        funding_rate_list = funding_rate_list[:10]
        fprint(coin_funding_value)
        for n in funding_rate_list:
            fprint(f"{n['instrument']:9s}{n['funding_rate']:7.3%}"
                   f"{n['funding_rate'] * 3 * 365:8.2%}{n['profitability']:8d}")
        return funding_rate_list

    def open_dist(self):
        """开仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=4)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$open_pd'}, 'std': {'$stdDevSamp': '$open_pd'},
                                'max': {'$max': '$open_pd'}, 'min': {'$min': '$open_pd'}, 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
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
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p15sigma, '$gt': m15sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p2sigma, '$gt': m2sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'open_pd': {'$lt': p3sigma, '$gt': m3sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count3 = result['count']
        frequency3 = count3 / total
        print(f'开仓 {self.coin} {p2sigma:.2%}')
        print(f'{frequency1:.2%} {frequency15:.2%} {frequency2:.2%} {frequency3:.2%}')

    def close_dist(self):
        """平仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=4)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$close_pd'}, 'std': {'$stdDevSamp': '$close_pd'},
                                'max': {'$max': '$close_pd'}, 'min': {'$min': '$close_pd'}, 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
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
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p15sigma, '$gt': m15sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p2sigma, '$gt': m2sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp},
                                'close_pd': {'$lt': p3sigma, '$gt': m3sigma}}},
                    {'$group': {'_id': '$instrument', 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        count3 = result['count']
        frequency3 = count3 / total
        print(f'平仓 {self.coin} {m2sigma:.2%}')
        print(f'{frequency1:.2%} {frequency15:.2%} {frequency2:.2%} {frequency3:.2%}')

    def recent_ticker(self, hours=4):
        """返回近期期现差价列表

        :param hours: 最近几小时
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)

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
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$open_pd'}, 'std': {'$stdDevSamp': '$open_pd'},
                                'max': {'$max': '$open_pd'}, 'min': {'$min': '$open_pd'}}}]
        return result[0] if (result := [x for x in Record.mycol.aggregate(pipeline)]) else None

    def recent_close_stat(self, hours=4):
        """返回近期平仓期现差价统计值

        :param hours: 最近几小时
        :rtype: dict
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$close_pd'}, 'std': {'$stdDevSamp': '$close_pd'},
                                'max': {'$max': '$close_pd'}, 'min': {'$min': '$close_pd'}}}]
        return result[0] if (result := [x for x in Record.mycol.aggregate(pipeline)]) else None

    def open_time(self, account):
        """返回开仓时间

        :param account: 账号id
        :rtype: datetime
        """
        Record = record.Record('Ledger')
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'title': "开仓"}},
                    {'$sort': {'_id': -1}}, {'$limit': 1}]
        open_time = result[0]['timestamp'] if (result := [x for x in Record.mycol.aggregate(pipeline)]) else None
        return open_time if open_time else datetime(2021, 4, 1)

    def close_time(self, account):
        """返回开仓时间

        :param account: 账号id
        :rtype: datetime
        """
        Record = record.Record('Ledger')
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'title': "平仓"}},
                    {'$sort': {'_id': -1}}, {'$limit': 1}]
        close_time = result[0]['timestamp'] if (result := [x for x in Record.mycol.aggregate(pipeline)]) else None
        return close_time if close_time else datetime.utcnow()

    def history_funding(self, account, days=0):
        """最近累计资金费

        :param account: 账号id
        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Record = record.Record('Ledger')
        if days == -1:
            open_time = datetime(2021, 4, 1)
        elif days == 0:
            open_time = self.open_time(account)
        else:
            open_time = datetime.utcnow() - timedelta(days=days)
        pipeline = [{'$match': {'account': account, 'instrument': self.coin, 'timestamp': {'$gt': open_time}}},
                    {'$group': {'_id': '$instrument', 'sum': {'$sum': '$funding'}}}]
        return result[0]['sum'] if (result := [x for x in Record.mycol.aggregate(pipeline)]) else 0.

    def history_cost(self, account, days=0):
        """最近累计成本

        :param account: 账号id
        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Record = record.Record('Ledger')
        if days == -1:
            open_time = datetime(2021, 4, 1)
        elif days == 0:
            open_time = self.open_time(account)
        else:
            open_time = datetime.utcnow() - timedelta(days=days)
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
