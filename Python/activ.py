import pandas as pd
from datetime import datetime as dt, timedelta
import subprocess
from copy import deepcopy
import pytz
import re
import numpy as np
from activfinancial import *
from activfinancial.constants import *
import activ_utils
from start_connection import createConnection
import time

current_time_in_NY = dt(2024, 11, 11)  # dt.now(pytz.timezone("America/New_York"))


fid_field_map = {
    "Bid": 0,
    "BidSize": 1,
    "BidTime": 3,
    "Ask": 5,
    "AskSize": 6,
    "AskTime": 8,
    "Expiry": 280,
    "Strike": 362,
    "OptionType": 329,
}
# cache to store option data per underlying/symbol
option_data = {}
usym_map = {"QQQ": "QQQ.USQ", "SPY": "SPY.USQ", "SPX": "=SPX.WI"}
usym_data = {
    "QQQ.USQ": {"Underlying": "QQQ", "Bid": 0, "Ask": 0, "Mid": 512},
    "SPY.USQ": {"Underlying": "SPY", "Bid": 0, "Ask": 0, "Mid": 597},
    "=SPX.WI": {"Underlying": "SPX", "Bid": 5950, "Ask": 5956, "Mid": 5953},
}


def format_number(x):
    return f"{x:,}"


def displayFieldAsStr(message, field):
    try:
        msg = message.fields[fid_field_map[field]]
        if msg is not None or msg != "None":
            return str(message.fields[fid_field_map[field]])
        else:
            return None
    except KeyError:
        return None


def displayStrAsNum(string):
    try:
        float(string)
        return float(string)
    except ValueError:
        return 0.0


def is_spx_third_friday(symbol: str, date: dt):
    # Get the first day of the month
    first_day = date.replace(day=1)
    # Get the first Friday of the month
    first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
    # Calculate the 3rd Friday
    third_friday = first_friday + timedelta(weeks=2)
    return date.date() == third_friday.date() and symbol == "SPX"


def clean_string(input_string):
    # Use regex to replace non-numeric characters with an empty string
    return re.sub(r"[^0-9.]", "", input_string)


def check_string(string):
    if not (string is None or string == "None"):
        return True
    return False


# activ classes
class SubscriptionHandler:
    def on_subscription_refresh(self, msg, context):
        # first timer!
        # print(f'REFRESH received for {msg.symbol}')
        bid = displayFieldAsStr(msg, "Bid")
        ask = displayFieldAsStr(msg, "Ask")
        bidSize = displayFieldAsStr(msg, "BidSize")
        askSize = displayFieldAsStr(msg, "AskSize")
        if msg.symbol in usym_data:
            if check_string(bid):
                usym_data[msg.symbol]["Bid"] = displayStrAsNum(clean_string(bid))
            if check_string(ask):
                usym_data[msg.symbol]["Ask"] = displayStrAsNum(clean_string(ask))
            usym_data[msg.symbol]["Mid"] = (
                usym_data[msg.symbol]["Ask"] + usym_data[msg.symbol]["Bid"]
            ) / 2
        else:
            underlying, sym = msg.symbol.split("/")
            usym = "SPX" if underlying == "SPXW" else underlying
            if usym not in option_data:
                option_data[usym] = {}
            if sym not in option_data[usym]:
                optionType = displayFieldAsStr(msg, "OptionType")
                expiry = displayFieldAsStr(msg, "Expiry")
                strike = displayFieldAsStr(msg, "Strike")
                option_data[usym][sym] = {
                    "Symbol": sym,
                    "Expiry": expiry,
                    "Underlying": usym,
                    "DisplayUnderlying": underlying,
                    "Strike": displayStrAsNum(strike),
                    "Bid": displayStrAsNum(
                        clean_string(bid) if bid is not None else "0"
                    ),
                    "BidSize": displayStrAsNum(bidSize),
                    "Ask": displayStrAsNum(
                        clean_string(ask) if ask is not None else "0"
                    ),
                    "AskSize": displayStrAsNum(askSize),
                    "OptionType": "C" if optionType == "C" else "P",
                }
                option_data[usym][sym]["Mid"] = (
                    option_data[usym][sym]["Ask"] + option_data[usym][sym]["Bid"]
                ) / 2

    def on_subscription_update(self, msg, context):
        # print(f'UPDATE received for {msg.symbol}')
        # print(common.update_message_to_string(msg, context.session.metadata))
        bid = displayFieldAsStr(msg, "Bid")
        ask = displayFieldAsStr(msg, "Ask")
        bidSize = displayFieldAsStr(msg, "BidSize")
        askSize = displayFieldAsStr(msg, "AskSize")
        askTime = displayFieldAsStr(msg, "AskTime")
        bidTime = displayFieldAsStr(msg, "BidTime")
        if msg.symbol in usym_data:
            if check_string(bid):
                usym_data[msg.symbol]["Bid"] = displayStrAsNum(clean_string(bid))
            if check_string(ask):
                usym_data[msg.symbol]["Ask"] = displayStrAsNum(clean_string(ask))
            if (
                usym_data[msg.symbol]["Ask"] is not None
                and usym_data[msg.symbol]["Bid"] is not None
            ):
                usym_data[msg.symbol]["Mid"] = (
                    usym_data[msg.symbol]["Ask"] + usym_data[msg.symbol]["Bid"]
                ) / 2
            if check_string(askTime):
                usym_data[msg.symbol]["AskTime"] = askTime
            if check_string(bidTime):
                usym_data[msg.symbol]["BidTime"] = bidTime
        else:
            underlying, sym = msg.symbol.split("/")
            usym = "SPX" if underlying == "SPXW" else underlying
            if check_string(bid):
                option_data[usym][sym]["Bid"] = displayStrAsNum(clean_string(bid))
            if check_string(ask):
                option_data[usym][sym]["Ask"] = displayStrAsNum(clean_string(ask))
            if check_string(bidSize):
                option_data[usym][sym]["BidSize"] = displayStrAsNum(bidSize)
            if check_string(askSize):
                option_data[usym][sym]["AskSize"] = displayStrAsNum(askSize)
            if askTime is not None:
                option_data[usym][sym]["AskTime"] = askTime
            if bidTime is not None:
                option_data[usym][sym]["BidTime"] = bidTime
            option_data[usym][sym]["Mid"] = (
                option_data[usym][sym]["Bid"] + option_data[usym][sym]["Ask"]
            ) / 2

    def on_subscription_topic_status(self, msg, context):
        a = 1
        # print(f'TOPIC STATUS received for {msg.symbol}')
        # print(activ_utils.topic_status_message_to_string(msg))

    def on_subscription_status(self, msg, context):
        state_string = subscription_state_to_string(msg.state)
        output = f"SUBSCRIPTION STATUS: {msg.request}, state={state_string}"
        if msg.is_error() or msg.is_failure():
            output += ", status_code=" + status_code_to_string(msg.status_code)
        # print(output)


class SessionHandler:
    def on_session_connect(self, session):
        # Called for reconnects.
        print("on_session_connect")

    def on_session_disconnect(self, session):
        # Called when a graceful disconnect has completed.
        print("on_session_disconnect")

    def on_session_error(self, session, status_code):
        print("on_session_error:")
        print("StatusCode: {}".format(status_code_to_string(status_code)))

    def on_session_log_message(self, session, log_type, message):
        # Only print errors and warnings.
        if log_type == LOG_TYPE_ERROR or log_type == LOG_TYPE_WARNING:
            print("on_session_log_message:")
            print("LogType: {}".format(log_type_to_string(log_type)))
            print(("Message: {}".format(message)))
        else:
            pass


class SpreadCalculation(createConnection):
    def connect_to_activ(self, parameters={}):
        parameters[FID_ENABLE_DICTIONARY_DOWNLOAD] = True
        parameters[FID_ENABLE_CTRL_HANDLER] = True
        connect_parameters = {
            FID_HOST: self.acp_host,
            FID_USER_ID: self.acp_username,
            FID_PASSWORD: self.acp_password,
        }
        handler = SessionHandler()
        session = Session(parameters, handler)
        timeout = 10000
        print("Connecting to {}".format(connect_parameters[FID_HOST]))
        session.connect(connect_parameters, timeout)
        return session

    # This function should narrow down the symbols to subscribe using SnapshotViewer.
    def get_symbols(
        self,
        target_symbols: list[str],
        expiry_ranges: list[str],
        put_spread_underlying: str,
        put_spread_expiries: list[str],
    ):
        query_string = []
        # long/short spreads
        for i in range(len(target_symbols)):
            ts = target_symbols[i]
            for j in range(len(expiry_ranges)):
                expiry_range = expiry_ranges[j]
                expiry_end, expiry_start = map(
                    lambda n: current_time_in_NY + timedelta(days=int(n)),
                    expiry_range.split(","),
                )
                if expiry_start.weekday() > 4 or expiry_end.weekday() > 4:
                    print(
                        "Expiry Start or End is on a weekend, please reconfigure!, Start: {}, End: {}".format(
                            expiry_start, expiry_end
                        )
                    )
                    continue
                if (
                    ts + "/" + expiry_start.strftime("%y%m%d") + "*.O"
                    not in query_string
                ):
                    query_string.append(
                        ts + "/" + expiry_start.strftime("%y%m%d") + "*.O"
                    )
                if ts + "/" + expiry_end.strftime("%y%m%d") + "*.O" not in query_string:
                    query_string.append(
                        ts + "/" + expiry_end.strftime("%y%m%d") + "*.O"
                    )

        # put spreads
        for put_spread_expiry in put_spread_expiries:
            put_spread_exp_start, put_spread_exp_end = map(
                lambda n: current_time_in_NY + timedelta(days=int(n)),
                put_spread_expiry.split(","),
            )
            if put_spread_exp_start.weekday() < 5:
                if (
                    put_spread_underlying
                    + "/"
                    + put_spread_exp_start.strftime("%y%m%d")
                    + "*.O"
                    not in query_string
                ):
                    query_string.append(
                        put_spread_underlying
                        + "/"
                        + put_spread_exp_start.strftime("%y%m%d")
                        + "*.O"
                    )
            if put_spread_exp_end.weekday() < 5:
                if (
                    put_spread_underlying
                    + "/"
                    + put_spread_exp_end.strftime("%y%m%d")
                    + "*.O"
                    not in query_string
                ):
                    query_string.append(
                        put_spread_underlying
                        + "/"
                        + put_spread_exp_end.strftime("%y%m%d")
                        + "*.O"
                    )

        self.query_string = ";".join(query_string)
        if put_spread_underlying not in target_symbols:
            self.target_symbols = target_symbols.append(put_spread_underlying)
        else:
            self.target_symbols = target_symbols

    def subscribe(self, activ_session: Session):
        symbols_to_subscribe = self.symbols_all.tolist()
        for key in usym_data.keys():
            symbols_to_subscribe.append(key)
        self.subscribe_to_symbols(symbols_to_subscribe, activ_session)

    def invoke_update_viewer(self, directory):
        # should call the ACP Update Viewer, and write to a txt file
        path = r".\SnapshotViewer\SnapshotViewer_x86-64_win64_vc142_mds.exe"

        # -u: username
        # -p: password
        # -h: host:port
        # -t: table name
        # -f: Column fields
        # -s: symbols
        # -o: output file

        args = [
            "-u",
            "replay",
            "-p",
            "replay",
            "-h",
            "66.150.109.180:9150",
            "-t",
            "602",
            "-f",
            "456;280;362;329",
            "-s",
            self.query_string,
            "-o",
            directory,
        ]
        command = [path] + args
        subprocess.run(" ".join(command), capture_output=True, text=True)
        self.directory = directory

    def read_activ_strikes(self):
        # ./sampleResult.txt
        symbols_to_sub = []
        self.directory = "./symbols.txt"
        option_symbols = pd.read_csv(self.directory, delim_whitespace=True)
        # filter out 3rd Week for SPX symbols
        option_symbols["ExpirationDate"] = pd.to_datetime(
            option_symbols["ExpirationDate"]
        )
        option_symbols["Underlying"] = option_symbols["Symbol"].str.split("/").str[0]
        option_symbols = option_symbols[
            ~option_symbols.apply(
                lambda row: is_spx_third_friday(
                    row["Underlying"], row["ExpirationDate"]
                ),
                axis=1,
            )
        ]
        option_symbols_df = {
            elem: pd.DataFrame() for elem in option_symbols["Underlying"].unique()
        }
        for key in option_symbols_df.keys():
            key_to_read = "SPX" if key == "SPXW" else key
            mid_price = usym_data[usym_map[key_to_read]]["Mid"]
            option_symbols_df[key] = option_symbols[:][
                (option_symbols["Underlying"] == key)
                & (option_symbols["OptionType"] == "P")
                & (option_symbols["StrikePrice"] / mid_price > 0.8)
                & (option_symbols["StrikePrice"] <= mid_price)
            ]
            # option_symbols_df[key]["ExpirationDate"] = pd.to_datetime(
            #    option_symbols_df[key]["ExpirationDate"]
            # )
            symbols_to_sub = np.concatenate(
                (symbols_to_sub, option_symbols_df[key]["Symbol"].to_numpy().flatten())
            )
        self.symbols_df = option_symbols_df
        buy_sell_df = deepcopy(option_symbols_df)
        if "SPX" in buy_sell_df:
            buy_sell_df["SPX"] = pd.concat(
                [buy_sell_df["SPX"], buy_sell_df["SPXW"]], ignore_index=True
            )
        elif "SPXW" in buy_sell_df:
            buy_sell_df["SPX"] = buy_sell_df["SPXW"]
        self.symbols_df_buy_sell = buy_sell_df
        self.symbols_all = symbols_to_sub

    def get_put_spread_pairs(
        self,
        ul_pcts: list[float],
        ul_pts_wide: list[int],
        ul_exp_range: list[str],
        ps_mid_avg: dict,
    ):
        # TODO: Exclude SPX 3rd Friday!
        # same length for pcts, pts wide and exp range
        put_spread_pairs = []
        symbols = ["SPX", "SPXW"]
        spx_price = usym_data[usym_map["SPX"]]["Mid"]
        if "SPX" in option_data:
            for symbol in symbols:
                if hasattr(self, "symbols_df") and symbol in self.symbols_df:
                    symbols_df = self.symbols_df[symbol]
                    # for each row
                    for index, ul_pct in enumerate(ul_pcts):
                        target_price = float(spx_price) * float(ul_pct) / 100
                        pts_wide = ul_pts_wide[index]
                        expiry_days = map(
                            lambda n: current_time_in_NY + timedelta(days=int(n)),
                            ul_exp_range[index].split(","),
                        )
                        for date in expiry_days:
                            eligible_strikes = symbols_df[
                                symbols_df["ExpirationDate"].dt.date == date.date()
                            ]
                            if len(eligible_strikes) > 0:
                                closest_index_upper = (
                                    (eligible_strikes["StrikePrice"] - target_price)
                                    .abs()
                                    .idxmin()
                                )
                                closest_upper = eligible_strikes.loc[
                                    closest_index_upper
                                ]["Symbol"].split("/")[1]
                                closest_upper_strike = eligible_strikes.loc[
                                    closest_index_upper
                                ]["StrikePrice"]
                                target_strike = float(closest_upper_strike) - float(
                                    pts_wide
                                )
                                closest_index_lower = (
                                    (target_strike - eligible_strikes["StrikePrice"])
                                    .abs()
                                    .idxmin()
                                )
                                closest_lower = eligible_strikes.loc[
                                    closest_index_lower
                                ]["Symbol"].split("/")[1]
                                closest_lower_strike = eligible_strikes.loc[
                                    closest_index_lower
                                ]["StrikePrice"]
                                # only append when we can find 2 separate symbols!
                                if closest_upper != closest_lower:
                                    # also need to append to an array of pairs!
                                    print(
                                        "Upper Symbol: {}, Strike: {}; Lower Symbol: {}, Strike: {}".format(
                                            symbol + "/" + closest_upper,
                                            closest_upper_strike,
                                            symbol + "/" + closest_lower,
                                            closest_lower_strike,
                                        )
                                    )
                                    if (
                                        closest_lower in option_data["SPX"]
                                        and closest_upper in option_data["SPX"]
                                    ):
                                        sell_strike = option_data["SPX"][closest_upper]
                                        buy_strike = option_data["SPX"][closest_lower]
                                        sell_exp = dt.strptime(
                                            sell_strike["Expiry"], "%Y-%m-%d"
                                        )  # .replace(tzinfo=pytz.timezone("America/New_York"))
                                        buy_exp = dt.strptime(
                                            buy_strike["Expiry"], "%Y-%m-%d"
                                        )
                                        buy_mid = (
                                            buy_strike["Ask"] + buy_strike["Bid"]
                                        ) / 2
                                        sell_mid = (
                                            sell_strike["Ask"] + sell_strike["Bid"]
                                        ) / 2
                                        if (
                                            sell_strike["Symbol"]
                                            + "-"
                                            + buy_strike["Symbol"]
                                            in ps_mid_avg
                                        ):
                                            c_avg = format_number(
                                                round(
                                                    ps_mid_avg[
                                                        sell_strike["Symbol"]
                                                        + "-"
                                                        + buy_strike["Symbol"]
                                                    ],
                                                    2,
                                                )
                                            )
                                        else:
                                            c_avg = round(sell_mid - buy_mid, 4)
                                        put_spread_pairs.append(
                                            {
                                                "Short %UL": round(
                                                    sell_strike["Strike"]
                                                    / spx_price
                                                    * 100,
                                                    2,
                                                ),
                                                "K-Diff": round(
                                                    sell_strike["Strike"]
                                                    - buy_strike["Strike"],
                                                    0,
                                                ),
                                                "DTE": (
                                                    sell_exp - current_time_in_NY
                                                ).days,
                                                "C": round(sell_mid - buy_mid, 3),
                                                "Sell Symbol": sell_strike["Symbol"],
                                                "Buy Symbol": buy_strike["Symbol"],
                                                "MidAvg": round(c_avg, 3),
                                                "Sell Mid": round(sell_mid, 3),
                                                "Buy Mid": round(buy_mid, 3),
                                                "Short Leg IceChat": (
                                                    symbol
                                                    + " "
                                                    + sell_exp.strftime("%b %d")
                                                    + ", "
                                                    + str(int(sell_strike["Strike"]))
                                                    + " puts"
                                                    if sell_strike["OptionType"] == "P"
                                                    else " calls"
                                                ),
                                                "Long Leg IceChat": (
                                                    symbol
                                                    + " "
                                                    + buy_exp.strftime("%b %d")
                                                    + ", "
                                                    + str(int(buy_strike["Strike"]))
                                                    + " puts"
                                                    if buy_strike["OptionType"] == "P"
                                                    else " calls"
                                                ),
                                            }
                                        )
        time.sleep(0.5)
        return put_spread_pairs

    def get_buy_sell_pairs(
        self,
        target_symbol: list[str],
        strike_range: list[str],
        expiry_ranges: list[str],
        points_over: int,
        c_average: dict,
        start_time: time,
        end_time: time,
    ):
        buy_sell_pairs = {
            "SPX": [],
            "SPY": [],
            "QQQ": [],
        }
        if not hasattr(self, "symbols_df") or len(target_symbol) != len(strike_range):
            return buy_sell_pairs

        symbols_df_all = self.symbols_df_buy_sell
        # need to merge SPX and SPXW!
        for idx, symbol in enumerate(target_symbol):
            usym_price = usym_data[usym_map[symbol]]["Mid"]
            symbols_df = symbols_df_all[symbol]
            lower_strike, upper_strike = map(
                lambda x: float(x) / 100 * usym_price, strike_range[idx].split("-")
            )
            print(
                "Query Range for {}: {} - {}".format(
                    symbol, str(lower_strike), str(upper_strike)
                )
            )
            for expiry_range in expiry_ranges:
                sell_date, buy_date = map(
                    lambda x: current_time_in_NY + timedelta(days=int(x)),
                    expiry_range.split(","),
                )
                eligible_sell_strikes = symbols_df[
                    (symbols_df["ExpirationDate"].dt.date == sell_date.date())
                    & (symbols_df["StrikePrice"] >= lower_strike)
                    & (symbols_df["StrikePrice"] <= upper_strike)
                ]
                if symbol == "SPY":
                    # If we sell SPY, we will only buy SPX!
                    spx_df = symbols_df_all["SPX"]
                    eligible_buy_strikes = spx_df[
                        spx_df["ExpirationDate"].dt.date == buy_date.date()
                    ]
                    buy_symbol = "SPX"
                else:
                    eligible_buy_strikes = symbols_df_all[symbol][
                        symbols_df["ExpirationDate"].dt.date == buy_date.date()
                    ]
                    buy_symbol = symbol
                # for each eligible sell strikes, look at the buy strikes and find the closest one that's within points over!
                if len(eligible_sell_strikes) > 0 and len(eligible_buy_strikes) > 0:
                    for sell_strike in eligible_sell_strikes.itertuples(index=False):
                        strike_price = getattr(sell_strike, "StrikePrice")
                        if symbol == "SPY":
                            # Sell SPY, buy SPX, so target strike needs to multiply by 10
                            target_strike = (
                                float(strike_price) + float(points_over)
                            ) * 10
                        elif symbol == "SPX":
                            target_strike = (
                                float(strike_price) + float(points_over) * 10
                            )
                        else:
                            # QQQ, no need do anything
                            target_strike = float(strike_price) + float(points_over)
                        closest_index = (
                            (eligible_buy_strikes["StrikePrice"] - target_strike)
                            .abs()
                            .idxmin()
                        )
                        closest_buy_strike = eligible_buy_strikes.at[
                            closest_index, "Symbol"
                        ]
                        sell_strike_symbol = getattr(sell_strike, "Symbol").split("/")[
                            1
                        ]
                        buy_strike_symbol = closest_buy_strike.split("/")[1]
                        if (
                            sell_strike_symbol in option_data[symbol]
                            and buy_strike_symbol in option_data[buy_symbol]
                        ):
                            c_dollar_result = self.calc_c_dollar(
                                option_data[symbol][sell_strike_symbol],
                                option_data[buy_symbol][buy_strike_symbol],
                                usym_price,
                                c_average,
                                start_time,
                                end_time,
                            )
                            if c_dollar_result is not None:
                                buy_sell_pairs[symbol].append(c_dollar_result)
        return buy_sell_pairs

    def subscribe_to_symbols(
        self, symbols_to_subscribe: list[str], activ_session: Session
    ):
        # ["QQQ/MOGHH.O", "QQQ/MaGkd.O"]
        for symbol in symbols_to_subscribe:
            activ_session.query_subscribe(
                DATA_SOURCE_ACTIV, "symbol={}".format(symbol), SubscriptionHandler()
            )
        activ_session.run()

    def calc_c_dollar(
        self,
        sell_strike: dict,
        buy_strike: dict,
        sell_u_price: float,
        c_average: dict,
        start_time: time,
        end_time: time,
    ) -> dict:
        sell_usym = sell_strike["DisplayUnderlying"]
        buy_usym = buy_strike["DisplayUnderlying"]
        if sell_usym == "SPY":
            sell_px = sell_strike["Bid"] * 10
            buy_px = buy_strike["Mid"]
        elif sell_usym == "QQQ":
            sell_px = 10 * sell_strike["Bid"]
            buy_px = 10 * buy_strike["Mid"]
        else:
            sell_px = sell_strike["Mid"]
            buy_px = buy_strike["Mid"]
        if sell_px != 0 and buy_px != 0:
            c = sell_px - buy_px
            c_dollar = 1000 * c * 100
            sell_dte = dt.strptime(sell_strike["Expiry"], "%Y-%m-%d")
            buy_dte = dt.strptime(buy_strike["Expiry"], "%Y-%m-%d")
            c_dollar_ddif = c_dollar / (sell_dte - buy_dte).days
            if sell_strike["Symbol"] + "-" + buy_strike["Symbol"] in c_average:
                c_avg = format_number(
                    round(
                        c_average[sell_strike["Symbol"] + "-" + buy_strike["Symbol"]], 2
                    )
                )
            else:
                c_avg = format_number(round(c_dollar))
            return {
                "C": round(c, 2),
                "C$": format_number(round(c_dollar)),
                "C$/DDiff": format_number(round(c_dollar_ddif)),
                "CAvg": c_avg,
                "Sell-K DTE": (sell_dte - current_time_in_NY.replace(tzinfo=None)).days,
                "D-Diff": (sell_dte - buy_dte).days,
                "Sell-K %UL": round(sell_strike["Strike"] / sell_u_price * 100, 2),
                "Strike Diff": (
                    round(buy_strike["Strike"] - sell_strike["Strike"] * 10)
                    if sell_usym == "SPY"
                    else round(buy_strike["Strike"] - sell_strike["Strike"])
                ),
                "Sell Symbol": sell_strike["Symbol"],
                "Buy Symbol": buy_strike["Symbol"],
                "Sell Bid": sell_strike["Bid"],
                "Sell Bid #": sell_strike["BidSize"],
                "Sell Ask": sell_strike["Ask"],
                "Sell Ask #": sell_strike["AskSize"],
                "Buy Bid": buy_strike["Bid"],
                "Buy Bid #": buy_strike["BidSize"],
                "Buy Ask": buy_strike["Ask"],
                "Buy Ask #": buy_strike["AskSize"],
                "Short Leg IceChat": (
                    sell_usym
                    + " "
                    + sell_dte.strftime("%b %d")
                    + ", "
                    + str(int(sell_strike["Strike"]))
                    + " puts"
                    if sell_strike["OptionType"] == "P"
                    else " calls"
                ),
                "Long Leg IceChat": (
                    buy_usym
                    + " "
                    + buy_dte.strftime("%b %d")
                    + ", "
                    + str(int(buy_strike["Strike"]))
                    + " puts"
                    if buy_strike["OptionType"] == "P"
                    else " calls"
                ),
            }


if __name__ == "__main__":
    sc = SpreadCalculation()
    # c.subscribe_to_symbols(["QQQ/MOGHH.O", "QQQ/MaGkd.O"], session)
    # session.query_subscribe(DATA_SOURCE_ACTIV, "symbol=QQQ/MOGHH.O", SubscriptionHandler())
    # sc.get_symbols(["SPY", "SPX", "QQQ"], ["10,5", "11,5"], "SPX", ["4,5"])
    # sc.invoke_update_viewer('./symbols.txt')
    # sesh = sc.connect_to_activ()
    sc.read_activ_strikes()
    # sc.subscribe(sesh)
    # sc.get_put_spread_pairs([97, 96], [50, 100], ["7,8", "7,8"])
    # sc.get_buy_sell_pairs(["SPY", "SPX", "QQQ"], ["82-86", "82-86", "82-86"], ["10,4"], 50)
