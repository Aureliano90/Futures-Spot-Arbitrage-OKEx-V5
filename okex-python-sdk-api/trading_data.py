from math import sqrt
from typing import List
import okex.spot_api as spot
from datetime import datetime, timedelta, timezone
import statistics
import record
import funding_rate
import matplotlib.pyplot as plt
from log import fprint
from lang import *


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


def profitability(days=7) -> List[dict]:
    """显示各币种资金费率除以波动率

    :param days: 最近几天
    """
    fd = funding_rate.FundingRate()
    funding_rate_list = fd.get_rate(days)
    funding_rate_list.sort(key=lambda x: x['funding_rate'], reverse=True)
    funding_rate_list = funding_rate_list[:20]
    for n in funding_rate_list:
        s = Stat(n['instrument'])
        candles = s.get_candles()
        atr = s.atr(candles, days)
        n['profitability'] = int(n['funding_rate'] / sqrt(atr) * 10000)
    funding_rate_list.sort(key=lambda x: x['profitability'], reverse=True)
    funding_rate_list = funding_rate_list[:10]
    fprint(coin_funding_value)
    for n in funding_rate_list:
        fprint('{:7s}{:7.3%}{:6d}'.format(n['instrument'], n['funding_rate'], n['profitability']))
    return funding_rate_list


class Stat:
    """交易数据统计功能类
    """

    def __init__(self, coin=''):
        self.spotAPI = spot.SpotAPI(api_key='', api_secret_key='', passphrase='')

        self.coin = coin
        self.spot_ID = coin + '-USDT'
        self.swap_ID = coin + '-USDT-SWAP'
        self.exist = True

        self.spot_info = self.spotAPI.get_instrument(self.spot_ID)
        if not self.spot_info:
            print(nonexistent_crypto)
            self.exist = False
            del self

    def open_dist(self):
        """开仓期现差价正态分布统计
        """
        Record = record.Record('Ticker')

        timestamp = datetime.utcnow()
        # print(timestamp)
        # 只统计最近4小时
        timestamp = timestamp.__sub__(timedelta(hours=4))
        # print(timestamp)

        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'avg': {
                        '$avg': '$open_pd'
                    },
                    'std': {
                        '$stdDevSamp': '$open_pd'
                    },
                    'max': {
                        '$max': '$open_pd'
                    },
                    'min': {
                        '$min': '$open_pd'
                    },
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
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

        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'open_pd': {
                        '$lt': p1sigma,
                        '$gt': m1sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'open_pd': {
                        '$lt': p15sigma,
                        '$gt': m15sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'open_pd': {
                        '$lt': p2sigma,
                        '$gt': m2sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'open_pd': {
                        '$lt': p3sigma,
                        '$gt': m3sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
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

        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'avg': {
                        '$avg': '$close_pd'
                    },
                    'std': {
                        '$stdDevSamp': '$close_pd'
                    },
                    'max': {
                        '$max': '$close_pd'
                    },
                    'min': {
                        '$min': '$close_pd'
                    },
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
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

        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'close_pd': {
                        '$lt': p1sigma,
                        '$gt': m1sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count1 = result['count']
        frequency1 = count1 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'close_pd': {
                        '$lt': p15sigma,
                        '$gt': m15sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count15 = result['count']
        frequency15 = count15 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'close_pd': {
                        '$lt': p2sigma,
                        '$gt': m2sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count2 = result['count']
        frequency2 = count2 / total
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    },
                    'close_pd': {
                        '$lt': p3sigma,
                        '$gt': m3sigma
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            result = x
        count3 = result['count']
        frequency3 = count3 / total
        print("平仓", self.coin, '{:.2%}'.format(m2sigma))
        print('{:.2%}'.format(frequency1), '{:.2%}'.format(frequency15), '{:.2%}'.format(frequency2),
              '{:.2%}'.format(frequency3))

    def get_candles(self, granularity=14400):
        """获取4小时K线

        :param granularity: 秒数
        :rtype: List[list]
        """
        return self.spotAPI.get_kline(instrument_id=self.spot_ID, granularity=granularity)

    @staticmethod
    def tr(candle: list, previous: list):
        """相对振幅

        :param candle: 当前K线
        :param previous: 上一K线
        """
        return max(high(candle) - low(candle), abs(high(candle) - close(previous)),
                   abs(low(candle) - close(previous))) / close(previous)

    def atr(self, candles: list, days=7):
        """平均相对振幅

        :param candles: K线列表
        :param days:最近几天
        """
        tr = []
        # Use 4h candles
        for n in range(days * 6):
            tr.append(self.tr(candles[n], candles[n + 1]))
        return statistics.mean(tr)

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

        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    }
                }
            }
            ]
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
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'avg': {
                        '$avg': '$open_pd'
                    },
                    'std': {
                        '$stdDevSamp': '$open_pd'
                    },
                    'max': {
                        '$max': '$open_pd'
                    },
                    'min': {
                        '$min': '$open_pd'
                    }
                }
            }
        ]
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
        pipeline = [
            {
                '$match': {
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': timestamp
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'avg': {
                        '$avg': '$close_pd'
                    },
                    'std': {
                        '$stdDevSamp': '$close_pd'
                    },
                    'max': {
                        '$max': '$close_pd'
                    },
                    'min': {
                        '$min': '$close_pd'
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            return x

    def open_time(self, account):
        """返回开仓时间

        :param account: 账号id
        :rtype: datetime
        """
        Record = record.Record('Ledger')
        pipeline = [{
            '$match': {
                'account': account,
                'instrument': self.coin,
                'title': "开仓"
            }
        }, {
            '$sort': {
                '_id': -1
            }
        }, {
            '$limit': 1
        }
        ]
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
        pipeline = [
            {
                '$match': {
                    'account': account,
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': open_time
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'sum': {
                        '$sum': '$funding'
                    }
                }
            }
        ]
        for x in Record.mycol.aggregate(pipeline):
            # 累计资金费
            return x['sum']
        return 0

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
        pipeline = [
            {
                '$match': {
                    'account': account,
                    'instrument': self.coin,
                    'timestamp': {
                        '$gt': open_time
                    }
                }
            }, {
                '$group': {
                    '_id': '$instrument',
                    'spot_notional': {
                        '$sum': '$spot_notional'
                    },
                    'swap_notional': {
                        '$sum': '$swap_notional'
                    },
                    'fee': {
                        '$sum': '$fee'
                    }
                }}
        ]
        for x in Record.mycol.aggregate(pipeline):
            return x['spot_notional'] + x['swap_notional'] + x['fee']
        return 0

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


if __name__ == '__main__':
    # BADGER, CHZ, DORA, FTM, LON, MASK, MIR, TORN
    # for m in ['BADGER', 'CHZ', 'DORA', 'FTM', 'LON', 'MASK', 'MIR', 'TORN']:
    #     stat = Stat(m)
    #     stat.open_dist()
    #     stat.close_dist()

    # profitability(day=14)

    stat = Stat('BTT')
    stat.plot(4)
