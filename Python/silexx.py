import requests
import re
import pandas as pd
from datetime import datetime
from start_connection import createConnection

relogin_mins = 55

def ice_chat_to_info(ice_chat_string: str):
    # Current date for reference
    today = datetime.now()
    
    # Regular expression to match the option string pattern
    pattern = r"(\w+)\s+(\w+\s+\d{1,2}),\s+(\d+)\s+(puts|calls)"
    match = re.search(pattern, ice_chat_string, re.IGNORECASE)

    if not match:
        return None

    # Extract the components
    underlying = match.group(1)[:3]
    expiry_str = match.group(2)
    strike = match.group(3)
    option_type = 'P' if match.group(4).lower() == 'puts' else 'C'
    
    # Convert expiry date to required format
    expiry_date = datetime.strptime(expiry_str, "%b %d")
    # Set the year to the current year
    expiry_date = expiry_date.replace(year=today.year)

    # Check if expiry is already passed, if so, set it to the next year
    if expiry_date < today:
        expiry_date = expiry_date.replace(year=today.year + 1)

    # Format expiry date to MMDDYY
    expiry_formatted = expiry_date.strftime("%y%m%d")

    return f"{underlying}/{expiry_formatted}/{strike}{option_type}"

class silexx_positions_and_trades(createConnection):
    def __init__(self):
        createConnection.__init__(self)
        self.login_to_silexx()

    def login_to_silexx(self):
        # login to silexx
        login_cred = requests.post(
            url=self.login_url, 
            json={
                "application_name": "SilexxAPI",
                "application_version": "1.0",
                "domain": "silexx",
                "password": self.silexx_password,
                "username": self.silexx_username
            }, 
            headers={
                "Content-type": "application/json"
            })
        self.login_cred = login_cred.json()
        if 'token' in self.login_cred:
            self.token = self.login_cred['token']
        # track this info, when it's around 50-55 minutes need to re-login and avoid timeout
        self.last_login_time = datetime.now()

    def get_positions(self, account_id: str, symbol = ""):
        if symbol != "":
            url = self.url + "/portfolio/positions?accountIdAndSymbol.accountId={}&accountIdAndSymbol.symbol={}".format(account_id, symbol)
        else:
            url = self.url + "/portfolio/positions?accountID={}".format(account_id)
        headers = {
            "Authorization": "Bearer {}".format(self.token),
            # "Content-type": "application/json",
        }
        print(headers)
        positions = requests.get(url, headers=headers)
        print(positions.json())
        # a bit of transformation to the table we wanna see
        return positions.json()
    
    def positions_to_html(self):
        if len(self.positions_df.index) > 0:
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
                    "Business DTE",
                ]
            ]
            positions_df = selected_positions_cols.rename(
                columns={"Lots (Display)": "Lots", "Strike (Display)": "Strike"}
            )
        else:
            # Blank DF if there are no positions
            positions_df = pd.DataFrame(
                columns=[
                    "DTE",
                    "Lots",
                    "Underlying",
                    "Strike",
                    "%UL",
                    "IceChat String",
                    "P/C",
                    "Symbol",
                    "Business DTE",
                ]
            )
        positions_df_html = positions_df.to_html(
            classes="positions", header="true", index=False, table_id="positions_table"
        )
        self.positions_df_html = positions_df_html
    
    def generate_order(self, account_id: str, side: str, order: dict, validate: bool):
        '''
        Function Params:
        account_id: Account ID to book positions in
        side: Can take Buy, Sell or Spread

        Order Params:
        ord_type: ORD_TYPE_LIMIT, ORD_TYPE_MARKET, ORD_TYPE_STOP
        price_type: PRICE_TYPE_PER_UNIT
        position_effect: POSITION_EFFECT_AUTO, POSITION_EFFECT_CLOSE, POSITION_EFFECT_OPEN
        tif: TIF_DAY, TIF_GTC?
        side: SIDE_BUY, SIDE_SELL, SIDE_SHORT_SELL

        '''
        qty = order["Quantity"]
        # get the long and short leg info
        if side == 'Spread':
            long_leg_symbol = ice_chat_to_info(order["Buy Leg IceChat"])
            short_leg_symbol = ice_chat_to_info(order["Sell Leg IceChat"])
            # generate the order
            order = {
                "account_id": account_id,
                "legs": [
                    {
                        "position_effect": "POSITION_EFFECT_AUTO",
                        "ratio": 1,
                        "side": "SIDE_BUY",
                        "symbol": {
                            "value": long_leg_symbol,
                        } 
                    },
                    {
                        "position_effect": "POSITION_EFFECT_AUTO",
                        "ratio": 1,
                        "side": "SIDE_SHORT_SELL",
                        "symbol": {
                            "value": short_leg_symbol,
                        }
                    }
                ],
                "quantity": qty,
                "price": {
                    "value": order["C"],
                },
                "ord_type": "ORD_TYPE_LIMIT",
                "price_type": "PRICE_TYPE_PER_UNIT",
                "tif": "TIF_DAY",
                "route": "CBOE"
            }
            if validate:
                return self.validate_before_execute(order, True)
            return self.execute_multi_leg_order(order)
        else:
            price = order["Price"]
            trade_side = order["Side"]
            symbol = ice_chat_to_info(order["IceChat"])
            order = {
                "account_id": account_id,
                "ord_type": "ORD_TYPE_LIMIT",
                "position_effect": "POSITION_EFFECT_AUTO",
                "price": {
                    "value": price
                },
                "price_type": "PRICE_TYPE_PER_UNIT",
                "qty": qty,
                "route": "CBOE",
                "side": "SIDE_BUY" if trade_side == 'Buy' else "SIDE_SELL",
                "symbol": {
                    "value": symbol,
                },
                "tif": "TIF_DAY",
            }
            if validate:
                return self.validate_before_execute(order, False)
            return self.execute_order(order)

    def execute_order(self, order: dict):
        order_url = self.url + "/OrderService/CreateOrder"
        order_id = requests.post(order_url, data=order)
        print("Order Executed, Order ID: {}", order_id)
        return order_id
    
    def execute_multi_leg_order(self, order: dict):
        multi_leg_url = self.url + "/OrderService/CreateMultiLegOrder"
        multi_leg_order_id = requests.post(multi_leg_url, data=order)
        print("Multi Leg Order Executed, Order ID: {}", multi_leg_order_id)
        return multi_leg_order_id

    def validate_before_execute(self, order: dict, is_multi_leg: bool):
        validate_url = self.url + "/OrderService/ValidateCreateOrderRisk"
        validate_order = requests.post(validate_url, data=order)
        if validate_order["status"] == "Success":
            if is_multi_leg:
                return self.execute_multi_leg_order(order)
            else:
                return self.execute_order(order)
        print("Validation Error {}", validate_order)
    
if __name__ == "__main__":
    # print(ice_chat_to_info("SPXW Dec 17, 4552 puts"))
    silexx = silexx_positions_and_trades()
    silexx.get_positions("kkibbe")