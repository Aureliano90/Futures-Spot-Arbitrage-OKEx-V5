from setuptools import setup, find_packages

setup(
    name='Futures-Spot-Arbitrage-OKEx-V5',
    version='0.100.0',
    packages=find_packages(),
    url='https://github.com/Aureliano90/Futures-Spot-Arbitrage-OKEx-V5',
    license='GNU Affero General Public License v3.0',
    author='Aureliano',
    author_email='shuhui.1990+@gmail.com',
    description='',
    python_requires=">=3.8",
    install_requires=[
        'aiohttp[speedups]~=3.8.4',
        'aiostream~=0.4.5',
        'pymongo~=4.6.0',
        'python-dotenv~=1.0.0',
        'matplotlib~=3.8.1',
        'numpy~=1.26.1',
        'websockets~=11.0.3'],
    entry_points={
        'console_scripts':
            'ok = main:main'
    },
)
