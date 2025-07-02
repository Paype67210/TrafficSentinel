import requests

def send_slack_alert(message):
    webhook_url = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    payload = {"text": message}
    requests.post(webhook_url, json=payload)
