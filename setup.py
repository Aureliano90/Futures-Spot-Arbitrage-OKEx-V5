from setuptools import setup, find_packages

setup(
    name='Futures-Spot-Arbitrage-OKEx-V5',
    version='0.95.1',
    packages=find_packages(),
    url='https://github.com/Aureliano90/Futures-Spot-Arbitrage-OKEx-V5',
    license='GNU Affero General Public License v3.0',
    author='Aureliano',
    author_email='81753529+Aureliano90@users.noreply.github.com',
    description='',
    python_requires=">=3.8",
    install_requires=['requests~=2.27.1',
                      'httpcore~=0.14.5',
                      'httpx[http2]~=0.22.0',
                      'pymongo~=4.0.1',
                      'matplotlib~=3.5.1',
                      'numpy~=1.22.1',
                      'websockets~=10.1'],
    entry_points={
            'console_scripts':
                'ok = main:main'
            },
)
