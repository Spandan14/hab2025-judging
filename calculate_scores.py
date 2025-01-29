import json
import numpy as np
import pandas as pd
import topsis

judging_config_file = 'judging_config.json'

judging_config = None
with open(judging_config_file, 'r') as f:
    judging_config = json.load(f)

scores_file = judging_config['scores_file']
scores = pd.read_csv(scores_file)
scores = pd.DataFrame.to_numpy(scores)

team_names = {}
agggregate_scores = {}
for team in scores:
    team_id = team[0]
    team_name = team[1]
    team_score = team[2:]
    team_names[team_id] = team_name
    if team_id not in agggregate_scores:
      agggregate_scores[team_id] = team_score
    else:
      agggregate_scores[team_id] = np.add(agggregate_scores[team_id], team_score)

# calculate scores
OVERALL_WEIGHTS = [18, 18, 18, 18, 18, 10]
ARCADE_WEIGHTS = [14, 14, 14, 14, 14, 30]
DESIGN_WEIGHTS = [14, 14, 30, 14, 14, 14]
CRITERIA = [True for _ in range(6)]

all_scores = []
topsis_id = {}
for i, team_score in enumerate(agggregate_scores.items()):
  team_id, score = team_score
  all_scores.append(score)
  topsis_id[i] = team_id 

def rank(weights, filename):
  ts = topsis.Topsis(all_scores, weights, CRITERIA)
  ts.calc()
  ts_ranks = ts.ranking(ts.worst_similarity)

  final_outputs = []
  for i in range(len(ts_ranks)):
      team_rank = ts_ranks[i]
      team_id = topsis_id[i]
      team_name = team_names[team_id]
      team_score = agggregate_scores[team_id]
      team_total_score = np.sum(np.multiply(team_score, weights))
      team_topsis_score = ts.worst_similarity[i]
      output = f'{team_rank} | {team_id} | {team_name} | {team_score} | {team_total_score} | {team_topsis_score}'
      final_outputs.append((team_rank, output))
  
  final_outputs.sort(key=lambda x: x[0])
  with open(filename, 'w') as f:
    for output in final_outputs:
      f.write(output[1] + '\n')


rank(OVERALL_WEIGHTS, 'overall_rankings.txt')
rank(ARCADE_WEIGHTS, 'arcade_rankings.txt')
rank(DESIGN_WEIGHTS, 'design_rankings.txt')