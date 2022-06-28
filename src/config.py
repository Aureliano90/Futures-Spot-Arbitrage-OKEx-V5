import os

# 中文输出
language = 'cn'


# English support
# language = 'en'


class Key:

    def __init__(self, account=1):
        if account == 1:
            self.api_key = os.environ['OKX_API_KEY']
            self.secret_key = os.environ['OKX_SECRET_KEY']
            self.passphrase = os.environ['OKX_PASSPHRASE']
        elif account == 2:
            self.api_key = ""
            self.secret_key = ""
            self.passphrase = ""
        # For testnet
        elif account == 3:
            self.api_key = os.environ['OKX_TEST_API_KEY']
            self.secret_key = os.environ['OKX_TEST_SECRET_KEY']
            self.passphrase = os.environ['OKX_TEST_PASSPHRASE']
        else:
            import src.lang
            print(src.lang.nonexistent_account)
            exit()
