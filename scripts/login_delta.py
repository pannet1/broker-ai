import yaml
import sys

with open("/home/pannet1/programs/python/github.com/pannet1/ai_broker.yml") as f:
    config = yaml.safe_load(f)

delta_cfg = config["delta"]
api_key = delta_cfg["api_key"]
api_secret = delta_cfg["api_secret"]

from broker_ai.delta import Delta

delta = Delta(api_key=api_key, api_secret=api_secret)
result = delta.authenticate()

if result:
    print(f"Login SUCCESS: {result}")
else:
    print("Login FAILED")
    sys.exit(1)
