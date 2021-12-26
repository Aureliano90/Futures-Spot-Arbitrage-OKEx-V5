import time
from datetime import datetime
from typing import List
import okex.public as public
import statistics
import record
import trading_data
from log import fprint
from lang import *
import asyncio


def utcfrommillisecs(millisecs: str):
    return datetime.utcfromtimestamp(int(millisecs) / 1000)


class FundingRate:

    def __init__(self):
        self.publicAPI = public.PublicAPI()

    def __del__(self):
        # print("FundingRate del started")
        del self.publicAPI
        # print("FundingRate del finished")

    async def get_instruments_ID(self):
        """获取合约币种列表

        :rtype: List[str]
        """
        instruments = await self.publicAPI.get_instruments('SWAP')
        # pprint(instruments)
        instrumentsID = []  # 空列表
        for n in instruments:
            if n['instId'].find('USDT') != -1:  # 只统计U本位合约
                instrumentsID.append(n['instId'])
        # print(instrumentsID)
        return instrumentsID

    async def current(self, instrument_id=''):
        """当期资金费

        :param instrument_id: 币种合约
        """
        current_rate = (await self.publicAPI.get_funding_time(instId=instrument_id))['fundingRate']
        if current_rate:
            current_rate = float(current_rate)
        else:
            current_rate = 0.
        return current_rate

    async def next(self, instrument_id=''):
        """预测资金费

        :param instrument_id: 币种合约
        """
        next_rate = (await self.publicAPI.get_funding_time(instId=instrument_id))['nextFundingRate']
        if next_rate:
            next_rate = float(next_rate)
        else:
            next_rate = 0.
        return next_rate

    async def current_next(self, instrument_id=''):
        """当期和预测资金费

        :param instrument_id: 币种合约
        """
        funding_rate = await self.publicAPI.get_funding_time(instId=instrument_id)
        current_rate = funding_rate['fundingRate']
        if current_rate:
            current_rate = float(current_rate)
        else:
            current_rate = 0.
        next_rate = funding_rate['nextFundingRate']
        if next_rate:
            next_rate = float(next_rate)
        else:
            next_rate = 0.
        return current_rate, next_rate

    async def show_current_rate(self):
        """显示当前资金费
        """
        # begin = time.monotonic()
        instrumentsID = await self.get_instruments_ID()

        task_list = []
        funding_rate_list = []
        for m in instrumentsID:
            task_list.append(self.publicAPI.get_funding_time(instId=m))
        gather_result = await asyncio.gather(*task_list)
        for funding_time in gather_result:
            instId = funding_time['instId']
            if funding_time['fundingRate']:
                current_rate = float(funding_time['fundingRate'])
            else:
                current_rate = 0.
            if funding_time['nextFundingRate']:
                estimated_rate = float(funding_time['nextFundingRate'])
            else:
                estimated_rate = 0.
            funding_rate_list.append(
                {'instrument_id': instId, 'current_rate': current_rate, 'estimated_rate': estimated_rate})
        funding_rate_list.sort(key=lambda x: x['current_rate'], reverse=True)
        # pprint(funding_rate_list)
        fprint(coin_current_next)
        for n in funding_rate_list:
            instrumentID = n['instrument_id'][:n['instrument_id'].find('-')]
            current_rate = n['current_rate']
            estimated_rate = n['estimated_rate']
            fprint('{:8s}{:9.3%}{:11.3%}'.format(instrumentID, current_rate, estimated_rate))
        # end = time.monotonic()
        # print("show_current_rate takes %f s" % (end - begin))
        # 50 s without asyncio
        # 1.6 s with asyncio

    async def show_nday_rate(self, days: int):
        """显示最近n天平均资金费

        :param days: 天数
        """
        # begin = time.monotonic()
        instrumentsID = await self.get_instruments_ID()
        limit = '{:d}'.format(days * 3)
        task_list = []
        funding_rate_list = []
        for m in instrumentsID:
            task_list.append(self.publicAPI.get_historical_funding_rate(instId=m, limit=limit))
        gather_result = await asyncio.gather(*task_list)
        for historical_funding_rate in gather_result:
            instId = historical_funding_rate[0]['instId']
            realized_rate = []
            if len(historical_funding_rate) == 0:
                pass
            elif len(historical_funding_rate) < days * 3:
                pass
            else:
                for n in historical_funding_rate:
                    realized_rate.append(float(n['realizedRate']))
                funding_rate_list.append(
                    {'instrument_id': instId, 'funding_rate': statistics.mean(realized_rate[:days * 3])})

        funding_rate_list.sort(key=lambda x: x['funding_rate'], reverse=True)
        for n in funding_rate_list:
            instrumentID = n['instrument_id'][:n['instrument_id'].find('-')]
            fprint('{:8s}{:8.3%}'.format(instrumentID, n['funding_rate']))
        # end = time.monotonic()
        # print("show_nday_rate takes %f s" % (end - begin))
        # 1.4 s with asyncio

    async def print_30day_rate(self):
        """输出最近30天平均资金费到文件
        """
        # begin = time.monotonic()
        instrumentsID = await self.get_instruments_ID()

        task_list = []
        funding_rate_list = []
        for m in instrumentsID:
            task_list.append(self.publicAPI.get_historical_funding_rate(instId=m, limit='90'))
        gather_result = await asyncio.gather(*task_list)
        for historical_funding_rate in gather_result:
            instId = historical_funding_rate[0]['instId']
            realized_rate = []
            # pprint(historical_funding_rate)
            # 永续合约上线不一定有30天
            if len(historical_funding_rate) < 21:
                # print(m + "上线不到7天。")
                pass
            elif len(historical_funding_rate) < 90:
                # print(m + "上线不到30天。")
                for n in historical_funding_rate:
                    realized_rate.append(float(n['realizedRate']))
                funding_rate_list.append(
                    {'instrument_id': instId, '7day_funding_rate': statistics.mean(realized_rate[:21]),
                     '30day_funding_rate': 0})
            else:
                for n in historical_funding_rate:
                    realized_rate.append(float(n['realizedRate']))
                funding_rate_list.append(
                    {'instrument_id': instId, '7day_funding_rate': statistics.mean(realized_rate[:21]),
                     '30day_funding_rate': statistics.mean(realized_rate[:90])})

        funding_rate_list.sort(key=lambda x: x['30day_funding_rate'], reverse=True)
        funding_rate_list.sort(key=lambda x: x['7day_funding_rate'], reverse=True)

        funding_rate_file = open("Funding Rate.txt", "w", encoding="utf-8")
        funding_rate_file.write(coin_7_30)
        for n in funding_rate_list:
            instrumentID = n['instrument_id'][:n['instrument_id'].find('-')]
            funding_rate_file.write(instrumentID.ljust(9))
            funding_rate_file.write('{:7.3%}'.format(n['7day_funding_rate']))
            funding_rate_file.write('{:8.3%}'.format(n['30day_funding_rate']) + '\n')
        funding_rate_file.close()
        # end = time.monotonic()
        # print("print_30day_rate takes %f s" % (end - begin))

    async def get_rate(self, days=7):
        """返回最近资金费列表

        :param days: 最近几天
        :rtype: List[dict]
        """
        instrumentsID = await self.get_instruments_ID()
        limit = str(days * 3)

        task_list = []
        funding_rate_list = []
        for m in instrumentsID:
            task_list.append(self.publicAPI.get_historical_funding_rate(instId=m, limit=limit))
        gather_result = await asyncio.gather(*task_list)
        for historical_funding_rate in gather_result:
            instId = historical_funding_rate[0]['instId']
            realized_rate = []
            if len(historical_funding_rate) < days * 3:
                pass
            else:
                instrumentID = instId[:instId.find('-')]
                for n in historical_funding_rate:
                    realized_rate.append(float(n['realizedRate']))
                funding_rate_list.append({'instrument': instrumentID, 'funding_rate': statistics.mean(realized_rate)})
        return funding_rate_list

    async def funding_history(self, instId):
        """下载最近3个月资金费率
        """
        historical_funding_rate = await self.publicAPI.get_historical_funding_rate(instId=instId)
        temp = historical_funding_rate
        while len(temp) == 100:
            temp = await self.publicAPI.get_historical_funding_rate(instId=instId, after=temp[99]['fundingTime'])
            historical_funding_rate.extend(temp)
        return historical_funding_rate

    async def back_tracking(self):
        """补录最近3个月资金费率
        """
        begin = time.monotonic()
        Record = record.Record('Funding')
        instrumentsID = await self.get_instruments_ID()
        found, inserted = 0, 0

        task_list = []
        for m in instrumentsID:
            task_list.append(self.funding_history(m))
        # API results
        api_funding_list = await asyncio.gather(*task_list)
        for api_funding in api_funding_list:
            found += len(api_funding)
            instId = api_funding[0]['instId']
            instrument = instId[:instId.find('-')]
            pipeline = [{'$match': {'instrument': instrument}}]
            results = Record.mycol.aggregate(pipeline)
            db_funding = []
            # Results in DB
            for m in results:
                db_funding.append(m)
            # print(db_funding)
            for m in api_funding:
                timestamp = utcfrommillisecs(m['fundingTime'])
                mydict = {'instrument': instrument, 'timestamp': timestamp, 'funding': float(m['realizedRate'])}
                # Check for duplicate
                for n in db_funding:
                    if n['timestamp'] == timestamp:
                        break
                else:
                    Record.mycol.insert_one(mydict)
                    inserted += 1
        print("Found: {}, Inserted: {}".format(found, inserted))
        end = time.monotonic()
        print("back_tracking takes %f s" % (end - begin))

    async def show_profitable_rate(self, days=7):
        """显示收益最高十个币种资金费
        """
        funding_rate_list = await self.get_rate(days)
        funding_rate_list.sort(key=lambda x: x['funding_rate'], reverse=True)
        funding_rate_list = funding_rate_list[:20]
        funding_rate_list = [n['instrument'] for n in await trading_data.Stat().profitability(funding_rate_list, days)]
        await self.show_selected_rate(funding_rate_list)

    async def show_selected_rate(self, coinlist: List[str]):
        """显示列表币种当前资金费
        """
        task_list = []
        for n in coinlist:
            task_list.append(self.publicAPI.get_funding_time(instId=n + '-USDT-SWAP'))
        gather_result = await asyncio.gather(*task_list)

        funding_rate_list = []
        for funding_time in gather_result:
            instrument = funding_time['instId'][:funding_time['instId'].find('-')]
            if funding_time['fundingRate']:
                current_rate = float(funding_time['fundingRate'])
            else:
                current_rate = 0.
            if funding_time['nextFundingRate']:
                estimated_rate = float(funding_time['nextFundingRate'])
            else:
                estimated_rate = 0.
            funding_rate_list.append(
                {'instrument': instrument, 'current_rate': current_rate, 'estimated_rate': estimated_rate})

        funding_rate_list.sort(key=lambda x: x['current_rate'], reverse=True)
        # pprint(funding_rate_list)
        fprint(coin_current_next)
        for n in funding_rate_list:
            instrumentID = n['instrument']
            current_rate = n['current_rate']
            estimated_rate = n['estimated_rate']
            fprint('{:8s}{:9.3%}{:11.3%}'.format(instrumentID, current_rate, estimated_rate))
