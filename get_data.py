# -*- coding: utf-8 -*-
from osgeo import gdal, ogr, osr
from gdal_error_handler import GdalErrorHandler
from shapely import wkt

import datetime
import json
import math
import numpy as np
import os
import random
import sqlite3


def get_data(project_folder):

    #url = 'https://api.dataforsyningen.dk/DAGI_10MULTIGEOM_GMLSFP_DAF?service=WFS&request=GetCapabilities&token=' + token

    #driver = ogr.GetDriverByName('WFS')
    #in_ds = driver.Open('WFS:' + url)
    #in_layer = in_ds.GetLayerByName('kommuneinddeling')

    #total = in_layer.GetFeatureCount()
    #current_feature = in_layer.GetNextFeature()

    #a = 1

    result = {}

    driver = ogr.GetDriverByName('GML')
    in_ds = driver.Open(os.path.join(project_folder, 'raw_data', 'dagi_10m_nohist_l1.kommuneinddeling.gml'))
    in_layer = in_ds.GetLayerByIndex(0)

    count = 0
    total = in_layer.GetFeatureCount()
    current_feature = in_layer.GetNextFeature()

    while current_feature is not None:
        count += 1
        kom_id = current_feature.GetFieldAsString('kommunekode')

        result[kom_id] = current_feature.Clone()
        current_feature = in_layer.GetNextFeature()

        #if count > 5:
        #    break

    return result


def calculate_relations(features):

    distances = {}

    directions = {}

    for src_kom_id, src_feature in features.items():
        # Calculate the distance from this feature to all other features.

        #if src_kom_id != '0621':
        #    continue

        for dst_kom_id, dst_feature in features.items():
            print(' - {} -> {}'.format(src_kom_id, dst_kom_id), end='')
            if src_kom_id == dst_kom_id:
                # Do not process us.
                print(' same')
                continue

            if (dst_kom_id in distances and src_kom_id in distances[dst_kom_id] or
                src_kom_id in distances and dst_kom_id in distances[src_kom_id]):
                print(' calculated')
                # This has been calculated.
                continue

            distance, direction = calculate_relation(src_feature, dst_feature)

            if src_kom_id not in distances:
                distances[src_kom_id] = {}
                directions[src_kom_id] = {}
            
            if dst_kom_id not in distances:
                distances[dst_kom_id] = {}
                directions[dst_kom_id] = {}

            distances[src_kom_id][dst_kom_id] = distance
            distances[dst_kom_id][src_kom_id] = distance
            directions[src_kom_id][dst_kom_id] = direction
            directions[dst_kom_id][src_kom_id] = direction - math.pi if direction > math.pi else direction + math.pi

            print(': {} ({})'.format(distance, direction))
    
    return distances, directions


def calculate_relation(src_feature, dst_feature):

    src_geometry = src_feature.GetGeometryRef()
    dst_geometry = dst_feature.GetGeometryRef()
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


def create_images(features, max_size, folder):
    for kommune_id, feature in features.items():
        out_filename = os.path.join(folder, 'images', kommune_id + '.png')

        cols = max_size
        rows = max_size
        bbox = feature.GetGeometryRef().GetEnvelope()

        width = bbox[1] - bbox[0]
        height = bbox[3] - bbox[2]

        if width > height:
            rows = math.ceil(max_size * height / width)
        else:
            cols = math.ceil(max_size * width / height)
        geotransform = [bbox[0], width / cols, 0, bbox[2], 0, height / rows]

        vector_ds = ogr.GetDriverByName('Memory').CreateDataSource('wrk')
        mem_layer = vector_ds.CreateLayer('poly')

        f = ogr.Feature(mem_layer.GetLayerDefn())
        f.SetGeometry(feature.GetGeometryRef())
        mem_layer.CreateFeature(f)
        
        raster_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 4, gdal.GDT_Byte)
        #raster_ds.SetProjection(projection)
        raster_ds.SetGeoTransform(geotransform)

        #background = np.stack((np.ones((rows, cols)) * 255, np.zeros((rows, cols)), np.ones((rows, cols)) * 255))
        #raster_ds.WriteArray(background)

        # Run the algorithm.
        err = gdal.RasterizeLayer(raster_ds, [1,2,3,4], mem_layer, burn_values=[49,130,189,255], options=['ALL_TOUCHED=TRUE'])

        # f.SetGeometry(polygon_to_lines(feature.GetGeometryRef()))
        # mem_layer.SetFeature(f)
        # err = gdal.RasterizeLayer(raster_ds, [1,2,3,4], mem_layer, burn_values=[0,0,0,255], options=['ALL_TOUCHED=TRUE'])

        # Flip the image up-down.
        data = raster_ds.ReadAsArray()
        for i in range(data.shape[0]):
            data[i] = np.flipud(data[i])

        raster_ds.WriteArray(data)

        out_ds = gdal.GetDriverByName('PNG').CreateCopy(out_filename, raster_ds, strict=0)
        out_ds = None
    

def polygon_to_lines(geometry):

    g = ogr.Geometry(ogr.wkbMultiLineString)

    if geometry.GetGeometryType() == ogr.wkbMultiPolygon or geometry.GetGeometryType() == ogr.wkbMultiPolygon25D:
        for i in range(geometry.GetGeometryCount()):
            gs = polygon_to_lines(geometry.GetGeometryRef(i))

            for item in gs:
                g.AddGeometry(item)
    else:
        for i in range(geometry.GetGeometryCount()):
            g.AddGeometry(geometry.GetGeometryRef(i))

    return g.Clone()


def save_relations(distances, directions):

    outfile = os.path.join(project_folder, 'relations.db')
    conn = sqlite3.connect(outfile)
    cursor = conn.cursor()

    cursor.execute('''create table relations (src_id int, dst_id int, distance real, direction real)''')

    db_data = []

    for src_kom_id, relations in distances.items():

        for dst_kom_id, distance in relations.items():
            db_data.append((src_kom_id, dst_kom_id, distance, directions[src_kom_id][dst_kom_id]))


    cursor.executemany('INSERT INTO relations VALUES (?,?,?,?)', db_data)
    
    conn.commit()
    conn.close()


def save_json_data(distances, directions, folder):

    # JSON file.
    out_filename = os.path.join(folder, 'relations2.json')

    data = []
    for src_kom_id, relations in distances.items():
        for dst_kom_id, distance in relations.items():
            entry = {}
            entry['src_id'] = src_kom_id
            entry['dst_id'] = dst_kom_id
            entry['distance'] = round(distance,0)
            entry['direction'] = round(directions[src_kom_id][dst_kom_id], 2)
            data.append(entry)


    with open(out_filename, 'w') as outfile:
        outfile.write(json.dumps(data))


def create_json_from_db(database, folder):
    
    # JSON file.
    out_filename = os.path.join(folder, 'relations.json')

    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    cursor.execute('''SELECT * FROM relations''')

    data = []

    for row in cursor.fetchall():
        entry = {}
        entry['src_id'] = row[0]
        entry['dst_id'] = row[1]
        entry['distance'] = round(row[2],0)
        entry['direction'] = round(row[3], 2)
        data.append(entry)

    with open(out_filename, 'w') as outfile:
        outfile.write(json.dumps(data))


def create_municipality_list_json(features, folder):

    # JSON file.
    out_filename = os.path.join(folder, 'municipality_list.json')

    data = []
    for src_kom_id, feature in features.items():
        entry = {}
        entry['id'] = src_kom_id
        entry['name'] = feature.GetFieldAsString('navn')
        data.append(entry)

    with open(out_filename, 'w', encoding="utf-8") as outfile:
        outfile.write(json.dumps(data, ensure_ascii=False))


def create_date_list_json(features, start_date, folder):

    # JSON file.
    out_filename = os.path.join(folder, 'date_list.json')

    data =[]

    current_date = start_date

    src_kom_ids = list(features.keys())
    random.shuffle(src_kom_ids)

    for src_kom_id in src_kom_ids:
        
        entry = {
            'id': src_kom_id,
            'date': current_date.strftime('%Y%m%d')
        }

        data.append(entry)

        current_date +=  + datetime.timedelta(days=1)

    with open(out_filename, 'w') as outfile:
        outfile.write(json.dumps(data))

if __name__ == "__main__":
    err = GdalErrorHandler()
    gdal.PushErrorHandler(err.handler)
    gdal.UseExceptions()  # Exceptions will get raised on anything >= gdal.CE_Failure

    project_folder = os.path.dirname(os.path.realpath(__file__))

    features = get_data(project_folder)
    
    distances, directions = calculate_relations(features)

    #save_relations(distances, directions)

    # Create JSON data.
    save_json_data(distances, directions, project_folder)
    #create_json_from_db(os.path.join(project_folder, 'relations.db'), project_folder)

    #create_municipality_list_json(features, project_folder)

    #create_date_list_json(features, datetime.datetime.now(), project_folder)

    # Create images.
    #create_images(features, 512, project_folder)

    gdal.PopErrorHandler()