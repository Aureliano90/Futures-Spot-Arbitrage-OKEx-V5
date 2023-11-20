from src.close_position import ReducePosition
from src.funding_rate import FundingRate
from src.open_position import AddPosition
from src.okex_api import *
from src.trading_data import Stat


# 监控一个币种，如果当期资金费+预测资金费小于重新开仓成本（开仓期现差价-平仓期现差价-手续费），进行平仓。
# 如果合约仓位到达下级杠杆，进行减仓。如果合约仓位到达上级杠杆，进行加仓。
# 如果距离下期资金费3小时以上，（开仓期现差价-平仓期现差价-手续费）>0.2%，进行套利。
class Monitor(OKExAPI):
    """监控功能类
    """

    def __init__(self, coin=None, account=3):
        super().__init__(coin=coin, account=account)

    async def apr(self, days=0):
        """最近年利率

        :param days: 最近几天，默认开仓算起
        :rtype: float
        """
        stat = Stat(self.coin)
        holding = await self.swap_holding()
        margin = holding['margin']
        upl = holding['upl']
        last = holding['last']
        position = - holding['pos'] * float(self.swap_info['ctVal'])
        size = position * last + margin + upl

        if size > 10:
            if days == 0:
                open_time = stat.open_time(self.account)
                delta = (datetime.utcnow() - open_time).total_seconds()
                funding = stat.history_funding(self.account)
                cost = stat.history_cost(self.account)
                apr = (funding + cost) / size / delta * 86400 * 365
            else:
                funding = stat.history_funding(self.account, days)
                cost = stat.history_cost(self.account, days)
                apr = (funding + cost) / size / days * 365
        else:
            apr = 0.
        return apr

    async def record_funding(self):
        """记录最近一次资金费
        """
        Ledger = Record('Ledger')
        ledger = await self.accountAPI.get_ledger(instType='SWAP', ccy='USDT', type='8')
        realized_rate = 0.
        for item in ledger:
            if item['instId'] == self.swap_ID:
                realized_rate = float(item['pnl'])
                timestamp = datetime.utcfromtimestamp(float(item['ts']) / 1000)
                mydict = dict(account=self.account, instrument=self.coin, timestamp=timestamp, title='资金费',
                              funding=realized_rate)
                Ledger.mycol.find_one_and_replace(mydict, mydict, upsert=True)
                break
        fprint(lang.received_funding.format(self.coin, realized_rate))

    async def position_exist(self, swap_ID=None):
        """判断是否有仓位
        """
        if not swap_ID: swap_ID = self.swap_ID
        if await self.swap_position(swap_ID) == 0:
            # fprint(lang.nonexistent_position.format(swap_ID))
            return False
        else:
            result = Record('Ledger').find_last(dict(account=self.account, instrument=self.coin))
            if result and result['title'] == '平仓':
                fprint(lang.has_closed.format(self.swap_ID))
                return False
        return True

    @manager.submit
    async def watch(self):
        """监控仓位，自动加仓、减仓
        """
        if not await self.position_exist():
            fprint(lang.nonexistent_position.format(self.swap_ID))
            return

        fundingRate = FundingRate(self.account)
        addPosition: Optional[AddPosition] = None
        reducePosition: Optional[ReducePosition] = None
        stat = Stat(self.coin)
        Ledger = Record('Ledger')
        # OP = Record('OP')

        # Obtain leverage
        portfolio = Record('Portfolio').mycol.find_one(dict(account=self.account, instrument=self.coin))
        assert portfolio is not None, f"{self.coin}"
        leverage = portfolio['leverage']
        if 'size' not in portfolio:
            portfolio = await self.update_portfolio()
        size = portfolio['size']
        fprint(lang.start_monitoring.format(self.coin, size, leverage))

        # Get trade fees
        spot_trade_fee, swap_trade_fee, liquidation_price = await gather(self.spot_trade_fee(), self.swap_trade_fee(),
                                                                         self.liquidation_price())
        trade_fee = spot_trade_fee + swap_trade_fee

        task_started = False
        time_to_accelerate = None
        accelerated = False
        adding = reducing = False
        add_task: Any = None
        reduce_task = add_task
        usdt_size = 0
        margin_reducible = True
        self.exit_flag = False

        ten_seconds = Looper(interval=10)
        now = datetime.utcnow()
        one_hour = UTCLooper(datetime(now.year, now.month, now.day, (now.hour + 1) % 24), interval=timedelta(hours=1))
        funding_time = FundingTime()

        async for event in EventChain(ten_seconds, one_hour, funding_time):
            if self.exit_flag:
                break
            try:
                timestamp = datetime.utcnow()
                # Record funding fees
                if event == funding_time:
                    (current_rate, next_rate), _ = await gather(fundingRate.current_next(self.swap_ID),
                                                                self.record_funding())
                    fprint(lang.coin_current_next)
                    fprint(f'{self.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
                # Update funding rates and liquidation price every hour.
                elif event == one_hour:
                    (current_rate, next_rate), liquidation_price = await gather(fundingRate.current_next(self.swap_ID),
                                                                                self.liquidation_price())
                    # Swap position is closed.
                    if not liquidation_price:
                        fprint(lang.has_closed.format(self.swap_ID))
                        mydict = dict(account=self.account, instrument=self.coin, timestamp=timestamp, title='平仓')
                        Ledger.mycol.insert_one(mydict)
                        Record('Portfolio').mycol.delete_one(dict(account=self.account, instrument=self.coin))
                        return

                    assert (recent := stat.recent_open_stat()), lang.fetch_ticker_first
                    open_pd = recent['avg'] + recent['std']
                    recent = stat.recent_close_stat()
                    close_pd = recent['avg'] - recent['std']
                    cost = open_pd - close_pd + 2 * trade_fee
                    # Expected funding rates too low.
                    if (timestamp.hour + 4) % 8 == 0 and current_rate + next_rate < cost:
                        fprint(lang.coin_current_next)
                        fprint(f'{self.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
                        fprint(lang.cost_to_close.format(cost))
                        fprint(lang.closing.format(self.coin))
                        if not reducePosition:
                            reducePosition = await ReducePosition(self.coin, self.account)
                        await reducePosition.close(price_diff=close_pd)
                        return
                # Update price every 10s.
                elif event == ten_seconds:
                    swap_ticker = await self.publicAPI.get_specific_ticker(self.swap_ID)
                    last = float(swap_ticker['last'])
                    # 线程未创建
                    if not task_started:
                        # 接近强平价，现货减仓
                        if liquidation_price < last * (1 + 1 / (leverage + 1)):
                            if not await self.is_hedged():
                                spot, swap = await gather(self.spot_position(), self.swap_position())
                                fprint(lang.hedge_fail.format(self.coin, spot, swap))
                                self.exit_flag = True
                                continue
                            fprint(lang.approaching_liquidation)
                            mydict = dict(account=self.account, instrument=self.coin, timestamp=timestamp,
                                          title='自动减仓')
                            Ledger.mycol.insert_one(mydict)

                            # 期现差价控制在2个标准差
                            assert (recent := stat.recent_close_stat()), lang.fetch_ticker_first
                            close_pd = recent['avg'] - 2 * recent['std']

                            swap_position = await self.swap_position()
                            target_size = swap_position / (leverage + 1) ** 2

                            if not reducePosition:
                                reducePosition = await ReducePosition(self.coin, self.account)
                            reduce_task = await reducePosition.reduce(target_size=target_size, price_diff=close_pd)
                            task_started = True
                            reducing = True
                            time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                        # 保证金过多，现货加仓
                        if margin_reducible and liquidation_price > last * (1 + 1 / (leverage - 1)):
                            if not await self.is_hedged():
                                spot, swap = await gather(self.spot_position(), self.swap_position())
                                fprint(lang.hedge_fail.format(self.coin, spot, swap))
                                self.exit_flag = True
                                continue
                            fprint(lang.too_much_margin)
                            mydict = dict(account=self.account, instrument=self.coin, timestamp=timestamp,
                                          title='自动加仓')
                            Ledger.mycol.insert_one(mydict)

                            # 期现差价控制在2个标准差
                            assert (recent := stat.recent_open_stat()), lang.fetch_ticker_first
                            open_pd = recent['avg'] + 2 * recent['std']

                            if not addPosition:
                                addPosition = await AddPosition(self.coin, self.account)
                            # swap_position = await self.swap_position()
                            # target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)
                            usdt_size = await addPosition.adjust_swap_lever(leverage)
                            if usdt_size:
                                add_task = await addPosition.add(usdt_size=usdt_size, price_diff=open_pd)
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
                                    await asyncio.sleep(0.1)

                                assert (recent := stat.recent_close_stat(1)), lang.fetch_ticker_first
                                close_pd = recent['avg'] - 1.5 * recent['std']

                                liquidation_price, swap_position = await gather(self.liquidation_price(),
                                                                                self.swap_position())
                                target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                                reduce_task = await reducePosition.reduce(target_size=target_size, price_diff=close_pd)
                                reducing = True
                                accelerated = True
                                time_to_accelerate = datetime.utcnow() + timedelta(hours=2)

                            if timestamp > time_to_accelerate:
                                reducePosition.exitFlag = True
                                while not reduce_task.done():
                                    await asyncio.sleep(0.1)

                                assert (recent := stat.recent_close_stat(2)), lang.fetch_ticker_first
                                close_pd = recent['avg'] - 2 * recent['std']

                                liquidation_price, swap_position = await gather(self.liquidation_price(),
                                                                                self.swap_position())
                                target_size = swap_position * (1 - liquidation_price / last / (1 + 1 / leverage))
                                reduce_task = await reducePosition.reduce(target_size=target_size, price_diff=close_pd)
                                reducing = True
                                time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                        elif adding and not add_task.done():
                            if timestamp > time_to_accelerate:
                                addPosition.exitFlag = True
                                while not add_task.done():
                                    await asyncio.sleep(0.1)

                                assert (recent := stat.recent_open_stat(2)), lang.fetch_ticker_first
                                open_pd = recent['avg'] + 2 * recent['std']

                                # liquidation_price = await self.liquidation_price()
                                # swap_position = await self.swap_position()
                                # target_size = swap_position * (liquidation_price / last / (1 + 1 / leverage) - 1)
                                if (usdt_size := usdt_size - add_task.result()) > 0:
                                    add_task = await addPosition.add(usdt_size=usdt_size, price_diff=open_pd)
                                    adding = True
                                    time_to_accelerate = datetime.utcnow() + timedelta(hours=2)
                        else:
                            liquidation_price = await self.liquidation_price()
                            adding = reducing = task_started = False
                else:
                    raise ValueError
            except aiohttp.ClientError:
                print(lang.network_interruption)
                await asyncio.sleep(30)
        self.fut.set_result(None)
