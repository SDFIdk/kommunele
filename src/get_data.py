# -*- coding: utf-8 -*-
from osgeo import gdal, ogr, osr
from gdal_error_handler import GdalErrorHandler

import datetime
import json
import math
import numpy as np
import os
import pyperclip
import random

from .list_creator import ListCreator


def get_data(folder):

    #url = 'https://api.dataforsyningen.dk/DAGI_10MULTIGEOM_GMLSFP_DAF?service=WFS&request=GetCapabilities&token=' + token

    #driver = ogr.GetDriverByName('WFS')
    #in_ds = driver.Open('WFS:' + url)
    #in_layer = in_ds.GetLayerByName('kommuneinddeling')

    #total = in_layer.GetFeatureCount()
    #current_feature = in_layer.GetNextFeature()

    #a = 1

    result = {}

    driver = ogr.GetDriverByName('GML')
    in_ds = driver.Open(os.path.join(folder, 'dagi_10m_nohist_l1.kommuneinddeling.gml'))
    in_layer = in_ds.GetLayerByIndex(0)

    count = 0
    total = in_layer.GetFeatureCount()
    current_feature = in_layer.GetNextFeature()

    while current_feature is not None:
        count += 1
        kom_id = current_feature.GetFieldAsString('kommunekode')

        result[kom_id] = current_feature.Clone()
        current_feature = in_layer.GetNextFeature()

        if count > 5:
            break

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
    err = gdal.RasterizeLayer(country_raster_ds, [1,2,3,4], mem_layer, burn_values=[0,109,44,255], options=['ALL_TOUCHED=TRUE'])

    # Save the rasterization for later reuse.
    country_data = country_raster_ds.ReadAsArray()

    for kommune_id, feature in features.items():
        
        out_image_filename = os.path.join(folder, kommune_id + '.png')
        out_result_filename = os.path.join(folder, kommune_id + '_result.png')

        raster_ds = create_raster_ds(feature.GetGeometryRef(), max_size)

        vector_ds, mem_layer = create_vector_layer(feature.GetGeometryRef())

        # Rasterize the municipality.
        err = gdal.RasterizeLayer(raster_ds, [1,2,3,4], mem_layer, burn_values=[0,109,44,255], options=['ALL_TOUCHED=TRUE'])

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


def shuffle_slightly(items, amount=2):
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


def create_relations_list_json(distances, directions, folder):

    # JSON file.
    out_filename = os.path.join(folder, 'relations.json')

    data = []
    for src_kom_id, relations in distances.items():
        entries = []
        for dst_kom_id, distance in relations.items():
            entries.append((dst_kom_id, [round(distance, 0), round(directions[src_kom_id][dst_kom_id], 2)]))
            # entry = {}
            # entry['src_id'] = src_kom_id
            # entry['dst_id'] = dst_kom_id
            # entry['distance'] = round(distance,0)
            # entry['direction'] = round(directions[src_kom_id][dst_kom_id], 2)
            # data.append(entry)
        
        data.append((src_kom_id, entries))

    data = dict(data)

    with open(out_filename, 'w') as outfile:
        outfile.write(json.dumps(data))


def create_municipality_list_json(features, folder):

    # JSON file.
    out_filename = os.path.join(folder, 'municipality_list.json')

    data = []
    for src_kom_id, feature in features.items():
        data.append((src_kom_id, feature.GetFieldAsString('navn')))

    # Sort the list alphabetically.
    data.sort(key=lambda x: x[1])

    # Convert to a dictionary for a more compressed output. This seems to keep the order of the elements.
    data = dict(data)

    with open(out_filename, 'w', encoding="utf-8") as outfile:
        outfile.write(json.dumps(data, ensure_ascii=False))


def create_date_list_json(features, start_date, folder):

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
            next_list = shuffle_slightly(src_kom_ids[i], 10)
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


if __name__ == "__main__":
    err = GdalErrorHandler()
    gdal.PushErrorHandler(err.handler)
    gdal.UseExceptions()  # Exceptions will get raised on anything >= gdal.CE_Failure

    project_folder = os.path.dirname(os.path.realpath(__file__))
    input_data_folder = os.path.join(project_folder, 'input_data')
    public_folder = os.path.join(project_folder, 'public')
    data_folder = os.path.join(public_folder, 'data')
    image_folder = os.path.join(public_folder, 'images')

    features = get_data(input_data_folder)
    
    distances, directions = calculate_relations(features)

    list_creator = ListCreator()
    # Create JSON data.
    list_creator.create_relations_list_json(distances, directions, data_folder)

    list_creator.create_municipality_list_json(features, data_folder)

    list_creator.create_date_list_json(features, datetime.datetime.now() + datetime.timedelta(days=1), data_folder)

    # Create images.
    create_images(features, 512, image_folder)

    gdal.PopErrorHandler()