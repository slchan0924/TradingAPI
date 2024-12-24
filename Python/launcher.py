from flask import (
    Flask,
    session,
    render_template,
    request,
    redirect,
    url_for,
    copy_current_request_context,
)

from datetime import datetime
import json
from flask_socketio import SocketIO
import threading
import time
import pytz
import asyncio

lock = threading.Lock()

# Import from other python scripts
from activ import SpreadCalculation, option_data, usym_data, usym_map
from sre import SRERisk
from sqlite3db import createDatabase

app = Flask(__name__, template_folder="../templates", static_folder="../static")
socketio = SocketIO(app, async_mode="threading")
app.secret_key = "kkibbe"  # Required for session management


def read_input_data():
    with open("inputs.json", "r") as f:
        return json.load(f)


def write_data_to_json(data):
    with open("inputs.json", "w") as f:
        json.dump(data, f)


# Create global instances
sre_risk = SRERisk()
spread_calc = SpreadCalculation()
activ_session = spread_calc.connect_to_activ()
sre_html = ""


async def launch_subscription():
    count = 1
    while count <= 1:
        spread_calc.subscribe(activ_session)
        count += 1


def run_async_task():
    asyncio.run(launch_subscription())


# Route Functions
@app.route("/")
def home():
    # form_data = session.get("form_data", {})
    # if not form_data:
    form_data = read_input_data()
    # table here controls the output display of the strikes!
    return render_template(
        "index.html",
        table=session.get("symbols", "No data yet."),
        form_data=form_data,
        zip=zip,
    )


@app.route("/srepositions", methods=["POST"])
def get_positions():
    @copy_current_request_context
    def sre_run():
        run_count = 0
        global sre_html
        while run_count < 10:
            sre_risk.get_positions(usym_data)
            sre_risk.calc_ps_ladder(1, 10, usym_data[usym_map["SPX"]]["Mid"])
            sre_risk.calc_weighted_avg()
            sre_risk.get_house_policy(False)
            sre_risk.calc_mkt_risk()
            sre_html = sre_risk.get_sre_html()
            time.sleep(5)
            run_count += 1

    thread = threading.Thread(target=sre_run, daemon=True)
    thread.start()
    return "", 204


@app.route("/srepositions/check", methods=["GET"])
def check_sre_status():
    if sre_html:
        return {"ready": True, "html": sre_html}
    return {"ready": False}


@app.route("/submit", methods=["POST"])
def collectdataFromWebsite():
    first_time = True
    with lock:
        db = createDatabase()
        # 1 sell strike only pair with 1 buy strike
        form_data = {
            "target_symbols": list(
                filter(None, request.form.getlist("target_symbols[]"))
            ),
            "target_strike_ranges": list(
                filter(None, request.form.getlist("target_strike_ranges[]"))
            ),
            "expiry_combo": list(filter(None, request.form.getlist("expiry_combo[]"))),
            "ps_ul": list(filter(None, request.form.getlist("ps_ul[]"))),
            "ps_points_wide": list(
                filter(None, request.form.getlist("ps_points_wide[]"))
            ),
            "ps_expiry_range": list(
                filter(None, request.form.getlist("ps_expiry_range[]"))
            ),
            "points_over": request.form.get("points_over"),
            "showLongBidVolume": request.form.get("showLongBidVolume"),
            "showLongAskVolume": request.form.get("showLongAskVolume"),
            "showShortBidVolume": request.form.get("showShortBidVolume"),
            "showShortAskVolume": request.form.get("showShortAskVolume"),
            "c_first_d": request.form.get("c_first_d"),
            "c_second_d": request.form.get("c_second_d"),
            "c_avg_start_time": request.form.get("c_avg_start_time") or "16:00",
            "c_avg_end_time": request.form.get("c_avg_end_time") or "16:30",
            "selectedTimezone": request.form.get("selectedTimezone") or "Asia/Tokyo",
        }
        write_data_to_json(form_data)
        session["form_data"] = form_data
        spread_calc.get_symbols(
            form_data["target_symbols"],
            form_data["expiry_combo"],
            ["SPX", "SPXW"],
            form_data["ps_expiry_range"],
        )

        # update viewer will only be invoked if input params are changed
        re_subscribe = spread_calc.invoke_update_viewer()
        if re_subscribe or first_time:
            first_time = True
            thread = threading.Thread(target=run_async_task)
            thread.start()

        tz_selected = pytz.timezone(form_data["selectedTimezone"])
        current_time = datetime.now(tz_selected)
        db.cleanup(current_time)
        c_avg_start = tz_selected.localize(
            datetime.strptime(form_data["c_avg_start_time"], "%H:%M").replace(
                year=current_time.year, month=current_time.month, day=current_time.day
            )
        )
        c_avg_end = tz_selected.localize(
            datetime.strptime(form_data["c_avg_end_time"], "%H:%M").replace(
                year=current_time.year, month=current_time.month, day=current_time.day
            )
        )

        run_count = 0
        spread_start_run_time = datetime.now(tz_selected)
        pairs_start_run_time = datetime.now(tz_selected)
        while run_count < 20:
            c_avg = db.get_rolling_c_dollar_average(10)
            ps_mid_avg = db.get_rolling_mid_average(10)
            try:
                put_spread_pairs = spread_calc.get_put_spread_pairs(
                    form_data["ps_ul"],
                    form_data["ps_points_wide"],
                    form_data["ps_expiry_range"],
                    ps_mid_avg,
                )
                spread_current_run_time = datetime.now(tz_selected)
                if (
                    (spread_current_run_time - spread_start_run_time).seconds >= 30
                    and spread_current_run_time > c_avg_start
                    and spread_current_run_time < c_avg_end
                ):
                    print("Inserting Mid Data")
                    db.insertMidData(put_spread_pairs, spread_current_run_time)
                    spread_start_run_time = spread_current_run_time
                session["put_spread_pairs"] = put_spread_pairs
                socketio.emit("put_spread_pairs", put_spread_pairs)
            except Exception as error:
                print("An exception occurred while getting put spread:", error)
            try:
                buy_sell_pairs = spread_calc.get_buy_sell_pairs(
                    form_data["target_symbols"],
                    form_data["target_strike_ranges"],
                    form_data["expiry_combo"],
                    form_data["points_over"],
                    c_avg,
                )
                pairs_current_run_time = datetime.now(tz_selected)
                if (
                    (pairs_current_run_time - pairs_start_run_time).seconds >= 30
                    and pairs_current_run_time > c_avg_start
                    and pairs_current_run_time < c_avg_end
                ):
                    print("Inserting C$ Data")
                    db.insertCDollarData(buy_sell_pairs, pairs_current_run_time)
                    pairs_start_run_time = pairs_current_run_time
                session["buy_sell_pairs"] = buy_sell_pairs
                socketio.emit("buy_sell_pairs", buy_sell_pairs)
            except Exception as error:
                print("An exception occurred while getting buy/sell pairs:", error)
            time.sleep(5)
            run_count += 1
    return redirect(url_for("home"))


@app.route("/pairs/<usym>/<expiry_combo>")
def pairs(usym, expiry_combo):
    buy_sell_pairs = session.get("buy_sell_pairs", "{}")
    if expiry_combo in buy_sell_pairs[usym]:
        usym_pairs = buy_sell_pairs[usym][expiry_combo]
        return render_template(
            "pairs.html",
            usym=usym,
            expiry_combo=expiry_combo,
            pairs=json.dumps(usym_pairs),
        )


@app.route("/putSpread")
def spread():
    put_spread_pairs = session.get("put_spread_pairs", "{}")
    return render_template("spread.html", pairs=json.dumps(put_spread_pairs))


@app.route("/SRE")
def SRE():
    return render_template("sre.html", data=sre_html)


if __name__ == "__main__":
    # threading.Thread(target=launch_subscription, daemon=True).start()
    socketio.run(app, allow_unsafe_werkzeug=True)
