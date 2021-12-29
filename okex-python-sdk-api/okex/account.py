from typing import List
from .client import Client
from .consts import *


class AccountAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test)

    def __del__(self):
        # print("AccountAPI del started")
        super().__del__()
        # print("AccountAPI del finished")

    async def get_account_config(self) -> dict:
        """查看当前账户的配置信息\n
        GET /api/v5/account/config
        """
        return (await self.async_request_without_params(GET, ACCOUNT_CONFIG))['data'][0]

    async def set_position_mode(self, posMode) -> dict:
        """设置持仓模式\n
        POST /api/v5/account/set-position-mode

        :param posMode: 持仓方式 long_short_mode：双向持仓 net_mode：单向持仓
        """
        params = {'posMode': posMode}
        return (await self.async_request_with_params(POST, POSITION_MODE, params))['data'][0]

    async def get_positions(self, instType='', posId='') -> List[dict]:
        """查看持仓信息

        :param instType: MARGIN：币币杠杆 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param posId: 持仓ID，支持多个posId查询（不超过20个），逗号分割
        """
        params = {}
        if instType:
            params = {'instType': instType}
        elif posId:
            params = {'posId': posId}
        return (await self.async_request_with_params(GET, ACCOUNT_POSITION, params))['data']

    async def get_specific_position(self, instId: str) -> List[dict]:
        """查看持仓信息\n
        GET /api/v5/account/positions?instId=BTC-USDT

        :param instId: 产品ID
        """
        params = {'instId': instId}
        return (await self.async_request_with_params(GET, ACCOUNT_POSITION, params))['data']

    async def get_account_balance(self) -> dict:
        """获取账户中所有资产余额\n
        GET /api/v5/account/balance
        """
        return (await self.async_request_without_params(GET, ACCOUNT_BALANCE))['data'][0]

    async def get_coin_account(self, currency) -> dict:
        """获取账户中单币种余额\n
        GET /api/v5/account/balance?ccy=BTC,ETH

        :param currency: 币种，如 BTC，支持多币种查询（不超过20个），币种之间逗号分隔
        """
        params = {'ccy': currency}
        return (await self.async_request_with_params(GET, ACCOUNT_BALANCE, params))['data'][0]

    async def get_trade_fee(self, instType, instId='', uly='', category='') -> dict:
        """获取当前账户交易手续费费率\n
        GET /api/v5/account/trade-fee?instType=SPOT&instId=BTC-USDT

        :param instType: SPOT：币币 MARGIN：币币杠杆 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param instId: 产品ID，仅适用于instType为币币/币币杠杆
        :param uly: 合约标的指数，仅适用于instType为交割/永续/期权
        :param category: 手续费档位
        :return:
        """
        # 获取币币BTC-USDT交易手续费率
        # GET /api/v5/account/trade-fee?instType=SPOT&instId=BTC-USDT
        params = {'instType': instType}
        if instId:
            params['instId'] = instId
        elif uly:
            params['uly'] = uly
        elif category:
            params['category'] = category
        return (await self.async_request_with_params(GET, TRADE_FEE, params))['data'][0]

    async def get_leverage(self, instId, mgnMode) -> dict:
        """获取杠杆倍数\n
        GET /api/v5/account/leverage-info

        :param instId: 产品ID
        :param mgnMode: 保证金模式 isolated：逐仓 cross：全仓
        """
        params = {'instId': instId, 'mgnMode': mgnMode}
        return (await self.async_request_with_params(GET, GET_LEVERAGE, params))['data'][0]

    async def set_leverage(self, lever, mgnMode, instId='', ccy='') -> dict:
        """设置杠杆倍数\n
        POST /api/v5/account/set-leverage

        :param instId: 产品ID：币对、合约
        :param ccy: 保证金币种
        :param lever: 杠杆倍数
        :param mgnMode: isolated：逐仓 cross：全仓
        """
        if instId:
            params = {'instId': instId, 'lever': lever, 'mgnMode': mgnMode}
        else:
            params = {'ccy': ccy, 'lever': lever, 'mgnMode': mgnMode}
        return (await self.async_request_with_params(POST, SET_LEVERAGE, params))['data'][0]

    async def get_max_size(self, instId, tdMode, ccy='') -> dict:
        """获取最大可买卖/开仓数量\n
        GET /api/v5/account/max-size

        :param instId: 产品ID
        :param tdMode: 交易模式 cross：全仓 isolated：逐仓 cash：非保证金
        :param ccy: 保证金币种
        """
        params = {'instId': instId, 'tdMode': tdMode}
        if ccy:
            params['ccy'] = ccy
        return (await self.async_request_with_params(GET, MAX_SIZE, params))['data'][0]

    async def get_ledger(self, instType, ccy, mgnMode='', ctType='', type='', subType='', after='', before='', limit=''):
        """账单流水查询\n
        GET /api/v5/account/bills

        :param instType: 产品类型 SPOT：币币 MARGIN：币币杠杆 SWAP：永续合约 FUTURES：交割合约 OPTION：期权
        :param ccy: 币种
        :param mgnMode: 仓位类型 isolated：逐仓 cross：全仓
        :param ctType: linear： 正向合约 inverse： 反向合约
        :param type: 账单类型 1：划转 2：交易 3：交割 4：强制换币 5：强平 6：保证金划转 7：扣息 8：资金费 9：自动减仓 10：穿仓代偿
        :param subType: 账单子类型
        :param after: 请求此id之前
        :param before: 请求此id之后
        :param limit: 分页返回的结果集数量，最大为100，不填默认返回100条
        :rtype: List[dict]
        """
        params = {'instType': instType, 'ccy': ccy}
        if mgnMode:
            params['mgnMode'] = mgnMode
        if ctType:
            params['ctType'] = ctType
        if type:
            params['type'] = type
        if subType:
            params['subType'] = subType
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if limit:
            params['limit'] = limit
        return (await self.async_request_with_params(GET, GET_LEDGER, params))['data']

    async def adjust_margin(self, instId, posSide, type, amt):
        """增加或者减少逐仓保证金\n
        POST /api/v5/account/position/margin-balance

        :param instId: 产品ID
        :param posSide: 持仓方向 long：双向持仓多头 short：双向持仓空头 net：单向持仓
        :param type: add：增加 reduce：减少
        :param amt: 增加或减少的保证金数量
        :rtype: bool
        """
        params = {'instId': instId, 'posSide': posSide, 'type': type, 'amt': amt}
        result = await self.async_request_with_params(POST, MARGIN_BALANCE, params)
        if result['code'] == '0':
            return True
        else:
            print(result['msg'])
            return False
