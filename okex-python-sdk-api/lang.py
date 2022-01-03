import gettext
import os

APP_NAME = "main"
LOCALE_DIR = os.path.abspath("locale")
currentDir = os.path.dirname(os.path.realpath(__file__))
lang_zh_CN = gettext.translation(APP_NAME, LOCALE_DIR, ["zh_CN"])
lang_en = gettext.translation(APP_NAME, LOCALE_DIR, ["en"])

# 中文输出
lang_zh_CN.install()
# English support
# lang_en.install()

input_USDT = _('Input USDT\n')
# "输入USDT数量\n"

input_leverage = _('Input leverage\n')
# "输入杠杆大小\n"

input_crypto = _('Input crypto\n')
# "输入币种\n"

hedge_success = _('Successfully hedged')
# "成功对冲"

hedge_fail = _('{:s} hedging failed.\n Spot: {:f}\n Swap: {:f}')
# "{:s}对冲失败。\n 现货：{:f}\n 合约：{:f}"

no_position = _('Position does not exist.')
# "没有仓位"

apr_message = _('{:6s} Today\'s APR: {:.2%}, 7 day APR: {:.2%}, overall APR: {:.2%}')
# "{:6s}今日APR: {:.2%}，7日APR: {:.2%}，累计APR: {:.2%}"

apy_message = _('{:6s} Today\'s APY: {:.2%}, 7 day APY: {:.2%}, overall APY: {:.2%}')
# "{:6s}今日APY: {:.2%}，7日APY: {:.2%}，累计APY: {:.2%}"

open_time_pnl = _('Position opened at {}. Overall PnL: {:.2f} USDT')
# "开仓时间：{}，累计收益：{:.2f} USDT"

open_close_pnl = _('{} position opened at {}, closed at {}.\n'
                   'PnL: {:.2f} USDT, APR: {:.2%}')
# "{}开仓时间：{}，平仓时间：{}。\n
# 收益：{:.2f} USDT，APR：{:.2%}"

wrong_command = _('Wrong command')
# "错误指令"

how_many_days = _('How many days?\n')
# "统计最近几天？\n"

how_many_hours = _('How many hours?\n')
# "统计最近几小时？\n"

main_menu_text = _("""
1   Monitor existing positions
2   Manipulate given crypto
3   Funding rates
4   Portfolio related
5   Fetch ticker
q   Quit
""")
# """
# 1   监控现有仓位
# 2   单一币种操作
# 3   资金费数据
# 4   账户数据
# 5   记录行情
# q   退出
# """

crypto_menu_text = _("""
1   Open or add
2   Reduce
3   Monitor
4   Adjust leverage
5   Close
6   PnL
7   Premium/discount statistics
b   Back
""")
# """
# 1   加仓
# 2   减仓
# 3   监控
# 4   调整杠杆
# 5   平仓
# 6   收益统计
# 7   期现差价统计
# b   返回
# """

funding_menu_text = _("""
1   Top 10 for arbitrage
2   Portfolio current funding rates
3   Current funding rates for all
4   Last 7 days funding rates for all
5   Last 30 days funding rates for all
b   Back
""")
# """
# 1   显示收益最高十个币种
# 2   显示持仓币种当前资金费
# 3   显示全币种当前资金费
# 4   显示全币种最近7天资金费
# 5   显示全币种最近30天资金费
# b   返回
# """

account_menu_text = _("""
1   Backtrack funding fees
2   Portfolio PnL
3   History PnL
4   Delete record
b   Back
""")
# """
# 1   补录资金费
# 2   持仓收益
# 3   历史收益
# 4   删除记录
# b   返回
# """

coin_current_next = _('Crypto    Current  Predicted')
# '币种      当期资金费   预测资金费'

funding_close = _('{:6s} Funding Rate: {:7.3%}, Avg premium at close: {:7.3%}, Std: {:7.3%},'
                  ' Min: {:7.3%}, Minus 2 std: {:7.3%}')
# "{:6s} 资金费：{:7.3%}，平仓价差：{:7.3%}，标准差：{:7.3%}，最小值：{:7.3%}，减2个标准差：{:7.3%}"

funding_7day = _('Crypto  7 day funding')
# "币种     7天资金费"

funding_30day = _('Crypto  30 day funding')
# "币种     30天资金费"

coin_7_30 = _('Crypto     7 day  30 day\n')
# "币种     7天资金费 30天资金费\n"

coin_funding_value = _('Crypto   Funding     APR Profitability')
# '币种        资金费     APR   投资价值'

pd_open = _('Premium/discount at open')
# '开仓期现差价'

pd_close = _('Premium/discount at close')
# '平仓期现差价'

two_std = _('Two standard deviation')
# '两个标准差'

plot_time = _('Time')
# "时间"

plot_premium = _('Premium')
# "差价"

plot_title = _('{:s} premium in {:d} hours')
# "{:s} {:d}小时期现差价"

nonexistent_crypto = _('Crypto {:s} does not exist.')
# "{:s}币种不存在。"

nonexistent_position = _('Position {:s} does not exist.')
# "{:s}仓位不存在。"

nonexistent_account = _('Account does not exist.')
# "账户不存在。"

transfer_failed = _('Transfer failed')
# "划转失败"

amount_to_add = _('amounts to add:')
# '加仓数量:'

added_amount = _('Added ')
# '已加仓'

insufficient_USDT = _('Insufficient USDT')
# 'USDT余额不足'

insufficient_margin = _('Insufficient margin')
# '合约余额不足'

insufficient_spot = _('Insufficient spot')
# '现货仓位不足'

insufficient_swap = _('Insufficient swap')
# '合约仓位不足'

current_leverage = _('Current notional leverage:')
# "当前名义杠杆："

set_leverage = _('Setting notional leverage:')
# "设置名义杠杆："

finished_leverage = _("Finished setting leverage.")
# "设置杠杆完毕。"

failed_leverage = _("Failed to set leverage.")
# "设置杠杆失败。"

adjust_leverage= _('Adjust actual leverage:')
# "调整实际杠杆："

futures_market_down = _('Swap market is down')
# "合约系统出错"

spot_order_failed = _('Spot order failed')
# "现货下单失败"

swap_order_failed = _('Swap order failed')
# "合约下单失败"

both_order_failed = _('Both orders failed')
# "均下单失败"

swap_order_retract = _('Swap order retracted:')
# "合约撤单:"

spot_order_retract = _('Spot order retracted:')
# "现货撤单:"

swap_order_state = _('Swap order state:')
# "合约订单状态:"

spot_order_state = _('Spot order state:')
# "现货订单状态:"

await_status_update = _('Await status update')
# "等待状态更新"

remaining = _('. Remaining ')
# "，剩余"

position_exist = _('{:f} {:s} position exists.')
# "已有{:f} {:s}仓位。"

delete_anyway = _('Enter y to delete')
# "输入y删除记录"

deleted = _('Deleted {:d} records.')
# "已删除{:d}条。"

amount_to_reduce = _('amounts to reduce:')
# '减仓数量:'

reduced_amount = _('Reduced')
# '已减仓'

spot_recoup = _('Spot recouped')
# "现货回收"

amount_to_close = _('amounts to close:')
# '平仓数量:'

has_closed = _('{:s} has been closed.')
# "{:s}已平仓。"

closed_amount = _('{:f} {:s} has been closed.')
# "已平仓{:f} {:s}。"

start_monitoring = _('Start monitoring {}\nPosition: {:.2f} USDT Leverage: {}')
# "开始监控{}\n仓位：{:.2f} USDT 杠杆：{}"

cost_to_close = _('Cost to close: {:.3%}')
# "平仓成本{:.3%}"

closing = _('Closing {:s}')
# "正在平仓{:s}"

approaching_liquidation = _('Approaching liquidation. Reduce spot.')
# "接近强平价，现货减仓"

too_much_margin = _('Too much margin. Add spot.')
# "保证金过多，现货加仓"

transfer_text = _('Transferred ')
# "划转"

to_spot_account = _('to spot account')
# "到现货账户"

to_swap_account = _('to swap account')
# "到合约账户"

spot_text = _('Spot: ')
# "现货:"

swap_text = _('Swap: ')
# "期货:"

received_funding = _('{} Receive funding fee {:.3f}')
# "{}收到资金费{:.3f}"

back_track_funding = _('Backtrack {} funding fee records {}')
# "补录{}资金费{}条"

reach_max_retry = _('Reach max retry.')
# "达到最大重试次数。"

more_than_one_position = _('{} has more than one swap position.')
# "{}合约仓位不止一个。"

upgrade_account = _('Upgrade account mode to margin mode.')
# "升级账户模式为保证金模式。"

position_mode = _('Position mode is {}.')
# ""持仓方式为{}。"

change_net_mode = _('Changed to net_mode.')
# "设置为单向持仓。"

set_mode_fail =  _('Failed to set net_mode.')
# "设置单向持仓失败。"

target_position_text = _('Target position')
# "目标数量"

less_than_ctval = _('less than contract value')
# "小于合约面值"

abort_text = _('Abort.')
# "中止。"

added_margin = _('Added margin')
# "增加保证金"

reduced_margin = _('Reduced margin')
# "减少保证金"

fetch_ticker_first = _('Fetch ticker first.')
# "先记录行情。"

record_ticker = _('Recording ticker')
# "记录行情中"

no_margin_reduce = _('Margin cannot be reduced.')
# "无法减少保证金。"

