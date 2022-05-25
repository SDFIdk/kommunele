# -*- coding: utf-8 -*-
import datetime
import json
import numpy as np
import os
import pyperclip
import random


class ListCreator(object):

    def __init__(self):
        pass


    def shuffle_slightly(self, items, amount=2):
        # Naive algorithm which doesn't equally distribute the items.
        # It uses one pass to redistribute the input elements by +/- offset amount.
        result = [None for x in items]

        for i in range(len(items)):
            # Get the possible locations.
            locations = np.array(range(0, amount * 2 + 1)) - amount

            # The possible locations should not extend outside the result.
            if i < amount:
                locations = locations[amount - i:]
            
            if i + amount >= len(items):
                locations = locations[:-(amount - (len(items) - i - 1))]

            # Reduce the possible locations by looking at the current result.
            locations = [x for x in locations if result[i + x] is None]

            # If only one valid location, choose that one.
            if len(locations) == 1:
                result[i + locations[0]] = items[i]
                continue

            # If a valid location is -amount, then we need to chose that one to ensure a stable result.
            if locations[0] == -amount:
                result[i + locations[0]] = items[i]
                continue

            # We can choose a random location from the list.
            x = random.randint(0, len(locations) - 1)
            result[i + locations[x]] = items[i]

        return result


    def create_relations_list_json(self, relations, folder):

        # JSON file.
        out_filename = os.path.join(folder, 'relations.json')

        data = {}

        for src_kom_id, dst_relations in relations:
            entries = {}
            for dst_kom_id, distance, direction in dst_relations:
                entries[dst_kom_id] = [round(distance, 0), round(direction, 2)]
                # entry = {}
                # entry['src_id'] = src_kom_id
                # entry['dst_id'] = dst_kom_id
                # entry['distance'] = round(distance,0)
                # entry['direction'] = round(directions[src_kom_id][dst_kom_id], 2)
                # data.append(entry)
            
            data[src_kom_id] = entries

        #data = dict(data)

        with open(out_filename, 'w') as outfile:
            outfile.write(json.dumps(data))


    def create_municipality_list_json(self, features, folder):

        # JSON file.
        out_filename = os.path.join(folder, 'municipality_list.json')

        data = []
        for src_kom_id, feature in features.items():
            data.append((feature.GetFieldAsString('navn'), src_kom_id))

        # Sort the list alphabetically.
        data.sort(key=lambda x: x[0])

        # Convert to a dictionary for a more compressed output. This seems to keep the order of the elements.
        data = dict(data)

        with open(out_filename, 'w', encoding="utf-8") as outfile:
            outfile.write(json.dumps(data, ensure_ascii=False))


    def create_date_list_json(self, features, start_date, folder):

        # JSON file.
        out_filename = os.path.join(folder, 'date_list.json')

        data = {}

        current_date = start_date

        src_kom_ids = list(features.keys())
        random.shuffle(src_kom_ids)

        # Store the list as a single entry.
        src_kom_ids = [src_kom_ids]

        # Extend the list of municipality ids by adding a slightly shuffled version of the previous list at the end.
        # 10 rounds of 99 elements should suffice for now. Roughly 3 years of daily entries.
        for i in range(9):
            # Two lists next to each other should'nt have identical start and end elements.
            while True:
                next_list = self.shuffle_slightly(src_kom_ids[i], 10)
                if next_list[0] != src_kom_ids[i][-1]:
                    src_kom_ids.append(next_list)
                    break

        # Convert the lists to one long list.
        src_kom_ids = [x for y in src_kom_ids for x in y]

        for src_kom_id in src_kom_ids:       
            data[current_date.strftime('%Y%m%d')] = src_kom_id

            current_date +=  + datetime.timedelta(days=1)

        with open(out_filename, 'w') as outfile:
            outfile.write(json.dumps(data))