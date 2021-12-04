from datetime import datetime
import funding_rate
import open_position
import close_position
import monitor
import trading_data
from log import fprint
import record
import multiprocessing
import command
from lang import *

if __name__ == '__main__':
    print(datetime.now())
    process = multiprocessing.Process(target=record.record_ticker)
    process.start()
    command.get_command(3)
    # command.monitor_all(2)
    # command.open_diff_all(2)
    # command.close_diff_all(2)
    # command.back_track_all(2)
    exit()

    coin = 'TORN'  # BADGER, BTT, CFX, CRO, DORA, LON, MIR, SWRV, TORN, XEM
    spot_ID = coin + '-USDT'
    swap_ID = coin + '-USDT-SWAP'

    account = 2
    Monitor = monitor.Monitor(coin=coin, accountid=account)
    AddPosition = open_position.AddPosition(coin=coin, accountid=account)
    ReducePosition = close_position.ReducePosition(coin=coin, accountid=account)
    FundingRate = funding_rate.FundingRate()
    Stat = trading_data.Stat(coin)

    # FundingRate.show_selected_rate(coinlist)
    # FundingRate.store()
    # fprint('{:.3%}'.format(FundingRate.current(swap_ID)))
    # fprint('{:.3%}'.format(FundingRate.next(swap_ID)))
    # FundingRate.show_profitable_rate(0.0004, 7)
    # FundingRate.show_current_rate()
    # FundingRate.show_7day_rate()
    # FundingRate.show_30day_rate()
    # FundingRate.print_30day_rate()
    # exit()

    # 获取近期开仓期现差价
    hours = 2
    recent = Stat.recent_open_stat(hours)
    open_pd = recent['avg'] + 2 * recent['std']
    fprint("{:6s} Funding Rate: {:7.3%}, Open Avg: {:7.3%}, Std: {:7.3%}, Max: {:7.3%}, 2 Sigma: {:7.3%}"
           .format(coin, FundingRate.current(swap_ID), recent['avg'], recent['std'], recent['max'], open_pd))
    # Stat.plot(hours)

    # print(AddPosition.max_buy_size())
    # AddPosition.open(usdt_size=100, leverage=3, price_diff=open_pd, accelerate_after=2)
    # AddPosition.add(usdt_size=130, leverage=3, price_diff=open_pd, accelerate_after=2)
    # AddPosition.add(target_size=150, leverage=3, price_diff=open_pd, accelerate_after=2)
    # print(AddPosition.usdt_balance())
    # print(AddPosition.spot_balance())
    # print(AddPosition.spot_position())
    # print(AddPosition.swap_position())
    # fprint(coin, "Hedged:", AddPosition.is_hedged())
    # exit()

    # 获取近期平仓期现差价
    recent = Stat.recent_close_stat(hours)
    close_pd = recent['avg'] - 2 * recent['std']
    # fprint("{:6s} Funding Rate: {:7.3%}, Close Avg: {:7.3%}, Std: {:7.3%}, Min: {:7.3%}, 2 Sigma: {:7.3%}"
    #        .format(coin, FundingRate.current(swap_ID), recent['avg'], recent['std'], recent['min'], close_pd))
    # ReducePosition.reduce(usdt_size=100, price_diff=close_pd, accelerate_after=2)
    # ReducePosition.reduce(target_size=1, price_diff=0.001, accelerate_after=2)
    # ReducePosition.close(price_diff=close_pd, accelerate_after=2)

    # print('{:.3%}'.format(float(Monitor.accountAPI.get_trade_fee(instType='SPOT', instId=spot_ID)['taker'])))
    # print('{:.3%}'.format(float(Monitor.accountAPI.get_trade_fee(instType='SWAP', uly=spot_ID)['taker'])))
    # fprint("APR: {:.2%}".format(Stat.apr()))
    # fprint("APY: {:.2%}".format(Stat.apy()))
    # Monitor.show_pd()
    # Monitor.rebalance(4)
    # Monitor.back_tracking()
    # Monitor.watch()
