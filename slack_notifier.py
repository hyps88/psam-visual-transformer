import requests
import json

# Replace this with your actual Webhook URL from Step 1
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/HERE"

def send_notification(user_name, project_name, file_count, formats):
    """
    Sends a formatted alert to the PSAM Marketing Channel.
    """
    # Create a list of the formats used for the message
    format_list = ", ".join([f.get('label', 'Custom') for f in formats])
    
    payload = {
        "text": f"🚀 *New Assets Ready for Marketing!*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚀 *New Assets Ready for Marketing!*\n*Project:* {project_name}\n*Creator:* {user_name}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Files Processed:*\n{file_count}"},
                    {"type": "mrkdwn", "text": f"*Formats:*\n{format_list}"}
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "📍 Processed via PSAM Visual Transformer"}
                ]
            }
        ]
    }

    try:
        response = requests.post(
            SLACK_WEBHOOK_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Slack Error: {e}")
        return False
