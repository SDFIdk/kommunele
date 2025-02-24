# -*- coding: utf-8 -*-
from osgeo import gdal, ogr
from gdal_error_handler import GdalErrorHandler

import datetime
import os
import pyperclip

from list_creator import ListCreator
from image_creator import ImageCreator
from relations_creator import RelationsCreator


def get_data(folder):

    #url = 'https://api.dataforsyningen.dk/DAGI_10MULTIGEOM_GMLSFP_DAF?service=WFS&request=GetCapabilities&token=' + token

    #driver = ogr.GetDriverByName('WFS')
    #in_ds = driver.Open('WFS:' + url)
    #in_layer = in_ds.GetLayerByName('kommuneinddeling')

    #total = in_layer.GetFeatureCount()
    #current_feature = in_layer.GetNextFeature()

    #a = 1

    result = {}

    driver = ogr.GetDriverByName('GPKG')
    in_ds = driver.Open(os.path.join(folder, 'dagi_250.gpkg'))
    in_layer = in_ds.GetLayerByIndex(0)

    count = 0
    total = in_layer.GetFeatureCount()
    current_feature = in_layer.GetNextFeature()

    while current_feature is not None:
        if current_feature.GetFieldAsString('skala') == '1:250.000':
            count += 1
            kom_id = current_feature.GetFieldAsString('kommunekode')

            result[kom_id] = current_feature.Clone()

        current_feature = in_layer.GetNextFeature()

        #if count > 15:
        #    break

    return result
    

if __name__ == "__main__":
    '''
    As input data use the DAGI data set from Datafordeler.dk called "DAGI Fildownload". It it probably the most easy DAGI data set to fetch.
    Create a folder "input_folder", put the data set into that folder and rename it to dagi_250.gpkg.
    '''
    err = GdalErrorHandler()
    gdal.PushErrorHandler(err.handler)
    gdal.UseExceptions()  # Exceptions will get raised on anything >= gdal.CE_Failure

    project_folder = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    input_data_folder = os.path.join(project_folder, 'input_data')
    public_folder = os.path.join(project_folder, 'public')
    data_folder = os.path.join(public_folder, 'data')
    image_folder = os.path.join(public_folder, 'images')
    max_image_size = 512

    # More colorblind friendly colours.
    polygon_color = [77,172,38,255]
    highlight_color = [208,28,139,255]

    features = get_data(input_data_folder)
    
    relations_creator = RelationsCreator()
    print('Calculating relations...')
    relations = relations_creator.calculate(features)

    list_creator = ListCreator()
    print('Creating data lists...')
    # Create JSON data.
    list_creator.create_relations_list_json(relations, data_folder)
    list_creator.create_municipality_list_json(features, data_folder)
    list_creator.create_date_list_json(features, datetime.datetime.now() + datetime.timedelta(days=1), data_folder)

    # Create images.
    image_creator = ImageCreator()
    image_creator.run(features, max_image_size, polygon_color, highlight_color, image_folder)

    gdal.PopErrorHandler()