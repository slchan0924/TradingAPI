from datetime import datetime, timedelta
import sqlite3
import random
import time
import pandas as pd

rebuild_db = False


class createDatabase:
    def __init__(self):
        db_con_avg = sqlite3.connect("api_data_store.db")
        cur_avg = db_con_avg.cursor()
        cur_avg.execute(
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

        db_con_history = sqlite3.connect("eod_cdollar.db")
        cur_eod = db_con_history.cursor()
        cur_eod.execute(
            """
            CREATE TABLE IF NOT EXISTS CEod (
                OptionSymbol varchar(255), 
                Underlying varchar(255), 
                CDollar double(2),
                Mid double(2)
            )
        """
        )
        db_con_avg.commit()
        db_con_history.commit()
        self.Cursor_Eod = cur_eod
        self.Cursor_Avg = cur_avg
        self.Connection_Eod = db_con_history
        self.Connection_Avg = db_con_avg

    def run_query(self, command: str):
        connection = self.Connection
        df = pd.read_sql_query(command, connection)
        print(df)

    def cleanup(self, current_time: datetime):
        cursor = self.Cursor_Avg
        connection = self.Connection_Avg
        cutoff_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
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

    def insertCDollarData(self, data: dict[dict[dict[list[dict]]]], current_time):
        cursor = self.Cursor_Avg
        connection = self.Connection_Avg
        data_to_insert = []
        for underlying in data:
            for expiry_range in data[underlying]:
                for position_data in data[underlying][expiry_range]:
                    data_to_insert.append(
                        tuple(
                            (
                                position_data["Sell Symbol"]
                                + "-"
                                + position_data["Buy Symbol"],
                                underlying,
                                float(position_data["C$"].replace(",", "")),
                                current_time,
                            )
                        )
                    )

        cursor.executemany(
            """
            INSERT INTO CHistory (OptionSymbol, Underlying, CDollar, Timestamp) VALUES (?, ?, ?, ?)
        """,
            data_to_insert,
        )

        connection.commit()

    def insertMidData(self, data: list[dict], current_time):
        cursor = self.Cursor_Avg
        connection = self.Connection_Avg
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
                        current_time,
                    )
                )
            )

        cursor.executemany(
            """
            INSERT INTO CHistory (OptionSymbol, Underlying, Mid, Timestamp) VALUES (?, ?, ?, ?)
        """,
            data_to_insert,
        )

        connection.commit()

    def insert_eod_cavg_record(self, data: dict[dict[dict[list[dict]]]]):
        cursor = self.Cursor_Eod
        connection = self.Connection_Eod
        data_to_insert = []
        for underlying in data:
            for expiry_range in data[underlying]:
                for position_data in data[underlying][expiry_range]:
                    symbol = (
                        position_data["Sell Symbol"] + "-" + position_data["Buy Symbol"]
                    )
                    data_to_insert.append(
                        tuple(
                            (
                                symbol,
                                underlying,
                                float(position_data["C$"].replace(",", "")),
                                symbol,
                            )
                        )
                    )

        execute_query = """
            UPDATE CEod
            SET OptionSymbol = ?, Underlying = ?, CDollar = ?
            WHERE OptionSymbol = ?
        """
        cursor.executemany(execute_query, data_to_insert)

        connection.commit()

    def insert_eod_mid_record(self, data: list[dict]):
        cursor = self.Cursor_Eod
        connection = self.Connection_Eod
        data_to_insert = []
        for position_data in data:
            symbol = position_data["Sell Symbol"] + "-" + position_data["Buy Symbol"]
            data_to_insert.append(
                tuple((symbol, "SPX", position_data["MidAvg"], symbol))
            )

        execute_query = """
            UPDATE CEod
            SET OptionSymbol = ?, Underlying = ?, Mid = ?
            WHERE OptionSymbol = ?
        """
        cursor.executemany(execute_query, data_to_insert)

        connection.commit()

    def get_rolling_c_dollar_average(self, rolling_average_mins: int):
        cursor = self.Cursor_Avg
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
        cursor = self.Cursor_Avg
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

    def get_eod_record(self, metric: str):
        # metric can be either CAvg or Mid
        cursor = self.Cursor_Eod
        query_str = """
            SELECT OptionSymbol, AVG({}) 
            FROM CAvg 
            AND {} IS NOT NULL
            GROUP BY OptionSymbol
        """.format(
            metric, metric
        )
        cursor.execute(query_str)
        eod_record = cursor.fetchall()
        result_dict = {row[0]: row[1] for row in eod_record}
        return result_dict


if __name__ == "__main__":
    db = createDatabase()
    run = False
    while run is True:
        data = {
            "SPX": [
                {
                    "Strike": 450,
                    "Sell Symbol": "Test1",
                    "Buy Symbol": "Test2",
                    "Expiry": "2024-11-11",
                    "C$": "150",  # random.uniform(1.0, 10.0),
                    "Call/Put": "P",
                }
            ],
            "QQQ": [
                {
                    "Strike": 470,
                    "Sell Symbol": "Test3",
                    "Buy Symbol": "Test4",
                    "Expiry": "2024-11-12",
                    "C$": "200",  # random.uniform(1.0, 10.0),
                    "Call/Put": "P",
                }
            ],
        }
        db.insertCDollarData(data)
        db.cleanup()
        time.sleep(5)
