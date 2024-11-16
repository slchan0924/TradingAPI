import yaml
import os
import requests

current_dir = os.path.dirname(__file__)


class createConnection:
    def __init__(self):
        with open(os.path.join(current_dir, "..", "config.yaml"), "r") as file:
            config = yaml.safe_load(file)
            # SRE
            self.sre_url_base = config["settings"]["SRE"]["url_base"]
            self.sre_username = config["credentials"]["SRE"]["username"]
            self.sre_password = config["credentials"]["SRE"]["password"]
            self.sre_account = config["credentials"]["SRE"]["account"]
            # ActivOne (Market Data)
            self.aop_username = config["credentials"]["ActivOnePlatform"]["username"]
            self.aop_password = config["credentials"]["ActivOnePlatform"]["password"]
            self.aop_host = config["settings"]["ActivOnePlatform"]["host"]
            # ActivContent (Snapshot Viewer)
            self.acp_username = config["credentials"]["ActivContentPlatform"][
                "username"
            ]
            self.acp_password = config["credentials"]["ActivContentPlatform"][
                "password"
            ]
            self.acp_host = config["settings"]["ActivContentPlatform"]["host"]
            self.acp_table = config["settings"]["ActivContentPlatform"]["table"]
            self.acp_output_fields = config["settings"]["ActivContentPlatform"][
                "output_fields"
            ]

        login_url = "{}/oauth/token?grant_type=client_credentials&client_id={}&client_secret={}".format(
            self.sre_url_base, self.sre_username, self.sre_password
        )
        login_obj = requests.post(login_url, headers={"Content-type": "text/plain"})
        if login_obj.status_code != 200:
            self.sre_access_token = "No Service"
        else:
            login_obj = login_obj.json()
            if "error" in login_obj:
                raise Exception("Login Error: {}".format(login_obj["error"]))
            self.sre_access_token = login_obj["access_token"]
