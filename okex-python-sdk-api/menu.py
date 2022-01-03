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
    # /api/v5/account/bills 限速：5次/s
    sem = multiprocessing.Semaphore(5)
    coinlist = await get_coinlist(accountid)
    for n in coinlist:
        await print_apy(n, accountid)
        # 不能直接传Monitor对象
        process = multiprocessing.Process(target=monitor_one, args=(n, accountid, sem))
        process.start()
        processes.append(process)
    for n in processes:
        n.join()


def monitor_one(coin: str, accountid: int, sem=None):
    mon = monitor.Monitor(coin=coin, accountid=accountid)
    if sem:
        mon.set_psemaphore(sem)
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
        gather_result = await gather(mon.apr(1), mon.apr(7), mon.apr())
        fprint(apy_message.format(coin, *gather_result))
        funding = Stat.history_funding(accountid)
        cost = Stat.history_cost(accountid)
        localtime = Stat.open_time(accountid).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))


# 历史收益统计
async def history_profit(accountid: int):
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    temp = []
    for x in Record.mycol.aggregate(pipeline):
        temp.append(x['_id'])
    coinlist = await get_coinlist(accountid)
    coinlist = set(temp) - set(coinlist)
    while True:
        try:
            coin = coinlist.pop()
            Stat = await trading_data.Stat(coin)
            funding = Stat.history_funding(accountid)
            cost = Stat.history_cost(accountid)
            open_time = Stat.open_time(accountid)
            close_time = Stat.close_time(accountid)
            Stat.__del__()
            pipeline = [{'$match': {'account': accountid, 'instrument': coin, 'title': "平仓"}},
                        {'$sort': {'_id': -1}}, {'$limit': 1}]
            position = 0
            for x in Record.mycol.aggregate(pipeline):
                if 'position' in x:
                    position = x['position']
            delta = close_time.__sub__(open_time).total_seconds()
            apr = 0
            if position:
                apr = (funding + cost) / position / delta * 86400 * 365
            fprint(open_close_pnl.format(coin, open_time.isoformat(timespec='minutes'),
                                         close_time.isoformat(timespec='minutes'), funding + cost, apr))
        except KeyError:
            break


# 补录资金费
async def back_track_all(accountid: int):
    coinlist = await get_coinlist(accountid)
    # /api/v5/account/bills-archive 限速：5次/2s
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
    coinlist = []
    for x in Record.mycol.aggregate(pipeline):
        coinlist.append(x['_id'])
    # print(temp)
    mon = await monitor.Monitor(accountid=accountid)
    # /api/v5/account/positions 限速：10次/2s
    mon.set_asemaphore(asyncio.Semaphore(10))
    task_list = []
    swap_list = [n + '-USDT-SWAP' for n in coinlist]
    for n in swap_list:
        task_list.append(mon.position_exist(n))
    gather_result = await gather(*task_list)
    result = []
    for n in range(len(coinlist)):
        if gather_result[n]:
            result.append(coinlist[n])
    return result


def main_menu(accountid: int):
    command = ''
    while command != 'q':
        command = input(main_menu_text)
        loop = asyncio.get_event_loop()
        if command == '1':
            Monitor = monitor.Monitor(coin='BTC', accountid=accountid)
            loop.run_until_complete(gather(Monitor.check_account_level(), Monitor.check_position_mode()))
            del Monitor
            loop.run_until_complete(monitor_all(accountid))
        elif command == '2':
            crypto_menu(accountid)
        elif command == '3':
            funding_menu(accountid)
        elif command == '4':
            account_menu(accountid)
        elif command == '5':
            process = multiprocessing.Process(target=record.record_ticker)
            process.start()
            process.join(0.1)
        elif command == 'q':
            break
        else:
            print(wrong_command)


def crypto_menu(accountid: int):
    command = ''
    loop = asyncio.get_event_loop()
    while True:
        coin = input(input_crypto).upper()
        Monitor = monitor.Monitor(coin=coin, accountid=accountid)
        loop.run_until_complete(gather(Monitor.check_account_level(), Monitor.check_position_mode()))
        if Monitor.exist:
            command = input(crypto_menu_text)
            break
        else:
            Monitor.__del__()
            continue

    while command != 'b':
        if command == '1':
            while True:
                try:
                    usdt = float(input(input_USDT))
                except:
                    continue
                try:
                    leverage = float(input(input_leverage))
                except:
                    continue
                AddPosition = open_position.AddPosition(coin=coin, accountid=accountid)
                hours = 2
                Stat = trading_data.Stat(coin)
                recent = Stat.recent_open_stat(hours)
                if recent:
                    open_pd = recent['avg'] + 2 * recent['std']
                    loop.run_until_complete(
                        AddPosition.open(usdt_size=usdt, leverage=leverage, price_diff=open_pd,
                                         accelerate_after=hours))
                    # loop.run_until_complete(Monitor.watch())
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
            process = multiprocessing.Process(target=monitor_one, args=(coin, accountid))
            process.start()
            process.join(0.1)
        elif command == '4':
            while True:
                try:
                    leverage = float(input(input_leverage))
                except:
                    continue
                AddPosition = open_position.AddPosition(coin=coin, accountid=accountid)
                loop.run_until_complete(AddPosition.adjust_swap_lever(leverage))
                break
        elif command == '5':
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
        elif command == '6':
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
        elif command == '7':
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
        command = input(crypto_menu_text)


def funding_menu(accountid: int):
    loop = asyncio.get_event_loop()
    FundingRate = funding_rate.FundingRate()
    command = input(funding_menu_text)
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
        command = input(funding_menu_text)


def account_menu(accountid: int):
    command = ''
    loop = asyncio.get_event_loop()
    while command != 'b':
        command = input(account_menu_text)
        if command == '1':
            loop.run_until_complete(back_track_all(accountid=accountid))
        elif command == '2':
            loop.run_until_complete(profit_all(accountid=accountid))
        elif command == '3':
            loop.run_until_complete(history_profit(accountid=accountid))
        elif command == '4':
            coin = input(input_crypto).upper()
            Monitor = monitor.Monitor(coin=coin, accountid=accountid)
            if Monitor.exist:
                existed, swap_position = loop.run_until_complete(
                    gather(Monitor.position_exist(), Monitor.swap_position()))
                if existed:
                    fprint(position_exist.format(swap_position, coin))
                    command = input(delete_anyway)
                    if command == 'y':
                        pass
                    else:
                        continue
            Record = record.Record('Ledger')
            filter = {'account': accountid, 'instrument': coin}
            delete_result = Record.mycol.delete_many(filter)
            fprint(deleted.format(delete_result.deleted_count))
        elif command == 'b':
            break
        else:
            print(wrong_command)
