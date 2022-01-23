from typing import List
import okex.public as public
import statistics
import record
import trading_data
from utils import *
from lang import *


# @debug_timer
class FundingRate:

    @property
    def __name__(self):
        return 'FundingRate'

    def __init__(self):
        self.publicAPI = public.PublicAPI()

    def __del__(self):
        self.publicAPI.__del__()

    async def get_instruments_ID(self):
        """获取合约币种列表

        :rtype: List[str]
        """
        return [n['instId'] for n in await self.publicAPI.get_instruments('SWAP') if n['instId'].find('USDT') != -1]

    @call_coroutine
    async def current(self, instrument_id=''):
        """当期资金费

        :param instrument_id: 币种合约
        """
        current_rate = (await self.publicAPI.get_funding_time(instId=instrument_id))['fundingRate']
        return float(current_rate) if current_rate else 0.

    async def next(self, instrument_id=''):
        """预测资金费

        :param instrument_id: 币种合约
        """
        next_rate = (await self.publicAPI.get_funding_time(instId=instrument_id))['nextFundingRate']
        return float(next_rate) if next_rate else 0.

    async def current_next(self, instrument_id=''):
        """当期和预测资金费

        :param instrument_id: 币种合约
        """
        funding_rate = await self.publicAPI.get_funding_time(instId=instrument_id)
        current_rate = float(m) if (m := funding_rate['fundingRate']) else 0.
        next_rate = float(m) if (m := funding_rate['nextFundingRate']) else 0.
        return current_rate, next_rate

    @call_coroutine
    # @debug_timer
    async def show_current_rate(self):
        """显示当前资金费
        """
        task_list = [self.publicAPI.get_funding_time(instId=m) for m in await self.get_instruments_ID()]
        funding_rate_list = []
        for funding_time in await asyncio.gather(*task_list):
            instId = funding_time['instId']
            current_rate = float(m) if (m := funding_time['fundingRate']) else 0.
            estimated_rate = float(m) if (m := funding_time['nextFundingRate']) else 0.
            funding_rate_list.append(
                dict(instrument_id=instId, current_rate=current_rate, estimated_rate=estimated_rate))
        funding_rate_list.sort(key=lambda x: x['current_rate'], reverse=True)
        fprint(coin_current_next)
        for n in funding_rate_list:
            instrumentID = n['instrument_id'][:n['instrument_id'].find('-')]
            current_rate = n['current_rate']
            estimated_rate = n['estimated_rate']
            fprint(f'{instrumentID:8s}{current_rate:9.3%}{estimated_rate:11.3%}')
        # 50 s without asyncio
        # 1.6 s with asyncio

    @call_coroutine
    # @debug_timer
    async def show_nday_rate(self, days: int):
        """显示最近n天平均资金费

        :param days: 天数
        """
        assert isinstance(days, int) and days > 0
        limit = f'{days * 3:d}'
        task_list = [self.publicAPI.get_historical_funding_rate(instId=m, limit=limit) for m in
                     await self.get_instruments_ID()]
        funding_rate_list = []
        for historical_funding_rate in await asyncio.gather(*task_list):
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
                    dict(instrument_id=instId, funding_rate=statistics.mean(realized_rate[:days * 3])))

        funding_rate_list.sort(key=lambda x: x['funding_rate'], reverse=True)
        for n in funding_rate_list:
            instrumentID = n['instrument_id'][:n['instrument_id'].find('-')]
            fprint(f"{instrumentID:8s}{n['funding_rate']:8.3%}")
        # 1.4 s with asyncio

    # @debug_timer
    async def print_30day_rate(self):
        """输出最近30天平均资金费到文件
        """
        task_list = [self.publicAPI.get_historical_funding_rate(instId=m, limit='90') for m in
                     await self.get_instruments_ID()]
        funding_rate_list = []
        for historical_funding_rate in await asyncio.gather(*task_list):
            instId = historical_funding_rate[0]['instId']
            # pprint(historical_funding_rate)
            # 永续合约上线不一定有30天
            if len(historical_funding_rate) < 21:
                # print(m + "上线不到7天。")
                pass
            elif len(historical_funding_rate) < 90:
                # print(m + "上线不到30天。")
                realized_rate = [float(n['realizedRate']) for n in historical_funding_rate]
                funding_rate_list.append(
                    {'instrument_id': instId, '7day_funding_rate': statistics.mean(realized_rate[:21]),
                     '30day_funding_rate': 0})
            else:
                realized_rate = [float(n['realizedRate']) for n in historical_funding_rate]
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
            funding_rate_file.write(f"{n['7day_funding_rate']:7.3%}")
            funding_rate_file.write(f"{n['30day_funding_rate']:8.3%}\n")
        funding_rate_file.close()

    async def get_rate(self, days=7):
        """返回最近资金费列表

        :param days: 最近几天
        :rtype: List[dict]
        """
        assert isinstance(days, int) and days > 0
        limit = str(days * 3)
        task_list = [self.publicAPI.get_historical_funding_rate(instId=m, limit=limit) for m in
                     await self.get_instruments_ID()]
        funding_rate_list = []
        for historical_funding_rate in await asyncio.gather(*task_list):
            instId = historical_funding_rate[0]['instId']
            if len(historical_funding_rate) < days * 3:
                pass
            else:
                realized_rate = [float(n['realizedRate']) for n in historical_funding_rate]
                instrumentID = instId[:instId.find('-')]
                funding_rate_list.append(dict(instrument=instrumentID, funding_rate=statistics.mean(realized_rate)))
        return funding_rate_list

    async def funding_history(self, instId):
        """下载最近3个月资金费率
        """
        temp = historical_funding_rate = await self.publicAPI.get_historical_funding_rate(instId=instId)
        while len(temp) == 100:
            temp = await self.publicAPI.get_historical_funding_rate(instId=instId, after=temp[99]['fundingTime'])
            historical_funding_rate.extend(temp)
        return historical_funding_rate

    @call_coroutine
    @debug_timer
    async def back_tracking(self):
        """补录最近3个月资金费率
        """
        Record = record.Record('Funding')
        found = inserted = 0
        task_list = [self.funding_history(m) for m in await self.get_instruments_ID()]
        # API results
        for api_funding in await asyncio.gather(*task_list):
            found += len(api_funding)
            instId = api_funding[0]['instId']
            instrument = instId[:instId.find('-')]
            pipeline = [{'$match': {'instrument': instrument}}]
            # Results in DB
            db_funding = [m for m in Record.mycol.aggregate(pipeline)]
            # print(db_funding)
            for m in api_funding:
                timestamp = utcfrommillisecs(m['fundingTime'])
                mydict = dict(instrument=instrument, timestamp=timestamp, funding=float(m['realizedRate']))
                # Check for duplicate
                for n in db_funding:
                    if n['funding'] == float(m['realizedRate']):
                        if n['timestamp'] == timestamp:
                            break
                else:
                    Record.mycol.insert_one(mydict)
                    inserted += 1
        print(f"Found: {found}, Inserted: {inserted}")

    @call_coroutine
    # @debug_timer
    async def show_profitable_rate(self, days=7):
        """显示收益最高十个币种资金费
        """
        assert isinstance(days, int) and days > 0
        funding_rate_list = await self.get_rate(days)
        funding_rate_list.sort(key=lambda x: x['funding_rate'], reverse=True)
        funding_rate_list = funding_rate_list[:20]
        funding_rate_list = [n['instrument'] for n in await trading_data.Stat().profitability(funding_rate_list, days)]
        await self.show_selected_rate(funding_rate_list)

    @call_coroutine
    async def show_selected_rate(self, coinlist):
        """显示列表币种当前资金费
        """
        task_list = [self.publicAPI.get_funding_time(instId=n + '-USDT-SWAP') for n in coinlist]
        funding_rate_list = []
        for funding_time in await asyncio.gather(*task_list):
            instrument = funding_time['instId'][:funding_time['instId'].find('-')]
            current_rate = float(n) if (n := funding_time['fundingRate']) else 0.
            estimated_rate = float(n) if (n := funding_time['nextFundingRate']) else 0.
            funding_rate_list.append(
                dict(instrument=instrument, current_rate=current_rate, estimated_rate=estimated_rate))

        funding_rate_list.sort(key=lambda x: x['current_rate'], reverse=True)
        fprint(coin_current_next)
        for n in funding_rate_list:
            fprint(f"{n['instrument']:8s}{n['current_rate']:9.3%}{n['estimated_rate']:11.3%}")
