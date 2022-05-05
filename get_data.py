# -*- coding: utf-8 -*-
from osgeo import gdal, ogr, osr
from gdal_error_handler import GdalErrorHandler
from shapely import wkt

import datetime
import json
import math
import numpy as np
import os
import pyperclip
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


def create_raster_ds(geometry, max_size):

    cols = max_size
    rows = max_size
    bbox = geometry.GetEnvelope()

    width = bbox[1] - bbox[0]
    height = bbox[3] - bbox[2]

    if width > height:
        rows = math.ceil(max_size * height / width)
    else:
        cols = math.ceil(max_size * width / height)
    geotransform = [bbox[0], width / cols, 0, bbox[2], 0, height / rows]

    raster_ds = gdal.GetDriverByName('MEM').Create('', cols, rows, 4, gdal.GDT_Byte)
    raster_ds.SetGeoTransform(geotransform)

    return raster_ds


def create_vector_layer(geometry):
    vector_ds = ogr.GetDriverByName('Memory').CreateDataSource('wrk')
    mem_layer = vector_ds.CreateLayer('poly')

    f = ogr.Feature(mem_layer.GetLayerDefn())
    f.SetGeometry(geometry)
    mem_layer.CreateFeature(f)

    return vector_ds, mem_layer


def flip_image(raster_ds):
    # Flip the image up-down.
    data = raster_ds.ReadAsArray()
    for i in range(data.shape[0]):
        data[i] = np.flipud(data[i])

    raster_ds.WriteArray(data)

    return raster_ds


def create_images(features, max_size, folder):

    # Create a single multi polygon with all features.
    polygon = ogr.Geometry(ogr.wkbMultiPolygon)
    for kommune_id, feature in features.items():
        for i in range(feature.GetGeometryRef().GetGeometryCount()):
            polygon.AddGeometry(feature.GetGeometryRef().GetGeometryRef(i).Buffer(1).Clone())

    combined = polygon.UnionCascaded()

    country_raster_ds = create_raster_ds(combined, max_size)

    vector_ds, mem_layer = create_vector_layer(combined)

    # Rasterize the country only.
    err = gdal.RasterizeLayer(country_raster_ds, [1,2,3,4], mem_layer, burn_values=[49,130,189,255], options=['ALL_TOUCHED=TRUE'])

    # Save the rasterization for later reuse.
    country_data = country_raster_ds.ReadAsArray()

    for kommune_id, feature in features.items():
        out_image_filename = os.path.join(folder, 'images', kommune_id + '.png')
        out_result_filename = os.path.join(folder, 'images', kommune_id + '_result.png')

        raster_ds = create_raster_ds(feature.GetGeometryRef(), max_size)

        vector_ds, mem_layer = create_vector_layer(feature.GetGeometryRef())

        # Rasterize the municipality.
        err = gdal.RasterizeLayer(raster_ds, [1,2,3,4], mem_layer, burn_values=[49,130,189,255], options=['ALL_TOUCHED=TRUE'])

        # Flip image to fit non geographical view.
        raster_ds = flip_image(raster_ds)

        # Save the municipality image.
        out_ds = gdal.GetDriverByName('PNG').CreateCopy(out_image_filename, raster_ds, strict=0)
        out_ds = None

        # Create result image.

        # Reuse country data.
        country_raster_ds.WriteArray(country_data)

        # Rasterize the current municipality into the country.
        err = gdal.RasterizeLayer(country_raster_ds, [1,2,3,4], mem_layer, burn_values=[222,45,38,255], options=['ALL_TOUCHED=TRUE'])

        # Flip image to fit non geographical view.
        country_raster_ds = flip_image(country_raster_ds)

        # Save the result image.
        out_ds = gdal.GetDriverByName('PNG').CreateCopy(out_result_filename, country_raster_ds, strict=0)
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


def create_municipality_list_json(features):

    # JSON file.
    out_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'municipality_list.json')

    data = []
    for src_kom_id, feature in features.items():
        entry = {}
        entry['id'] = src_kom_id
        entry['name'] = feature.GetFieldAsString('navn')
        data.append(entry)

    # Sort the list alphabetically.
    data.sort(key=lambda x: x['name'])

    with open(out_filename, 'w', encoding="utf-8") as outfile:
        outfile.write(json.dumps(data, ensure_ascii=False))


def create_date_list_json(features, start_date):

    # JSON file.
    out_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'date_list.json')

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
    
    #distances, directions = calculate_relations(features)

    #save_relations(distances, directions)

    # Create JSON data.
    #save_json_data(distances, directions, project_folder)
    #create_json_from_db(os.path.join(project_folder, 'relations.db'), project_folder)

    create_municipality_list_json(features)

    create_date_list_json(features, datetime.datetime.now() + datetime.timedelta(days=1))

    # Create images.
    #create_images(features, 512, project_folder)

    gdal.PopErrorHandler()