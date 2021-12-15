from okex_api import *
from datetime import datetime, timedelta
import record
import trading_data
from log import fprint


class AddPosition(OKExAPI):
    """建仓、加仓功能类
    """

    def __init__(self, coin, accountid):
        OKExAPI.__init__(self, coin, accountid)

    def is_hedged(self):
        """判断合约现货是否对冲
        """
        contract_val = float(self.swap_info['ctVal'])
        short = self.swap_position()
        long = self.spot_position()

        if abs(long - short) < contract_val:
            return True
        else:
            fprint(self.coin, lang.spot_text, long, lang.swap_text, short)
            return False

    def hedge(self):
        """加仓以达到完全对冲
        """

    def set_swap_lever(self, leverage: int):
        # 获取某个合约的用户配置
        self.check_position_mode()
        setting = self.accountAPI.get_leverage(self.swap_ID, 'isolated')
        while setting['mgnMode'] != 'isolated' or int(float(setting['lever'])) != leverage:
            # 设定某个合约的杠杆
            fprint(lang.current_leverage, setting['lever'])
            fprint(lang.set_leverage, leverage)
            self.accountAPI.set_leverage(instId=self.swap_ID, lever='{:d}'.format(leverage), mgnMode='isolated')
            time.sleep(1)
            setting = self.accountAPI.get_leverage(self.swap_ID, 'isolated')
            # print(setting)
        fprint(lang.finished_leverage)

    def add(self, usdt_size=0.0, target_size=0.0, leverage=2, price_diff=0.002, accelerate_after=0):
        """加仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param leverage: 杠杆
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 加仓数量
        :rtype: float
        """
        if usdt_size:
            last = float(self.publicAPI.get_specific_ticker(self.spot_ID)['last'])
            target_position = usdt_size * leverage / (leverage + 1) / last
        else:
            target_position = target_size
        fprint(self.coin, lang.amount_to_add, target_position)

        min_size = float(self.spot_info['minSz'])
        size_increment = float(self.spot_info['lotSz'])
        contract_val = float(self.swap_info['ctVal'])

        # 现货手续费率
        trade_fee = float(self.accountAPI.get_trade_fee(instType='SPOT', instId=self.spot_ID)['taker'])

        self.set_swap_lever(leverage)

        counter = 0
        filled_sum = 0
        fee_total = 0
        spot_notional = 0
        swap_notional = 0
        time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)
        Stat = trading_data.Stat(self.coin)

        if target_position < contract_val:
            fprint(lang.target_position_text, target_position, lang.less_than_ctval, contract_val)
            fprint(lang.abort_text)
            return 0.

        OP = record.Record('OP')
        mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'add', 'size': target_position}
        OP.insert(mydict)

        # 如果仍未建仓完毕
        while target_position >= contract_val and not self.exitFlag:
            # 判断是否加速
            if accelerate_after and datetime.utcnow() > time_to_accelerate:
                recent = Stat.recent_open_stat(accelerate_after)
                price_diff = recent['avg'] + 2 * recent['std']
                time_to_accelerate = datetime.utcnow() + timedelta(hours=accelerate_after)

            # 公共-获取现货ticker信息
            # spot_ticker = self.publicAPI.get_specific_ticker(self.spot_ID)
            # 公共-获取合约ticker信息
            # swap_ticker = self.publicAPI.get_specific_ticker(self.swap_ID)
            tickers = self.parallel_ticker()
            spot_ticker = tickers[0]
            swap_ticker = tickers[1]
            # 现货最低买入价
            best_ask = float(spot_ticker['askPx'])
            # 合约最高卖出价
            best_bid = float(swap_ticker['bidPx'])

            # 如果不满足期现溢价
            if best_bid < best_ask * (1 + price_diff):
                # print("当前期现差价: ", (best_bid - best_ask) / best_ask, "<", price_diff)
                counter = 0
                time.sleep(SLEEP)
            # 监视溢价持久度
            else:
                if counter < CONFIRMATION:
                    counter += 1
                    time.sleep(SLEEP)
                else:
                    # 查询账户余额
                    usdt_balance = self.usdt_balance()

                    # 更新价格
                    tickers = self.parallel_ticker()
                    spot_ticker = tickers[0]
                    swap_ticker = tickers[1]
                    best_ask = float(spot_ticker['askPx'])
                    last = float(spot_ticker['last'])
                    best_bid = float(swap_ticker['bidPx'])

                    if usdt_balance < target_position * last * (1 + 1 / leverage):
                        while usdt_balance < target_position * last * (1 + 1 / leverage):
                            target_position -= min_size
                        if target_position < min_size:
                            fprint(lang.insufficient_USDT)
                            break
                    else:
                        # 计算下单数量
                        best_ask_size = float(spot_ticker['askSz'])
                        best_bid_size = float(swap_ticker['bidSz'])
                        # print(best_ask_size, best_bid_size)
                        # continue
                        order_size = min(target_position, round_to(best_ask_size, min_size),
                                         best_bid_size * contract_val)
                        order_size = round_to(order_size, contract_val)

                        # 考虑现货手续费，分别计算现货数量与合约张数
                        contract_size = round(order_size / contract_val)
                        spot_size = round_to(order_size / (1 + trade_fee), size_increment)
                        # print(order_size, contract_size, spot_size)

                        # 下单
                        if order_size > 0:
                            try:
                                # 现货下单（Fill or Kill）
                                kwargs = {'instId': self.spot_ID, 'side': 'buy', 'size': str(spot_size),
                                          'price': best_ask, 'order_type': 'fok'}
                                thread1 = MyThread(target=self.tradeAPI.take_spot_order, kwargs=kwargs)
                                thread1.start()

                                # 合约下单（Fill or Kill）
                                kwargs = {'instId': self.swap_ID, 'side': 'sell', 'size': str(contract_size),
                                          'price': best_bid, 'order_type': 'fok'}
                                thread2 = MyThread(target=self.tradeAPI.take_swap_order, kwargs=kwargs)
                                thread2.start()

                                thread1.join()
                                thread2.join()
                                spot_order = thread1.get_result()
                                swap_order = thread2.get_result()
                            except OkexAPIException as e:
                                if e.message == "System error" or e.code == "35003":
                                    fprint(lang.futures_market_down)
                                    spot_order = thread1.get_result()
                                    spot_order_info = self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                                   order_id=spot_order['ordId'])
                                    fprint(spot_order_info)
                                fprint(e)
                                return filled_sum

                            # 查询订单信息
                            if spot_order['ordId'] != '-1' and swap_order['ordId'] != '-1':
                                spot_order_info = self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                               order_id=spot_order['ordId'])
                                swap_order_info = self.tradeAPI.get_order_info(instId=self.swap_ID,
                                                                               order_id=swap_order['ordId'])
                                spot_order_state = spot_order_info['state']
                                swap_order_state = swap_order_info['state']
                            else:
                                if spot_order['ordId'] == '-1':
                                    fprint(lang.spot_order_failed)
                                    fprint(spot_order)
                                else:
                                    fprint(lang.swap_order_failed)
                                    fprint(swap_order)
                                fprint(lang.added_amount, filled_sum, self.coin)
                                return filled_sum

                            # 其中一单撤销
                            while spot_order_state != 'filled' or swap_order_state != 'filled':
                                # print(spot_order_state+','+swap_order_state)
                                if spot_order_state == 'filled':
                                    if swap_order_state == 'canceled':
                                        fprint(lang.swap_order_retract, swap_order_state)
                                        try:
                                            # 市价开空合约
                                            swap_order = self.tradeAPI.take_swap_order(instId=self.swap_ID, side='sell',
                                                                                       order_type='market',
                                                                                       size=str(contract_size))
                                        except Exception as e:
                                            fprint(e)
                                            return filled_sum
                                    else:
                                        fprint(lang.swap_order_state, swap_order_state)
                                        fprint(lang.await_status_update)
                                elif swap_order_state == 'filled':
                                    if spot_order_state == 'canceled':
                                        fprint(lang.spot_order_retract, spot_order_state)
                                        # 重新定价
                                        tick_size = float(self.spot_info['tickSz'])
                                        limit_price = best_ask * (1 + 0.02)
                                        limit_price = str(round_to(limit_price, tick_size))
                                        try:
                                            spot_order = self.tradeAPI.take_spot_order(instId=self.spot_ID, side='buy',
                                                                                       size=str(spot_size),
                                                                                       price=limit_price,
                                                                                       order_type='limit')
                                        except Exception as e:
                                            fprint(e)
                                            return filled_sum
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
                                    spot_order_info = self.tradeAPI.get_order_info(instId=self.spot_ID,
                                                                                   order_id=spot_order['ordId'])
                                    swap_order_info = self.tradeAPI.get_order_info(instId=self.swap_ID,
                                                                                   order_id=swap_order['ordId'])
                                    spot_order_state = spot_order_info['state']
                                    swap_order_state = swap_order_info['state']
                                    time.sleep(SLEEP)
                                else:
                                    if spot_order['ordId'] == '-1':
                                        fprint(lang.spot_order_failed)
                                        fprint(spot_order)
                                    else:
                                        fprint(lang.swap_order_failed)
                                        fprint(swap_order)
                                    fprint(lang.added_amount, filled_sum, self.coin)
                                    return filled_sum

                            # 下单成功
                            if spot_order_state == 'filled' and swap_order_state == 'filled':
                                spot_filled = float(spot_order_info['accFillSz'])
                                swap_filled = float(swap_order_info['accFillSz']) * contract_val
                                filled_sum += swap_filled
                                spot_price = float(spot_order_info['avgPx'])
                                fee_total += float(spot_order_info['fee']) * spot_price
                                spot_notional -= spot_filled * spot_price
                                fee_total += float(swap_order_info['fee'])
                                swap_price = float(swap_order_info['avgPx'])
                                swap_notional += swap_filled * swap_price

                                # 对冲检查
                                if abs(spot_filled - swap_filled) < contract_val:
                                    target_position_prev = target_position
                                    target_position -= swap_filled
                                    fprint(lang.hedge_success, swap_filled, lang.remaining + str(target_position))
                                    mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'add',
                                              'size': target_position_prev}
                                    OP.mycol.find_one_and_update(mydict, {'$set': {'size': target_position}})
                                else:
                                    fprint(lang.hedge_fail)
                                    return filled_sum

                            usdt_balance = self.usdt_balance()
                            target_position = min(target_position, usdt_balance * leverage / (leverage + 1) / best_ask)
                            counter = 0
                        else:
                            # print("订单太小", order_size)
                            time.sleep(SLEEP)
        if spot_notional != 0:
            Ledger = record.Record('Ledger')
            timestamp = datetime.utcnow()
            mylist = []
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "现货买入",
                      'spot_notional': spot_notional}
            mylist.append(mydict)
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "合约开空",
                      'swap_notional': swap_notional}
            mylist.append(mydict)
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "手续费",
                      'fee': fee_total}
            mylist.append(mydict)
            Ledger.mycol.insert_many(mylist)

        mydict = {'account': self.accountid, 'instrument': self.coin, 'op': 'add'}
        OP.delete(mydict)
        fprint(lang.added_amount, filled_sum, self.coin)
        return filled_sum

    def open(self, usdt_size=0.0, target_size=0.0, leverage=2, price_diff=0.002, accelerate_after=0):
        """建仓期现组合

        :param usdt_size: U本位目标仓位
        :param target_size: 币本位目标仓位
        :param leverage: 杠杆
        :param price_diff: 期现差价
        :param accelerate_after: 几小时后加速
        :return: 建仓数量
        :rtype: float
        """
        Ledger = record.Record('Ledger')
        result = Ledger.find_last({'account': self.accountid, 'instrument': self.coin})
        if result and result['title'] != '平仓':
            fprint(lang.position_exist, self.swap_position(), self.coin)
        else:
            timestamp = datetime.utcnow()
            mydict = {'account': self.accountid, 'instrument': self.coin, 'timestamp': timestamp, 'title': "开仓"}
            Ledger.insert(mydict)

        usdt_balance = self.usdt_balance()
        if target_size:
            last = float(self.publicAPI.get_specific_ticker(self.spot_ID)['last'])
            usdt_size = last * target_size * (1 + 1 / leverage)
        if usdt_balance >= usdt_size:
            return self.add(usdt_size=usdt_size, leverage=leverage, price_diff=price_diff,
                            accelerate_after=accelerate_after)
        else:
            fprint(lang.insufficient_USDT)
