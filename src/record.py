from okex.public import PublicAPI
import pymongo
import src.funding_rate as funding_rate
from src.utils import *


class Record:
    myclient = pymongo.MongoClient('mongodb://localhost:27017/', connect=False)
    mydb = myclient['OKEx']

    def __init__(self, col=''):
        self.mycol = self.mydb[col]

    def find_last(self, match: dict):
        """返回最后一条记录

        :param match: 匹配条件
        :rtype: dict
        """
        pipeline = [{'$match': match},
                    {'$sort': {'_id': -1}},
                    {'$limit': 1}]
        for x in self.mycol.aggregate(pipeline):
            return x

    def insert(self, match: dict):
        """插入对应记录

        :param match: 匹配条件
        """
        self.mycol.find_one_and_replace(match, match, upsert=True)

    def delete(self, match: dict):
        """删除对应记录

        :param match: 匹配条件
        """
        self.mycol.delete_one(match)


recording = False


def record_ticker(accountid=3):
    global recording
    if not recording:
        recording = True
        loop = asyncio.get_event_loop()
        while True:
            try:
                loop.run_until_complete(record(accountid))
            except aiohttp.ClientError:
                print(lang.network_interruption)
                time.sleep(30)


async def record(accountid=3):
    print(lang.record_ticker)
    ticker = Record('Ticker')
    funding = Record('Funding')
    fundingRate = funding_rate.FundingRate(accountid)
    instrumentsID = await fundingRate.get_instruments_ID()
    publicAPI = fundingRate.publicAPI
    ten_seconds = Looper(interval=10)
    funding_time = FundingTime()
    async for event in EventChain(ten_seconds, funding_time):
        timestamp = datetime.utcnow()
        # 每8小时记录资金费
        if event == funding_time:
            funding_rate_list = []
            instrumentsID = await fundingRate.get_instruments_ID()
            tasks = [publicAPI.get_historical_funding_rate(instId=swap_ID) for swap_ID in instrumentsID]
            res = await asyncio.gather(*tasks, return_exceptions=True)
            for swap_ID, historical_funding_rate in zip(instrumentsID, res):
                if isinstance(historical_funding_rate, AssertionError):
                    continue
                instrument = swap_ID[:swap_ID.find('-')]
                pipeline = [{'$match': {'instrument': instrument}}]
                # Results in DB
                db_funding = [n for n in funding.mycol.aggregate(pipeline)]
                for n in historical_funding_rate:
                    timestamp = utcfrommillisecs(n['fundingTime'])
                    realized_rate = safe_float(n['realizedRate'])
                    for item in db_funding:
                        if item['funding'] == realized_rate:
                            if item['timestamp'] == timestamp:
                                break
                    else:
                        mydict = {'instrument': instrument, 'timestamp': timestamp,
                                  'funding': realized_rate}
                        funding_rate_list.append(mydict)
            if funding_rate_list:
                funding.mycol.insert_many(funding_rate_list)
            myquery = {'timestamp': {'$lt': timestamp - timedelta(hours=48)}}
            ticker.mycol.delete_many(myquery)
        elif event == ten_seconds:
            assert (spot_ticker := await publicAPI.get_tickers('SPOT'))
            assert (swap_ticker := await publicAPI.get_tickers('SWAP'))
            mylist = []
            for swap_ID in instrumentsID:
                spot_ID = swap_ID[:swap_ID.find('-SWAP')]
                coin = spot_ID[:spot_ID.find('-USDT')]
                spot_ask = spot_bid = swap_bid = swap_ask = 0.
                for i, n in enumerate(spot_ticker):
                    if n['instId'] == spot_ID:
                        timestamp = utcfrommillisecs(n['ts'])
                        spot_ask = safe_float(n['askPx'])
                        spot_bid = safe_float(n['bidPx'])
                        spot_ticker.pop(i)
                        break
                for i, n in enumerate(swap_ticker):
                    if n['instId'] == swap_ID:
                        swap_ask = safe_float(n['askPx'])
                        swap_bid = safe_float(n['bidPx'])
                        swap_ticker.pop(i)
                        break
                if spot_ask and spot_bid:
                    open_pd = (swap_bid - spot_ask) / spot_ask
                    close_pd = (swap_ask - spot_bid) / spot_bid
                else:
                    continue
                mydict = {'instrument': coin, "timestamp": timestamp, 'spot_bid': spot_bid, 'spot_ask': spot_ask,
                          'swap_bid': swap_bid, 'swap_ask': swap_ask, 'open_pd': open_pd, 'close_pd': close_pd}
                mylist.append(mydict)
            ticker.mycol.insert_many(mylist)
        else:
            raise ValueError
