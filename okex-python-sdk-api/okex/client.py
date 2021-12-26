from datetime import datetime
import requests
import json
from . import consts as c, utils, exceptions
import time
import asyncio
import httpx


class Client(object):

    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):

        self.API_KEY = api_key
        self.API_SECRET_KEY = api_secret_key
        self.PASSPHRASE = passphrase
        self.use_server_time = use_server_time
        self.test = test
        self.client = httpx.Client(base_url=c.API_URL, http2=True)
        self.aclient = httpx.AsyncClient(base_url=c.API_URL, http2=True)

    def __del__(self):
        # print("Client del started")
        self.client.close()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.aclient.aclose())
        else:
            loop.run_until_complete(self.aclient.aclose())
        # print("Client del finished")

    def update_limits(self, limits: httpx.Limits = None):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.aclient.aclose())
        else:
            loop.run_until_complete(self.aclient.aclose())
        del self.aclient
        if limits:
            self.aclient = httpx.AsyncClient(base_url=c.API_URL, http2=True, limits=limits)
        else:
            self.aclient = httpx.AsyncClient(base_url=c.API_URL, http2=True)

    def _get_timestamp(self):
        url = c.SERVER_TIMESTAMP_URL
        response = self.client.get(url)
        if response.status_code == 200:
            t = datetime.utcfromtimestamp(int(response.json()['data'][0]['ts']) / 1000)
            t = t.isoformat("T", "milliseconds")
            return t + "Z"
        else:
            return ""

    async def async_request(self, method, request_path, params):
        if method == c.GET:
            request_path = request_path + utils.parse_params_to_str(params)
        # url
        url = request_path

        success = False
        retry = 0
        # 处理网络异常
        while not success and retry < 120:
            try:
                # sign & header
                if self.use_server_time:
                    # 获取服务器时间
                    timestamp = self._get_timestamp()
                else:
                    # 获取本地时间
                    timestamp = utils.get_timestamp()

                body = json.dumps(params) if method == c.POST else ""
                sign = utils.sign(utils.pre_hash(timestamp, method, request_path, str(body)), self.API_SECRET_KEY)
                header = utils.get_header(self.API_KEY, sign, timestamp, self.PASSPHRASE)

                if self.test:
                    header['x-simulated-trading'] = '1'

                # send request
                if method == c.GET:
                    response = await self.aclient.get(url, headers=header)
                elif method == c.POST:
                    response = await self.aclient.post(url, data=body, headers=header)
                elif method == c.DELETE:
                    response = await self.aclient.delete(url, headers=header)
                else:
                    raise ValueError

            except requests.exceptions.RequestException as e:
                print(e)
                retry += 1
                time.sleep(30)

            # Cloudflare error
            if str(response.status_code).startswith('5'):
                # print(response)
                retry += 1
                time.sleep(30)
            else:
                success = True

        # exception handle
        if not str(response.status_code).startswith('2'):
            print('client.py error')
            print("response.status_code: ", response.status_code)
            raise exceptions.OkexAPIException(response)

        try:
            return response.json()
        except ValueError:
            raise exceptions.OkexRequestException('Invalid Response: %s' % response.text)

    async def async_request_without_params(self, method, request_path):
        return await self.async_request(method, request_path, {})

    async def async_request_with_params(self, method, request_path, params):
        return await self.async_request(method, request_path, params)

    # def _request(self, method, request_path, params):
    #     if method == c.GET:
    #         request_path = request_path + utils.parse_params_to_str(params)
    #     # url
    #     url = request_path
    #
    #     response = None
    #     success = False
    #     retry = 0
    #     # 处理网络异常
    #     while not success and retry < 120:
    #         try:
    #             # sign & header
    #             if self.use_server_time:
    #                 # 获取服务器时间
    #                 timestamp = self._get_timestamp()
    #             else:
    #                 # 获取本地时间
    #                 timestamp = utils.get_timestamp()
    #
    #             body = json.dumps(params) if method == c.POST else ""
    #             sign = utils.sign(utils.pre_hash(timestamp, method, request_path, str(body)), self.API_SECRET_KEY)
    #             header = utils.get_header(self.API_KEY, sign, timestamp, self.PASSPHRASE)
    #
    #             if self.test:
    #                 header['x-simulated-trading'] = '1'
    #
    #             # send request
    #             if method == c.GET:
    #                 response = self.client.get(url, headers=header)
    #             elif method == c.POST:
    #                 response = self.client.post(url, data=body, headers=header)
    #             elif method == c.DELETE:
    #                 response = self.client.delete(url, headers=header)
    #             else:
    #                 raise ValueError
    #
    #         except requests.exceptions.RequestException as e:
    #             # print(e)
    #             retry += 1
    #             time.sleep(30)
    #
    #         # Cloudflare error
    #         if str(response.status_code).startswith('5'):
    #             # print(response)
    #             retry += 1
    #             time.sleep(30)
    #         else:
    #             success = True
    #
    #     # exception handle
    #     if not str(response.status_code).startswith('2'):
    #         print('client.py error')
    #         print("response.status_code: ", response.status_code)
    #         raise exceptions.OkexAPIException(response)
    #
    #     try:
    #         return response.json()
    #     except ValueError:
    #         raise exceptions.OkexRequestException('Invalid Response: %s' % response.text)

    # def _request_without_params(self, method, request_path):
    #     return self._request(method, request_path, {})
    #
    # def _request_with_params(self, method, request_path, params):
    #     return self._request(method, request_path, params)
