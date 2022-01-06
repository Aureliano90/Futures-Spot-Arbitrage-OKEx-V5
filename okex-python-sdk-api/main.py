import funding_rate
import open_position
import close_position
import monitor
import trading_data
import menu
from utils import *
import sys

if sys.version_info < (3, 8):
    print('Python version >=3.8 is required.')
    print('Your Python version: ', sys.version)


@call_coroutine
async def async_init():
    stat = await trading_data.Stat('BTC')
    print(trading_data.Stat)
    print(f'{stat.__name__}({stat.coin}), {stat}, {stat.__doc__}')
    add = await open_position.AddPosition('BTC', 3)
    print(open_position.AddPosition)
    print(f'{add.__name__}({add.coin}), {add}, {add.__doc__}')


def main():
    print(datetime.now())
    menu.main_menu(accountid=2)
    # menu.monitor_all(2)
    # menu.profit_all(2)
    # menu.close_all(2)
    # menu.back_track_all(2)
    exit()
    # async_init()
    # funding_rate.FundingRate().back_tracking()
    # add = open_position.AddPosition('ATOM', accountid=3)
    # res = add.swap_holding()
    # res = add.open(usdt_size=1000, leverage=3, price_diff=-0.02)
    # reduce = close_position.ReducePosition('BTC', accountid=3)
    # res = reduce.close(price_diff=0.2)
    # print(res)


if __name__ == '__main__':
    main()
