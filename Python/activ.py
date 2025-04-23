import pandas as pd
from datetime import datetime as dt, timedelta
import subprocess
from copy import deepcopy
import pytz
import re
import numpy as np
from activfinancial import *
from activfinancial.constants import *
from start_connection import createConnection
import time
import shutil
import math
import os

current_time_in_NY = dt.now(pytz.timezone("America/New_York"))  # dt(2024, 11, 11)
current_time = dt.now(pytz.timezone("America/New_York"))


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
# note that SPX symbol doesn't exist, we just need to populate it via SPY * 10
usym_map = {"QQQ": "QQQ.Q", "SPY": "SPY.Q", "SPX": "=SPX.WI"}
usym_data = {
    "QQQ.Q": {"Underlying": "QQQ", "Bid": 0, "Ask": 0, "Mid": 0},
    "SPY.Q": {"Underlying": "SPY", "Bid": 0, "Ask": 0, "Mid": 0},
    "=SPX.WI": {"Underlying": "SPX", "Bid": 0, "Ask": 0, "Mid": 0},
}
pairs_logging = {}
debug_mode = False
original_directory = os.path.dirname(os.getcwd())
snapshot_path = os.path.join(original_directory, "SnapshotViewer", "opra_snapshot.txt")
snapshot_path_editor = os.path.join(original_directory, "TradingAPI", "SnapshotViewer", "opra_snapshot.txt")
snapshot_path_copy = os.path.join(original_directory, "SnapshotViewer", "opra_snapshot_copy.txt")
snapshot_path_copy_editor = os.path.join(original_directory, "TradingAPI", "SnapshotViewer", "opra_snapshot_copy.txt")

# Underlying -> Date Range
pairs_found = {
    "PutSpread": [],
    "BuySell": {
        "SPX": {},
        "SPY": {},
        "QQQ": {},
    },
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
        # print(f'REFRESH received for {msg.symbol}')
        bid = displayFieldAsStr(msg, "Bid")
        ask = displayFieldAsStr(msg, "Ask")
        bidSize = displayFieldAsStr(msg, "BidSize")
        askSize = displayFieldAsStr(msg, "AskSize")
        if msg.symbol in usym_data:
            bid_true = check_string(bid)
            ask_true = check_string(ask)
            if bid_true:
                usym_data[msg.symbol]["Bid"] = displayStrAsNum(clean_string(bid))
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Bid"] = usym_data[msg.symbol]["Bid"] * 10
            if ask_true:
                usym_data[msg.symbol]["Ask"] = displayStrAsNum(clean_string(ask))
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Ask"] = usym_data[msg.symbol]["Ask"] * 10
            if bid_true and ask_true:
                usym_data[msg.symbol]["Mid"] = (
                    usym_data[msg.symbol]["Ask"] + usym_data[msg.symbol]["Bid"]
                ) / 2
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Mid"] = usym_data[msg.symbol]["Mid"] * 10
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
        if debug_mode:
            print(f'UPDATE received for {msg.symbol}')
        bid = displayFieldAsStr(msg, "Bid")
        ask = displayFieldAsStr(msg, "Ask")
        bidSize = displayFieldAsStr(msg, "BidSize")
        askSize = displayFieldAsStr(msg, "AskSize")
        askTime = displayFieldAsStr(msg, "AskTime")
        bidTime = displayFieldAsStr(msg, "BidTime")
        if msg.symbol in usym_data:
            if check_string(bid):
                usym_data[msg.symbol]["Bid"] = displayStrAsNum(clean_string(bid))
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Bid"] = usym_data[msg.symbol]["Bid"] * 10
            if check_string(ask):
                usym_data[msg.symbol]["Ask"] = displayStrAsNum(clean_string(ask))
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Ask"] = usym_data[msg.symbol]["Ask"] * 10
            if (
                usym_data[msg.symbol]["Ask"] is not None
                and usym_data[msg.symbol]["Bid"] is not None
            ):
                usym_data[msg.symbol]["Mid"] = (
                    usym_data[msg.symbol]["Ask"] + usym_data[msg.symbol]["Bid"]
                ) / 2
                if msg.symbol == "SPY.Q":
                    usym_data["=SPX.WI"]["Mid"] = usym_data[msg.symbol]["Mid"] * 10
            if check_string(askTime):
                usym_data[msg.symbol]["AskTime"] = askTime
            if check_string(bidTime):
                usym_data[msg.symbol]["BidTime"] = bidTime
            if debug_mode:
                print("{}: {}".format(msg.symbol, usym_data[msg.symbol]))
                if msg.symbol == "SPY.Q":
                    print("SPX: {}".format(usym_data["=SPX.WI"]))
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
            if debug_mode:
                print("{}: {}".format(msg.symbol, option_data[usym][sym]))

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
        print("Connected")
        return session

    # This function should narrow down the symbols to subscribe using SnapshotViewer.
    def get_symbols(
        self,
        target_symbols: list[str],
        expiry_ranges: list[str],
        put_spread_underlyings: list[str],
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
                    if ts == "SPX":
                        query_string.append(
                            "SPXW" + "/" + expiry_start.strftime("%y%m%d") + "*.O"
                        )
                if ts + "/" + expiry_end.strftime("%y%m%d") + "*.O" not in query_string:
                    query_string.append(
                        ts + "/" + expiry_end.strftime("%y%m%d") + "*.O"
                    )
                    if ts == "SPX":
                        query_string.append(
                            "SPXW" + "/" + expiry_end.strftime("%y%m%d") + "*.O"
                        )

        # put spreads
        for put_spread_expiry in put_spread_expiries:
            put_spread_exp_start, put_spread_exp_end = map(
                lambda n: current_time_in_NY + timedelta(days=int(n)),
                put_spread_expiry.split(","),
            )
            for put_spread_underlying in put_spread_underlyings:
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
        if (
            put_spread_underlying not in target_symbols
            and put_spread_underlying != "SPXW"
        ):
            self.target_symbols = target_symbols.append(put_spread_underlying)
        else:
            self.target_symbols = target_symbols

    def subscribe(self, activ_session: Session):
        # symbols_all is an empty list to start with, but concat to an array when there are valid symbols
        symbols_to_subscribe = (
            self.symbols_all.tolist() 
            if hasattr(self, "symbols_all") and not isinstance(self.symbols_all, list) 
            else []
        )
        for key in usym_data.keys():
            symbols_to_subscribe.append(key)
        print("Subscribing to Symbols.")
        self.subscribe_to_symbols(symbols_to_subscribe, activ_session)

    def subscribe_usym(self, activ_session: Session):
        symbols_to_subscribe = []
        for key in usym_data.keys():
            symbols_to_subscribe.append(key)
        print("Subscribing to Underlying symbols.")
        self.subscribe_to_symbols(symbols_to_subscribe, activ_session)

    def invoke_update_viewer(self):
        # should call the ACP Update Viewer, and write to a txt file
        batch_file_path_1 = os.path.join(original_directory, "SnapshotViewer", "runSnapshot.bat")
        batch_file_path_2 = os.path.join(".", "SnapshotViewer", "runSnapshot.bat")
        # Read the contents of the batch file
        try:
            with open(batch_file_path_1, "r") as file:
                content = file.read()
                used_path = batch_file_path_1
        except FileNotFoundError:
            try:
                with open(batch_file_path_2, "r") as file:
                    content = file.read()
                    used_path = batch_file_path_2
            except FileNotFoundError:
                content = 'SnapshotViewer_x86-64_win64_vc142_mds.exe -u "keki9000-user01" -p "keki-u1" -t 602 -f "456;280;362;329" -o "opra_snapshot.txt" -s  SPX/250415*.O;SPXW/250415*.O;SPX/250422*.O;SPXW/250422*.O;QQQ/250415*.O;QQQ/250422*.O;SPY/250415*.O;SPY/250422*.O;SPX/250416*.O;SPX/250418*.O;SPXW/250416*.O;SPXW/250418*.O'
                try:
                    with open(batch_file_path_1, "w") as file:
                        file.write(content)
                        used_path = batch_file_path_1
                except FileNotFoundError:
                    with open(batch_file_path_2, "w") as file:
                        file.write(content)
                        used_path = batch_file_path_2

        # Use regex to find and replace the parameter after -s
        match = re.search(r"(-s\s+)(\S+)", content)
        # If we have rerun the batch, we need to resubscribe
        re_subscribe = False
        if match:
            current_value = match.group(2)
            if current_value == self.query_string:
                print("Params are unchanged.")
            else:
                updated_content = re.sub(
                    r"(-s\s+)(\S+)", r"\1" + self.query_string, content
                )
                # Write the updated content back to the batch file
                with open(used_path, "w") as file:
                    file.write(updated_content)
                # -u: username
                # -p: password
                # -h: host:port
                # -t: table name
                # -f: Column fields
                # -s: symbols
                # -o: output file

                # Copy always has the previous run's result just in case it got wiped
                try:
                    shutil.copy(
                        snapshot_path,
                        snapshot_path_copy
                    )
                except FileNotFoundError:
                    try:
                        shutil.copy(
                            snapshot_path_editor,
                            snapshot_path_copy_editor
                        )
                    except FileNotFoundError:
                        print("Main snapshot file does not currently exist.")

                batch_file_directory = os.path.dirname(used_path)
                os.chdir(batch_file_directory)
                subprocess.run("runSnapshot.bat", shell=True)
                os.chdir(original_directory)
                re_subscribe = True
        self.read_activ_strikes()
        return re_subscribe

    def read_activ_strikes(self):
        symbols_to_sub = []
        try:
            option_symbols = pd.read_csv(
                snapshot_path, sep='\s+'
            )
        except FileNotFoundError:
            option_symbols = pd.read_csv(
                snapshot_path_editor, sep='\s+'
            )
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
            # key_to_read = "SPX" if key == "SPXW" else key
            # mid_price = usym_data[usym_map[key_to_read]]["Mid"]
            option_symbols_df[key] = option_symbols[:][
                (option_symbols["Underlying"] == key)
                & (option_symbols["OptionType"] == "P")
                # & (option_symbols["StrikePrice"] / mid_price > 0.7)
                # & (option_symbols["StrikePrice"] <= mid_price)
            ]
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
                                    if debug_mode:
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
                                        ).replace(
                                            tzinfo=pytz.timezone("America/New_York")
                                        )
                                        buy_exp = dt.strptime(
                                            buy_strike["Expiry"], "%Y-%m-%d"
                                        ).replace(
                                            tzinfo=pytz.timezone("America/New_York")
                                        )
                                        buy_mid = (
                                            buy_strike["Ask"] + buy_strike["Bid"]
                                        ) / 2
                                        sell_mid = (
                                            sell_strike["Ask"] + sell_strike["Bid"]
                                        ) / 2
                                        if (buy_mid != 0) and (sell_mid != 0):
                                            if (
                                                sell_strike["Symbol"]
                                                + "-"
                                                + buy_strike["Symbol"]
                                                in ps_mid_avg
                                            ):
                                                c_avg = round(
                                                    ps_mid_avg[
                                                        sell_strike["Symbol"]
                                                        + "-"
                                                        + buy_strike["Symbol"]
                                                    ],
                                                    0,
                                                )
                                            else:
                                                c_avg = round(sell_mid - buy_mid, 3)
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
                                                    "MidAvg": c_avg,
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
    ):
        buy_sell_pairs = {
            "SPX": {},
            "SPY": {},
            "QQQ": {},
        }
        if not hasattr(self, "symbols_df") or len(target_symbol) != len(strike_range):
            return buy_sell_pairs

        symbols_df_all = self.symbols_df_buy_sell
        for idx, symbol in enumerate(target_symbol):
            usym_price = usym_data[usym_map[symbol]]["Mid"]
            if (symbol != "SPY" and symbol in symbols_df_all) or (
                symbol == "SPY" and "SPX" in symbols_df_all and "SPY" in symbols_df_all
            ):
                symbols_df = symbols_df_all[symbol]
                lower_strike, upper_strike = map(
                    lambda x: float(x) / 100 * usym_price, strike_range[idx].split("-")
                )
                if debug_mode:
                    print(
                        "Query Range for {}: {} - {}".format(
                            symbol, str(lower_strike), str(upper_strike)
                        )
                    )
                for expiry_range in expiry_ranges:
                    buy_sell_pairs[symbol][expiry_range] = []
                    if expiry_range not in pairs_found["BuySell"][symbol] or not pairs_found["BuySell"][symbol][expiry_range]:
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
                            if "SPX" in symbols_df_all:
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
                            for sell_strike in eligible_sell_strikes.itertuples(
                                index=False
                            ):
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
                                sell_strike_symbol = getattr(sell_strike, "Symbol").split(
                                    "/"
                                )[1]
                                buy_strike_symbol = closest_buy_strike.split("/")[1]
                                if (
                                    symbol in option_data and buy_symbol in option_data and
                                    sell_strike_symbol in option_data[symbol]
                                    and buy_strike_symbol in option_data[buy_symbol]
                                ):
                                    c_dollar_result = self.calc_c_dollar(
                                        option_data[symbol][sell_strike_symbol],
                                        option_data[buy_symbol][buy_strike_symbol],
                                        usym_price,
                                        c_average,
                                    )
                                    if c_dollar_result is not None: # and float(c_dollar_result['C$'].replace(",", "")) > 0:
                                        buy_sell_pairs[symbol][expiry_range].append(
                                            c_dollar_result
                                        )
                    else:
                        existing_results = pairs_found["BuySell"][symbol][expiry_range]
                        for pair in existing_results:
                            c_dollar_result = self.calc_c_dollar(
                                option_data[symbol][pair["SellSymbol"]],
                                option_data["SPX" if symbol == "SPY" else symbol][pair["BuySymbol"]],
                                usym_price,
                                c_average,
                            )
                            if c_dollar_result is not None: # and float(c_dollar_result['C$'].replace(",", "")) > 0:
                                buy_sell_pairs[symbol][expiry_range].append(
                                    c_dollar_result
                                )
        current_time = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        for key, ranges_dict in buy_sell_pairs.items():
            if key not in pairs_logging:
                pairs_logging[key] = {}
            for ranges, pairs in ranges_dict.items():
                # this part only do if it wasn't declared!
                if ranges not in pairs_found["BuySell"][key]:
                    pairs_found["BuySell"][key][ranges] = []
                if len(pairs_found["BuySell"][key][ranges]) == 0:
                    for pair in pairs:
                        pairs_found["BuySell"][key][ranges].append({
                            "BuySymbol": pair["Buy Symbol"],
                            "SellSymbol": pair["Sell Symbol"],
                            "C$": pair["C$"],
                        })
                    # reorder data by C$
                    pairs_found["BuySell"][key][ranges] = sorted(pairs_found["BuySell"][key][ranges], key=lambda x: x["C$"], reverse=True)
                count = len(pairs)
                if count > 0:
                    if ranges not in pairs_logging[key]:
                        print("[{}] NEW: {} on expiration {} has {} eligible pairs".format(current_time, key, ranges, count))
                    elif count != pairs_logging[key][ranges]:
                        print("[{}] UPDATE: {} on expiration {} has {} eligible pairs".format(current_time, key, ranges, count))
                    pairs_logging[key][ranges] = count
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
        self, sell_strike: dict, buy_strike: dict, sell_u_price: float, c_average: dict
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
                        c_average[sell_strike["Symbol"] + "-" + buy_strike["Symbol"]]
                    )
                )
            else:
                c_avg = format_number(round(c_dollar))
            sell_dte_days = math.ceil((sell_dte - current_time_in_NY.replace(tzinfo=None)).total_seconds() / (24 * 3600))
            return {
                "C": round(c, 2),
                "C$": format_number(round(c_dollar)),
                "C$/DDiff": format_number(round(c_dollar_ddif)),
                "CAvg": c_avg,
                "Sell-DTE": sell_dte_days,
                "Diff": (sell_dte - buy_dte).days,
                "%UL": round(sell_strike["Strike"] / sell_u_price * 100, 2),
                "K-Diff": (
                    round(buy_strike["Strike"] - sell_strike["Strike"] * 10)
                    if sell_usym == "SPY"
                    else round(buy_strike["Strike"] - sell_strike["Strike"])
                ),
                "Sell Symbol": sell_strike["Symbol"],
                "Buy Symbol": buy_strike["Symbol"],
                "Sell-B": sell_strike["Bid"],
                "Sell-B#": sell_strike["BidSize"],
                "Sell-A": sell_strike["Ask"],
                "Sell-A#": sell_strike["AskSize"],
                "Buy-B": buy_strike["Bid"],
                "Buy-B#": buy_strike["BidSize"],
                "Buy-A": buy_strike["Ask"],
                "Buy-A#": buy_strike["AskSize"],
                "Sell IceChat": (
                    sell_usym
                    + " "
                    + sell_dte.strftime("%b %d")
                    + ", "
                    + str(int(sell_strike["Strike"]))
                    + " puts"
                    if sell_strike["OptionType"] == "P"
                    else " calls"
                ),
                "Buy IceChat": (
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
    sc.get_symbols(["SPY", "SPX", "QQQ"], ["7,2", "8,2"], "SPX", ["4,6"])
    sc.invoke_update_viewer()
    sesh = sc.connect_to_activ()
    sc.subscribe(sesh)
    #sc.subscribe_usym(sesh)
    # sc.get_put_spread_pairs([97, 96], [50, 100], ["7,8", "7,8"])
    sc.get_buy_sell_pairs(["SPY", "SPX", "QQQ"], ["82-86", "82-86", "82-86"], ["10,4"], 50)
