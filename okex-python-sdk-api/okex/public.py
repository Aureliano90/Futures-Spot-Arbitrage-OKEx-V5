from typing import List
from .client import Client
from .consts import *
from .exceptions import OkexAPIException
import time


class PublicAPI(Client):

    def __init__(self, use_server_time=False, test=False, first=False):
        Client.__init__(self, '', '', '', use_server_time, test, first)

    def get_instruments(self, instType: str, uly='') -> List[dict]:
        """获取所有可交易产品的信息列表\n
        GET /api/v5/public/instruments?instType=SWAP

        :param instType: SPOT：币币 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param uly: 合约标的指数
        """
        params = {'instType': instType}
        if uly:
            params['uly'] = uly
        return self._request_with_params(GET, GET_INSTRUMENTS, params)['data']

    def get_specific_instrument(self, instType, instId, uly='') -> dict:
        """获取单个可交易产品的信息\n

        :param instType: SPOT：币币 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param instId: 产品ID
        :param uly: 合约标的指数，仅适用于交割/永续/期权，期权必填
        """
        # GET /api/v5/public/instruments?instType=SWAP&instId=BTC-USDT-SWAP
        params = {'instType': instType, 'instId': instId}
        if uly:
            params['uly'] = uly
        return self._request_with_params(GET, GET_INSTRUMENTS, params)['data'][0]

    def get_funding_time(self, instId: str) -> dict:
        """获取当前资金费率\n
        GET /api/v5/public/funding-rate?instId=BTC-USD-SWAP

        :param instId: 产品ID，如 BTC-USD-SWAP
        """
        params = {'instId': instId}
        return self._request_with_params(GET, FUNDING_RATE, params)['data'][0]

    def get_historical_funding_rate(self, instId: str, after='', before='', limit='') -> List[dict]:
        """获取最近3个月的历史资金费率\n
        GET /api/v5/public/funding-rate-history?instId=BTC-USD-SWAP

        :param instId: 产品ID
        :param after: 请求此时间戳之前
        :param before: 请求此时间戳之后
        :param limit: 分页返回的结果集数量，最大为100，不填默认返回100条
        """
        params = {'instId': instId}
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return self._request_with_params(GET, FUNDING_RATE_HISTORY, params)['data']

    def get_tickers(self, instType: str, uly='') -> List[dict]:
        """获取所有产品行情信息\n
        GET /api/v5/market/tickers?instType=SWAP

        :param instType: 产品类型，SPOT：币币 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param uly: 合约标的指数
        """
        params = {'instType': instType}
        if uly:
            params['uly'] = uly
        return self._request_with_params(GET, GET_TICKERS, params)['data']

    def get_specific_ticker(self, instId: str) -> dict:
        """获取单个产品行情信息\n
        GET /api/v5/market/ticker?instId=BTC-USD-SWAP

        :param instId: 产品ID
        """
        #
        params = {'instId': instId}
        try:
            # 最小延时0.33
            # send = time.time()
            data = self._request_with_params(GET, GET_TICKER, params)['data'][0]
            # receive = time.time()
            # if receive - send > 1:
            #     print("timeout", receive - send)
            return data
        except Exception as e:
            time.sleep(60)
            print("get_ticker exception: ", e)
            return self._request_with_params(GET, GET_TICKER, params)['data'][0]
