import okex.public as public
import pymongo
from datetime import datetime, timedelta
import time
import funding_rate


class Record:

    def __init__(self, col=''):
        self.myclient = pymongo.MongoClient('mongodb://localhost:27017/')
        self.mydb = self.myclient['OKEx']
        self.mycol = self.mydb[col]

    def find_last(self, match: dict):
        """返回最后一条记录

        :param match: 匹配条件
        :rtype: dict
        """
        pipeline = [{
            '$match': match
        }, {
            '$sort': {
                '_id': -1
            }
        }, {
            '$limit': 1
        }
        ]
        for x in self.mycol.aggregate(pipeline):
            return x

    def delete(self):
        myquery = {
            'instrument': 'CFX',
            'title': '自动加仓',
            'timestamp': {
                '$gt': datetime.fromisoformat("2021-04-18T03:23:00.000")
            }}
        self.mycol.delete_many(myquery)


def record_ticker():
    ticker = Record('Ticker')
    funding = Record('Funding')
    fundingRate = funding_rate.FundingRate()
    instrumentsID = fundingRate.get_instruments_ID()
    publicAPI = public.PublicAPI()

    while True:
        timestamp = datetime.utcnow()
        begin = timestamp

        # 每8小时记录资金费
        if timestamp.hour % 8 == 0:
            if timestamp.minute == 1:
                if timestamp.second < 10:
                    funding_rate_list = []
                    for m in instrumentsID:
                        historical_funding_rate = publicAPI.get_historical_funding_rate(instId=m, limit='1')
                        for n in historical_funding_rate:
                            timestamp = funding_rate.utcfrommillisecs(n['fundingTime'])
                            mydict = {'instrument': m[:m.find('-')], 'timestamp': timestamp, 'funding': float(n['realizedRate'])}
                            funding_rate_list.append(mydict)
                    funding.mycol.insert_many(funding_rate_list)

                    myquery = {
                        'timestamp': {
                            '$lt': timestamp.__sub__(timedelta(hours=24))
                        }}
                    ticker.mycol.delete_many(myquery)

        spot_ticker = publicAPI.get_tickers('SPOT')
        swap_ticker = publicAPI.get_tickers('SWAP')
        mylist = []
        for m in instrumentsID:
            swap_ID = m
            spot_ID = swap_ID[:swap_ID.find('-SWAP')]
            coin = spot_ID[:spot_ID.find('-USDT')]
            spot_ask, spot_bid, swap_bid, swap_ask = 0., 0., 0., 0.
            for n in spot_ticker:
                if n['instId'] == spot_ID:
                    timestamp = funding_rate.utcfrommillisecs(n['ts'])
                    # print(timestamp)
                    spot_ask = float(n['askPx'])
                    spot_bid = float(n['bidPx'])
            for n in swap_ticker:
                if n['instId'] == swap_ID:
                    swap_ask = float(n['askPx'])
                    swap_bid = float(n['bidPx'])
            if spot_ask and spot_bid:
                open_pd = (swap_bid - spot_ask) / spot_ask
                close_pd = (swap_ask - spot_bid) / spot_bid
            else:
                continue
            mydict = {'instrument': coin, "timestamp": timestamp, 'spot_bid': spot_bid, 'spot_ask': spot_ask,
                      'swap_bid': swap_bid, 'swap_ask': swap_ask, 'open_pd': open_pd, 'close_pd': close_pd}
            mylist.append(mydict)
        ticker.mycol.insert_many(mylist)
        timestamp = datetime.utcnow()
        delta = timestamp.__sub__(begin).total_seconds()
        if delta < 10:
            time.sleep(10 - delta)
