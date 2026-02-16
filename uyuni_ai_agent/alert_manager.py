import requests
import datetime

from uyuni_ai_agent.config import load_config
from uyuni_ai_agent.schemas import AnalysisResult


# Ref: https://prometheus.io/docs/alerting/latest/alerts_api/
# Ref: https://prometheus.io/docs/alerting/latest/notification_examples/
def send_to_alertmanager(
    analysis,
    severity="info",
    minion_id="",
    metric_name="",
    current_value=None,
    threshold=None,
):
    """Send an enriched alert to AlertManager.

    Args:
        analysis: AnalysisResult from the ReAct agent
        severity: alert severity (info, warning, critical)
        minion_id: the affected minion
        metric_name: the metric that triggered the alert
        current_value: the metric value that triggered the alert
        threshold: the threshold that was exceeded
    """
    config = load_config()
    url = f"{config['alertmanager']['url']}/api/v2/alerts"

    annotations = {
        "summary": f"{metric_name} issue on {minion_id}: {analysis.root_cause}",
        "description": analysis.description,
        "root_cause": analysis.root_cause,
        "remediation": "\n".join(f"• {step}" for step in analysis.remediation),
        "evidence": "\n".join(f"• {item}" for item in analysis.evidence),
    }
    if current_value is not None:
        annotations["current_value"] = f"{current_value:.1f}%"
    if threshold is not None:
        annotations["threshold"] = f"{threshold:.1f}%"

    payload = [{
        "labels": {
            "alertname": "AIAgentResponse",
            "severity": severity,
            "urgency": analysis.urgency,
            "source": "ai-bot",
            "minion": minion_id,
            "metric": metric_name,
        },
        "annotations": annotations,
        "startsAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }]

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return "Success: Alert routed through Alertmanager."
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Failed: {str(e)}"
