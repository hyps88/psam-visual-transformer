import streamlit as st
import requests
import json

def send_notification(user_name, project_name, file_count, formats):
    """
    Sends a simple text-based alert to the Slack Webhook.
    """
    try:
        webhook_url = st.secrets["SLACK_WEBHOOK_URL"]
    except Exception:
        return False

    format_list = ", ".join([f.get('label', 'Custom') for f in formats])
    
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🖼️ New Image Batch Processed"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Project:* {project_name}\n*Creator:* {user_name}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Images:*\n{file_count}"},
                    {"type": "mrkdwn", "text": f"*Formats:*\n{format_list}"}
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "📍 PSAM Visual Transformer — Automated Marketing Alert"}
                ]
            }
        ]
    }

    try:
        requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'}, timeout=10)
        return True
    except Exception:
        return False
