from typing import List
from .client import Client
from .consts import *
from .exceptions import OkexAPIException
import time


class AssetAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False, first=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test, first)

    def get_balance(self, ccy) -> dict:
        """获取资金账户余额信息\n
        GET /api/v5/asset/balances

        :param ccy: 币种
        """
        params = {'ccy': ccy}
        return self._request_with_params(GET, ASSET_BALANCE, params)['data'][0]

    def transfer(self, ccy, amt, account_from, account_to, instId='', toInstId=''):
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
        result = self._request_with_params(POST, ASSET_TRANSFER, params)
        if result['code'] == '0':
            return True
        else:
            print(result['msg'])
            return False
