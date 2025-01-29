import json
import datetime
from ortools.sat.python import cp_model
import pandas as pd
# import matplotlib.pyplot as plt
import numpy as np

# read config file
CONFIG_FILE = 'judging_config.json'
config = None
with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# read all setup data
team_ids = pd.read_csv(config["team_ids"])
judges_file = pd.read_csv(config["judge_names"])
rooms_file = pd.read_csv(config["room_names"])
hab_reps_file = pd.read_csv(config["rep_names"])

num_teams = len(team_ids)
team_names = team_ids["Team Name"].tolist()
team_ids = team_ids['Team ID'].tolist()
prhi_team_ids = [team_id for team_id in team_ids if 'prhi' in team_id] # these teams must meet the prhi judge

num_judges = 9 # 8 + 1 for PRHI
judges = judges_file["Judge Name"].tolist()

# prhi room needs to be separate
prhi_room = rooms_file.loc[rooms_file["Org"] == "PRHI"].iloc[0]
prhi_room_name = prhi_room["Room Name"]
rooms_file = rooms_file.drop(prhi_room.name)
rooms = rooms_file["Room Name"].tolist()

hab_reps = hab_reps_file["Rep Name"].tolist()

room_info = []
for room in list(np.array_split(judges, len(rooms))):
    # room info is always judges, room, rep
    room_info += [(room.tolist(), rooms.pop(0), hab_reps.pop(0))]

# read scheduling info
num_slots = config["scheduling"]["slot_count"]

# problem parameters
pres_per_team = config["presentation_count"]

# prhi judge availability (only available in certain slots)
judging_start = datetime.datetime.strptime(config["scheduling"]["start_time"], "%H:%M")
slot_delta = datetime.timedelta(minutes=config["scheduling"]["slot_length"])

prhi_judge = num_judges - 1

prhi_start = datetime.datetime.strptime(config["scheduling"]["prhi_window_start"], "%H:%M")
prhi_end = datetime.datetime.strptime(config["scheduling"]["prhi_window_end"], "%H:%M")

prhi_judge_slots = set()
for slot in range(num_slots):
    slot_time = judging_start + slot * slot_delta
    if prhi_start <= slot_time <= prhi_end:
        prhi_judge_slots.add(slot)

model = cp_model.CpModel()

# Variables: assignments[team, slot, judge] (1 if assigned, 0 otherwise)
assignments = {}
for team in range(num_teams):
    for slot in range(num_slots):
        for judge in range(num_judges):
            assignments[(team, slot, judge)] = model.NewBoolVar(f"T{team}_S{slot}_J{judge}")

# Constraint: Each team must be scheduled to see exactly 2 H@B judges (0-7)
for team in range(num_teams):
    model.Add(sum(assignments[(team, slot, judge)] 
                  for slot in range(num_slots) 
                  for judge in range(num_judges - 1)) == pres_per_team)

# Constraint: Each judge must be assigned up to once per slot
for slot in range(num_slots):
    for judge in range(num_judges - 1):
        model.Add(sum(assignments[(team, slot, judge)] for team in range(num_teams)) <= 1)

# Constraint: Each team must be assignd up to once per slot (including PRHI judge)
for team in range(num_teams):
    for slot in range(num_slots):
        model.Add(sum(assignments[(team, slot, judge)] for judge in range(num_judges)) <= 1)

# Constraint: No judge-team pairing should appear twice
for team in range(num_teams):
    for judge in range(num_judges - 1):
        model.Add(sum(assignments[(team, slot, judge)] for slot in range(num_slots)) <= 1)

# Constraint: No back-to-back judging slots
for team in range(num_teams):
    for slot in range(num_slots - 1):
        model.Add(sum(assignments[(team, slot, judge)] for judge in range(num_judges - 1)) +
                  sum(assignments[(team, slot + 1, judge)] for judge in range(num_judges - 1)) <= 1)

# Constraint: PRHI teams must meet the PRHI judge in PRHI slots, and no other interactions present
for slot in range(num_slots):
  for team in range(num_teams):
      if slot in prhi_judge_slots:
          model.Add(assignments[(team, slot, prhi_judge)] == (team in prhi_team_ids))
      else:
          model.Add(assignments[(team, slot, prhi_judge)] == 0)

# Objective to equalize judging load
# count how many teams each judge sees
judge_counts = [model.NewIntVar(0, num_teams, f"JudgeCount_{j}") for j in range(num_judges - 1)]

for judge in range(num_judges - 1):
    model.Add(judge_counts[judge] == sum(assignments[(team, slot, judge)] 
                                         for team in range(num_teams) 
                                         for slot in range(num_slots)))

max_assignments = model.NewIntVar(0, num_teams, "MaxAssignments")
min_assignments = model.NewIntVar(0, num_teams, "MinAssignments")

model.AddMaxEquality(max_assignments, judge_counts)
model.AddMinEquality(min_assignments, judge_counts)

model.Minimize(max_assignments - min_assignments)

# solve
solver = cp_model.CpSolver()
status = solver.Solve(model)

# prepare output
schedule = []
id_schedule = []
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    prhi_teams_slots = {}

    for team in range(num_teams):
        for slot in range(num_slots):
            for judge in range(num_judges - 1):
                if solver.Value(assignments[(team, slot, judge)]):  # If assigned
                    team_id = team_ids[team]
                    team_name = team_names[team]
                    slot_time = judging_start + slot * slot_delta
                    slot_time = slot_time.strftime("%H:%M")
                    judge_name = room_info[judge][1]

                    schedule.append((team_name, slot_time, judge_name))
                    id_schedule.append((team_id, slot_time, judge_name))
                    
                    # check if the slot belongs to a prhi team
                    if team_id in prhi_team_ids:
                        if (team_name, team_id) not in prhi_teams_slots:
                            prhi_teams_slots[(team_name, team_id)] = []
                        prhi_teams_slots[(team_name, team_id)].append(f"{slot_time} ({judge_name})")
    
    with open("prhi_judging_info.txt", "w") as f:
        f.write(f"PRHI Judging Schedule ({datetime.datetime.now()})\n\n")
        f.write(f"In room {prhi_room_name}, from {prhi_start.strftime('%H:%M')} to {prhi_end.strftime('%H:%M')}.\n")
        f.write("PRHI Teams, H@B Slot 1, H@B Slot 2,\n")
        for team, slots in prhi_teams_slots.items():
            team_name, team_id = team
            f.write(f"{team_name}, {team_id}, {slots[0]}, {slots[1]}\n")
    
    with open("room_assignments.txt", "w") as f:
        f.write(f"Room Assignments ({datetime.datetime.now()})\n\n")
        f.write("Room | Judges | Rep\n")
        for room in room_info:
            f.write(f"{room[1]} | {', '.join(room[0])} | {room[2]}\n")

else:
    print("No feasible schedule found.")

# print(schedule)

df = pd.DataFrame(schedule, columns=["Team", "Slot", "Judge"])
pivot_df = df.pivot(index="Slot", columns="Judge", values="Team")
pivot_df.to_excel("team_schedule.xlsx")

df = pd.DataFrame(id_schedule, columns=["Team ID", "Slot", "Judge"])
pivot_df = df.pivot(index="Slot", columns="Judge", values="Team ID")
pivot_df.to_excel("id_schedule.xlsx")