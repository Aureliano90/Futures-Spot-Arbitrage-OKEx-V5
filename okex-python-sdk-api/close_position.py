from okex_api import *
from datetime import datetime, timedelta
import record
import trading_data
from log import fprint


class ReducePosition(OKExAPI):
    """平仓、减仓功能类
    """

    def __init__(self, coin, accountid=3):
        OKExAPI.__init__(self, coin, accountid)

    def hedge(self):
        """减仓以达到完全对冲
        """

    async def reduce(self, usdt_size=0.0, target_size=0.0, price_diff=0.002, accelerate_after=0):
        """减仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 卖现货所得USDT
        :rtype: float
        """
        if usdt_size:
            ticker, leverage = await gather(self.publicAPI.get_specific_ticker(self.spot_ID), self.get_lever())
            last = float(ticker['last'])
            target_position = usdt_size * leverage / (leverage + 1) / last
        else:
            target_position = target_size

        min_size = float(self.spot_info['minSz'])
        size_increment = float(self.spot_info['lotSz'])
        contract_val = float(self.swap_info['ctVal'])

        spot_position, swap_position = await gather(self.spot_position(), self.swap_position())

        if target_position < contract_val:
            fprint(lang.target_position_text, target_position, lang.less_than_ctval, contract_val)
            fprint(lang.abort_text)
            return 0.
        if target_position > spot_position or target_position > swap_position:
            await self.close(price_diff, accelerate_after)
        else:
            fprint(self.coin, lang.amount_to_reduce, target_position)
            OP = record.Record('OP')
            mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'reduce', 'size': target_position}
            OP.insert(mydict)

            filled_sum = 0.
            usdt_release = 0.
            fee_total = 0.
            spot_notional = 0.
            swap_notional = 0.
            time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

            channels = [{"channel": "tickers", "instId": self.spot_ID}, {"channel": "tickers", "instId": self.swap_ID}]
            spot_ticker, swap_ticker = None, None

            # 如果仍未减仓完毕
            while target_position >= contract_val and not self.exitFlag:
                # 下单后重新订阅
                async for ticker in subscribe_without_login(self.public_url, channels, verbose=False):
                    # 判断是否加速
                    if accelerate_after and datetime.utcnow() > time_to_accelerate:
                        Stat = await trading_data.Stat(self.coin)
                        recent = Stat.recent_close_stat(accelerate_after)
                        if recent:
                            price_diff = recent['avg'] - 2 * recent['std']
                        else:
                            fprint(lang.fetch_ticker_first)
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
                        # print("当前期现差价: ", (best_ask - best_bid) / best_bid, ">", price_diff)
                        pass
                    else:
                        if target_position > spot_position:
                            fprint(lang.insufficient_spot)
                            self.exitFlag = True
                            break
                        elif target_position > swap_position:
                            fprint(lang.insufficient_margin)
                            self.exitFlag = True
                            break
                        else:
                            # 计算下单数量
                            best_bid_size = float(spot_ticker['bidSz'])
                            best_ask_size = float(swap_ticker['askSz'])
                            order_size = min(target_position, round_to(best_bid_size, min_size),
                                             best_ask_size * contract_val)
                            order_size = round_to(order_size, contract_val)
                            # print(order_size)
                            contract_size = round(order_size / contract_val)
                            spot_size = round_to(order_size, size_increment)
                            # print(contract_size, spot_size, min_size)

                            # 下单
                            if order_size > 0:
                                spot_order, swap_order = await gather(
                                    self.tradeAPI.take_spot_order(instId=self.spot_ID, side='sell', size=str(spot_size),
                                                                  price=best_bid, order_type='fok'),
                                    self.tradeAPI.take_swap_order(instId=self.swap_ID, side='buy',
                                                                  size=str(contract_size), price=best_ask,
                                                                  order_type='fok', reduceOnly=True),
                                    return_exceptions=True)

                                if (not isinstance(spot_order, OkexAPIException)) and (
                                        not isinstance(swap_order, OkexAPIException)):
                                    pass
                                else:
                                    if spot_order is OkexAPIException:
                                        swap_order_info = await self.tradeAPI.get_order_info(instId=self.swap_ID,
                                                                                             order_id=swap_order[
                                                                                                 'ordId'])
                                        fprint(swap_order_info)
                                        fprint(spot_order)
                                    elif swap_order is OkexAPIException:
                                        if swap_order.message == "System error" or swap_order.code == "51022":
                                            fprint(lang.futures_market_down)
                                        spot_order_info = await self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                                             order_id=spot_order[
                                                                                                 'ordId'])
                                        fprint(spot_order_info)
                                        fprint(swap_order)
                                    self.exitFlag = True
                                    break

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
                                    else:
                                        fprint(lang.swap_order_failed)
                                        fprint(swap_order)
                                    self.exitFlag = True
                                    break

                                # 其中一单撤销
                                while spot_order_state != 'filled' or swap_order_state != 'filled':
                                    # print(spot_order_state+','+swap_order_state)
                                    if spot_order_state == 'filled':
                                        if swap_order_state == 'canceled':
                                            fprint(lang.swap_order_retract, swap_order_state)
                                            try:
                                                # 市价平空合约
                                                swap_order = await self.tradeAPI.take_swap_order(instId=self.swap_ID,
                                                                                                 side='buy', size=str(
                                                        contract_size),
                                                                                                 order_type='market',
                                                                                                 reduceOnly=True)
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
                                                # 市价卖出现货
                                                spot_order = await self.tradeAPI.take_spot_order(instId=self.spot_ID,
                                                                                                 side='sell',
                                                                                                 size=str(spot_size),
                                                                                                 order_type='market')
                                            except Exception as e:
                                                fprint(e)
                                                self.exitFlag = True
                                                break
                                        else:
                                            fprint(lang.spot_order_state, spot_order_state)
                                            fprint(lang.await_status_update)
                                    elif spot_order_state == 'canceled' and swap_order_state == 'canceled':
                                        # print("下单失败")
                                        break
                                    else:
                                        fprint(lang.await_status_update)

                                    # 更新订单信息
                                    if spot_order['ordId'] != '-1' and swap_order['ordId'] != '-1':
                                        spot_order_info, swap_order_info = await gather(
                                            self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                         order_id=spot_order['ordId']),
                                            self.tradeAPI.get_order_info(instId=self.swap_ID,
                                                                         order_id=swap_order['ordId']))
                                        spot_order_state = spot_order_info['state']
                                        swap_order_state = swap_order_info['state']
                                    else:
                                        if spot_order['ordId'] == '-1':
                                            fprint(lang.spot_order_failed)
                                            fprint(spot_order)
                                        else:
                                            fprint(lang.swap_order_failed)
                                            fprint(swap_order)
                                        self.exitFlag = True
                                        break

                                # 下单成功
                                if spot_order_state == 'filled' and swap_order_state == 'filled':
                                    spot_filled = float(spot_order_info['accFillSz'])
                                    swap_filled = float(swap_order_info['accFillSz']) * contract_val
                                    filled_sum += swap_filled
                                    spot_price = float(spot_order_info['avgPx'])
                                    usdt_release += spot_filled * spot_price + float(spot_order_info['fee'])
                                    fee_total += float(spot_order_info['fee'])
                                    spot_notional += spot_filled * spot_price
                                    fee_total += float(swap_order_info['fee'])
                                    swap_price = float(swap_order_info['avgPx'])
                                    swap_notional -= swap_filled * swap_price

                                    # 对冲检查
                                    if abs(spot_filled - swap_filled) < contract_val:
                                        target_position_prev = target_position
                                        target_position -= swap_filled
                                        fprint(lang.hedge_success, swap_filled, lang.remaining + str(target_position))
                                        mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'reduce',
                                                  'size': target_position_prev}
                                        OP.mycol.find_one_and_update(mydict, {'$set': {'size': target_position}})
                                    else:
                                        fprint(lang.hedge_fail)
                                        self.exitFlag = True
                                        break

                                spot_position, swap_position = await gather(self.spot_position(), self.swap_position())
                                target_position = min(target_position, spot_position, swap_position)
                                # 重新订阅
                                break
                            else:
                                # print("订单太小", order_size)
                                pass
            if spot_notional != 0:
                Ledger = record.Record('Ledger')
                timestamp = datetime.utcnow()
                mylist = []
                mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "现货卖出",
                          'spot_notional': spot_notional}
                mylist.append(mydict)
                mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "合约平空",
                          'swap_notional': swap_notional}
                mylist.append(mydict)
                mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "手续费",
                          'fee': fee_total}
                mylist.append(mydict)
                Ledger.mycol.insert_many(mylist)

            mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'reduce'}
            OP.delete(mydict)
            fprint(lang.reduced_amount, filled_sum, self.coin)
            if usdt_release != 0:
                fprint(lang.spot_recoup, usdt_release, "USDT")
                await self.add_margin(usdt_release)
            return usdt_release

    async def close(self, price_diff=0.002, accelerate_after=0):
        """平仓期现组合

        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 平仓所得USDT
        :rtype: float
        """
        spot_position, swap_position, swap_balance = await gather(self.spot_position(), self.swap_position(),
                                                                  self.swap_balance())
        target_position = min(spot_position, swap_position)
        fprint(self.coin, lang.amount_to_close, target_position)

        min_size = float(self.spot_info['minSz'])
        size_increment = float(self.spot_info['lotSz'])
        contract_val = float(self.swap_info['ctVal'])

        filled_sum = 0.
        usdt_release = 0.
        fee_total = 0.
        spot_notional = 0.
        swap_notional = 0.
        time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

        if target_position < contract_val:
            fprint(lang.target_position_text, target_position, lang.less_than_ctval, contract_val)
            fprint(lang.abort_text)
            return 0.

        OP = record.Record('OP')
        mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'close', 'size': target_position}
        OP.insert(mydict)

        channels = [{"channel": "tickers", "instId": self.spot_ID}, {"channel": "tickers", "instId": self.swap_ID}]
        spot_ticker, swap_ticker = None, None

        # 如果仍未减仓完毕
        while target_position > 0 and not self.exitFlag:
            # 下单后重新订阅
            async for ticker in subscribe_without_login(self.public_url, channels, verbose=False):
                # 判断是否加速
                if accelerate_after and datetime.utcnow() > time_to_accelerate:
                    Stat = await trading_data.Stat(self.coin)
                    recent = Stat.recent_close_stat(accelerate_after)
                    if recent:
                        price_diff = recent['avg'] - 2 * recent['std']
                    else:
                        fprint(lang.fetch_ticker_first)
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
                    # print("当前期现差价: ", (best_ask - best_bid) / best_bid, ">", price_diff)
                    pass
                else:
                    if target_position > spot_position:
                        fprint(lang.insufficient_spot)
                        self.exitFlag = True
                        break
                    elif target_position > swap_position:
                        fprint(lang.insufficient_swap)
                        self.exitFlag = True
                        break
                    else:
                        # 计算下单数量
                        best_bid_size = float(spot_ticker['bidSz'])
                        best_ask_size = float(swap_ticker['askSz'])

                        if target_position < swap_position:  # spot=target=1.9 swap=2.0
                            order_size = min(target_position, round_to(best_bid_size, min_size),
                                             best_ask_size * contract_val)  # order=1.9 or 1, 44
                            contract_size = round(order_size / contract_val)  # 2 or 1, 40
                            spot_size = round_to(order_size, size_increment)  # 1.9 or 1, 44
                            remnant = (spot_position - spot_size) / min_size
                            # print(order_size, contract_size, spot_size, remnant)
                            # 必须一次把现货出完
                            if remnant >= 1:
                                order_size = contract_size * contract_val
                                spot_size = round_to(order_size, size_increment)
                            elif round(remnant) > 0 and remnant < 1:  # 1.9-1=0.9<1
                                continue
                            else:  # 1.9-1.9=0
                                pass
                        else:  # spot=2.1 swap=target=2.0
                            order_size = min(target_position, round_to(best_bid_size, min_size),
                                             best_ask_size * contract_val)  # order=2 or 1, 1.5
                            contract_size = round(order_size / contract_val)  # 2 or 1
                            spot_size = round_to(order_size, size_increment)  # 2 or 1, 1.5
                            remnant = (spot_position - spot_size) / min_size
                            # 必须一次把现货出完
                            if remnant >= 1:  # 2.1-1>1
                                order_size = contract_size * contract_val
                                spot_size = round_to(order_size, size_increment)
                            elif remnant < 1:  # 2.1-2=0.1
                                if spot_position <= best_bid_size:  # 2.1<3
                                    spot_size = spot_position  # 2->2.1
                                else:
                                    continue

                        # 下单
                        if order_size > 0:
                            spot_order, swap_order = await gather(
                                self.tradeAPI.take_spot_order(instId=self.spot_ID, side='sell', size=str(spot_size),
                                                              price=best_bid, order_type='fok'),
                                self.tradeAPI.take_swap_order(instId=self.swap_ID, side='buy', size=str(contract_size),
                                                              price=best_ask, order_type='fok', reduceOnly=True))

                            if (not isinstance(spot_order, OkexAPIException)) and (
                                    not isinstance(swap_order, OkexAPIException)):
                                pass
                            else:
                                if spot_order is OkexAPIException:
                                    swap_order_info = await self.tradeAPI.get_order_info(instId=self.swap_ID,
                                                                                         order_id=swap_order['ordId'])
                                    fprint(swap_order_info)
                                    fprint(spot_order)
                                elif swap_order is OkexAPIException:
                                    if swap_order.message == "System error" or swap_order.code == "51022":
                                        fprint(lang.futures_market_down)
                                    spot_order_info = await self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                                         order_id=spot_order['ordId'])
                                    fprint(spot_order_info)
                                    fprint(swap_order)
                                self.exitFlag = True
                                break

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
                                else:
                                    fprint(lang.swap_order_failed)
                                    fprint(swap_order)
                                self.exitFlag = True
                                break

                            # 其中一单撤销
                            while spot_order_state != 'filled' or swap_order_state != 'filled':
                                # print(spot_order_state+','+swap_order_state)
                                if spot_order_state == 'filled':
                                    if swap_order_state == 'canceled':
                                        fprint(lang.swap_order_retract, swap_order_state)
                                        try:
                                            # 市价平空合约
                                            swap_order = await self.tradeAPI.take_swap_order(instId=self.swap_ID,
                                                                                             side='buy',
                                                                                             size=str(contract_size),
                                                                                             order_type='market',
                                                                                             reduceOnly=True)
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
                                            # 市价卖出现货
                                            spot_order = await self.tradeAPI.take_spot_order(instId=self.spot_ID,
                                                                                             side='sell',
                                                                                             size=str(spot_size),
                                                                                             order_type='market')
                                        except Exception as e:
                                            fprint(e)
                                            self.exitFlag = True
                                            break
                                    else:
                                        fprint(lang.spot_order_state, spot_order_state)
                                        fprint(lang.await_status_update)
                                elif spot_order_state == 'canceled' and swap_order_state == 'canceled':
                                    # print("下单失败")
                                    break
                                else:
                                    fprint(lang.await_status_update)

                                # 更新订单信息
                                if spot_order['ordId'] != '-1' and swap_order['ordId'] != '-1':
                                    spot_order_info, swap_order_info = await gather(
                                        self.tradeAPI.get_order_info(instId=self.spot_ID, order_id=spot_order['ordId']),
                                        self.tradeAPI.get_order_info(instId=self.swap_ID, order_id=swap_order['ordId']))
                                    spot_order_state = spot_order_info['state']
                                    swap_order_state = swap_order_info['state']
                                else:
                                    if spot_order['ordId'] == '-1':
                                        fprint(lang.spot_order_failed)
                                        fprint(spot_order)
                                    else:
                                        fprint(lang.swap_order_failed)
                                        fprint(swap_order)
                                    self.exitFlag = True
                                    break

                            # 下单成功
                            if spot_order_state == 'filled' and swap_order_state == 'filled':
                                prev_swap_balance = swap_balance
                                swap_balance = await self.swap_balance()
                                spot_filled = float(spot_order_info['accFillSz'])
                                swap_filled = float(swap_order_info['accFillSz']) * contract_val
                                filled_sum += swap_filled
                                spot_price = float(spot_order_info['avgPx'])
                                # 现货成交量加保证金变动
                                usdt_release += spot_filled * spot_price + float(
                                    spot_order_info['fee']) + prev_swap_balance - swap_balance
                                fee_total += float(spot_order_info['fee'])
                                spot_notional += spot_filled * spot_price
                                fee_total += float(swap_order_info['fee'])
                                swap_price = float(swap_order_info['avgPx'])
                                swap_notional -= swap_filled * swap_price

                                # 对冲检查
                                if abs(spot_filled - swap_filled) < contract_val:
                                    target_position_prev = target_position
                                    target_position -= swap_filled
                                    fprint(lang.hedge_success, swap_filled, lang.remaining + str(target_position))
                                    mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'close',
                                              'size': target_position_prev}
                                    OP.mycol.find_one_and_update(mydict, {'$set': {'size': target_position}})
                                else:
                                    fprint(lang.hedge_fail)
                                    self.exitFlag = True
                                    break

                            spot_position, swap_position = await gather(self.spot_position(), self.swap_position())
                            target_position = min(target_position, spot_position, swap_position)
                            # 重新订阅
                            break
                        else:
                            # print("订单太小", order_size)
                            pass
        if spot_notional != 0:
            Ledger = record.Record('Ledger')
            timestamp = datetime.utcnow()
            mylist = []
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "现货卖出",
                      'spot_notional': spot_notional}
            mylist.append(mydict)
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "合约平空",
                      'swap_notional': swap_notional}
            mylist.append(mydict)
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "手续费",
                      'fee': fee_total}
            mylist.append(mydict)
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "平仓"}
            mylist.append(mydict)
            Ledger.mycol.insert_many(mylist)

        mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'close'}
        OP.delete(mydict)
        fprint(lang.closed_amount.format(filled_sum, self.coin))
        if usdt_release != 0:
            fprint(lang.spot_recoup, usdt_release, "USDT")
        return usdt_release
