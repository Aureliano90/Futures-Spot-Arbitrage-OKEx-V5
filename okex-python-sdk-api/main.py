from datetime import datetime
import funding_rate
import open_position
import close_position
import monitor
import trading_data
import command
import asyncio


if __name__ == '__main__':
    print(datetime.now())
    command.get_command(accountid=3)
    # command.monitor_all(2)
    # command.profit_all(2)
    # command.close_all(2)
    # command.back_track_all(2)
    # asyncio.get_event_loop().run_until_complete(funding_rate.FundingRate().back_tracking())
    exit()
