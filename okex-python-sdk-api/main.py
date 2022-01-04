import time
from datetime import datetime
import funding_rate
import open_position
import close_position
import monitor
import trading_data
import menu
import asyncio


if __name__ == '__main__':
    print(datetime.now())
    menu.main_menu(accountid=2)
    # menu.monitor_all(2)
    # menu.profit_all(2)
    # menu.close_all(2)
    # menu.back_track_all(2)
    exit()
    # asyncio.get_event_loop().run_until_complete(funding_rate.FundingRate().back_tracking())
    # add = open_position.AddPosition('ATOM', accountid=3)
    # asyncio.get_event_loop().run_until_complete(add.swap_holding())
    # res = asyncio.get_event_loop().run_until_complete(add.add(usdt_size=1000, leverage=3, price_diff=-0.02))
    # print(res)
    # reduce = close_position.ReducePosition('BTC', accountid=3)
    # res = asyncio.get_event_loop().run_until_complete(reduce.close(price_diff=0.2))
    # print(res)
