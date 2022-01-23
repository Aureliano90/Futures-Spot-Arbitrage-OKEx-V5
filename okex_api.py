import okex.account as account
import okex.public as public
import okex.trade as trade
from okex.exceptions import OkexException, OkexAPIException
import key
import record
from utils import *
from asyncio import create_task, gather
from websocket import subscribe, subscribe_without_login


@call_coroutine
# @debug_timer
class OKExAPI(object):
    """基本OKEx功能类
    """
    api_initiated = False
    asem = None
    psem = None
    __key = None

    @property
    def __name__(self):
        return 'OKExAPI'

    def __init__(self, coin: str = None, accountid=3):
        self.accountid = accountid

        if not OKExAPI.api_initiated:
            apikey = key.Key(accountid)
            api_key = apikey.api_key
            secret_key = apikey.secret_key
            passphrase = apikey.passphrase
            OKExAPI.__key = dict(api_key=api_key, passphrase=passphrase, secret_key=secret_key)
            if accountid == 3:
                OKExAPI.accountAPI = account.AccountAPI(api_key, secret_key, passphrase, test=True)
                OKExAPI.tradeAPI = trade.TradeAPI(api_key, secret_key, passphrase, test=True)
                OKExAPI.publicAPI = public.PublicAPI(test=True)
                OKExAPI.public_url = "wss://wspap.okx.com:8443/ws/v5/public"
                OKExAPI.private_url = "wss://wspap.okx.com:8443/ws/v5/private"
            else:
                OKExAPI.accountAPI = account.AccountAPI(api_key, secret_key, passphrase, False)
                OKExAPI.tradeAPI = trade.TradeAPI(api_key, secret_key, passphrase, False)
                OKExAPI.publicAPI = public.PublicAPI()
                OKExAPI.public_url = "wss://ws.okx.com:8443/ws/v5/public"
                OKExAPI.private_url = "wss://ws.okx.com:8443/ws/v5/private"
            OKExAPI.api_initiated = True

        self.coin = coin
        if coin:
            assert isinstance(coin, str)
            self.spot_ID = coin + '-USDT'
            self.swap_ID = coin + '-USDT-SWAP'
            self.spot_info = None
            self.swap_info = None
            self.holding = None
            self.exitFlag = False
            self.exist = True
        else:
            self.exist = False

    def __await__(self):
        """异步构造函数\n
        await OKExAPI()先召唤__init__()，然后是awaitable __await__()。

        :return: OKExAPI
        """
        if self.coin:
            try:
                self.spot_info = create_task(self.publicAPI.get_specific_instrument('SPOT', self.spot_ID))
                self.swap_info = create_task(self.publicAPI.get_specific_instrument('SWAP', self.swap_ID))
                yield from gather(self.spot_info, self.swap_info)
                self.spot_info = self.spot_info.result()
                self.swap_info = self.swap_info.result()
            except Exception as e:
                fprint(f'{self.__name__}__await__({self.coin}) error')
                fprint(e)
                self.exist = False
                fprint(lang.nonexistent_crypto.format(self.coin))
        else:
            self.exist = False
        return self

    @staticmethod
    def clean():
        if hasattr(OKExAPI, 'accountAPI'):
            OKExAPI.accountAPI.__del__()
        if hasattr(OKExAPI, 'tradeAPI'):
            OKExAPI.tradeAPI.__del__()
        if hasattr(OKExAPI, 'publicAPI'):
            OKExAPI.publicAPI.__del__()

    @staticmethod
    def set_asemaphore(sem):
        """控制并发连接
        """
        OKExAPI.asem = sem

    @staticmethod
    def set_psemaphore(sem):
        """控制并发连接
        """
        OKExAPI.psem = sem

    async def check_account_level(self):
        """检查账户模式，需开通合约交易
        """
        level = (await self.accountAPI.get_account_config())['acctLv']
        assert level != '1', lang.upgrade_account

    async def check_position_mode(self):
        """检查是否为买卖模式
        """
        mode = (await self.accountAPI.get_account_config())['posMode']
        if mode != 'net_mode':
            fprint(lang.position_mode.format(mode))
            await self.accountAPI.set_position_mode('net_mode')
            fprint(lang.change_net_mode)
        mode = (await self.accountAPI.get_account_config())['posMode']
        assert mode == 'net_mode', lang.set_mode_fail

    async def usdt_balance(self):
        """获取USDT保证金
        """
        return await self.spot_position('USDT')

    @call_coroutine
    async def spot_position(self, coin=None):
        """获取现货余额
        """
        if not coin: coin = self.coin
        data: list = (await self.accountAPI.get_coin_account(coin))['details']
        return float(data[0]['availEq']) if data else 0.

    @call_coroutine
    async def swap_holding(self, swap_ID=None):
        """获取合约持仓
        """
        # /api/v5/account/positions 限速：10次/2s
        sem = self.asem if self.asem else asyncio.Semaphore(5)
        async with sem:
            if not swap_ID: swap_ID = self.swap_ID
            try:
                result: list = await self.accountAPI.get_specific_position(swap_ID)
            except OkexAPIException:
                await asyncio.sleep(10)
                result: list = await self.accountAPI.get_specific_position(swap_ID)
            if self.asem: await asyncio.sleep(1)
            keys = ['pos', 'margin', 'last', 'avgPx', 'liqPx', 'upl', 'lever']
            for holding in result:
                if holding['mgnMode'] == 'isolated':
                    self.holding = dict([(n, float(holding[n])) if holding[n] else (n, 0.) for n in keys])
                    return self.holding
            return None

    async def swap_position(self, swap_ID=None):
        """获取合约仓位
        """
        if not swap_ID:
            swap_ID = self.swap_ID
            swap_info = self.swap_info
        else:
            try:
                swap_info = await self.publicAPI.get_specific_instrument('SWAP', swap_ID)
            except OkexException:
                return 0.
        contract_val = float(swap_info['ctVal'])
        holding = await self.swap_holding(swap_ID)
        return - holding['pos'] * contract_val if holding else 0.

    async def swap_balance(self):
        """获取占用保证金
        """
        holding = await self.swap_holding(self.swap_ID)
        return holding['margin'] if holding else 0.

    async def liquidation_price(self):
        """获取强平价
        """
        holding = await self.swap_holding()
        return holding['liqPx'] if holding else 0.

    async def get_lever(self):
        setting = await self.accountAPI.get_leverage(self.swap_ID, 'isolated')
        return float(setting['lever'])

    async def update_portfolio(self):
        Record = record.Record('Portfolio')
        holding = await self.swap_holding()
        margin = holding['margin']
        upl = holding['upl']
        last = holding['last']
        position = - holding['pos'] * float(self.swap_info['ctVal'])
        size = position * last + margin + upl
        portfolio = Record.mycol.find_one(dict(account=self.accountid, instrument=self.coin))
        portfolio['size'] = size
        Record.mycol.find_one_and_replace(dict(account=self.accountid, instrument=self.coin), portfolio)
        return portfolio

    async def add_margin(self, transfer_amount):
        """增加保证金

        :param transfer_amount: 划转金额
        :return: 是否成功
        :rtype: bool
        """
        if transfer_amount <= 0: return False
        try:
            if await self.accountAPI.adjust_margin(instId=self.swap_ID, posSide='net', type='add', amt=transfer_amount):
                fprint(lang.added_margin.format(transfer_amount))
                return True
            else:
                return False
        except OkexAPIException as e:
            fprint(e)
            fprint(lang.transfer_failed)
            if e.code == "58110": await asyncio.sleep(600)
            return False

    async def reduce_margin(self, transfer_amount):
        """减少保证金

        :param transfer_amount: 划转金额
        :return: 是否成功
        :rtype: bool
        """
        if transfer_amount <= 0: return False
        try:
            if await self.accountAPI.adjust_margin(instId=self.swap_ID, posSide='net', type='reduce',
                                                   amt=transfer_amount):
                fprint(lang.reduced_margin.format(transfer_amount))
                return True
            else:
                return False
        except OkexAPIException as e:
            fprint(e)
            fprint(lang.transfer_failed)
            if e.code == "58110": await asyncio.sleep(600)
            return False

    @staticmethod
    def _key():
        return OKExAPI.__key
