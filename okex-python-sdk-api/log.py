from datetime import datetime

logfile = open("log.txt", "a", encoding="utf-8")


def fprint(*args):
    print(*args)
    print(datetime.now(), end='    ', file=logfile)
    print(*args, file=logfile, flush=True)

