# 中文输出
language = 'cn'


# English support
# language = 'en'


class Key:

    def __init__(self, account=1):
        if account == 1:
            self.api_key = ""
            self.secret_key = ""
            self.passphrase = ""
        elif account == 2:
            self.api_key = ""
            self.secret_key = ""
            self.passphrase = ""
        # For testnet
        elif account == 3:
            self.api_key = ""
            self.secret_key = ""
            self.passphrase = ""
        else:
            import src.lang
            print(src.lang.nonexistent_account)
            exit()
