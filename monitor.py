import funding_rate
import close_position
import open_position
from okex_api import *
from utils import *


# 监控一个币种，如果当期资金费+预测资金费小于重新开仓成本（开仓期现差价-平仓期现差价-手续费），进行平仓。
# 如果合约仓位到达下级杠杆，进行减仓。如果合约仓位到达上级杠杆，进行加仓。
# 如果距离下期资金费3小时以上，（开仓期现差价-平仓期现差价-手续费）>0.2%，进行套利。
class Monitor(OKExAPI):
    """监控功能类
    """

    @property
    def __name__(self):
        return 'Monitor'

    def __init__(self, coin=None, accountid=3):
        super().__init__(coin=coin, accountid=accountid)

    async def apr(self, days=0):
        """最近年利率

        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        Stat, holding = await gather(trading_data.Stat(self.coin), self.swap_holding())
        margin = holding['margin']
        upl = holding['upl']
        last = holding['last']
        position = - holding['pos'] * float(self.swap_info['ctVal'])
        size = position * last + margin + upl

        if size > 10:
            if days == 0:
                open_time = Stat.open_time(self.accountid)
                delta = (datetime.utcnow() - open_time).total_seconds()
                funding = Stat.history_funding(self.accountid)
                cost = Stat.history_cost(self.accountid)
                apr = (funding + cost) / size / delta * 86400 * 365
            else:
                funding = Stat.history_funding(self.accountid, days)
                cost = Stat.history_cost(self.accountid, days)
                apr = (funding + cost) / size / days * 365
        else:
            apr = 0.
        return apr

    async def record_funding(self):
        """记录最近一次资金费
        """
        # /api/v5/account/bills 限速：5次/s
        sem = self.psem if self.psem else multiprocessing.Semaphore(1)
        with sem:
            Ledger = record.Record('Ledger')
            ledger = await self.accountAPI.get_ledger(instType='SWAP', ccy='USDT', type='8')
            if self.psem: await asyncio.sleep(1)
        realized_rate = 0.
        for item in ledger:
            if item['instId'] == self.swap_ID:
                realized_rate = float(item['pnl'])
                timestamp = datetime.utcfromtimestamp(float(item['ts']) / 1000)
                mydict = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='资金费',
                              funding=realized_rate)
                Ledger.mycol.find_one_and_replace(mydict, mydict, upsert=True)
                break
        fprint(lang.received_funding.format(self.coin, realized_rate))

    @call_coroutine
    async def position_exist(self, swap_ID=None):
        """判断是否有仓位
        """
        if not swap_ID: swap_ID = self.swap_ID
        if await self.swap_position(swap_ID) == 0:
            # fprint(lang.nonexistent_position.format(swap_ID))
            return False
        else:
            result = record.Record('Ledger').find_last(dict(account=self.accountid, instrument=self.coin))
            if result and result['title'] == '平仓':
                fprint(lang.has_closed.format(self.swap_ID))
                return False
        return True

    @run_with_cancel
    async def watch(self):
        """监控仓位，自动加仓、减仓
        """
        if not await self.position_exist():
            fprint(lang.nonexistent_position.format(self.swap_ID))
            return

        fundingRate = funding_rate.FundingRate()
        addPosition: open_position.AddPosition
        reducePosition: close_position.ReducePosition
        Stat: trading_data.Stat
        addPosition, reducePosition, Stat = await gather(open_position.AddPosition(self.coin, self.accountid),
                                                         close_position.ReducePosition(self.coin, self.accountid),
                                                         trading_data.Stat(self.coin))
        Ledger = record.Record('Ledger')
        # OP = record.Record('OP')

        # Obtain leverage
        portfolio = record.Record('Portfolio').mycol.find_one(dict(account=self.accountid, instrument=self.coin))
        leverage = portfolio['leverage']
        if 'size' not in portfolio:
            portfolio = await self.update_portfolio()
        size = portfolio['size']
        fprint(lang.start_monitoring.format(self.coin, size, leverage))

        # Get trade fees
        spot_trade_fee, swap_trade_fee, liquidation_price = await gather(
            self.accountAPI.get_trade_fee(instType='SPOT', instId=self.spot_ID),
            self.accountAPI.get_trade_fee(instType='SWAP', uly=self.spot_ID),
            self.liquidation_price())
        spot_trade_fee = float(spot_trade_fee['taker'])
        swap_trade_fee = float(swap_trade_fee['taker'])
        trade_fee = swap_trade_fee + spot_trade_fee

        updated = False
        task_started = False
        time_to_accelerate = None
        accelerated = False
        adding = False
        add_task = None
        usdt_size = 0
        reducing = False
        reduce_task = None
        margin_reducible = True
        self.exitFlag = False

        while not self.exitFlag:
            begin = timestamp = datetime.utcnow()
            # Update price every 10s.
            swap_ticker = await self.publicAPI.get_specific_ticker(self.swap_ID)
            last = float(swap_ticker['last'])

            # Update funding rates and liquidation price every hour.
            if not updated and timestamp.minute == 1:
                (current_rate, next_rate), liquidation_price = await gather(fundingRate.current_next(self.swap_ID),
                                                                            self.liquidation_price())
                # Swap position is closed.
                if not liquidation_price:
                    fprint(lang.has_closed.format(self.swap_ID))
                    mydict = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='平仓')
                    Ledger.mycol.insert_one(mydict)
                    record.Record('Portfolio').mycol.delete_one(dict(account=self.accountid, instrument=self.coin))
                    return

                assert (recent := Stat.recent_open_stat()), lang.fetch_ticker_first
                open_pd = recent['avg'] + recent['std']
                recent = Stat.recent_close_stat()
                close_pd = recent['avg'] - recent['std']
                cost = open_pd - close_pd + 2 * trade_fee
                # Expected funding rates too low.
                if (timestamp.hour + 4) % 8 == 0 and current_rate + next_rate < cost:
                    fprint(lang.coin_current_next)
                    fprint(f'{self.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
                    fprint(lang.cost_to_close.format(cost))
                    fprint(lang.closing.format(self.coin))
                    await reducePosition.close(price_diff=close_pd)
                    return

                if timestamp.hour % 8 == 0:
                    await self.record_funding()
                    fprint(lang.coin_current_next)
                    fprint(f'{self.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
                updated = True
            elif updated and timestamp.minute == 2:
                updated = False

            # 线程未创建
            if not task_started:
                # 接近强平价，现货减仓
                if liquidation_price < last * (1 + 1 / (leverage + 1)):
                    # 等待上一操作完成
                    # if OP.find_last({'account': self.accountid, 'instrument': self.coin}):
                    #     timestamp = datetime.utcnow()
                    #     delta = (timestamp - begin).total_seconds()
                    #     if delta < 10:
                    #         await asyncio.sleep(10 - delta)
                    #     continue
                    if not await addPosition.is_hedged():
                        spot, swap = await gather(self.spot_position(), self.swap_position())
                        fprint(lang.hedge_fail.format(self.coin, spot, swap))
                        exit()
                    fprint(lang.approaching_liquidation)
                    mydict = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='自动减仓')
                    Ledger.mycol.insert_one(mydict)

                    # 期现差价控制在2个标准差
                    assert (recent := Stat.recent_close_stat()), lang.fetch_ticker_first
                    close_pd = recent['avg'] - 2 * recent['std']

                    swap_position = await self.swap_position()
                    target_size = swap_position / (leverage + 1) ** 2

                    reduce_task = create_task(reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                    task_started = True
                    reducing = True
                    time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                # 保证金过多，现货加仓
                if margin_reducible and liquidation_price > last * (1 + 1 / (leverage - 1)):
                    # 等待上一操作完成
                    # if OP.find_last({'account': self.accountid, 'instrument': self.coin}):
                    #     timestamp = datetime.utcnow()
                    #     delta = (timestamp - begin).total_seconds()
                    #     if delta < 10:
                    #         await asyncio.sleep(10 - delta)
                    #     continue
                    if not await addPosition.is_hedged():
                        spot, swap = await gather(self.spot_position(), self.swap_position())
                        fprint(lang.hedge_fail.format(self.coin, spot, swap))
                        exit()
                    fprint(lang.too_much_margin)
                    mydict = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='自动加仓')
                    Ledger.mycol.insert_one(mydict)

                    # 期现差价控制在2个标准差
                    assert (recent := Stat.recent_open_stat()), lang.fetch_ticker_first
                    open_pd = recent['avg'] + 2 * recent['std']

                    # swap_position = await self.swap_position()
                    # target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)
                    usdt_size = await addPosition.adjust_swap_lever(leverage)
                    if usdt_size:
                        add_task = create_task(addPosition.add(usdt_size=usdt_size, price_diff=open_pd))
                        task_started = True
                        adding = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                    else:
                        # Liquidation price can't be less than open price.
                        fprint(lang.no_margin_reduce)
                        margin_reducible = False
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

                        assert (recent := Stat.recent_close_stat(1)), lang.fetch_ticker_first
                        close_pd = recent['avg'] - 1.5 * recent['std']

                        liquidation_price, swap_position = await gather(self.liquidation_price(), self.swap_position())
                        target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                        reduce_task = create_task(reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                        reducing = True
                        accelerated = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                    if timestamp > time_to_accelerate:
                        reducePosition.exitFlag = True
                        while not reduce_task.done():
                            await asyncio.sleep(1)

                        assert (recent := Stat.recent_close_stat(2)), lang.fetch_ticker_first
                        close_pd = recent['avg'] - 2 * recent['std']

                        liquidation_price, swap_position = await gather(self.liquidation_price(), self.swap_position())
                        target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                        reduce_task = create_task(reducePosition.reduce(target_size=target_size, price_diff=close_pd))
                        reducing = True
                        time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                elif adding and not add_task.done():
                    if timestamp > time_to_accelerate:
                        addPosition.exitFlag = True
                        while not add_task.done():
                            await asyncio.sleep(1)

                        assert (recent := Stat.recent_open_stat(2)), lang.fetch_ticker_first
                        open_pd = recent['avg'] + 2 * recent['std']

                        # liquidation_price = await self.liquidation_price()
                        # swap_position = await self.swap_position()
                        # target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)
                        if (usdt_size := usdt_size - add_task.result()) > 0:
                            add_task = create_task(addPosition.add(usdt_size=usdt_size, price_diff=open_pd))
                            adding = True
                            time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                else:
                    liquidation_price = await self.liquidation_price()
                    adding = reducing = task_started = False
            delta = (datetime.utcnow() - begin).total_seconds()
            if delta < 10:
                await asyncio.sleep(10 - delta)
