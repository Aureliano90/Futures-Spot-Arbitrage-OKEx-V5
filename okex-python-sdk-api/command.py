from datetime import timezone
import funding_rate
import monitor
import open_position
import close_position
import trading_data
import record
import multiprocessing
from log import fprint
from lang import *
import asyncio
from asyncio import gather


# 监控
async def monitor_all(accountid: int):
    processes = []
    coinlist = await get_coinlist(accountid)
    for n in coinlist:
        await print_apy(n, accountid)
        # 不能直接传Monitor对象
        process = multiprocessing.Process(target=monitor_one, args=(n, accountid))
        process.start()
        processes.append(process)
    for n in processes:
        n.join()


def monitor_one(coin: str, accountid: int):
    mon = monitor.Monitor(coin=coin, accountid=accountid)
    asyncio.get_event_loop().run_until_complete(mon.watch())


async def print_apy(coin: str, accountid: int):
    mon = await monitor.Monitor(coin=coin, accountid=accountid)
    fundingRate = funding_rate.FundingRate()
    current_rate, next_rate = await fundingRate.current_next(mon.swap_ID)
    fprint(coin_current_next)
    fprint('{:6s}{:9.3%}{:11.3%}'.format(mon.coin, current_rate, next_rate))
    gather_result = await gather(mon.apr(1), mon.apr(7), mon.apr(), mon.apy(1), mon.apy(7), mon.apy())
    fprint(apr_message.format(mon.coin, *gather_result[0:3]))
    fprint(apy_message.format(mon.coin, *gather_result[3:6]))


# 收益统计
async def profit_all(accountid: int):
    coinlist = await get_coinlist(accountid)
    for coin in coinlist:
        mon, Stat = await gather(monitor.Monitor(coin=coin, accountid=accountid), trading_data.Stat(coin))
        gather_result = await gather(mon.apy(1), mon.apy(7), mon.apy())
        fprint(apy_message.format(coin, *gather_result))
        funding = Stat.history_funding(accountid)
        cost = Stat.history_cost(accountid)
        localtime = Stat.open_time(accountid).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))


# 补录资金费
async def back_track_all(accountid: int):
    coinlist = await get_coinlist(accountid)
    sem = asyncio.Semaphore(5)
    task_list = []
    for n in coinlist:
        mon = await monitor.Monitor(coin=n, accountid=accountid)
        task_list.append(mon.back_tracking(sem))
    await gather(*task_list)


# 平仓
async def close_all(accountid: int):
    fundingRate = funding_rate.FundingRate()
    processes = []
    coinlist = await get_coinlist(accountid)
    for n in coinlist:
        Stat, reducePosition = await gather(trading_data.Stat(coin=n),
                                            close_position.ReducePosition(coin=n, accountid=accountid))
        recent = Stat.recent_close_stat(4)
        if recent:
            close_pd = recent['avg'] - 2 * recent['std']
            fprint(funding_close.format(n, await fundingRate.current(n + '-USDT-SWAP'), recent['avg'], recent['std'],
                                        recent['min'], close_pd))
        else:
            fprint(fetch_ticker_first)
            break
        process = multiprocessing.Process(target=reducePosition.close, args=(close_pd, 2))
        process.start()
        processes.append(process)
    for n in processes:
        n.join()


# 当前持仓币种
async def get_coinlist(accountid: int):
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    temp = []
    for x in Record.mycol.aggregate(pipeline):
        temp.append(x['_id'])
    mon = await monitor.Monitor(accountid=accountid)
    task_list = []
    swap_list = [n + '-USDT-SWAP' for n in temp]
    for n in swap_list:
        task_list.append(mon.position_exist(n))
    gather_result = await gather(*task_list)
    result = []
    for n in range(len(swap_list)):
        if gather_result[n]:
            result.append(swap_list[n][:swap_list[n].find('-')])
    return result


def get_command(accountid: int):
    command = ''
    while command != 'q':
        command = input(main_menu)
        loop = asyncio.get_event_loop()
        if command == '1':
            Monitor = monitor.Monitor(coin='BTC', accountid=accountid)
            loop.run_until_complete(gather(Monitor.check_account_level(), Monitor.check_position_mode()))
            del Monitor
            loop.run_until_complete(monitor_all(accountid))

        elif command == '2':
            while True:
                coin = input(input_crypto).upper()
                Monitor = monitor.Monitor(coin=coin, accountid=accountid)
                loop.run_until_complete(gather(Monitor.check_account_level(), Monitor.check_position_mode()))
                if Monitor.exist:
                    command = input(coin_menu)
                    break
                else:
                    continue

            while command != 'b':
                if command == '1':
                    while True:
                        try:
                            usdt = float(input(input_USDT))
                        except:
                            continue
                        AddPosition = open_position.AddPosition(coin=coin, accountid=accountid)
                        hours = 2
                        Stat = trading_data.Stat(coin)
                        recent = Stat.recent_open_stat(hours)
                        if recent:
                            open_pd = recent['avg'] + 2 * recent['std']
                            loop.run_until_complete(
                                AddPosition.open(usdt_size=usdt, leverage=3, price_diff=open_pd,
                                                 accelerate_after=hours))
                        else:
                            fprint(fetch_ticker_first)
                        break
                elif command == '2':
                    while True:
                        try:
                            usdt = float(input(input_USDT))
                        except:
                            continue
                        ReducePosition = close_position.ReducePosition(coin=coin, accountid=accountid)
                        hours = 2
                        Stat = trading_data.Stat(coin)
                        recent = Stat.recent_close_stat(hours)
                        if recent:
                            close_pd = recent['avg'] - 2 * recent['std']
                            loop.run_until_complete(
                                ReducePosition.reduce(usdt_size=usdt, price_diff=close_pd, accelerate_after=hours))
                        else:
                            fprint(fetch_ticker_first)
                        break
                elif command == '3':
                    ReducePosition = close_position.ReducePosition(coin=coin, accountid=accountid)
                    hours = 2
                    Stat = trading_data.Stat(coin)
                    recent = Stat.recent_close_stat(hours)
                    if recent:
                        close_pd = recent['avg'] - 2 * recent['std']
                        loop.run_until_complete(
                            ReducePosition.close(price_diff=close_pd, accelerate_after=hours))
                    else:
                        fprint(fetch_ticker_first)
                elif command == '4':
                    if not loop.run_until_complete(Monitor.position_exist()):
                        fprint(no_position)
                    else:
                        task_list = [Monitor.apy(1), Monitor.apy(7), Monitor.apy()]
                        gather_result = loop.run_until_complete(gather(*task_list))
                        fprint(apy_message.format(coin, *gather_result))
                        Stat = trading_data.Stat(coin)
                        funding = Stat.history_funding(accountid)
                        cost = Stat.history_cost(accountid)
                        localtime = Stat.open_time(accountid).replace(tzinfo=timezone.utc).astimezone().replace(
                            tzinfo=None)
                        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))
                elif command == '5':
                    while True:
                        try:
                            hours = int(input(how_many_hours))
                        except:
                            continue
                        Stat = trading_data.Stat(coin)
                        Stat.plot(hours)
                        break
                elif command == 'b':
                    pass
                else:
                    print(wrong_command)
                command = input(coin_menu)

        elif command == '3':
            FundingRate = funding_rate.FundingRate()
            command = input(funding_menu)
            while command != 'b':
                if command == '1':
                    while True:
                        try:
                            days = int(input(how_many_days))
                        except:
                            continue
                        loop.run_until_complete(FundingRate.show_profitable_rate(days))
                        break
                elif command == '2':
                    coinlist = loop.run_until_complete(get_coinlist(accountid))
                    if coinlist:
                        loop.run_until_complete(FundingRate.show_selected_rate(coinlist))
                    else:
                        fprint(no_position)
                elif command == '3':
                    loop.run_until_complete(FundingRate.show_current_rate())
                elif command == '4':
                    fprint(funding_7day)
                    loop.run_until_complete(FundingRate.show_nday_rate(7))
                elif command == '5':
                    fprint(funding_30day)
                    loop.run_until_complete(FundingRate.show_nday_rate(30))
                elif command == 'b':
                    break
                else:
                    print(wrong_command)
                command = input(funding_menu)

        elif command == '4':
            command = input(account_menu)
            while command != 'b':
                if command == '1':
                    loop.run_until_complete(back_track_all(accountid=accountid))
                elif command == '2':
                    loop.run_until_complete(profit_all(accountid=accountid))
                elif command == 'b':
                    break
                else:
                    print(wrong_command)
                command = input(account_menu)

        elif command == '5':
            process = multiprocessing.Process(target=record.record_ticker)
            process.start()
            process.join(0.1)

        elif command == 'q':
            break
        else:
            print(wrong_command)
