from datetime import datetime
import json
from . import consts as c, utils, exceptions
from src.codedict import codes
import asyncio
import requests
import httpx


class Client(object):
    def __init__(self, api_key, api_secret_key, passphrase, use_server_time=False, test=False):
        self.API_KEY = api_key
        self.API_SECRET_KEY = api_secret_key
        self.PASSPHRASE = passphrase
        self.use_server_time = use_server_time
        self.test = test
        self.client = httpx.AsyncClient(base_url=c.API_URL, http2=True, follow_redirects=True)

    async def aclose(self):
        if not self.client.is_closed:
            await self.client.aclose()

    async def _get_timestamp(self):
        url = c.SERVER_TIMESTAMP_URL
        response = await self.client.get(url)
        if response.status_code == 200:
            t = datetime.utcfromtimestamp(int(response.json()['data'][0]['ts']) / 1000)
            t = t.isoformat("T", "milliseconds")
            return t + "Z"
        else:
            return ""

    async def _request(self, method, request_path, params):
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
                    timestamp = await self._get_timestamp()
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
                    try:
                        response = await self.client.get(url, headers=header)
                    except httpx.TimeoutException:
                        # timestamp = datetime.utcnow().strftime("%Y-%m-%d, %H:%M:%S.%f")
                        # print(timestamp[:len(timestamp) - 4], httpx.ReadTimeout)
                        # print(f'{request_path=}')
                        continue
                elif method == c.POST:
                    response = await self.client.post(url, data=body, headers=header)
                elif method == c.DELETE:
                    response = await self.client.delete(url, headers=header)
                else:
                    raise ValueError
            except requests.exceptions.RequestException as e:
                print(e)
                retry += 1
                await asyncio.sleep(30)
                continue
            else:
                # Cloudflare error
                if str(response.status_code).startswith('5'):
                    # print(response)
                    retry += 1
                    await asyncio.sleep(30)
                    continue
                try:
                    json_res = response.json()
                except ValueError:
                    raise exceptions.OkexRequestException(f'Invalid Response: {response.text}')
                # Endpoint request timeout
                if hasattr(json_res, 'code') and json_res['code'] == '50004':
                    retry += 1
                    await asyncio.sleep(2)
                    continue
                # Requests too frequent
                if response.status_code == 429:
                    retry += 1
                    print(request_path, codes[json_res['code']])
                    await asyncio.sleep(2)
                    continue
                success = True

        # exception handle
        if not str(response.status_code).startswith('2'):
            print(f'Client error: {request_path}')
            print(f'{response.status_code=}')
            raise exceptions.OkexAPIException(response)

        return json_res

    async def _request_without_params(self, method, request_path):
        return await self._request(method, request_path, {})

    async def _request_with_params(self, method, request_path, params):
        return await self._request(method, request_path, params)
