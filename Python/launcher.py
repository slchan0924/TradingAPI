from flask import (
    Flask,
    session,
    render_template,
    request,
    jsonify,
    copy_current_request_context
)

from datetime import datetime
import pytz
import json
from flask_socketio import SocketIO
import threading
import time

# Import from other python scripts
from activ import SpreadCalculation, option_data, usym_data, usym_map
from sre import SRERisk
from sqlite3db import createDatabase

current_time_in_NY = datetime.now(pytz.timezone("America/New_York"))
app = Flask(__name__, template_folder="../templates", static_folder="../static")
socketio = SocketIO(app, async_mode='threading')
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
spread_calc.read_activ_strikes()
db = createDatabase()
sre_html = ""

def launch_subscription():
    """
    spread_calc.get_symbols(["SPY", "SPX", "QQQ"], ["10,7", "11,6", "10,5"], "SPX", ["5,6"])
    spread_calc.invoke_update_viewer('./symbols.txt')
    """
    spread_calc.subscribe(activ_session)

# Route Functions
@app.route("/")
def home():
    form_data = session.get("form_data", {})
    if not form_data:
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
            sre_risk.calc_dte_weighted_avg()
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
    # 1 sell strike only pair with 1 buy strike
    form_data = {
        "target_symbols": list(filter(None, request.form.getlist("target_symbols[]"))),
        "target_strike_ranges": list(
            filter(None, request.form.getlist("target_strike_ranges[]"))
        ),
        "expiry_combo": list(filter(None, request.form.getlist("expiry_combo[]"))),
        "ps_ul": list(filter(None, request.form.getlist("ps_ul[]"))),
        "ps_points_wide": list(filter(None, request.form.getlist("ps_points_wide[]"))),
        "ps_expiry_range": list(
            filter(None, request.form.getlist("ps_expiry_range[]"))
        ),
        "coloring": list(filter(None, request.form.getlist("coloring[]"))),
        "c_value": list(filter(None, request.form.getlist("c_value[]"))),
        "points_over": request.form.get("points_over"),
        "c_first_d": request.form.get("c'"),
        "c_second_d": request.form.get("c''"),
    }
    write_data_to_json(form_data)
    session["form_data"] = form_data
    spread_calc.get_symbols(
        form_data["target_symbols"],
        form_data["expiry_combo"],
        "SPX",
        form_data["ps_expiry_range"],
    )
    # spread_calc.invoke_update_viewer('./symbols.txt')

    run_count = 0
    while run_count < 10:
        put_spread_pairs = spread_calc.get_put_spread_pairs(
            form_data["ps_ul"], form_data["ps_points_wide"], form_data["ps_expiry_range"]
        )
        buy_sell_pairs = spread_calc.get_buy_sell_pairs(
            form_data["target_symbols"],
            form_data["target_strike_ranges"],
            form_data["expiry_combo"],
            form_data["points_over"],
        )
        session["buy_sell_pairs"] = buy_sell_pairs
        session["put_spread_pairs"] = put_spread_pairs
        socketio.emit("option_data", option_data)
        socketio.emit("put_spread_pairs", put_spread_pairs)
        socketio.emit("buy_sell_pairs", buy_sell_pairs)
        db.insertCDollarData(buy_sell_pairs)
        db.cleanup()
        run_count += 1
        time.sleep(10)
        
    return jsonify(result="Good")


@app.route("/pairs/<usym>")
def pairs(usym):
    # get all relevant strikes within range
    # calc buy/sell spreads according to original logic
    # calc C and C$ -> C$/DDif
    buy_sell_pairs = session.get("buy_sell_pairs", "{}")
    usym_pairs = buy_sell_pairs[usym]
    socketio.emit("update_pairs", {"usym": usym, "pairs": usym_pairs})
    return render_template("pairs.html", usym=usym, pairs=json.dumps(usym_pairs))


@app.route("/putSpread")
def spread():
    put_spread_pairs = session.get("put_spread_pairs", "{}")
    return render_template("spread.html", pairs=json.dumps(put_spread_pairs))


@app.route("/SRE")
def SRE():
    return render_template("sre.html", data=sre_html)


if __name__ == "__main__":
    threading.Thread(target=launch_subscription, daemon=True).start()
    socketio.run(app, allow_unsafe_werkzeug=True, debug=True)
