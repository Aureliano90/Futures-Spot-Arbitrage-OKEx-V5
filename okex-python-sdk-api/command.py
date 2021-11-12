from datetime import timezone
import funding_rate
import monitor
import open_position
import close_position
import trading_data
import record
import threading
import multiprocessing
from log import fprint
from lang import *


# 监控
def monitor_all(accountid=2):
    processes = []
    fundingRate = funding_rate.FundingRate()
    for n in get_coinlist(accountid):
        mon = monitor.Monitor(coin=n, accountid=accountid)
        process = multiprocessing.Process(target=mon.watch)
        process.start()
        processes.append(process)

        current_rate = fundingRate.current(mon.swap_ID)
        next_rate = fundingRate.next(mon.swap_ID)
        fprint(coin_current_next)
        fprint('{:6s}{:9.3%}{:11.3%}'.format(mon.coin, current_rate, next_rate))
        fprint(apr_message.format(n, mon.apr(1), mon.apr(7), mon.apr()))
        fprint(apy_message.format(n, mon.apy(1), mon.apy(7), mon.apy()))
    for n in processes:
        n.join()


# 收益统计
def profit_all(accountid=2):
    for coin in get_coinlist(accountid):
        mon = monitor.Monitor(coin=coin, accountid=accountid)
        fprint(apy_message.format(coin, mon.apy(1), mon.apy(7), mon.apy()))
        Stat = trading_data.Stat(coin)
        funding = Stat.history_funding(accountid)
        cost = Stat.history_cost(accountid)
        localtime = Stat.open_time(accountid).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))


# 补录资金费
def back_track_all(accountid=2):
    processes = []
    for n in get_coinlist(accountid):
        mon = monitor.Monitor(coin=n, accountid=accountid)
        process = multiprocessing.Process(target=mon.back_tracking)
        process.start()
        processes.append(process)
    for n in processes:
        n.join()


# 平仓
def close_all(accountid=2):
    fundingRate = funding_rate.FundingRate()
    processes = []
    for n in get_coinlist(accountid):
        mon = monitor.Monitor(coin=n, accountid=accountid)
        if not mon.position_exist():
            continue
        stat = trading_data.Stat(coin=n)
        reducePosition = close_position.ReducePosition(coin=n, accountid=accountid)
        recent = stat.recent_close_stat(4)
        close_pd = recent['avg'] - 2 * recent['std']
        fprint(funding_close.format(n, fundingRate.current(n + '-USDT-SWAP'), recent['avg'], recent['std'],
                                    recent['min'], close_pd))
        process = multiprocessing.Process(target=reducePosition.close, args=(close_pd, 2))
        process.start()
        processes.append(process)
    for n in processes:
        n.join()


# 当前持仓币种
def get_coinlist(account=2):
    Record = record.Record('Ledger')
    pipeline = [
        {
            '$match': {
                'account': account
            }
        }, {
            '$group': {
                '_id': '$instrument'
            }
        }
    ]
    temp = []
    result = []
    for x in Record.mycol.aggregate(pipeline):
        temp.append(x['_id'])
    for n in temp:
        mon = monitor.Monitor(coin=n, accountid=account)
        if not mon.position_exist():
            continue
        result.append(n)
    return result


def get_command(account=1):
    command = input(main_menu)
    while command != 'q':
        if command == '1':
            thread = threading.Thread(target=record.record_ticker)
            thread.start()
            monitor_all(account)
        elif command == '2':
            coin = input(input_crypto)
            Monitor = monitor.Monitor(coin=coin, accountid=account)
            Monitor.check_account_level()
            Monitor.check_position_mode()
            if Monitor.exist:
                command = input(coin_menu)
            else:
                continue
            if command == '1':
                usdt = float(input(input_USDT))
                AddPosition = open_position.AddPosition(coin=coin, accountid=account)
                hours = 2
                Stat = trading_data.Stat(coin)
                recent = Stat.recent_open_stat(hours)
                open_pd = recent['avg'] + 2 * recent['std']
                AddPosition.open(usdt_size=usdt, leverage=3, price_diff=open_pd, accelerate_after=hours)
                if AddPosition.is_hedged():
                    fprint(coin, hedge_success)
                else:
                    fprint(coin, hedge_fail)
            elif command == '2':
                usdt = float(input(input_USDT))
                ReducePosition = close_position.ReducePosition(coin=coin, accountid=account)
                hours = 2
                Stat = trading_data.Stat(coin)
                recent = Stat.recent_close_stat(hours)
                close_pd = recent['avg'] - 2 * recent['std']
                ReducePosition.reduce(usdt_size=usdt, price_diff=close_pd, accelerate_after=hours)
            elif command == '3':
                ReducePosition = close_position.ReducePosition(coin=coin, accountid=account)
                hours = 2
                Stat = trading_data.Stat(coin)
                recent = Stat.recent_close_stat(hours)
                close_pd = recent['avg'] - 2 * recent['std']
                ReducePosition.close(price_diff=close_pd, accelerate_after=hours)
            elif command == '4':
                if not Monitor.position_exist():
                    fprint(no_position)
                else:
                    fprint(apy_message.format(coin, Monitor.apy(1), Monitor.apy(7), Monitor.apy()))
                    Stat = trading_data.Stat(coin)
                    funding = Stat.history_funding(account)
                    cost = Stat.history_cost(account)
                    localtime = Stat.open_time(account).replace(tzinfo=timezone.utc).astimezone().replace(
                        tzinfo=None)
                    fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))
            elif command == 'b':
                pass
            else:
                print(wrong_command)
        elif command == '3':
            FundingRate = funding_rate.FundingRate()
            command = input(funding_menu)
            while command != 'b':
                if command == '1':
                    days = int(input(how_many_days))
                    FundingRate.show_profitable_rate(days)
                elif command == '2':
                    FundingRate.show_selected_rate(get_coinlist(account))
                elif command == '3':
                    FundingRate.show_7day_rate()
                elif command == '4':
                    FundingRate.show_30day_rate()
                elif command == 'b':
                    break
                else:
                    print(wrong_command)
                command = input(funding_menu)
        elif command == '4':
            command = input(account_menu)
            while command != 'b':
                if command == '1':
                    back_track_all(accountid=account)
                elif command == '2':
                    profit_all(accountid=account)
                elif command == '3':
                    coin = input(input_crypto)
                    Stat = trading_data.Stat(coin)
                    if Stat.exist:
                        hours = int(input(how_many_hours))
                        Stat.plot(hours)
                    else:
                        continue
                elif command == 'b':
                    break
                else:
                    print(wrong_command)
                command = input(account_menu)
        elif command == 'q':
            exit()
        else:
            print(wrong_command)
        command = input(main_menu)
