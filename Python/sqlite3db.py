from datetime import datetime, timedelta
import sqlite3
import random
import time
import pandas as pd
import pytz

rebuild_db = False


class createDatabase:
    def __init__(self):
        db_con = sqlite3.connect("spreadCalc.db")
        cur = db_con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS CHistory (
                OptionSymbol varchar(255), 
                Underlying varchar(255), 
                CDollar double(2),
                Mid double(2),
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        db_con.commit()
        self.Cursor = cur
        self.Connection = db_con

    def run_query(self, command: str):
        connection = self.Connection
        df = pd.read_sql_query(command, connection)
        print(df)

    def cleanup(self):
        cursor = self.Cursor
        connection = self.Connection
        cutoff_time = datetime.now(pytz.timezone("America/New_York")).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # clean up all from yesterday!
        cursor.execute(
            """
            DELETE FROM CHistory WHERE timestamp < ?
        """,
            (cutoff_time,),
        )
        connection.commit()

        if rebuild_db is True:
            cursor.execute("VACUUM")
            connection.commit()

    def insertCDollarData(self, data: dict[dict[list[dict]]]):
        cursor = self.Cursor
        data_to_insert = []
        for underlying in data:
            for position_data in data[underlying]:
                data_to_insert.append(
                    tuple(
                        (
                            position_data["Sell Symbol"]
                            + "-"
                            + position_data["Buy Symbol"],
                            underlying,
                            float(position_data["C$"].replace(",", "")),
                            datetime.now(pytz.timezone("America/New_York")),
                        )
                    )
                )

        cursor.executemany(
            """
            INSERT INTO CHistory (OptionSymbol, Underlying, CDollar, Timestamp) VALUES (?, ?, ?, ?)
        """,
            data_to_insert,
        )

    def insertMidData(self, data: list[dict]):
        cursor = self.Cursor
        data_to_insert = []
        for position_data in data:
            data_to_insert.append(
                tuple(
                    (
                        position_data["Sell Symbol"]
                        + "-"
                        + position_data["Buy Symbol"],
                        "SPX",
                        position_data["MidAvg"],
                        datetime.now(pytz.timezone("America/New_York")),
                    )
                )
            )

        cursor.executemany(
            """
            INSERT INTO CHistory (OptionSymbol, Underlying, Mid, Timestamp) VALUES (?, ?, ?, ?)
        """,
            data_to_insert,
        )

    def get_rolling_c_dollar_average(self, rolling_average_mins: int):
        cursor = self.Cursor
        cutoff_time = datetime.now() - timedelta(minutes=rolling_average_mins)
        cursor.execute(
            """
            SELECT OptionSymbol, AVG(CDollar) 
            FROM CHistory 
            WHERE Timestamp >= ?
            AND CDollar IS NOT NULL
            GROUP BY OptionSymbol
        """,
            (cutoff_time,),
        )
        averageCDollar = cursor.fetchall()
        result_dict = {row[0]: row[1] for row in averageCDollar}
        return result_dict

    def get_rolling_mid_average(self, rolling_average_mins: int):
        cursor = self.Cursor
        cutoff_time = datetime.now() - timedelta(minutes=rolling_average_mins)
        cursor.execute(
            """
            SELECT OptionSymbol, AVG(Mid) 
            FROM CHistory 
            WHERE Timestamp >= ?
            AND Mid IS NOT NULL
            GROUP BY OptionSymbol
        """,
            (cutoff_time,),
        )
        averageCDollar = cursor.fetchall()
        result_dict = {row[0]: row[1] for row in averageCDollar}
        return result_dict


if __name__ == "__main__":
    db = createDatabase()
    run = False
    while run is True:
        data = {
            "SPX": {
                "Test1": {
                    "Strike": 450,
                    "Expiry": "2024-11-11",
                    "CDollar": random.uniform(1.0, 10.0),
                    "Call/Put": "P",
                }
            },
            "QQQ": {
                "Test2": {
                    "Strike": 470,
                    "Expiry": "2024-11-12",
                    "CDollar": random.uniform(1.0, 10.0),
                    "Call/Put": "P",
                }
            },
        }
        db.insertCDollarData(data)
        db.cleanup()
        time.sleep(5)
