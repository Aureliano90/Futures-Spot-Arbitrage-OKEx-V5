from .client import Client
from .consts import *


class TradeAPI(Client):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):
        Client.__init__(self, api_key, api_secret_key, passphrase, use_server_time, test)

    def __del__(self):
        # print("TradeAPI del started")
        super().__del__()
        # print("TradeAPI del finished")

    async def take_spot_order(self, instId, side, order_type, size, tgtCcy='', price='', client_oid='') -> dict:
        """币币下单：POST /api/v5/trade/order\n
        body{"instId":"BTC-USDT","tdMode":"cash","ccy":"USDT","clOrdId":"b15","side":"buy","ordType":"limit","px":"2.15","sz":"2"}

        :param instId: 产品ID
        :param side: buy：买 sell：卖
        :param order_type: market：市价单 limit：限价单 post_only：只做maker单 fok：全部成交或立即取消 ioc：立即成交并取消剩余
        :param size: 委托数量
        :param tgtCcy: 市价单委托数量的类型 base_ccy: 交易货币 ；quote_ccy：计价货币
        :param price: 委托价格
        :param client_oid: 客户自定义订单ID
        """
        params = {'instId': instId, 'tdMode': 'cash', 'side': side, 'ordType': order_type, 'sz': size, 'tgtCcy': tgtCcy,
                  'px': price, 'clOrdId': client_oid}
        order = await self._request_with_params(POST, TRADE_ORDER, params)
        if order['code'] == '0':
            return order['data'][0]
        else:
            # print(params)
            return {'ordId': '-1', 'code': order['data'][0]['sCode'], 'msg': order['data'][0]['sMsg']}

    async def take_margin_order(self, instId, side, order_type, size, price='', client_oid='',
                                reduceOnly=False) -> dict:
        """币币杠杆下单：POST /api/v5/trade/order\n
        body{"instId":"BTC-USDT","tdMode":"cross","ccy":"USDT","clOrdId":"b15","side":"buy","ordType":"limit","px":"2.15","sz":"2"}

        :param instId: 产品ID
        :param side: buy：买 sell：卖
        :param order_type: market：市价单 limit：限价单 post_only：只做maker单 fok：全部成交或立即取消 ioc：立即成交并取消剩余
        :param size: 委托数量
        :param price: 委托价格
        :param client_oid: 客户自定义订单ID
        :param reduceOnly: 只减仓
        """
        params = {'instId': instId, 'tdMode': 'cross', 'ccy': 'USDT', 'side': side, 'ordType': order_type, 'sz': size,
                  'px': price, 'clOrdId': client_oid, 'reduceOnly': reduceOnly}
        order = await self._request_with_params(POST, TRADE_ORDER, params)
        if order['code'] == '0':
            return order['data'][0]
        else:
            # print(params)
            return {'ordId': '-1', 'code': order['data'][0]['sCode'], 'msg': order['data'][0]['sMsg']}

    async def take_swap_order(self, instId, side, order_type, size, price='', client_oid='', reduceOnly=False) -> dict:
        """合约下单: POST /api/v5/trade/order\n
        body{"instId":"BTC-USDT-SWAP","tdMode":"isolated","ccy":"USDT","clOrdId":"b15","side":"buy","ordType":"limit","px":"2.15","sz":"2"}

        :param instId: 产品ID
        :param side: buy：买 sell：卖
        :param order_type: market：市价单 limit：限价单 post_only：只做maker单 fok：全部成交或立即取消 ioc：立即成交并取消剩余
        :param size: 委托数量
        :param price: 委托价格
        :param client_oid: 客户自定义订单ID
        :param reduceOnly: 只减仓
        """
        params = {'instId': instId, 'tdMode': 'isolated', 'ccy': 'USDT', 'side': side, 'ordType': order_type,
                  'sz': size, 'px': price, 'clOrdId': client_oid, 'reduceOnly': reduceOnly}
        order = await self._request_with_params(POST, TRADE_ORDER, params)
        if order['code'] == '0':
            return order['data'][0]
        else:
            # print(params)
            return {'ordId': '-1', 'code': order['data'][0]['sCode'], 'msg': order['data'][0]['sMsg']}

    async def get_order_info(self, instId, order_id='', client_oid='') -> dict:
        """获取订单信息\n
        GET /api/v5/trade/order?ordId=2510789768709120&instId=BTC-USDT

        :param instId:
        :param order_id:
        :param client_oid:
        """
        if order_id:
            params = {'ordId': order_id, 'instId': instId}
            return (await self._request_with_params(GET, TRADE_ORDER, params))['data'][0]
        elif client_oid:
            params = {'clOrdId': order_id, 'instId': client_oid}
            return (await self._request_with_params(GET, TRADE_ORDER, params))['data'][0]
