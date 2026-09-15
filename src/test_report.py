import json

from report import get_report_data


report = get_report_data()

print(json.dumps(report, indent=2))