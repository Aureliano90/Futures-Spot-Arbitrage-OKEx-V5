from src.okex_api import *


class ReducePosition(OKExAPI):
    """平仓、减仓功能类
    """

    def __init__(self, coin=None, accountid=3):
        super().__init__(coin=coin, accountid=accountid)
        self.open_price = 0.
        self.swap_balance = 0.
        self.swap_position = 0.
        self.target_position = 0.
        self.spot_filled_sum = 0.
        self.swap_filled_sum = 0.
        self.usdt_release = 0.
        self.fee_total = 0.
        self.spot_notional = 0.
        self.swap_notional = 0.

    async def hedge(self):
        """减仓以达到完全对冲
        """

    async def place_close_order(self, bid_price: str, spot_size: str, ask_price: str, contract_size: str):
        spot_order_info = swap_order_info = spot_order_state = swap_order_state = dict()

        spot_task = create_task(
            self.tradeAPI.take_spot_order(instId=self.spot_ID, side='sell', size=spot_size, price=bid_price,
                                          order_type='fok'))
        swap_task = create_task(
            self.tradeAPI.take_swap_order(instId=self.swap_ID, side='buy', size=contract_size, price=ask_price,
                                          order_type='fok', reduceOnly=True))
        spot_res, swap_res = await gather(spot_task, swap_task, return_exceptions=True)

        if (not isinstance(spot_res, OkexAPIException)) and (not isinstance(swap_res, OkexAPIException)):
            spot_order, swap_order = spot_task.result(), swap_task.result()
        else:
            if spot_res is OkexAPIException:
                swap_order = swap_task.result()
                swap_order_info = await self.tradeAPI.get_order_info(instId=self.swap_ID, order_id=swap_order['ordId'])
                fprint(swap_order_info)
                fprint(spot_res)
            elif swap_res is OkexAPIException:
                spot_order = spot_task.result()
                if swap_res.code in ('50026', '51022'):
                    fprint(lang.futures_market_down)
                spot_order_info = await self.tradeAPI.get_order_info(instId=self.spot_ID, order_id=spot_order['ordId'])
                fprint(spot_order_info)
                fprint(swap_res)
            self.exitFlag = True
            return

        async def check_order():
            nonlocal spot_order_info, swap_order_info, spot_order_state, swap_order_state
            # 查询订单信息
            if spot_order['ordId'] != '-1' and swap_order['ordId'] != '-1':
                spot_order_info, swap_order_info = await gather(
                    self.tradeAPI.get_order_info(instId=self.spot_ID, order_id=spot_order['ordId']),
                    self.tradeAPI.get_order_info(instId=self.swap_ID, order_id=swap_order['ordId']))
                spot_order_state = spot_order_info['state']
                swap_order_state = swap_order_info['state']
            # 下单失败
            else:
                if spot_order['ordId'] == '-1':
                    fprint(lang.spot_order_failed)
                    fprint(spot_order)
                    self.exitFlag = True
                else:
                    fprint(lang.swap_order_failed)
                    fprint(swap_order)
                    if swap_order['code'] in ('50023', '51030'):
                        kwargs = dict(instId=self.spot_ID, order_id=spot_order['ordId'])
                        spot_order_info = await self.tradeAPI.get_order_info(**kwargs)
                        spot_order_state = spot_order_info['state']
                        await self.funding_settled()
                        swap_order_state = 'canceled'
                    else:
                        if swap_order['code'] in ('50026', '51022'):
                            fprint(lang.futures_market_down)
                        self.exitFlag = True

        await check_order()
        if self.exitFlag:
            return

        # 其中一单撤销
        while spot_order_state != 'filled' or swap_order_state != 'filled':
            # print(spot_order_state+','+swap_order_state)
            if spot_order_state == 'filled':
                if swap_order_state == 'canceled':
                    fprint(lang.swap_order_retract, swap_order_state)
                    try:
                        buy_price = round_to(1.01 * float(ask_price), self.tick_size)
                        buy_price = float_str(buy_price, self.tick_decimals)
                        kwargs = dict(instId=self.swap_ID, side='buy', size=contract_size, price=buy_price,
                                      order_type='limit', reduceOnly=True)
                        swap_order = await self.tradeAPI.take_swap_order(**kwargs)
                    except Exception as e:
                        fprint(e)
                        self.exitFlag = True
                        break
                else:
                    fprint(lang.swap_order_state, swap_order_state)
                    fprint(lang.await_status_update)
            elif swap_order_state == 'filled':
                if spot_order_state == 'canceled':
                    fprint(lang.spot_order_retract, spot_order_state)
                    try:
                        sell_price = round_to(0.99 * float(bid_price), self.tick_size)
                        sell_price = float_str(sell_price, self.tick_decimals)
                        kwargs = dict(instId=self.spot_ID, side='sell', size=spot_size, price=sell_price,
                                      order_type='limit')
                        spot_order = await self.tradeAPI.take_spot_order(**kwargs)
                    except Exception as e:
                        fprint(e)
                        self.exitFlag = True
                        break
                else:
                    fprint(lang.spot_order_state, spot_order_state)
                    fprint(lang.await_status_update)
            elif spot_order_state == 'canceled' and swap_order_state == 'canceled':
                # fprint(lang.both_order_failed)
                break
            else:
                fprint(lang.await_status_update)

            await check_order()
            if self.exitFlag:
                break

        # 下单成功
        if spot_order_state == 'filled' and swap_order_state == 'filled':
            prev_swap_balance = self.swap_balance
            holding = await self.swap_holding(self.swap_ID)
            self.swap_balance = holding['margin']
            self.swap_position = - holding['pos'] * self.contract_val
            spot_filled = float(spot_order_info['accFillSz'])
            swap_filled = float(swap_order_info['accFillSz']) * self.contract_val
            self.spot_filled_sum += spot_filled
            self.swap_filled_sum += swap_filled
            spot_price = float(spot_order_info['avgPx'])
            swap_price = float(swap_order_info['avgPx'])
            spot_fee = float(spot_order_info['fee'])
            swap_fee = float(swap_order_info['fee'])
            rpl = swap_filled * (self.open_price - swap_price)
            # margin_recoup = - Δswap_balance + rpl + swap_fee
            # 现货成交量加保证金变动
            self.usdt_release += (rpl + spot_filled * spot_price + spot_fee + swap_fee
                                  + prev_swap_balance - self.swap_balance)
            self.fee_total += spot_fee + swap_fee
            self.spot_notional += spot_filled * spot_price
            self.swap_notional -= swap_filled * swap_price

            # 对冲检查
            if abs(spot_filled - swap_filled) < self.contract_val:
                target_position_prev = self.target_position
                self.target_position -= swap_filled
                fprint(lang.hedge_success.format(swap_filled, self.coin), lang.remaining.format(self.target_position))
                mydict = dict(account=self.accountid, instrument=self.coin, op='reduce',
                              size=target_position_prev)
                Record('OP').mycol.find_one_and_update(mydict, {'$set': {'size': self.target_position}})
            else:
                fprint(lang.hedge_fail.format(self.coin, spot_filled, swap_filled))
                self.exitFlag = True
                return
        elif spot_order_state == 'canceled' and swap_order_state == 'canceled':
            return
        else:
            self.exitFlag = True
            return

    @manager.submit
    async def reduce(self, usdt_size=0.0, target_size=0.0, price_diff=0.002, accelerate_after=0):
        """减仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 释放USDT
        :rtype: float
        """
        spot_position, holding = await gather(self.spot_position(), self.swap_holding())
        self.swap_position = - holding['pos'] * self.contract_val
        if holding and self.swap_position:
            self.swap_balance = holding['margin']
            upl = holding['upl']
            last = holding['last']
            self.open_price = holding['avgPx']
            # net_margin = swap_balance + upl = swap_position * (liq - last)
            liq_last = (self.swap_balance + upl) / self.swap_position
        else:
            fprint(lang.nonexistent_position.format(self.swap_ID))
            return 0.
        if usdt_size:
            # usdt_size = target_position * last + (liq - last) * target_position
            self.target_position = usdt_size / (last + liq_last)
        else:
            self.target_position = target_size

        if self.target_position < self.contract_val:
            fprint(lang.target_position_text, self.target_position, lang.less_than_ctval, self.contract_val)
            fprint(lang.abort_text)
            return 0.
        if self.target_position > spot_position or self.target_position > self.swap_position:
            return await self.close(price_diff, accelerate_after)

        fprint(lang.amount_to_reduce.format(self.coin, self.target_position))
        OP = Record('OP')
        mydict = dict(account=self.accountid, instrument=self.coin, op='reduce', size=self.target_position)
        OP.insert(mydict)

        self.spot_filled_sum = 0.
        self.swap_filled_sum = 0.
        self.usdt_release = 0.
        self.fee_total = 0.
        self.spot_notional = 0.
        self.swap_notional = 0.
        time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

        channels = [dict(channel='tickers', instId=self.spot_ID), dict(channel='tickers', instId=self.swap_ID)]
        spot_ticker = swap_ticker = None
        self.exitFlag = False

        # 如果仍未减仓完毕
        while self.target_position >= self.contract_val and not self.exitFlag:
            # 下单后重新订阅
            async for ticker in subscribe_without_login(self.public_url, channels):
                # 判断是否加速
                if accelerate_after and datetime.utcnow() > time_to_accelerate:
                    Stat = trading_data.Stat(self.coin)
                    assert (recent := Stat.recent_close_stat(accelerate_after)), lang.fetch_ticker_first
                    price_diff = recent['avg'] - 2 * recent['std']
                    time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

                ticker = ticker['data'][0]
                if ticker['instId'] == self.spot_ID:
                    spot_ticker = ticker
                elif ticker['instId'] == self.swap_ID:
                    swap_ticker = ticker
                else:
                    continue
                if not (spot_ticker and swap_ticker):
                    continue

                # 现货最高卖出价
                best_bid = float(spot_ticker['bidPx'])
                # 合约最低买入价
                best_ask = float(swap_ticker['askPx'])

                # 如果不满足期现溢价
                if best_ask > best_bid * (1 + price_diff):
                    # print(f'当前期现差价: {(best_ask - best_bid) / best_bid:.3%} > {price_diff:.3%}')
                    pass
                else:
                    if self.target_position > spot_position:
                        fprint(lang.insufficient_spot)
                        self.exitFlag = True
                        break
                    elif self.target_position > self.swap_position:
                        fprint(lang.insufficient_margin)
                        self.exitFlag = True
                        break
                    else:
                        # 计算下单数量
                        best_bid_size = float(spot_ticker['bidSz'])
                        best_ask_size = float(swap_ticker['askSz'])
                        order_size = min(self.target_position, best_bid_size, best_ask_size * self.contract_val)
                        order_size = round_to(order_size, self.min_size)
                        order_size = round_to(order_size, self.contract_val)
                        # print(order_size)
                        contract_size = round(order_size / self.contract_val)
                        contract_size = f'{contract_size:d}'
                        spot_size = round_to(order_size, self.size_increment)
                        spot_size = float_str(spot_size, self.size_decimals)
                        # print(contract_size, spot_size, self.min_size)

                        # 下单，如果资金费不是马上更新
                        if order_size > 0 and not self.funding_settling():
                            await self.place_close_order(spot_ticker['bidPx'], spot_size, swap_ticker['askPx'],
                                                         contract_size)

                            if self.exitFlag:
                                break

                            spot_position = await self.spot_position()
                            self.target_position = min(self.target_position, spot_position, self.swap_position)
                            # 重新订阅
                            break
                        else:
                            # print('订单太小', order_size)
                            pass

        if self.spot_notional:
            Ledger = Record('Ledger')
            timestamp = datetime.utcnow()
            mydict1 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='现货卖出',
                           spot_notional=self.spot_notional)
            mydict2 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='合约平空',
                           swap_notional=self.swap_notional)
            mydict3 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='手续费',
                           fee=self.fee_total)
            Ledger.mycol.insert_many([mydict1, mydict2, mydict3])

        mydict = dict(account=self.accountid, instrument=self.coin, op='reduce')
        OP.delete(mydict)
        await self.update_portfolio()
        fprint(lang.reduced_amount.format(self.swap_filled_sum, self.coin))
        if self.usdt_release:
            fprint(lang.spot_recoup.format(self.usdt_release))
            await self.add_margin(self.usdt_release)
        return self.usdt_release

    @manager.submit
    async def close(self, price_diff=0.002, accelerate_after=0):
        """平仓期现组合

        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 释放USDT
        :rtype: float
        """
        spot_position, holding = await gather(self.spot_position(), self.swap_holding())
        self.swap_position = - holding['pos'] * self.contract_val
        if holding and self.swap_position:
            self.swap_balance = holding['margin']
            self.open_price = holding['avgPx']
        else:
            fprint(lang.nonexistent_position.format(self.swap_ID))
            return 0.

        self.target_position = min(spot_position, self.swap_position)
        if self.target_position < self.contract_val:
            fprint(lang.target_position_text, self.target_position, lang.less_than_ctval, self.contract_val)
            fprint(lang.abort_text)
            return 0.

        fprint(lang.amount_to_close.format(self.coin, self.target_position))
        OP = Record('OP')
        mydict = dict(account=self.accountid, instrument=self.coin, op='close', size=self.target_position)
        OP.insert(mydict)

        self.spot_filled_sum = 0.
        self.swap_filled_sum = 0.
        self.usdt_release = 0.
        self.fee_total = 0.
        self.spot_notional = 0.
        self.swap_notional = 0.
        time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

        channels = [dict(channel='tickers', instId=self.spot_ID), dict(channel='tickers', instId=self.swap_ID)]
        spot_ticker = swap_ticker = None
        self.exitFlag = False

        # 如果仍未减仓完毕
        while self.target_position > 0 and not self.exitFlag:
            # 下单后重新订阅
            async for ticker in subscribe_without_login(self.public_url, channels, verbose=False):
                # 判断是否加速
                if accelerate_after and datetime.utcnow() > time_to_accelerate:
                    Stat = trading_data.Stat(self.coin)
                    assert (recent := Stat.recent_close_stat(accelerate_after)), lang.fetch_ticker_first
                    price_diff = recent['avg'] - 2 * recent['std']
                    time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

                ticker = ticker['data'][0]
                if ticker['instId'] == self.spot_ID:
                    spot_ticker = ticker
                elif ticker['instId'] == self.swap_ID:
                    swap_ticker = ticker
                else:
                    continue
                if not (spot_ticker and swap_ticker):
                    continue

                # 现货最高卖出价
                best_bid = float(spot_ticker['bidPx'])
                # 合约最低买入价
                best_ask = float(swap_ticker['askPx'])

                # 如果不满足期现溢价
                if best_ask > best_bid * (1 + price_diff):
                    # print(f'当前期现差价: {(best_ask - best_bid) / best_bid:.3%} > {price_diff:.3%}')
                    pass
                else:
                    if self.target_position > spot_position:
                        fprint(lang.insufficient_spot)
                        self.exitFlag = True
                        break
                    elif self.target_position > self.swap_position:
                        fprint(lang.insufficient_swap)
                        self.exitFlag = True
                        break
                    else:
                        # 计算下单数量
                        best_bid_size = float(spot_ticker['bidSz'])
                        best_ask_size = float(swap_ticker['askSz'])

                        if self.target_position < self.swap_position:  # spot=target=1.9 swap=2.0
                            order_size = min(self.target_position, round_to(best_bid_size, self.min_size),
                                             best_ask_size * self.contract_val)  # order=1.9 or 1
                            contract_size = round(order_size / self.contract_val)  # 2 or 1
                            spot_size = round_to(order_size, self.size_increment)  # 1.9 or 1
                            remnant = (spot_position - spot_size) / self.min_size
                            # print(order_size, contract_size, spot_size, remnant)
                            # 必须一次把现货出完
                            if remnant >= 1:
                                order_size = contract_size * self.contract_val
                                spot_size = round_to(order_size, self.size_increment)
                            elif round(remnant) > 0 and remnant < 1:  # 1.9-1=0.9<1
                                continue
                            else:  # 1.9-1.9=0
                                pass
                        else:  # spot=2.1 swap=target=2.0
                            order_size = min(self.target_position, round_to(best_bid_size, self.min_size),
                                             best_ask_size * self.contract_val)  # order=2 or 1, 1.5
                            contract_size = round(order_size / self.contract_val)  # 2 or 1
                            spot_size = round_to(order_size, self.size_increment)  # 2 or 1, 1.5
                            remnant = (spot_position - spot_size) / self.min_size
                            # 必须一次把现货出完
                            if remnant >= 1:  # 2.1-1>1
                                order_size = contract_size * self.contract_val
                                spot_size = round_to(order_size, self.size_increment)
                            elif remnant < 1:  # 2.1-2=0.1
                                if spot_position <= best_bid_size:  # 2.1<3
                                    spot_size = spot_position  # 2->2.1
                                else:
                                    continue
                        contract_size = f'{contract_size:d}'
                        spot_size = float_str(spot_size, self.size_decimals)

                        # 下单，如果资金费不是马上更新
                        if order_size > 0 and not self.funding_settling():
                            await self.place_close_order(spot_ticker['bidPx'], spot_size, swap_ticker['askPx'],
                                                         contract_size)

                            if self.exitFlag:
                                break

                            spot_position = await self.spot_position()
                            self.target_position = min(self.target_position, spot_position, self.swap_position)
                            # 重新订阅
                            break
                        else:
                            # print('订单太小', order_size)
                            pass

        if self.spot_notional:
            Ledger = Record('Ledger')
            timestamp = datetime.utcnow()
            mydict1 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='现货卖出',
                           spot_notional=self.spot_notional)
            mydict2 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='合约平空',
                           swap_notional=self.swap_notional)
            mydict3 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='手续费',
                           fee=self.fee_total)
            mydict4 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='平仓',
                           position=self.usdt_release)
            Ledger.mycol.insert_many([mydict1, mydict2, mydict3, mydict4])

        mydict = dict(account=self.accountid, instrument=self.coin, op='close')
        OP.delete(mydict)
        Record('Portfolio').mycol.delete_one(dict(account=self.accountid, instrument=self.coin))
        fprint(lang.closed_amount.format(self.swap_filled_sum, self.coin))
        if self.usdt_release:
            fprint(lang.spot_recoup.format(self.usdt_release))
        return self.usdt_release
