from .client import Client
from .consts import *
from src.codedict import codes
from src.utils import REST_Semaphore


class AssetAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test)

    ASSET_BALANCE_SEMAPHORE = REST_Semaphore(6, 1)

    async def get_balance(self, ccy) -> dict:
        """获取资金账户余额信息

        GET /api/v5/asset/balances 限速： 6次/s

        :param ccy: 币种，支持多币种查询（不超过20个），币种之间半角逗号分隔
        """
        if not type(ccy) is str:
            assert len(ccy) <= 10
            ccy = ','.join(ccy)
        params = dict(ccy=ccy)
        async with AssetAPI.ASSET_BALANCE_SEMAPHORE:
            res = await self._request_with_params(GET, ASSET_BALANCE, params)
        assert res['code'] == '0', f"{ASSET_BALANCE}, msg={codes[res['code']]}"
        return res['data'][0]

    ASSET_TRANSFER_SEMAPHORE = dict()

    async def transfer(self, ccy, amt, account_from, account_to, instId='', toInstId='') -> bool:
        """资金划转

        POST /api/v5/asset/transfer

        限速： 1 次/s 限速规则：UserID + Currency

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
        if ccy not in AssetAPI.ASSET_TRANSFER_SEMAPHORE.keys():
            AssetAPI.ASSET_TRANSFER_SEMAPHORE[ccy] = REST_Semaphore(1, 1)
        async with AssetAPI.ASSET_TRANSFER_SEMAPHORE[ccy]:
            res = await self._request_with_params(POST, ASSET_TRANSFER, params)
        if res['code'] == '0':
            return True
        else:
            print(f"{ASSET_TRANSFER}, msg={codes[res['code']]}")
            return False
