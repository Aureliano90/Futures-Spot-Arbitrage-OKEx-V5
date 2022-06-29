import hmac
import base64
import datetime
from . import consts as c


def sign(message, secret_key):
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d)


def pre_hash(timestamp, method, request_path, body):
    return f'{timestamp}{str.upper(method)}{request_path}{body}'


def get_header(api_key, header_sign, timestamp, passphrase):
    return {
        c.CONTENT_TYPE: c.APPLICATION_JSON,
        c.OK_ACCESS_KEY: api_key,
        c.OK_ACCESS_SIGN: header_sign,
        c.OK_ACCESS_TIMESTAMP: str(timestamp),
        c.OK_ACCESS_PASSPHRASE: passphrase
    }


def parse_params_to_str(params):
    return '?' + '&'.join([f'{key}={value}' for key, value in params.items()])


def get_timestamp():
    now = datetime.datetime.utcnow()
    t = now.isoformat('T', 'milliseconds')
    return t + 'Z'


def signature(timestamp, method, request_path, body, secret_key):
    if str(body) == '{}' or str(body) == 'None':
        body = ''
    message = str(timestamp) + str.upper(method) + request_path + str(body)
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d)
