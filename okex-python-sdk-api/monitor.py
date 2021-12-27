from okex_api import *
import funding_rate
import open_position
import close_position
import trading_data
from datetime import datetime, timedelta
import record
from log import fprint
import asyncio


# 监控一个币种，如果当期资金费+预测资金费小于重新开仓成本（开仓期现差价-平仓期现差价-手续费），进行平仓。
# 如果合约仓位到达下级杠杆，进行减仓。如果合约仓位到达上级杠杆，进行加仓。
# 如果距离下期资金费3小时以上，（开仓期现差价-平仓期现差价-手续费）>0.2%，进行套利。
class Monitor(OKExAPI):
    """监控功能类
    """

    def __init__(self, coin=None, accountid=3):
        OKExAPI.__init__(self, coin, accountid)

    async def liquidation_price(self):
        """获取强平价
        """
        holding = await self.swap_holding()
        if holding and holding['liqPx']:
            return float(holding['liqPx'])
        else:
            return 0.

    async def apr(self, days=0):
        """最近年利率

        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Stat = trading_data.Stat(self.coin)
        swap_margin, spot_position, ticker = await gather(self.swap_balance(), self.spot_position(),
                                                          self.publicAPI.get_specific_ticker(self.spot_ID))
        last = float(ticker['last'])
        holding = swap_margin + last * spot_position
        timestamp = datetime.utcnow()

        if holding > 10:
            if days == 0:
                open_time = Stat.open_time(self.accountid)
                delta = timestamp.__sub__(open_time).total_seconds()
                funding = Stat.history_funding(self.accountid)
                cost = Stat.history_cost(self.accountid)
                apr = (funding + cost) / holding / delta * 86400 * 365
            else:
                funding = Stat.history_funding(self.accountid, days)
                cost = Stat.history_cost(self.accountid, days)
                apr = (funding + cost) / holding / days * 365
        else:
            apr = 0.
        return apr

    async def apy(self, days=0):
        """最近年化

        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        import math
        apr = await self.apr(days)
        return math.exp(apr) - 1

    async def back_tracking(self, sem):
        """补录最近七天资金费
        """
        async with sem:
            Ledger = record.Record('Ledger')
            pipeline = [{'$match': {'account': self.accountid, 'instrument': self.coin, 'title': "资金费"}}]
            results = Ledger.mycol.aggregate(pipeline)
            db_ledger = []
            # Results in DB
            for n in results:
                db_ledger.append(n)
            temp = await self.accountAPI.get_ledger(instType='SWAP', ccy='USDT', type='8')
            await asyncio.sleep(1)
            api_ledger = temp
            inserted = 0
            while len(temp) == 100:
                temp = await self.accountAPI.get_ledger(instType='SWAP', ccy='USDT', type='8', after=temp[99]['billId'])
                await asyncio.sleep(1)
                api_ledger.extend(temp)
            # API results
            for item in api_ledger:
                if item['instId'] == self.swap_ID:
                    realized_rate = float(item['pnl'])
                    timestamp = datetime.utcfromtimestamp(float(item['ts']) / 1000)
                    mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp,
                              'title': "资金费", 'funding': realized_rate}
                    # 查重
                    for n in db_ledger:
                        if n['timestamp'] == timestamp:
                            break
                    else:
                        Ledger.mycol.insert_one(mydict)
                        inserted += 1
            fprint(lang.back_track_funding.format(self.coin, inserted))

    async def record_funding(self):
        """记录最近一次资金费
        """
        Ledger = record.Record('Ledger')
        ledger = await self.accountAPI.get_ledger(instType='SWAP', ccy='USDT', type='8')
        realized_rate = 0
        for item in ledger:
            if item['instId'] == self.swap_ID:
                realized_rate = float(item['pnl'])
                timestamp = datetime.utcfromtimestamp(float(item['ts']) / 1000)
                mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "资金费",
                          'funding': realized_rate}
                Ledger.mycol.insert_one(mydict)
                break
        fprint(lang.received_funding.format(self.coin, realized_rate))

    async def position_exist(self, swap_ID=None):
        """判断是否有仓位
        """
        if not swap_ID:
            swap_ID = self.swap_ID
        if await self.swap_position(swap_ID) == 0:
            # fprint(lang.nonexistent_position.format(swap_ID))
            return False
        else:
            result = record.Record('Ledger').find_last({'account': self.accountid, 'instrument': self.coin})
            if result and result['title'] == '平仓':
                fprint(lang.has_closed.format(self.swap_ID))
                return False
        return True

    async def watch(self):
        """监控仓位，自动加仓、减仓
        """
        fprint(lang.start_monitoring, self.coin)
        if not await self.position_exist():
            exit()

        fundingRate = funding_rate.FundingRate()
        addPosition: open_position.AddPosition
        reducePosition: close_position.ReducePosition
        Stat: trading_data.Stat
        addPosition, reducePosition, Stat = await gather(open_position.AddPosition(self.coin, self.accountid),
                                                         close_position.ReducePosition(self.coin, self.accountid),
                                                         trading_data.Stat(self.coin))
        Ledger = record.Record('Ledger')
        OP = record.Record('OP')

        # 计算手续费
        spot_trade_fee, swap_trade_fee, leverage, liquidation_price = await gather(
            self.accountAPI.get_trade_fee(instType='SPOT', instId=self.spot_ID),
            self.accountAPI.get_trade_fee(instType='SWAP', uly=self.spot_ID),
            self.get_lever(),
            self.liquidation_price())
        spot_trade_fee = float(spot_trade_fee['taker'])
        swap_trade_fee = float(swap_trade_fee['taker'])
        trade_fee = swap_trade_fee + spot_trade_fee

        task_started = False
        time_to_accelerate = None
        accelerated = False
        adding = False
        reducing = False
        retry = 0

        while True:
            timestamp = datetime.utcnow()
            begin = timestamp
            swap_ticker = await self.publicAPI.get_specific_ticker(self.swap_ID)
            last = float(swap_ticker['last'])

            # 每小时更新一次资金费，强平价
            if timestamp.minute == 1:
                if timestamp.second < 10:
                    (current_rate, next_rate), liquidation_price = await gather(fundingRate.current_next(self.swap_ID),
                                                                                self.liquidation_price())
                    if liquidation_price == 0:
                        exit()

                    recent = Stat.recent_open_stat()
                    if recent:
                        open_pd = recent['avg'] + recent['std']
                    else:
                        fprint(lang.fetch_ticker_first)
                        break
                    recent = Stat.recent_close_stat()
                    close_pd = recent['avg'] - recent['std']

                    cost = open_pd - close_pd + 2 * trade_fee
                    if (timestamp.hour + 4) % 8 == 0 and current_rate + next_rate < cost:
                        fprint(lang.coin_current_next)
                        fprint('{:6s}{:9.3%}{:11.3%}'.format(self.coin, current_rate, next_rate))
                        fprint(lang.cost_to_close.format(cost))
                        fprint(lang.closing.format(self.coin))
                        await reducePosition.close(price_diff=close_pd)
                        break

                    if timestamp.hour % 8 == 0:
                        await self.record_funding()
                        fprint(lang.coin_current_next)
                        fprint('{:6s}{:9.3%}{:11.3%}'.format(self.coin, current_rate, next_rate))

            # 线程未创建
            if not task_started:
                # 接近强平价，现货减仓
                if liquidation_price < last * (1 + 1 / (leverage + 1)):
                    # 等待上一操作完成
                    if OP.find_last({'account': self.accountid, 'instrument': self.coin}):
                        timestamp = datetime.utcnow()
                        delta = timestamp.__sub__(begin).total_seconds()
                        if delta < 10:
                            await asyncio.sleep(10 - delta)
                        continue
                    if not await addPosition.is_hedged():
                        fprint(self.coin, lang.hedge_fail)
                        exit()
                    fprint(lang.approaching_liquidation)
                    mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp,
                              'title': "自动减仓"}
                    Ledger.mycol.insert_one(mydict)
                    swap_position = await self.swap_position()
                    target_size = swap_position / (leverage + 1) ** 2

                    # 期现差价控制在1.5个标准差
                    recent = Stat.recent_close_stat()
                    if recent:
                        close_pd = recent['avg'] - 1.5 * recent['std']
                    else:
                        fprint(lang.fetch_ticker_first)
                        break

                    reduce_task = asyncio.create_task(
                        reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                    task_started = True
                    reducing = True
                    time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                # 保证金过多，现货加仓
                if liquidation_price > last * (1 + 1 / (leverage - 1)):
                    # 等待上一操作完成
                    if OP.find_last({'account': self.accountid, 'instrument': self.coin}):
                        timestamp = datetime.utcnow()
                        delta = timestamp.__sub__(begin).total_seconds()
                        if delta < 10:
                            await asyncio.sleep(10 - delta)
                        continue
                    if not addPosition.is_hedged():
                        fprint(self.coin, lang.hedge_fail)
                        exit()
                    fprint(lang.too_much_margin)
                    mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp,
                              'title': "自动加仓"}
                    Ledger.mycol.insert_one(mydict)
                    swap_position = await self.swap_position()
                    target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)

                    # 期现差价控制在2个标准差
                    recent = Stat.recent_open_stat()
                    if recent:
                        open_pd = recent['avg'] + 2 * recent['std']
                    else:
                        fprint(lang.fetch_ticker_first)
                        break

                    if await self.reduce_margin(target_size * last):
                        add_task = asyncio.create_task(
                            addPosition.add(target_size=target_size, leverage=leverage, price_diff=open_pd))
                        task_started = True
                        adding = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                    else:
                        retry += 1
                        if retry == 3:
                            print(lang.reach_max_retry)
                            exit()
            # 线程已运行
            else:
                # 如果减仓时间过长，加速减仓
                if reducing and not reduce_task.done():
                    # 迫近下下级杠杆
                    if liquidation_price < last * (1 + 1 / (leverage + 2)) and not accelerated:
                        # 已加速就不另开线程
                        reducePosition.exitFlag = True
                        while not reduce_task.done():
                            await asyncio.sleep(1)

                        liquidation_price = await self.liquidation_price()
                        swap_position = await self.swap_position()
                        target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                        recent = Stat.recent_close_stat(1)
                        if recent:
                            close_pd = recent['avg'] - 1.5 * recent['std']
                        else:
                            fprint(lang.fetch_ticker_first)
                            break
                        reduce_task = asyncio.create_task(
                            reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                        reducePosition.exitFlag = False
                        reducing = True
                        accelerated = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                    if timestamp > time_to_accelerate:
                        reducePosition.exitFlag = True
                        while not reduce_task.done():
                            await asyncio.sleep(1)

                        liquidation_price = await self.liquidation_price()
                        swap_position = await self.swap_position()
                        target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                        recent = Stat.recent_close_stat(2)
                        if recent:
                            close_pd = recent['avg'] - 2 * recent['std']
                        else:
                            fprint(lang.fetch_ticker_first)
                            break
                        reduce_task = asyncio.create_task(
                            reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                        reducePosition.exitFlag = False
                        reducing = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                elif adding and not add_task.done():
                    if timestamp > time_to_accelerate:
                        addPosition.exitFlag = True
                        while not add_task.done():
                            await asyncio.sleep(1)

                        liquidation_price = await self.liquidation_price()
                        swap_position = await self.swap_position()
                        target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)
                        recent = Stat.recent_open_stat(2)
                        if recent:
                            open_pd = recent['avg'] + 2 * recent['std']
                        else:
                            fprint(lang.fetch_ticker_first)
                            break
                        add_task = asyncio.create_task(
                            addPosition.add(target_size=target_size, leverage=leverage, price_diff=open_pd))
                        addPosition.exitFlag = False
                        adding = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                else:
                    liquidation_price = await self.liquidation_price()
                    if adding:
                        adding = False
                    if reducing:
                        reducing = False
                    task_started = False
            timestamp = datetime.utcnow()
            delta = timestamp.__sub__(begin).total_seconds()
            if delta < 10:
                await asyncio.sleep(10 - delta)
