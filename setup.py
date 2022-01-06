from setuptools import setup, find_packages

setup(
    name='Futures-Spot-Arbitrage-OKEx-V5',
    version='0.9',
    packages=find_packages(),
    url='https://github.com/Aureliano90/Futures-Spot-Arbitrage-OKEx-V5',
    license='GNU Affero General Public License v3.0',
    author='Aureliano',
    author_email='81753529+Aureliano90@users.noreply.github.com',
    description='',
    python_requires=">=3.8",
    install_requires=['requests~=2.26.0',
                      'httpx~=0.18.2',
                      'pymongo~=4.0.1',
                      'matplotlib~=3.5.1',
                      'websockets~=10.1'],
    entry_points={
            'console_scripts': [
                'ok = okex-python-sdk-api.main:main'
            ]
        },
)
