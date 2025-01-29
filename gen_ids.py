import csv
import json
from hrid import HRID

hruid = HRID()

judging_config_file = 'judging_config.json'

judging_config = None
with open(judging_config_file, 'r') as f:
    judging_config = json.load(f)

team_names_file = judging_config['team_names']
# use csv reader
team_names = []
with open(team_names_file, 'r') as f:
    reader = csv.reader(f)
    for row in reader:
        team_names += [row]


HEADER = "Team ID"
team_ids = [HEADER]
for team_info in team_names[1:]:
    team_id = hruid.generate()
    if 'Patient' in team_info[1]:
        team_id = f'{team_id}-prhi'
    if 'Yes' in team_info[2]:
        team_id = f'{team_id}-first'
    team_ids += [team_id]


with open(judging_config['team_ids'], 'w') as f:
    writer = csv.writer(f)
    for i in range(len(team_names)):
        writer.writerow([team_names[i][0], team_names[i][1], team_ids[i]])