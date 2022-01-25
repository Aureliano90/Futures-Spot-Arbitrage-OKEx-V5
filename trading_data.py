from typing import List
import okex.asset as asset
import okex.public as public
import record
import matplotlib.pyplot as plt
from utils import *
from lang import *
from asyncio import create_task, gather
import numpy as np


def open(candle: np.ndarray):
    """开盘价

    :param candle: K线
    """
    return candle.T[1]


def high(candle: np.ndarray):
    """最高价

    :param candle: K线
    """
    return candle.T[2]


def low(candle: np.ndarray):
    """最低价

    :param candle: K线
    """
    return candle.T[3]


def close(candle: np.ndarray):
    """收盘价

    :param candle: K线
    """
    return candle.T[4]


def true_range(candle: np.ndarray, previous: np.ndarray) -> np.ndarray:
    """相对振幅

    :param candle: 当前K线
    :param previous: 上一K线
    """
    h = high(candle)
    l = low(candle)
    c = close(previous)
    hl = h - l
    hc = np.abs(h - c)
    lc = np.abs(l - c)
    return np.max([hl, hc, lc], axis=0) / c


def average_true_range(candles: List[List], days, bar='4H'):
    """平均相对振幅

    :param candles: K线列表
    :param days:最近几天
    :param bar: 精度
    """
    if bar.endswith('m'):
        limit = days * 1440 // int(rtruncate(bar, 1))
    elif bar.endswith('H'):
        limit = days * 24 // int(rtruncate(bar, 1))
    elif bar.endswith('D'):
        limit = days
    elif bar.endswith('W'):
        limit = days // 7
    elif bar.endswith('M'):
        limit = days // (30 * int(rtruncate(bar, 1)))
    else:
        limit = days // 365
    candles = np.asanyarray(candles, dtype=np.float64)
    num_candles = min(limit, np.shape(candles)[0] - 1)
    tr = true_range(candles[:num_candles], candles[1:num_candles + 1])
    return np.mean(tr)


@call_coroutine
# @debug_timer
class Stat:
    """交易数据统计功能类
    """
    assetAPI = asset.AssetAPI(api_key='', api_secret_key='', passphrase='')
    publicAPI = public.PublicAPI()
    sem = None

    @property
    def __name__(self):
        return 'Stat'

    def __init__(self, coin: str = None):
        # assetAPI = asset.AssetAPI(api_key='', api_secret_key='', passphrase='')
        # self.publicAPI = public.PublicAPI()

        self.coin = coin
        if coin:
            assert isinstance(coin, str)
            self.spot_ID = coin + '-USDT'
            self.swap_ID = coin + '-USDT-SWAP'
            self.spot_info = None
            self.swap_info = None
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

    @staticmethod
    def clean():
        if hasattr(Stat, 'assetAPI'):
            Stat.assetAPI.__del__()
        if hasattr(Stat, 'publicAPI'):
            Stat.publicAPI.__del__()

    async def get_candles(self, instId, days, bar='4H') -> List[List]:
        """获取4小时K线

        :param instId: 产品ID
        :param days: 最近几天
        :param bar: 时间粒度，默认值1m，如 [1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M/3M/6M/1Y]
        """
        async with Stat.sem:
            if bar.endswith('m'):
                limit = days * 1440 // int(rtruncate(bar, 1)) + 1
            elif bar.endswith('H'):
                limit = days * 24 // int(rtruncate(bar, 1)) + 1
            elif bar.endswith('D'):
                limit = days + 1
            elif bar.endswith('W'):
                limit = days // 7 + 1
            elif bar.endswith('M'):
                limit = days // (30 * int(rtruncate(bar, 1))) + 1
            else:
                limit = days // 365 + 1
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
            return candles

    async def history_candles(self, instId, days, bar='4H') -> List[List]:
        """获取4小时K线

        :param instId: 产品ID
        :param days: 最近几天
        :param bar: 时间粒度，默认值1m，如 [1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M/3M/6M/1Y]
        """
        async with Stat.sem:
            if bar.endswith('m'):
                limit = days * 1440 // int(rtruncate(bar, 1)) + 1
            elif bar.endswith('H'):
                limit = days * 24 // int(rtruncate(bar, 1)) + 1
            elif bar.endswith('D'):
                limit = days + 1
            elif bar.endswith('W'):
                limit = days // 7 + 1
            elif bar.endswith('M'):
                limit = days // (30 * int(rtruncate(bar, 1))) + 1
            else:
                limit = days // 365 + 1
            candles = temp = []
            while limit > 0:
                if limit <= 100:
                    if len(temp) == 100:
                        # 最后一次
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, after=temp[99][0], limit=limit)
                    else:
                        # 第一次
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, limit=limit)
                else:
                    if len(temp) == 100:
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, after=temp[99][0], limit='100')
                    else:
                        temp = await self.assetAPI.get_kline(instId=instId, bar=bar, limit='100')
                await asyncio.sleep(2)
                candles.extend(temp)
                limit -= 100
            if not candles: print(instId, candles)
            return candles

    # @debug_timer
    async def profitability(self, funding_rate_list, days=7) -> List[dict]:
        """显示各币种资金费率除以波动率
        """
        # /api/v5/market/candles 限速： 20次/2s
        Stat.sem = asyncio.Semaphore(20)
        bar = '4H'
        if bar.endswith('m'):
            limit = days * 1440 // int(rtruncate(bar, 1)) + 1
        elif bar.endswith('H'):
            limit = days * 24 // int(rtruncate(bar, 1)) + 1
        elif bar.endswith('D'):
            limit = days + 1
        elif bar.endswith('W'):
            limit = days // 7 + 1
        elif bar.endswith('M'):
            limit = days // (30 * int(rtruncate(bar, 1))) + 1
        else:
            limit = days // 365 + 1
        if limit <= 1440:
            task_list = [self.get_candles(n['instrument'] + '-USDT', days, bar) for n in funding_rate_list]
        else:
            task_list = [self.history_candles(n['instrument'] + '-USDT', days, bar) for n in funding_rate_list]
        gather_result = await gather(*task_list)
        for n in range(len(funding_rate_list)):
            atr = average_true_range(gather_result[n], days, '4H')
            funding_rate_list[n]['profitability'] = int(funding_rate_list[n]['funding_rate'] / np.sqrt(atr) * 10000)
        funding_rate_list.sort(key=lambda x: x['profitability'], reverse=True)
        funding_rate_list = funding_rate_list[:10]
        fprint(coin_funding_value)
        for n in funding_rate_list:
            fprint(f"{n['instrument']:9s}{n['funding_rate']:7.3%}"
                   f"{n['funding_rate'] * 3 * 365:8.2%}{n['profitability']:8d}")
        return funding_rate_list

    async def historical_volatility(self, instId):
        pass

    def open_dist(self, hours=4):
        """开仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$open_pd'}, 'std': {'$stdDevSamp': '$open_pd'},
                                'max': {'$max': '$open_pd'}, 'min': {'$min': '$open_pd'}, 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        avg = result['avg']
        std = result['std']
        total = result['count']
        p1sigma = avg + std
        m1sigma = avg - std
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
        return dict(avg=avg, std=std, frequency1=frequency1, frequency2=frequency2, frequency3=frequency3)

    def close_dist(self, hours=4):
        """平仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)

        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}},
                    {'$group': {'_id': '$instrument', 'avg': {'$avg': '$close_pd'}, 'std': {'$stdDevSamp': '$close_pd'},
                                'max': {'$max': '$close_pd'}, 'min': {'$min': '$close_pd'}, 'count': {'$sum': 1}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)][0]
        avg = result['avg']
        std = result['std']
        total = result['count']
        p1sigma = avg + std
        m1sigma = avg - std
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
        return dict(avg=avg, std=std, frequency1=frequency1, frequency2=frequency2, frequency3=frequency3)

    def gaussian_dist(self, hours=4, side='o'):
        Record = record.Record('Ticker')
        timestamp = datetime.utcnow() - timedelta(hours=hours)
        pipeline = [{'$match': {'instrument': self.coin, 'timestamp': {'$gt': timestamp}}}]
        result = [x for x in Record.mycol.aggregate(pipeline)]

        if side == 'o':
            arr = np.asarray([x['open_pd'] for x in result], dtype=float)
        else:
            arr = np.asarray([x['close_pd'] for x in result], dtype=float)
        min = np.min(arr)
        max = np.max(arr)
        bin_num = 40
        width = (max - min) / bin_num
        premiums = np.asarray([min + (i + 0.5) * width for i in range(bin_num)])
        binning = (arr - min) // width
        binning = np.asarray(binning, dtype=int)
        prob = np.zeros(bin_num)
        bins, counts = np.unique(binning, return_counts=True)
        for n in range(len(bins)):
            if bins[n] == bin_num:
                prob[bin_num - 1] += counts[n]
            else:
                prob[bins[n]] = counts[n]
        prob = prob / np.sum(counts)
        stat = self.open_dist(hours)
        avg = stat['avg']
        std = stat['std']
        p1sigma = avg + std
        m1sigma = avg - std
        p2sigma = avg + 2 * std
        m2sigma = avg - 2 * std
        p3sigma = avg + 3 * std
        m3sigma = avg - 3 * std
        frequency1 = stat['frequency1']
        frequency2 = stat['frequency2']
        frequency3 = stat['frequency3']
        x = np.arange(min, max, width / 10)
        y = np.exp(- np.square(x - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = 12
        plt.figure(figsize=(16, 8))
        color = 'g' if side == 'o' else 'r'
        plt.plot(premiums, prob, '.', color=color, label=historical_data)
        plt.plot(x, y, '-', color='b', label=gaussian_dist)

        plt.axvline(avg, color='orange', label=plot_average.format(avg))
        ymax = np.exp(- np.square(p1sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([p1sigma] * len(y), y, '-', color='m', label=one_std)
        ymax = np.exp(- np.square(m1sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([m1sigma] * len(y), y, '-', color='m', label=plot_probability + f': {frequency1:.2%}')
        ymax = np.exp(- np.square(p2sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([p2sigma] * len(y), y, '-', color='m', label=two_std)
        ymax = np.exp(- np.square(m2sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([m2sigma] * len(y), y, '-', color='m', label=plot_probability + f': {frequency2:.2%}')
        ymax = np.exp(- np.square(p3sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([p3sigma] * len(y), y, '-', color='m', label=three_std)
        ymax = np.exp(- np.square(m3sigma - avg) / 2. / std ** 2) / std / np.sqrt(2 * np.pi) * width
        y = np.arange(0, ymax, ymax / 100)
        plt.plot([m3sigma] * len(y), y, '-', color='m', label=plot_probability + f': {frequency3:.2%}')
        if side == 'o':
            plt.xlabel(pd_open, fontsize=14)
        else:
            plt.xlabel(pd_close, fontsize=14)
        plt.gca().xaxis.set_major_formatter('{x:.3%}')
        plt.ylabel(plot_probability, fontsize=14)
        plt.ylim(bottom=0)
        plt.legend(loc="best", fontsize=16)
        plt.title(plot_title.format(self.coin, hours), fontsize=18)
        plt.show()

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
        return dict(timestamp=timelist, open_pd=open_pd, close_pd=close_pd)

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
        mylist = self.recent_ticker(hours)
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = 12
        plt.figure(figsize=(16, 8))
        plt.plot(mylist['timestamp'], mylist['open_pd'], '.', color='g', label=pd_open)
        plt.axhline(y=open_pd, color='g', linestyle='-', label=two_std)
        # plt.plot(mylist['timestamp'], [open_pd] * len(mylist['timestamp']), '-', color='g', label=two_std)
        plt.plot(mylist['timestamp'], mylist['close_pd'], '.', color='r', label=pd_close)
        plt.axhline(y=close_pd, color='r', linestyle='-', label=two_std)
        # plt.plot(mylist['timestamp'], [close_pd] * len(mylist['timestamp']), '-', color='r', label=two_std)
        # plt.xticks(rotation=45)
        plt.gca().yaxis.set_major_formatter('{x:.3%}')
        plt.xlabel(plot_time, fontsize=14)
        plt.ylabel(plot_premium, fontsize=14)
        plt.legend(loc="best", fontsize=14)
        plt.title(plot_title.format(self.coin, hours), fontsize=18)
        plt.show()
