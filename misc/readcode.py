def main():
    with open("../src/codedict.py", 'w', encoding='utf-8') as c:
        c.write(
            """from config import language

if language == 'cn':
""")
        c.write('    codes = {\n')
        with open("错误码.txt", encoding='utf-8') as f:
            for line in f.readlines():
                strings = line.split()
                l = len(strings)
                print(strings, l)
                if l >= 3:
                    if strings[-1].isnumeric() and strings[-2].isnumeric():
                        description = ''.join([strings[i] for i in range(l - 2)])
                        c.write(f"        '{strings[-1]}': '{description}',\n")
        c.write(
            """    }
else:
    codes = {
""")
        with open("error codes.txt") as f:
            for line in f.readlines():
                strings = line.split()
                l = len(strings)
                print(strings, l)
                if l >= 3:
                    if strings[-1].isnumeric() and strings[-2].isnumeric():
                        description = ' '.join([strings[i] for i in range(l - 2)])
                        c.write(f"        '{strings[-1]}': '{description}',\n")
        c.write('    }\n')


if __name__ == '__main__':
    main()
