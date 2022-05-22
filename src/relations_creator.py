# -*- coding: utf-8 -*-
from osgeo import ogr
import math
import multiprocessing
import pyperclip

from multiprocessing import Manager, Process, Queue


class RelationsCreator(object):

    def __init__(self):
        pass


    def calculate(self, features):

        workers = {}
        manager = Manager()
        feature_map = manager.dict()

        results = []
        result_list = Queue()

        for id, feature in features.items():
            feature_map[id] = feature.GetGeometryRef().ExportToIsoWkb()

        # Split the work between the available cores.
        src_kom_ids = list(features.keys())
        chunk_size = math.ceil(len(src_kom_ids) / multiprocessing.cpu_count())
        chunks = [src_kom_ids[i:i + chunk_size] for i in range(0, len(src_kom_ids), chunk_size)]

        print('Distributing to {} workers...'.format(multiprocessing.cpu_count()))

        count = 0
        for chunk in chunks:
            count += 1
            worker = Process(target=self.calculate_relations, args=(chunk, feature_map, result_list, count,))
            workers[count] = worker
            worker.start()

        while True:
            for id, worker in workers.items():
                if worker is None:
                    continue

                if not worker.is_alive():
                    worker.join()
                    workers[id] = None

            while not result_list.empty():
                results.append(result_list.get())

            if len([k for k,v in workers.items() if v is not None]) == 0:
                break
        
        return results
        


    def calculate_relations(self, src_kom_ids, features, result_list, worker_id):
        #distances = {}
        #directions = {}

        geometries = {}
        for kom_id, wkb in features.items():
            geometries[kom_id] = ogr.CreateGeometryFromWkb(features[kom_id])

        for src_kom_id in src_kom_ids:
            # Calculate the distance from this feature to all other features.

            relations = []

            #if src_kom_id != '0621':
            #    continue
            src_geometry = geometries[src_kom_id]#ogr.CreateGeometryFromWkb(features[src_kom_id])

            for dst_kom_id, dst_geometry in geometries.items():
                #print(' - {} -> {}'.format(src_kom_id, dst_kom_id), end='')
                if src_kom_id == dst_kom_id:
                    # Do not process us.
                    #print(' same')
                    continue

                #dst_geometry = ogr.CreateGeometryFromWkb(wkb)

                # if (dst_kom_id in distances and src_kom_id in distances[dst_kom_id] or
                #     src_kom_id in distances and dst_kom_id in distances[src_kom_id]):
                #     print(' calculated')
                #     # This has been calculated.
                #     continue

                distance, direction = self.calculate_relation(src_geometry, dst_geometry)

                # if src_kom_id not in distances:
                #     distances[src_kom_id] = {}
                #     directions[src_kom_id] = {}
                
                # if dst_kom_id not in distances:
                #     distances[dst_kom_id] = {}
                #     directions[dst_kom_id] = {}

                # distances[src_kom_id][dst_kom_id] = distance
                # distances[dst_kom_id][src_kom_id] = distance
                # directions[src_kom_id][dst_kom_id] = direction
                # directions[dst_kom_id][src_kom_id] = direction - math.pi if direction > math.pi else direction + math.pi

                relations.append((dst_kom_id, distance, direction))

                #print('{}: {} ({})'.format(worker_id, distance, direction))
            
            result_list.put((src_kom_id, relations))
            print('[{}] - {} calculated...'.format(worker_id, src_kom_id))
        
        #return distances, directions


    def calculate_relation(self, src_geometry, dst_geometry):

        #src_geometry = src_feature.GetGeometryRef()
        #dst_geometry = dst_feature.GetGeometryRef()
        distance = src_geometry.Distance(dst_geometry)
        src_centroid = src_geometry.Centroid()
        dst_centroid = dst_geometry.Centroid()    
        direction = math.atan2(dst_centroid.GetY() - src_centroid.GetY(), dst_centroid.GetX() - src_centroid.GetX())

        if direction < 0:
            direction += 2 * math.pi

        if direction < 0:
            a = 1
            pass

        return distance, direction