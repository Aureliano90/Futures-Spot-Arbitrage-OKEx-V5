from typing import List
from .client import Client
from .consts import *


class AssetAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test)

    def __del__(self):
        # print("AssetAPI del started")
        super().__del__()
        # print("AssetAPI del finished")

    async def get_balance(self, ccy) -> dict:
        """获取资金账户余额信息\n
        GET /api/v5/asset/balances

        :param ccy: 币种
        """
        params = {'ccy': ccy}
        return (await self._request_with_params(GET, ASSET_BALANCE, params))['data'][0]

    async def transfer(self, ccy, amt, account_from, account_to, instId='', toInstId='') -> bool:
        """资金划转\n
        POST /api/v5/asset/transfer

        :param ccy: 币种
        :param amt: 划转数量
        :param account_from: 1：币币账户 3：交割合约 5：币币杠杆账户 6：资金账户 9：永续合约账户 12：期权合约 18：统一账户
        :param account_to: 1：币币账户 3：交割合约 5：币币杠杆账户 6：资金账户 9：永续合约账户 12：期权合约 18：统一账户
        :param instId:
        :param toInstId:
        """
        params = {'ccy': ccy, 'amt': amt, 'from': account_from, 'to': account_to}
        if instId:
            params['instId'] = instId
        if toInstId:
            params['toInstId'] = toInstId
        result = await self._request_with_params(POST, ASSET_TRANSFER, params)
        if result['code'] == '0':
            return True
        else:
            print(result['msg'])
            return False

    async def get_kline(self, instId: str, bar='4H', after='', before='', limit='') -> List[dict]:
        """获取K线数据。K线数据按请求的粒度分组返回，K线数据每个粒度最多可获取最近1440条。\n
        GET /api/v5/market/candles

        :param instId: 产品ID
        :param bar: 时间粒度
        :param after: 请求此时间戳之前
        :param before: 请求此时间戳之后
        :param limit: 分页返回的结果集数量，300，不填默认返回100条
        """
        params = {'instId': instId}
        if bar:
            params['bar'] = bar
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return (await self._request_with_params(GET, GET_CANDLES, params))['data']
