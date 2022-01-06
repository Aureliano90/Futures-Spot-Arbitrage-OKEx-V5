# Futures-Spot-Arbitrage-OKEx-V5

## Introduction

An object-oriented program for arbitrage between perpetual futures and spot on OKEx using V5 API. Written in April for
my personal use. Functional and stable enough for me. Modified and
optimized [OKEx V3 API SDK](https://github.com/okex/V3-Open-API-SDK)
according to [V5 API documentation](https://www.okex.com/docs-v5/en).

Chinese and English support, completed with annotations and docstrings.

## Features

* Interactive command line menu;
* Sort and output historical funding rates over a given period;
* Analyze historical funding rates and volatility (taken as [NATR](https://www.macroption.com/normalized-atr/)) to find
  most profitable underlying for arbitrage;
* Open a position by longing spot and shorting perpetual futures equally and simultaneously
    * Use historical tickers and statistics to open position when futures have max premium, on the basis that the
      premium over a period of time satisfies Gaussian distribution;
    * Accelerate when a desired premium does not appear by given time;
* Close a position by selling spot and closing short on perpetual futures
    * Use historical tickers and statistics to close position when futures have max discount;
    * Accelerate when a desired discount does not appear by given time;
    * Proactively close a position when the predicted funding rate is low enough such that it is better off to reopen
      later;
* Monitor existing positions
    * Sell spot and close short to add margin when price rises to avoid liquidation;
    * Reduce margin to buy spot and open short when price drops to maintain exposure;
* Precise order size control and leverage management;
* Store tickers, funding rates, portfolio and transactions in MongoDB;
* Calculate current and historical PnL, APR and APY;
* Plot the distribution of premium/discount for an underlying over a given period.

## Features may be added

* Typical arbitrage of perpetual futures and spot is passively receiving funding fees while keeping the position open.
  However it is profitable to proactively close a portion of the position when the futures premium surges and reopen it
  later when the premium subdues.
* The program does not interact when opening, closing or monitoring positions.
* If the program is killed when opening or closing positions, the operation will not resume. Could make it continue
  operation.

## Optimizations

Implemented asyncio and websocket. Web IOs are parallelized where possible. AsyncClient is initialzed as a class member
instead of Context Manager to avoid constantly creating and killing sessions which has non-negligible overheads. Special
care was taken for proper client closure. Semaphores are used where necessary to control concurrent API access.
Websocket is used to fetch real time price feed. Websocket streaming functions are used as AsyncGenerators for elegant
integration.

Classes are given `__await__` attribute where necessary and can be initialized asynchronously.
Decorator `@call_coroutine`
was created to call coroutines directly in normal context instead of `loop.run_until_complete(coro)`. So simply
call `coro` in normal context and `await coro` in async context.

## Installation

Install Python 3.8+ and required packages.

`pip install -r requirements.txt`

Install [MongoDB](https://www.mongodb.com/try/download/community).

Paste API keys in key.py (use account 3 for demo trading).

Un-annotate "lang_en.install()" in lang.py for English support.

Simply run main.py.

## Background

Futures spot arbitrage in crypto is profitable because there is a huge demand for long leverage in the crypto market.
Arbitrageurs act as the counterparty to buyers in the perpetual swap market. They effectively multiply and transfer the
buying pressure in the perpetual swap market to the spot market. Leverage comes at a cost. Therefore arbitrageurs or
market makers are entitled to charge interest on futures buyers, just like stockbrokers charge interest for margin. As a
result the APY depends on the market sentiment, ranging from 10% to 100%+.

## Disclaimer

The author does not assume responsibilities for the use of this program, nor is warranty granted.

## Reference

[1] [OKEx V5 API](https://www.okex.com/docs-v5/en)

[2] [Cryptocurrency Spot-Futures Arbitrage Strategy Report](https://www.okex.com/academy/en/spot-futures-arbitrage-strategy-report-2)

[3] [Alternative Opportunities In Crypto Space: Spot-Futures Arbitrage](https://seekingalpha.com/article/4410256-alternative-opportunities-in-crypto-spot-futures-arbitrage)
