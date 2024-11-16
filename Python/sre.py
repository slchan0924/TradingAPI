import requests
import pytz
from datetime import datetime
import pandas as pd

from activ import usym_map
from start_connection import createConnection


def format_number(x):
    return f"{x:,}"


# Global Variables
current_time_in_NY = datetime.now(pytz.timezone("America/New_York"))

def construct_risk_shocks(
    vol_min: int, vol_max: int, vol_incr: int, und_min: int, und_max: int, und_incr: int
) -> list[dict]:
    curr_vol = vol_min
    curr_und = und_min
    risk_shocks = []
    while curr_vol <= vol_max:
        curr_und = und_min
        while curr_und <= und_max:
            risk_shock = {
                "underlyingShock": curr_und,
                "volatilityShock": curr_vol,
                "shockLevel": "ParallelShock",
            }
            risk_shocks.append(risk_shock)
            curr_und += und_incr
        curr_vol += vol_incr
    return risk_shocks


def construct_risk_extreme_shocks(
    vol_shocks: list[int], und_shocks: list[int]
) -> list[dict]:
    extreme_shocks = []
    for vol_shock in vol_shocks:
        for und_shock in und_shocks:
            extreme_shock = {
                "underlyingShock": und_shock,
                "volatilityShock": vol_shock,
                "shockLevel": "ParallelShock",
            }
            extreme_shocks.append(extreme_shock)
    return extreme_shocks


def extract_pct(str: str):
    if "Vol" in str:
        _, new_str = str.split("Vol ")
    elif "Und" in str:
        _, new_str = str.split("Und ")

    # Handle both positive and negative percentages
    new_str = new_str.strip("%")  # Remove the '%' character
    if "+" in new_str:
        new_str = new_str.strip("+")  # Remove the '+' character
        return int(new_str)  # Return as integer
    return int(new_str)


def construct_risk_shocks_df(risk_ladder: dict):
    data = {}
    for key, value in risk_ladder.items():
        underlying_shock, volatility_shock = key.split("Par/")
        if int(underlying_shock.strip("%")) > 0:
            underlying_shock = "Und +" + underlying_shock
        else:
            underlying_shock = "Und " + underlying_shock

        if int(volatility_shock.strip("%")) > 0:
            volatility_shock = "Vol +" + volatility_shock
        else:
            volatility_shock = "Vol " + volatility_shock
        if volatility_shock not in data:
            data[volatility_shock] = {}
        data[volatility_shock][underlying_shock] = format_number(round(value, 2))

    all_vol_shocks = list(data.keys())
    all_und_shocks = list(data[all_vol_shocks[0]].keys())
    risk_ladder_df = pd.DataFrame(
        data,
        columns=sorted(all_vol_shocks, key=extract_pct),
        index=sorted(all_und_shocks, key=extract_pct),
    )
    risk_ladder_df = risk_ladder_df.transpose()
    return risk_ladder_df


class SRERisk(createConnection):
    def get_data(self, req_type: str, service: str, body=None, params=None):
        if self.sre_access_token == "No Service":
            return []
        if req_type == "GET":
            return requests.get(
                self.sre_url_base + "/service/" + service,
                params=params,
                headers={
                    "Content-Type": "application/json",
                    "accept": "*/*",
                    "Authorization": "Bearer {}".format(self.sre_access_token),
                },
            ).json()
        else:
            return requests.post(
                self.sre_url_base + "/service/" + service,
                json=body,
                params=params,
                headers={
                    "Content-Type": "application/json",
                    "accept": "*/*",
                    "Authorization": "Bearer {}".format(self.sre_access_token),
                },
            ).json()

    def get_account(self):
        return self.get_data("GET", "accounts/{}".format(self.sre_account))

    def get_positions(
        self,
        strike_prices: dict,
        security_type: str = "",
        expiry_start: str = "",
        expiry_end: str = "",
        symbol: str = "",
    ):
        if not security_type and not expiry_start and not expiry_end and not symbol:
            positions = self.get_data("POST", "account-positions", [self.sre_account])
        else:
            positions = self.get_data(
                "POST",
                "account-positions",
                [self.sre_account],
                {
                    "securityType": security_type,
                    "expirationDateStart": expiry_start,
                    "expirationDateEnd": expiry_end,
                    "symbol": symbol,
                },
            )
        if len(positions) == 0:
            # mock positions
            positions = [
                {"symbol": ".SPY 241114P475000", "pos": 1000},
                {"symbol": ".SPXW 241114P4890000", "pos": -500},
                {"symbol": ".SPXW 241114P4900000", "pos": 1000},
                {"symbol": ".SPY 241117P480000", "pos": 400},
                {"symbol": ".SPXW 241117P5435000", "pos": 1000},
            ]
        else:
            positions = positions[0]["positions"]

        eligible_positions = []
        position_result_list = []
        for position in positions:
            position_data = {}
            usym, data = position["symbol"].split(" ")
            position_data["Underlying"] = usym[1:]
            expiry = datetime.strptime(data[0:6], "%y%m%d").replace(
                tzinfo=pytz.timezone("America/New_York")
            )
            position_data["DTE"] = (expiry - current_time_in_NY).days + (
                1 if (expiry - current_time_in_NY).seconds > 0 else 0
            )
            # TODO: config to control whether include or exclude expiring options on run day!
            if position_data["DTE"] <= 0:
                continue
            position_data["Lots"] = position["pos"]
            position_data["Strike"] = round(int(data[7:]) / 1000)
            underlyingPrice = strike_prices[usym_map[usym[1:4]]]["Mid"]
            position_data["%UL"] = round(
                position_data["Strike"] / underlyingPrice * 100, 2
            )
            position_data["P/C"] = data[6]
            position_data["IceChat String"] = (
                str(position_data["Lots"])
                + " "
                + position_data["Underlying"]
                + " "
                + expiry.strftime("%b %d")
                + " "
                + str(int(position_data["Strike"]))
            )
            if data[6] == "P":
                position_data["IceChat String"] = (
                    position_data["IceChat String"] + " puts"
                )
            else:
                position_data["IceChat String"] = (
                    position_data["IceChat String"] + " calls"
                )
            position_data["Symbol"] = position["symbol"]

            eligible_positions.append(position)
            position_result_list.append(position_data)

        positions_df = pd.DataFrame(position_result_list)
        positions_df = positions_df[
            [
                "DTE",
                "Lots",
                "Underlying",
                "Strike",
                "%UL",
                "IceChat String",
                "P/C",
                "Symbol",
            ]
        ].sort_values(by=["DTE"])
        positions_df["Strike (Display)"] = positions_df["Strike"].apply(format_number)
        positions_df["Lots (Display)"] = positions_df["Lots"].apply(format_number)
        self.positions_df = positions_df
        self.positions = eligible_positions

    def get_house_margin_snapshot(
        self, house_policy: str, display_details: bool
    ) -> dict:
        # {"symbol": "NVDA", "pos": 2000}, {"symbol": "SQQQ", "pos": 2000}
        margin_snapshot = self.get_data(
            "POST",
            "house-policy/snapshot",
            {"positions": self.positions, "housePolicy": house_policy},
            {"details": display_details},
        )

        self.margin_snapshot = {
            "Current Equity": margin_snapshot["equity"],
            "SOD Equity": margin_snapshot["sodEquity"],
            "P&L": margin_snapshot["pl"],
            "TIMS": margin_snapshot["tims"],
            "Beta-1EventStress": margin_snapshot["beta-1EventStress"],
            "SingleName": margin_snapshot["singleName"],
            "CorrelationZeroStress": margin_snapshot["correlationZeroStress"],
        }

    def get_house_policy(self, display_details: bool) -> dict:
        margin = self.get_data(
            "POST", "house-policy", [self.sre_account], {"details": display_details}
        )
        if isinstance(margin, list) and len(margin) > 0:
            self.margin = {
                "Current Equity": format_number(margin[0]["equity"]),
                "SOD Equity": format_number(margin[0]["sodEquity"]),
                "P&L": format_number(margin[0]["pl"]),
                "TIMS": format_number(margin[0]["tims"]),
                "Beta-1EventStress": format_number(
                    margin[0]["riskShockMethods"]["beta-1EventStress"]
                ),
                "SingleName": format_number(
                    margin[0]["riskShockMethods"]["singleName"]
                ),
                "CorrelationZeroStress": format_number(
                    margin[0]["riskShockMethods"]["correlationZeroStress"]
                ),
            }
        else:
            # processed margin mock
            self.margin = {
                "Current Equity": 1405807.93,
                "SOD Equity": 1342168.72,
                "P&L": 63639.21,
                "TIMS": 199389.27,
                "Beta-1EventStress": -3812927.33,
                "SingleName": 0.0,
                "CorrelationZeroStress": -917020.5,
            }

    def get_market_risk(self, shocks: list[dict]):
        risk_result = self.get_data(
            "POST", "market-risk", {"accounts": [self.sre_account], "shocks": shocks}
        )
        risk_shocks = {}
        if self.sre_account in risk_result:
            for result in risk_result[self.sre_account]:
                shocks = result["shocks"]
                for shock in shocks:
                    if shock == "0%Mark/0%":
                        continue
                    if shock not in risk_shocks:
                        risk_shocks[shock] = shocks[shock]
                    else:
                        risk_shocks[shock] += shocks[shock]
        return risk_shocks

    def calc_ps_ladder(self, min_shock: int, max_shock: int, spx_price: float):
        ps_ladders = []
        threshold_ul = 94
        curr_shock = min_shock
        while curr_shock <= max_shock:
            ps_value = 0
            shocked_spx_price = spx_price * (1 - curr_shock / 100)
            for index, row in self.positions_df.iterrows():
                if (
                    row["%UL"] > threshold_ul
                    and "VIX" not in row["Underlying"]
                    and row["P/C"] == "P"
                ):
                    ps_value += (
                        max(row["Strike"] - shocked_spx_price, 0) * 100 * row["Lots"]
                    )
            ps_ladders.append(
                {
                    "SPX Change": "-" + str(curr_shock) + "%",
                    "PS Max Value": format_number(round(ps_value)),
                }
            )
            curr_shock += 1
        self.ps_ladders_df = pd.DataFrame(ps_ladders)

    def calc_dte_weighted_avg(self):
        threshold_ul = 93
        dte_wa = 0
        lots_total = 0
        for _, position in self.positions_df.iterrows():
            if (
                position["%UL"] > threshold_ul
                and position["Lots"] > 0
                and "VIX" not in position["Underlying"]
            ):
                dte_wa += position["Lots"] * position["DTE"]
                lots_total += position["Lots"]

        if lots_total != 0:
            self.dte_wa = round(dte_wa / lots_total, 2)
        else:
            self.dte_wa = 0

    def calc_mkt_risk(self):
        normal_risk_strings = construct_risk_shocks(0, 50, 25, -8, 1, 1)
        risk_ladder = self.get_market_risk(normal_risk_strings)
        if not risk_ladder:
            risk_ladder = {
                "1%Par/25%": -174375.41,
                "-8%Par/50%": -6020574.6899999995,
                "-3%Par/0%": 208138.75,
                "-6%Par/0%": 1267871.8099999998,
                "-8%Par/25%": -2010753.1399999997,
                "-2%Par/25%": -471212.02999999997,
                "-5%Par/25%": -581183.4099999999,
                "-2%Par/0%": 49339.41,
                "-6%Par/25%": -759225.4499999997,
                "-4%Par/50%": -2678290.5,
                "0%Par/25%": -266586.64,
                "-5%Par/50%": -3206767.67,
                "-1%Par/25%": -372182.68000000005,
                "-8%Par/0%": 973722.2499999995,
                "1%Par/50%": -851855.46,
                "0%Par/50%": -1130024.7,
                "-7%Par/25%": -1207628.5899999999,
                "-4%Par/25%": -546158.1500000001,
                "-4%Par/0%": 530771.3999999999,
                "-7%Par/0%": 1307154.1799999997,
                "-3%Par/50%": -2235357.34,
                "-6%Par/50%": -3896241.24,
                "-1%Par/0%": 6662.32,
                "-7%Par/50%": -4817916.07,
                "-3%Par/25%": -530195.0599999999,
                "-5%Par/0%": 947623.3599999999,
                "1%Par/0%": 21616.7,
                "-1%Par/50%": -1458612.04,
                "-2%Par/50%": -1832487.88,
                "0%Par/0%": 10065.21,
            }
        self.risk_ladder_df = construct_risk_shocks_df(risk_ladder)

        extreme_risk_strings = construct_risk_extreme_shocks([25, 50], [-40, -25])
        extreme_risk_ladder = self.get_market_risk(extreme_risk_strings)
        if not extreme_risk_ladder:
            extreme_risk_ladder = {
                "-40%Par/25%": 33186835.599999845,
                "-25%Par/50%": 15855971.23999998,
                "-25%Par/25%": 20147711.859999985,
                "-40%Par/50%": 37186835.599999845,
            }

        data_2 = {}
        for key, value in extreme_risk_ladder.items():
            if "Par/" in key:
                und_shock, vol_shock = key.split("Par/")
                if "Vol +" + str(vol_shock) not in data_2:
                    data_2["Vol +" + str(vol_shock)] = {}
                data_2["Vol +" + str(vol_shock)]["Und " + str(und_shock)] = (
                    format_number(round(value, 2))
                )
        extreme_risk_ladder_df = pd.DataFrame(
            data_2, index=["Und -40%", "Und -25%"], columns=["Vol +25%", "Vol +50%"]
        )
        self.extreme_risk_ladder_df = extreme_risk_ladder_df.transpose()

    def get_sre_html(self):
        selected_positions_cols = self.positions_df[
            [
                "DTE",
                "Lots (Display)",
                "Underlying",
                "Strike (Display)",
                "%UL",
                "IceChat String",
                "P/C",
                "Symbol",
            ]
        ]
        positions_df = selected_positions_cols.rename(
            columns={"Lots (Display)": "Lots", "Strike (Display)": "Strike"}
        )
        positions_df_html = positions_df.to_html(
            classes="positions", header="true", index=False
        )
        ps_max_value_df_html = self.ps_ladders_df.to_html(
            classes="ps_max_value", header="true", index=False
        )

        dte_avg = self.dte_wa
        # margin
        margin_values = self.margin

        account_status = {
            "Current Equity": [margin_values["Current Equity"]],
            "SOD Equity": [margin_values["SOD Equity"]],
            "P&L": [margin_values["P&L"]],
        }
        account_status_html = pd.DataFrame(account_status).to_html(
            classes="account_status", header="true", index=False
        )

        margin_status = {
            "Single Name": [margin_values["SingleName"]],
            "Beta-1 Event Stress": [margin_values["Beta-1EventStress"]],
            "Correlation Zero Stress": [margin_values["CorrelationZeroStress"]],
        }
        margin_status_html = pd.DataFrame(margin_status).to_html(
            classes="margin_status", header="true", index=False
        )

        # risk
        risk_ladder_df_html = self.risk_ladder_df.to_html(
            classes="risk_ladder", header="true", index=True
        )
        extreme_risk_ladder_df_html = self.extreme_risk_ladder_df.to_html(
            classes="extreme_risk_ladder", header="true", index=True
        )

        result = {
            'acct_status': account_status_html,
            'risk_ladder': risk_ladder_df_html,
            'extreme_risk_ladder': extreme_risk_ladder_df_html,
            'margin': margin_status_html,
            'positions': positions_df_html,
            'dte_avg': dte_avg,
            'ps_max_value': ps_max_value_df_html,
        }
        return result
