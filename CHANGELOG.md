# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.95.0] - February 2nd, 2022

### Changed
* Translated error codes.
* Improved robustness.
* Improved output format.

### Removed
* Duplicate code.

## [0.94.3] - January 26rd, 2022

### Changed
* Minor change to client.
* Updated `setup.py` and `requirements.txt`.

## [0.94.2] - January 25rd, 2022

### Changed
* Rolled back URLs.
* Updated `setup.py` and `requirements.txt`.

## [0.94.1] - January 25rd, 2022

### Fixed
* Minor bugs.

### Added
* More statistics and plots for the premium of futures.

## [0.94.0] - January 23rd, 2022

First metastable release.

### Changed

* Updated `setup.py` and `requirements.txt`.
* Rewrote client APIs and updated URLs.
* Removed redundant client connections by class attributes.
* Cleaned up syntax.

### Fixed
* Order size precision control.

### Added
* Methods to abort program safely.
* Assertions to avoid boundary conditions.
* An experimental function.

## [0.9.0] - January 6th, 2022

### Changed

* Optimized leverage control by distinguishing between actual leverage and notional leverage on the exchange.
* Corrected margin calculation.
* Simplified syntax using f-strings, ternary operator, walrus operator and list comprehension.

### Added

* Debug and timing decorator `@debug_timer`.
* Decorator `@call_coroutine` to call `coro(*args, **kwargs)` in normal context and `await coro(*args, **kwargs)` in async context.
* `setup.py`

## [0.8.1] - December 29th, 2021

### Changed

* Proper `AsyncClient` closure.
* `Semaphore` to avoid API speeding.

## [0.8.0] - December 27th, 2021

### Changed

* Rewrote menu module.
* Optimized funding fee backtracking.
* Changed `multiprocessing` in position monitor to `asyncio`.

### Added

* `websocket` integrated by `AsyncGenerator`.

## [0.7.0] December 25th, 2021

### Changed

* Overhauled with `asyncio` and parallelized Web IOs.

### Added

* Asyncio implementation.
* HTTP/2.
* `__await__` attribute to initiate class instances asynchronously.

### Removed

* Multithreading.
* V3 APIs.

## [0.2.1] - December 16th, 2021

### Changed

* Control flow.

## [0.2.0] - November 6th, 2021

### Added

* Bilingual support with `gettext`.

## [0.1.0] - May 12th, 2021

### Added

* Position opening, closing and monitoring.
* MongoDB integration.
* Funding rate statistics.
* API exceptions handling.
* Command line interface.

## [0.0.1] - April 1th, 2021

### Added

* Funding rates processing.

