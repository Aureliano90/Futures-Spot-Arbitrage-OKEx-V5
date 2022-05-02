from src.close_position import ReducePosition
from src.funding_rate import FundingRate
from src.monitor import Monitor
from src.open_position import AddPosition
from src.trading_data import Stat
from src.okex_api import *
from src.lang import *
from src.utils import *
import src.record as record

loop = asyncio.get_event_loop()


async def monitor_all(accountid: int):
    """监控现有仓位

    :param accountid: 账号id
    """
    for coin in await get_coinlist(accountid):
        await print_apy(coin, accountid)
        mon = await Monitor(coin=coin, accountid=accountid)
        await mon.watch()


async def print_apy(coin: str, accountid: int):
    mon = await Monitor(coin=coin, accountid=accountid)
    fundingRate = FundingRate()
    aprs = gather(mon.apr(1), mon.apr(7), mon.apr())
    (current_rate, next_rate), aprs = await gather(fundingRate.current_next(mon.swap_ID), aprs)
    apys = map(apy, aprs)
    fprint(coin_current_next)
    fprint(f'{mon.coin:6s}{current_rate:9.3%}{next_rate:11.3%}')
    fprint(apr_message.format(mon.coin, *aprs))
    fprint(apy_message.format(mon.coin, *apys))


# @debug_timer
async def profit_all(accountid: int):
    """当前仓位收益

    :param accountid: 账号id
    """
    coinlist = await get_coinlist(accountid)
    for coin in coinlist:
        stat = Stat(coin)
        mon = await Monitor(coin=coin, accountid=accountid)
        gather_result = await gather(mon.apr(1), mon.apr(7), mon.apr())
        fprint(apr_message.format(coin, *gather_result))
        funding = stat.history_funding(accountid)
        cost = stat.history_cost(accountid)
        localtime = utc_to_local(stat.open_time(accountid))
        fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))


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
        stat = Stat(coin)
        funding = stat.history_funding(accountid)
        cost = stat.history_cost(accountid)
        open_time = stat.open_time(accountid)
        close_time = stat.close_time(accountid)
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


async def cumulative_profit(accountid: int):
    """全部累计收益统计

    :param accountid: 账号id
    """
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    coinlist = [x['_id'] for x in Record.mycol.aggregate(pipeline)]
    for coin in coinlist:
        stat = Stat(coin)
        funding = stat.history_funding(accountid, -1)
        cost = stat.history_cost(accountid, -1)
        fprint(cumulative_pnl.format(coin, funding + cost))


# @debug_timer
async def back_track_all(accountid: int):
    """补录当前仓位资金费

    :param accountid: 账号id
    """
    Ledger = record.Record('Ledger')
    coinlist = await get_coinlist(accountid)
    mon = await Monitor(accountid=accountid)
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
        fprint(back_track_funding.format(coin, inserted))


async def close_all(accountid: int):
    """全部平仓

    :param accountid: 账号id
    """
    fundingRate = FundingRate()
    for coin in await get_coinlist(accountid):
        stat = Stat(coin=coin)
        if recent := stat.recent_close_stat(4):
            close_pd = recent['avg'] - 2 * recent['std']
            fprint(funding_close.format(coin, await fundingRate.current(coin + '-USDT-SWAP'),
                                        recent['avg'], recent['std'], recent['min'], close_pd))
            reducePosition = await ReducePosition(coin=coin, accountid=accountid)
            await reducePosition.close(close_pd, 2)
        else:
            fprint(fetch_ticker_first)


async def import_position(accountid: int, coin: str):
    while True:
        try:
            leverage = float(await ainput(loop, input_leverage))
            assert leverage > 0
        except:
            continue
        timestamp = datetime.utcnow()
        mydict = dict(account=accountid, instrument=coin, timestamp=timestamp, title='开仓')
        record.Record('Ledger').insert(mydict)
        record.Record('Portfolio').mycol.insert_one(dict(account=accountid, instrument=coin, leverage=leverage))
        addPosition = await AddPosition(coin=coin, accountid=accountid)
        await addPosition.adjust_swap_lever(leverage)
        fprint(imported)
        break


async def get_coinlist(accountid: int):
    """当前持仓币种

    :param accountid: 账号id
    :rtype: List[str]
    """
    Record = record.Record('Ledger')
    pipeline = [{'$match': {'account': accountid}},
                {'$group': {'_id': '$instrument'}}]
    coinlist = [x['_id'] for x in Record.mycol.aggregate(pipeline)]
    if not coinlist:
        fprint(empty_db, end='')
        while True:
            command = await ainput(loop, import_or_not)
            if command == 'y':
                coin, _ = await get_crypto(accountid)
                await import_position(accountid, coin)
            else:
                break

    mon = await Monitor(accountid=accountid)
    task_list = [mon.position_exist(n + '-USDT-SWAP') for n in coinlist]
    gather_result = await gather(*task_list)
    return [coinlist[n] for n in range(len(coinlist)) if gather_result[n]]


@call_coroutine
async def main_menu(accountid: int):
    """主菜单

    :param accountid: 账号id
    """
    try:
        assert isinstance(accountid, int)
        fprint(f'{accountid=}')
        while (command := await ainput(loop, main_menu_text)) != 'q':
            if command == '1':
                _ = await Monitor(coin='BTC', accountid=accountid)
                await gather(_.check_account_level(), _.check_position_mode())
                await monitor_all(accountid)
                await asyncio.sleep(2)
            elif command == '2':
                await crypto_menu(accountid)
            elif command == '3':
                await funding_menu(accountid)
            elif command == '4':
                await account_menu(accountid)
            elif command == '5':
                process = multiprocessing.Process(target=record.record_ticker)
                process.start()
                process.join(0.2)
            elif command == '6':
                await manager.menu()
            elif command == 'q':
                break
            else:
                print(wrong_command)
        await manager.stop()
    finally:
        if 'process' in locals():
            process.kill()
        await Stat.aclose()
        await Monitor.aclose()
        await FundingRate.aclose()


async def get_crypto(accountid: int) -> tuple[str, Monitor]:
    while True:
        coin = (await ainput(loop, input_crypto)).upper()
        mon = await Monitor(coin=coin, accountid=accountid)
        if mon.exist:
            break
        else:
            continue
    return coin, mon


async def crypto_menu(accountid: int):
    coin, mon = await get_crypto(accountid)
    await gather(mon.check_account_level(), mon.check_position_mode())
    while (command := await ainput(loop, crypto_menu_text)) != 'b':
        if command == '1':
            while True:
                try:
                    usdt = float(await ainput(loop, input_USDT))
                    assert usdt >= 0
                except:
                    continue
                try:
                    leverage = float(await ainput(loop, input_leverage))
                    assert leverage > 0
                except:
                    continue
                addPosition = await AddPosition(coin=coin, accountid=accountid)
                stat = Stat(coin)
                hours = 2
                if recent := stat.recent_open_stat(hours):
                    open_pd = recent['avg'] + 2 * recent['std']
                    await addPosition.open(usdt_size=usdt, leverage=leverage, price_diff=open_pd,
                                           accelerate_after=hours)
                    await mon.watch()
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == '2':
            while True:
                try:
                    usdt = float(await ainput(loop, input_USDT))
                    assert usdt >= 0
                except:
                    continue
                reducePosition = await ReducePosition(coin=coin, accountid=accountid)
                stat = Stat(coin)
                hours = 2
                if recent := stat.recent_close_stat(hours):
                    close_pd = recent['avg'] - 2 * recent['std']
                    await reducePosition.reduce(usdt_size=usdt, price_diff=close_pd, accelerate_after=hours)
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == '3':
            await mon.watch()
        elif command == '4':
            while True:
                try:
                    leverage = float(await ainput(loop, input_leverage))
                    assert leverage > 0
                except:
                    continue
                addPosition = await AddPosition(coin=coin, accountid=accountid)
                await addPosition.adjust_swap_lever(leverage)
                break
        elif command == '5':
            reducePosition = await ReducePosition(coin=coin, accountid=accountid)
            stat = Stat(coin)
            hours = 2
            if recent := stat.recent_close_stat(hours):
                close_pd = recent['avg'] - 2 * recent['std']
                await reducePosition.close(price_diff=close_pd, accelerate_after=hours)
            else:
                fprint(fetch_ticker_first)
        elif command == '6':
            if not await mon.position_exist():
                fprint(no_position)
            else:
                task_list = [mon.apr(1), mon.apr(7), mon.apr()]
                aprs = await gather(*task_list)
                apys = map(apy, aprs)
                fprint(apr_message.format(coin, *aprs))
                fprint(apy_message.format(coin, *apys))
                stat = Stat(coin)
                funding = stat.history_funding(accountid)
                cost = stat.history_cost(accountid)
                localtime = utc_to_local(stat.open_time(accountid))
                fprint(open_time_pnl.format(localtime.isoformat(timespec='minutes'), funding + cost))
        elif command == '7':
            while True:
                try:
                    hours = int(await ainput(loop, how_many_hours))
                    assert hours > 0
                except:
                    continue
                stat = Stat(coin)
                if stat.recent_open_stat(hours):
                    stat.plot(hours)
                    stat.gaussian_dist(hours, 'o')
                    stat.gaussian_dist(hours, 'c')
                else:
                    fprint(fetch_ticker_first)
                break
        elif command == '8':
            await import_position(accountid, coin)
        elif command == 'b':
            pass
        else:
            print(wrong_command)


async def funding_menu(accountid: int):
    fundingRate = FundingRate()
    while (command := await ainput(loop, funding_menu_text)) != 'b':
        if command == '1':
            while True:
                try:
                    days = int(await ainput(loop, how_many_days))
                    assert 0 < days <= 90
                except:
                    continue
                await fundingRate.show_profitable_rate(days)
                break
        elif command == '2':
            if coinlist := await get_coinlist(accountid):
                await fundingRate.show_selected_rate(coinlist)
            else:
                fprint(no_position)
        elif command == '3':
            await fundingRate.show_current_rate()
        elif command == '4':
            while True:
                try:
                    days = int(await ainput(loop, how_many_days))
                    assert 0 < days <= 90
                except:
                    continue
                await fundingRate.show_nday_rate(days)
                break
        elif command == '5':
            await fundingRate.show_nday_rate(30)
        elif command == '6':
            await fundingRate.print_30day_rate()
        elif command == 'b':
            break
        else:
            print(wrong_command)


async def account_menu(accountid: int):
    while (command := await ainput(loop, account_menu_text)) != 'b':
        if command == '1':
            await back_track_all(accountid=accountid)
        elif command == '2':
            await profit_all(accountid=accountid)
        elif command == '3':
            await history_profit(accountid=accountid)
        elif command == '4':
            await cumulative_profit(accountid=accountid)
        elif command == '5':
            coin = (await ainput(loop, input_crypto)).upper()
            mon = await Monitor(coin=coin, accountid=accountid)
            if mon.exist:
                existed, swap_position = await gather(mon.position_exist(), mon.swap_position())
                if existed:
                    fprint(position_exist.format(swap_position, coin))
                    command = await ainput(loop, delete_anyway)
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
