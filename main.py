from src import menu
from src.utils import *
import sys

assert sys.version_info >= (3, 8), print('Python version >=3.8 is required.\nYour Python version: ', sys.version)


def main():
    print(datetime_str(datetime.now()))
    menu.main_menu(accountid=1)


if __name__ == '__main__':
    main()
