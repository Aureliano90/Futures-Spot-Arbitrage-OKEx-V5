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

        :param ccy: 币种，支持多币种查询（不超过20个），币种之间半角逗号分隔
        """
        if not type(ccy) is str:
            assert len(ccy) <= 10
            ccy = ','.join(ccy)
        params = dict(ccy=ccy)
        res = await self._request_with_params(GET, ASSET_BALANCE, params)
        assert res['code'] == '0', f"/api/v5/asset/balances, msg={res['msg']}"
        return res['data'][0]

    async def transfer(self, ccy, amt, account_from, account_to, instId='', toInstId='') -> bool:
        """资金划转\n
        POST /api/v5/asset/transfer

        :param ccy: 币种
        :param amt: 划转数量
        :param account_from: 转出账户 6：资金账户 18：统一账户
        :param account_to: 转入账户 6：资金账户 18：统一账户
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

    async def get_kline(self, instId: str, bar='4H', after='', before='', limit='') -> List[List]:
        """获取K线数据。K线数据按请求的粒度分组返回，K线数据每个粒度最多可获取最近1440条。\n
        GET /api/v5/market/candles

        :param instId: 产品ID
        :param bar: 时间粒度, [1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M/3M/6M/1Y]
        :param after: 请求此时间戳之前
        :param before: 请求此时间戳之后
        :param limit: 分页返回的结果集数量，最大为300，不填默认返回100条
        """
        params = dict(instId=instId, bar=bar, after=after, before=before, limit=limit)
        res = await self._request_with_params(GET, GET_CANDLES, params)
        assert res['code'] == '0', f"/api/v5/market/candles, msg={res['msg']}"
        return res['data']

    async def history_kline(self, instId: str, bar='4H', after='', before='', limit='') -> List[List]:
        """获取最近几年的历史k线数据\n
        GET /api/v5/market/history-candles

        :param instId: 产品ID
        :param bar: 时间粒度, [1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M/3M/6M/1Y]
        :param after: 请求此时间戳之前
        :param before: 请求此时间戳之后
        :param limit: 分页返回的结果集数量，最大为100，不填默认返回100条
        """
        params = dict(instId=instId, bar=bar, after=after, before=before, limit=limit)
        res = await self._request_with_params(GET, HISTORY_CANDLES, params)
        assert res['code'] == '0', f"/api/v5/market/history-candles, msg={res['msg']}"
        return res['data']
