from okex_api import *
import trading_data


class AddPosition(OKExAPI):
    """建仓、加仓功能类
    """

    @property
    def __name__(self):
        return 'AddPosition'

    def __init__(self, coin=None, accountid=3):
        super().__init__(coin=coin, accountid=accountid)

    async def is_hedged(self):
        """判断合约现货是否对冲
        """
        contract_val = float(self.swap_info['ctVal'])
        long, short = await gather(self.spot_position(), self.swap_position())
        if abs(long - short) < contract_val:
            return True
        else:
            fprint(self.coin, lang.spot_text, long, lang.swap_text, short)
            return False

    async def hedge(self):
        """加仓以达到完全对冲
        """

    async def set_swap_lever(self, leverage: float):
        """设置名义杠杆

        :param leverage: 杠杆
        :return: 成败
        """
        setting = create_task(self.accountAPI.get_leverage(self.swap_ID, 'isolated'))
        await gather(setting, self.check_position_mode())
        setting = setting.result()
        if float(setting['lever']) != (leverage := float(f'{leverage:.2f}')):
            # 设定某个合约的杠杆
            fprint(lang.current_leverage, setting['lever'])
            fprint(lang.set_leverage, leverage)
            await self.accountAPI.set_leverage(instId=self.swap_ID, lever=f'{leverage:.2f}', mgnMode='isolated')
            setting = await self.accountAPI.get_leverage(self.swap_ID, 'isolated')
            # print(setting)
            fprint(lang.finished_leverage)
        if float(setting['lever']) != leverage:
            fprint(lang.failed_leverage)
            return False
        return True

    @call_coroutine
    async def adjust_swap_lever(self, leverage: float):
        """调整实际杠杆

        :param leverage: 杠杆
        :return: 减少保证金
        """
        assert leverage > 0
        holding = await self.swap_holding()
        position = abs(holding['pos'] * float(self.swap_info['ctVal']))
        if holding and position:
            fprint(lang.adjust_leverage, leverage)
            avgPx = holding['avgPx']
            last = holding['last']
            prev_margin = holding['margin']
            prev_lever = holding['lever']
            max_lever = float(self.swap_info['lever'])

            if last >= avgPx:
                # net_margin = margin + upl = (liq - last) * position
                # margin = min_margin + extra
                # min_margin = occ_margin - upl
                # occ_margin = (min_liq - last) * position = avgPx / notional_lever * position
                # min_liq = last + avgPx / notional_lever = last * (1 + 1 / leverage)
                # upl < 0, upl = (avgPx - last) * position
                # min_margin = occ_margin - upl
                # = (avgPx / notional_lever - avgPx + last) * position
                # = (min_liq - avgPx) * position
                occ_margin = last / leverage * position
                notional_lever = avgPx * position / occ_margin
            else:
                # net_margin = margin + upl = (liq - last) * position
                # = (liq - avgPx) * position + upl
                # margin = min_margin + extra
                # occ_margin = avgPx / notional_lever * position = (min_liq - avgPx) * position
                # = (min_liq - last + last - avgPx) * position
                # = (min_liq - last) * position - upl
                # min_liq = avgPx + avgPx / notional_lever = last * (1 + 1 / leverage)
                # if min_liq < avgPx, occ_margin < 0
                # upl > 0, upl = (avgPx - last) * position
                # min_margin = occ_margin
                # = (min_liq - avgPx) * position
                occ_margin = (last / leverage + last - avgPx) * position
                notional_lever = avgPx * position / occ_margin
                if notional_lever < 0 or notional_lever > max_lever:
                    notional_lever = max_lever

            notional_lever = float(f'{notional_lever:.2f}')
            if await self.set_swap_lever(notional_lever):
                record.Record('Portfolio').mycol.find_one_and_update(dict(account=self.accountid, instrument=self.coin),
                                                                     {'$set': {'leverage': leverage}}, upsert=True)

            holding = await self.swap_holding()
            margin = holding['margin']
            last = holding['last']
            notional_lever = holding['lever']
            if last >= avgPx:
                min_liq = last + avgPx / notional_lever
            else:
                min_liq = avgPx + avgPx / notional_lever
            extra = int(margin - (min_liq - avgPx) * position)

            # 有多余保证金
            if extra > 0:
                if not await self.reduce_margin(extra):
                    extra -= 1
                    await self.reduce_margin(extra)
                    return extra
                return extra
            elif prev_lever > notional_lever:
                fprint(lang.added_margin.format(margin - prev_margin))
            return 0

    @run_with_cancel
    async def add(self, usdt_size=0.0, target_size=0.0, leverage=0, price_diff=0.002, accelerate_after=0):
        """加仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param leverage: 杠杆
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 加仓金额
        :rtype: float
        """
        if not leverage: leverage = await self.get_lever()
        if usdt_size:
            last = float((await self.publicAPI.get_specific_ticker(self.spot_ID))['last'])
            target_position = usdt_size * leverage / (leverage + 1) / last
        else:
            target_position = target_size
        fprint(self.coin, lang.amount_to_add, target_position)

        min_size = float(self.spot_info['minSz'])
        size_increment = float(self.spot_info['lotSz'])
        size_decimals = num_decimals(self.spot_info['lotSz'])
        contract_val = float(self.swap_info['ctVal'])

        # 查询账户余额
        trade_fee, usdt_balance = await gather(self.accountAPI.get_trade_fee(instType='SPOT', instId=self.spot_ID),
                                               self.usdt_balance())
        # 现货手续费率
        trade_fee = float(trade_fee['taker'])

        spot_filled_sum = 0.
        swap_filled_sum = 0.
        fee_total = 0.
        spot_notional = 0.
        swap_notional = 0.
        time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

        if target_position < contract_val:
            fprint(lang.target_position_text, target_position, lang.less_than_ctval, contract_val)
            fprint(lang.abort_text)
            return 0.

        OP = record.Record('OP')
        mydict = dict(account=self.accountid, instrument=self.coin, op='add', size=target_position)
        OP.insert(mydict)

        channels = [dict(channel='tickers', instId=self.spot_ID), dict(channel='tickers', instId=self.swap_ID)]
        spot_ticker = swap_ticker = None
        self.exitFlag = False

        # 如果仍未建仓完毕
        while target_position >= contract_val and not self.exitFlag:
            # 下单后重新订阅
            async for ticker in subscribe_without_login(self.public_url, channels):
                # 判断是否加速
                if accelerate_after and datetime.utcnow() > time_to_accelerate:
                    Stat = await trading_data.Stat(self.coin)
                    assert (recent := Stat.recent_open_stat(accelerate_after)), lang.fetch_ticker_first
                    price_diff = recent['avg'] + 2 * recent['std']
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

                last = float(spot_ticker['last'])
                # 现货最低买入价
                best_ask = float(spot_ticker['askPx'])
                # 合约最高卖出价
                best_bid = float(swap_ticker['bidPx'])

                # 如果不满足期现溢价
                if best_bid < best_ask * (1 + price_diff):
                    # print(f'当前期现差价: {(best_bid - best_ask) / best_ask:.3%} < {price_diff:.3%}')
                    pass
                else:
                    if usdt_balance < target_position * last * (1 + 1 / leverage):
                        while usdt_balance < target_position * last * (1 + 1 / leverage):
                            target_position -= min_size
                        if target_position < min_size:
                            fprint(lang.insufficient_USDT)
                            self.exitFlag = True
                            break
                    else:
                        # 计算下单数量
                        best_ask_size = float(spot_ticker['askSz'])
                        best_bid_size = float(swap_ticker['bidSz'])
                        # print(best_ask_size, best_bid_size)
                        # continue
                        order_size = min(target_position, best_ask_size, best_bid_size * contract_val)
                        order_size = round_to(order_size, min_size)
                        order_size = round_to(order_size, contract_val)

                        # 考虑现货手续费，分别计算现货数量与合约张数
                        spot_size = round_to(order_size / (1 + trade_fee), size_increment)
                        if spot_size > best_ask_size:
                            order_size -= min_size
                            order_size = round_to(order_size, contract_val)
                            spot_size = round_to(order_size / (1 + trade_fee), size_increment)
                        spot_size = float_str(spot_size, size_decimals)
                        contract_size = round(order_size / contract_val)
                        contract_size = f'{contract_size:d}'
                        # print(order_size, contract_size, spot_size)

                        spot_order_info = swap_order_info = spot_order_state = swap_order_state = dict()
                        # 下单，如果资金费不是马上更新
                        if order_size > 0 and not self.funding_settling():
                            spot_order, swap_order = await gather(
                                self.tradeAPI.take_spot_order(instId=self.spot_ID, side='buy', size=spot_size,
                                                              price=spot_ticker['askPx'], order_type='fok'),
                                self.tradeAPI.take_swap_order(instId=self.swap_ID, side='sell', size=contract_size,
                                                              price=swap_ticker['bidPx'], order_type='fok'),
                                return_exceptions=True)

                            if ((not isinstance(spot_order, OkexAPIException)) and
                                    (not isinstance(swap_order, OkexAPIException))):
                                pass
                            # 下单失败
                            else:
                                if spot_order is OkexAPIException:
                                    kwargs = dict(instId=self.swap_ID, order_id=swap_order['ordId'])
                                    swap_order_info = await self.tradeAPI.get_order_info(**kwargs)
                                    fprint(swap_order_info)
                                    fprint(spot_order)
                                elif swap_order is OkexAPIException:
                                    if swap_order['code'] in ('50026', '51022'):
                                        fprint(lang.futures_market_down)
                                    kwargs = dict(instId=self.spot_ID, order_id=spot_order['ordId'])
                                    spot_order_info = await self.tradeAPI.get_order_info(**kwargs)
                                    fprint(spot_order_info)
                                    fprint(swap_order)
                                self.exitFlag = True
                                break

                            swap_order_info = dict()

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
                                            self.exitFlag = True

                            await check_order()
                            if self.exitFlag:
                                break

                            # 其中一单撤销
                            while spot_order_state != 'filled' or swap_order_state != 'filled':
                                # print(spot_order_state+','+swap_order_state)
                                if spot_order_state == 'filled':
                                    if swap_order_state == 'canceled':
                                        fprint(lang.swap_order_retract, swap_order_state)
                                        try:
                                            # 市价开空合约
                                            kwargs = dict(instId=self.swap_ID, side='sell', size=contract_size,
                                                          order_type='market')
                                            swap_order = await self.tradeAPI.take_swap_order(**kwargs)
                                        except OkexAPIException as e:
                                            fprint(e)
                                            self.exitFlag = True
                                            break
                                    else:
                                        fprint(lang.swap_order_state, swap_order_state)
                                        fprint(lang.await_status_update)
                                elif swap_order_state == 'filled':
                                    if spot_order_state == 'canceled':
                                        fprint(lang.spot_order_retract, spot_order_state)
                                        # 重新定价
                                        # tick_size = float(self.spot_info['tickSz'])
                                        # limit_price = best_ask * (1 + 0.02)
                                        # limit_price = str(round_to(limit_price, tick_size))
                                        try:
                                            # 市价做多现货
                                            kwargs = dict(instId=self.spot_ID, side='buy', size=spot_size,
                                                          tgtCcy='base_ccy', order_type='market')
                                            spot_order = await self.tradeAPI.take_spot_order(**kwargs)
                                        except OkexAPIException as e:
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
                                # 手续费扣币
                                spot_filled = float(spot_order_info['accFillSz']) + float(spot_order_info['fee'])
                                swap_filled = float(swap_order_info['accFillSz']) * contract_val
                                spot_filled_sum += spot_filled
                                swap_filled_sum += swap_filled
                                spot_price = float(spot_order_info['avgPx'])
                                swap_price = float(swap_order_info['avgPx'])
                                spot_fee = float(spot_order_info['fee']) * spot_price
                                swap_fee = float(swap_order_info['fee'])
                                fee_total += spot_fee + swap_fee
                                spot_notional -= spot_filled * spot_price
                                swap_notional += swap_filled * swap_price

                                # 对冲检查
                                if abs(spot_filled - swap_filled) < contract_val:
                                    target_position_prev = target_position
                                    target_position -= swap_filled
                                    fprint(lang.hedge_success, swap_filled, lang.remaining + str(target_position))
                                    mydict = dict(account=self.accountid, instrument=self.coin, op='add',
                                                  size=target_position_prev)
                                    OP.mycol.find_one_and_update(mydict, {'$set': {'size': target_position}})
                                else:
                                    fprint(lang.hedge_fail.format(self.coin, spot_filled, swap_filled))
                                    self.exitFlag = True
                                    break
                            elif spot_order_state == 'canceled' and swap_order_state == 'canceled':
                                break
                            else:
                                self.exitFlag = True
                                break

                            usdt_balance = await self.usdt_balance()
                            target_position = min(target_position, usdt_balance * leverage / (leverage + 1) / best_ask)
                            # print(usdt_balance, target_position)
                            # 重新订阅
                            break
                        else:
                            # print('订单太小', order_size)
                            pass

        if spot_notional:
            Ledger = record.Record('Ledger')
            timestamp = datetime.utcnow()
            mydict1 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='现货买入',
                           spot_notional=spot_notional)
            mydict2 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='合约开空',
                           swap_notional=swap_notional)
            mydict3 = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='手续费',
                           fee=fee_total)
            Ledger.mycol.insert_many([mydict1, mydict2, mydict3])

        mydict = dict(account=self.accountid, instrument=self.coin, op='add')
        OP.delete(mydict)
        await self.update_portfolio()
        fprint(lang.added_amount, swap_filled_sum, self.coin)
        if await self.is_hedged():
            fprint(lang.hedge_success, swap_filled_sum, self.coin)
        else:
            fprint(lang.hedge_fail.format(self.coin, spot_filled_sum, swap_filled_sum))
        usdt_size = - spot_notional - fee_total + swap_notional / leverage
        return usdt_size

    @call_coroutine
    async def open(self, usdt_size=0.0, target_size=0.0, leverage=2., price_diff=0.002, accelerate_after=0):
        """建仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param leverage: 杠杆
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 建仓金额
        :rtype: float
        """
        Ledger = record.Record('Ledger')
        result = Ledger.find_last(dict(account=self.accountid, instrument=self.coin))
        if result and result['title'] != '平仓':
            fprint(lang.position_exist.format(await self.swap_position(), self.coin))
            return await self.add(usdt_size=usdt_size, price_diff=price_diff, accelerate_after=accelerate_after)
        else:
            usdt_balance = await self.usdt_balance()
            if target_size:
                last = float((await self.publicAPI.get_specific_ticker(self.spot_ID))['last'])
                usdt_size = last * target_size * (1 + 1 / leverage)
            if usdt_balance >= usdt_size:
                timestamp = datetime.utcnow()
                mydict = dict(account=self.accountid, instrument=self.coin, timestamp=timestamp, title='开仓')
                Ledger.insert(mydict)
                record.Record('Portfolio').mycol.insert_one(
                    dict(account=self.accountid, instrument=self.coin, leverage=leverage))
                await self.set_swap_lever(leverage)
                return await self.add(usdt_size=usdt_size, price_diff=price_diff, accelerate_after=accelerate_after)
            else:
                fprint(lang.insufficient_USDT)
                return 0.
