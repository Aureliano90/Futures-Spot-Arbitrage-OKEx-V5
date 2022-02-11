from asyncio import gather
import close_position
import funding_rate
import monitor
import open_position
import record
import trading_data
from lang import *
from utils import *


@call_coroutine
async def monitor_all(accountid: int):
    """监控现有仓位

    :param accountid: 账号id
    """
    coinlist = await get_coinlist(accountid)
    processes = []
    # /api/v5/account/bills 限速：5次/s
    psem = multiprocessing.Semaphore(5)
    for coin in coinlist:
        await print_apy(coin, accountid)
        # 不能直接传Monitor对象
        # AsyncClient has Logger. Logger can't be pickled.
        process = multiprocessing.Process(target=monitor_one, args=(coin, accountid, psem))
        process.start()
        processes.append(process)
    for p in processes:
        p.join()


def monitor_one(coin: str, accountid: int, psem: multiprocessing.Semaphore = None):
    try:
        mon = monitor.Monitor(coin=coin, accountid=accountid)
        if psem: mon.set_psemaphore(psem)
        mon.watch()
    finally:
        trading_data.Stat.clean()
        monitor.Monitor.clean()


async def print_apy(coin: str, accountid: int):
    mon = await monitor.Monitor(coin=coin, accountid=accountid)
    fundingRate = funding_rate.FundingRate()
    aprs = gather(mon.apr(1), mon.apr(7), mon.apr())
    (current_rate, next_rate), aprs = await gather(fundingRate.current_next(mon.swap_ID), aprs)
    apys = [apy(x) for x in aprs]
    fprint(coin_current_next)
    fprint(f'{mon.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
    fprint(apr_message.format(mon.coin, *aprs))
    fprint(apy_message.format(mon.coin, *apys))


# @debug_timer
@call_coroutine
async def profit_all(accountid: int):
    """当前仓位收益

    :param accountid: 账号id
    """
    coinlist = await get_coinlist(accountid)
    for coin in coinlist:
        mon, Stat = await monitor.Monitor(coin=coin, accountid=accountid), trading_data.Stat(coin)
        gather_result = await gather(mon.apr(1), mon.apr(7), mon.apr())
        fprint(apr_message.format(coin, *gather_result))
        funding = Stat.history_funding(accountid)
        cost = Stat.history_cost(accountid)
        localtime = utc_to_local(Stat.open_time(accountid))
        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))


@call_coroutine
async def history_profit(accountid: int):
    """已平仓收益统计

    :param accountid: 账号id
    """
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    temp = [x['_id'] for x in Record.mycol.aggregate(pipeline)]
    coinlist = await get_coinlist(accountid)
    coinlist = set(temp) - set(coinlist)
    for coin in coinlist:
        Stat = await trading_data.Stat(coin)
        funding = Stat.history_funding(accountid)
        cost = Stat.history_cost(accountid)
        open_time = Stat.open_time(accountid)
        close_time = Stat.close_time(accountid)
        pipeline = [{'$match': {'account': accountid, 'instrument': coin, 'title': '平仓'}},
                    {'$sort': {'_id': -1}}, {'$limit': 1}]
        position = 0
        for x in Record.mycol.aggregate(pipeline):
            if 'position' in x: position = x['position']
        delta = (close_time - open_time).total_seconds()
        apr = 0
        if position:
            apr = (funding + cost) / position / delta * 86400 * 365
        fprint(open_close_pnl.format(coin, open_time.isoformat(timespec='minutes'),
                                     close_time.isoformat(timespec='minutes'), funding + cost, apr))


@call_coroutine
async def cumulative_profit(accountid: int):
    """全部累计收益统计

    :param accountid: 账号id
    """
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    coinlist = [x['_id'] for x in Record.mycol.aggregate(pipeline)]
    for coin in coinlist:
        Stat = await trading_data.Stat(coin)
        funding = Stat.history_funding(accountid, -1)
        cost = Stat.history_cost(accountid, -1)
        fprint(cumulative_pnl.format(coin, funding + cost))


# @debug_timer
@call_coroutine
async def back_track_all(accountid: int):
    """补录当前仓位资金费

    :param accountid: 账号id
    """
    Ledger = record.Record('Ledger')
    coinlist = await get_coinlist(accountid)
    mon = await monitor.Monitor(accountid=accountid)
    # API results
    api_ledger = await get_with_limit(mon.accountAPI.get_archive_ledger, tag='billId', max=100, limit=0,
                                      instType='SWAP', ccy='USDT', type='8')
    for coin in coinlist:
        pipeline = [{'$match': {'account': accountid, 'instrument': coin, 'title': '资金费'}}]
        # Results in DB
        db_ledger = [n for n in Ledger.mycol.aggregate(pipeline)]
        inserted = 0
        for item in api_ledger:
            if item['instId'] == coin + '-USDT-SWAP':
                realized_rate = float(item['pnl'])
                timestamp = datetime.utcfromtimestamp(float(item['ts']) / 1000)
                mydict = dict(account=accountid, instrument=coin, timestamp=timestamp, title='资金费',
                              funding=realized_rate)
                # 查重
                for n in db_ledger:
                    if n['funding'] == realized_rate:
                        if n['timestamp'] == timestamp:
                            break
                else:
                    Ledger.mycol.insert_one(mydict)
                    inserted += 1
        fprint(lang.back_track_funding.format(coin, inserted))


@call_coroutine
async def close_all(accountid: int):
    """全部平仓

    :param accountid: 账号id
    """
    processes = []
    for coin in await get_coinlist(accountid):
        process = multiprocessing.Process(target=close_one, args=(coin, accountid))
        process.start()
        processes.append(process)
    for p in processes:
        p.join()


def close_one(coin: str, accountid: int):
    fundingRate = funding_rate.FundingRate()
    Stat = trading_data.Stat(coin=coin)
    if recent := Stat.recent_close_stat(4):
        close_pd = recent['avg'] - 2 * recent['std']
        fprint(funding_close.format(coin, fundingRate.current(coin + '-USDT-SWAP'), recent['avg'], recent['std'],
                                    recent['min'], close_pd))
        reducePosition = close_position.ReducePosition(coin=coin, accountid=accountid)
        reducePosition.close(close_pd, 2)
    else:
        fprint(fetch_ticker_first)


@call_coroutine
async def get_coinlist(accountid: int):
    """当前持仓币种

    :param accountid: 账号id
    :rtype: List[str]
    """
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    coinlist = [x['_id'] for x in Record.mycol.aggregate(pipeline)]
    assert coinlist, empty_db
    mon = await monitor.Monitor(accountid=accountid)
    task_list = [mon.position_exist(n + '-USDT-SWAP') for n in coinlist]
    gather_result = await gather(*task_list)
    return [coinlist[n] for n in range(len(coinlist)) if gather_result[n]]


def main_menu(accountid: int):
    """主菜单

    :param accountid: 账号id
    """
    try:
        assert isinstance(accountid, int)
        fprint(f'{accountid=}')
        Monitor = monitor.Monitor(coin='BTC', accountid=accountid)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(gather(Monitor.check_account_level(), Monitor.check_position_mode()))
        while (command := input(main_menu_text)) != 'q':
            if command == '1':
                monitor_all(accountid)
            elif command == '2':
                crypto_menu(accountid)
            elif command == '3':
                funding_menu(accountid)
            elif command == '4':
                account_menu(accountid)
            elif command == '5':
                process = multiprocessing.Process(target=record.record_ticker)
                process.start()
                process.join(0.2)
            elif command == 'q':
                break
            else:
                print(wrong_command)
    finally:
        if 'process' in locals():
            process.kill()
        trading_data.Stat.clean()
        monitor.Monitor.clean()


def crypto_menu(accountid: int):
    loop = asyncio.get_event_loop()
    while True:
        coin = input(input_crypto).upper()
        Monitor = monitor.Monitor(coin=coin, accountid=accountid)
        if Monitor.exist:
            break
        else:
            continue

    while (command := minput(crypto_menu_text)) != 'b':
        if command == '1':
            while True:
                try:
                    usdt = float(input(input_USDT))
                    assert usdt >= 0
                except:
                    continue
                try:
                    leverage = float(input(input_leverage))
                    assert leverage > 0
                except:
                    continue
                AddPosition, Stat = loop.run_until_complete(
                    gather(open_position.AddPosition(coin=coin, accountid=accountid), trading_data.Stat(coin)))
                hours = 2
                if recent := Stat.recent_open_stat(hours):
                    open_pd = recent['avg'] + 2 * recent['std']
                    AddPosition.open(usdt_size=usdt, leverage=leverage, price_diff=open_pd, accelerate_after=hours)
                    Monitor.watch()
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == '2':
            while True:
                try:
                    usdt = float(input(input_USDT))
                    assert usdt >= 0
                except:
                    continue
                ReducePosition, Stat = loop.run_until_complete(
                    gather(close_position.ReducePosition(coin=coin, accountid=accountid), trading_data.Stat(coin)))
                hours = 2
                if recent := Stat.recent_close_stat(hours):
                    close_pd = recent['avg'] - 2 * recent['std']
                    ReducePosition.reduce(usdt_size=usdt, price_diff=close_pd, accelerate_after=hours)
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == '3':
            Monitor.watch()
        elif command == '4':
            while True:
                try:
                    leverage = float(input(input_leverage))
                    assert leverage > 0
                except:
                    continue
                AddPosition = open_position.AddPosition(coin=coin, accountid=accountid)
                AddPosition.adjust_swap_lever(leverage)
                break
        elif command == '5':
            ReducePosition, Stat = loop.run_until_complete(
                gather(close_position.ReducePosition(coin=coin, accountid=accountid), trading_data.Stat(coin)))
            hours = 2
            if recent := Stat.recent_close_stat(hours):
                close_pd = recent['avg'] - 2 * recent['std']
                ReducePosition.close(price_diff=close_pd, accelerate_after=hours)
            else:
                fprint(fetch_ticker_first)
        elif command == '6':
            if not Monitor.position_exist():
                fprint(no_position)
            else:
                task_list = [Monitor.apr(1), Monitor.apr(7), Monitor.apr()]
                aprs = loop.run_until_complete(gather(*task_list))
                apys = [apy(x) for x in aprs]
                fprint(apr_message.format(coin, *aprs))
                fprint(apy_message.format(coin, *apys))
                Stat = trading_data.Stat(coin)
                funding = Stat.history_funding(accountid)
                cost = Stat.history_cost(accountid)
                localtime = utc_to_local(Stat.open_time(accountid))
                fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))
        elif command == '7':
            while True:
                try:
                    hours = int(input(how_many_hours))
                    assert hours > 0
                except:
                    continue
                Stat = trading_data.Stat(coin)
                if Stat.recent_open_stat(hours):
                    Stat.plot(hours)
                    Stat.gaussian_dist(hours, 'o')
                    Stat.gaussian_dist(hours, 'c')
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == 'b':
            pass
        else:
            print(wrong_command)


def funding_menu(accountid: int):
    FundingRate = funding_rate.FundingRate()
    while (command := input(funding_menu_text)) != 'b':
        if command == '1':
            while True:
                try:
                    days = int(input(how_many_days))
                    assert 0 < days <= 90
                except:
                    continue
                FundingRate.show_profitable_rate(days)
                break
        elif command == '2':
            if coinlist := get_coinlist(accountid):
                FundingRate.show_selected_rate(coinlist)
            else:
                fprint(no_position)
        elif command == '3':
            FundingRate.show_current_rate()
        elif command == '4':
            while True:
                try:
                    days = int(input(how_many_days))
                    assert 0 < days <= 90
                except:
                    continue
                FundingRate.show_nday_rate(days)
                break
        elif command == '5':
            FundingRate.show_nday_rate(30)
        elif command == '6':
            FundingRate.print_30day_rate()
        elif command == 'b':
            break
        else:
            print(wrong_command)
    FundingRate.__del__()


def account_menu(accountid: int):
    loop = asyncio.get_event_loop()
    while (command := input(account_menu_text)) != 'b':
        if command == '1':
            back_track_all(accountid=accountid)
        elif command == '2':
            profit_all(accountid=accountid)
        elif command == '3':
            history_profit(accountid=accountid)
        elif command == '4':
            cumulative_profit(accountid=accountid)
        elif command == '5':
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
            delete_result = Record.mycol.delete_many(dict(account=accountid, instrument=coin))
            fprint(deleted.format(delete_result.deleted_count))
        elif command == 'b':
            break
        else:
            print(wrong_command)
