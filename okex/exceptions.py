from codedict import codes
# coding=utf-8


class OkexException(Exception):

    def __init__(self):
        super().__init__(self)


class OkexAPIException(OkexException):

    def __init__(self, response):
        print(f'{response.text}, {response.status_code}')
        self.code = 0
        try:
            json_res = response.json()
        except ValueError:
            self.message = f'Invalid JSON error message from OKEx: {response.text}'
        else:
            if 'code' in json_res.keys():
                self.code = json_res['code']
                self.message = codes[self.code]
            else:
                self.code = 'None'
                self.message = 'System error'

        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):  # pragma: no cover
        return f'API Request Error(error_code={self.code}): {self.message}'


class OkexRequestException(OkexException):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f'OkexRequestException: {self.message}'


class OkexParamsException(OkexException):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f'OkexParamsException: {self.message}'
