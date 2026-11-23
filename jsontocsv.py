import json
import csv

with open("CESSDA_Topics_All_Datasets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

with open("CESSDA_Topics_All_Datasets.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)