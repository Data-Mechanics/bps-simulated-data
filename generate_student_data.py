import os
import random
import zipfile
import json
import geojson
import shapefile # pyshp library
import pyproj
from tqdm import tqdm
import geoleaflet

def point_in_poly(x, y, poly):
    """
    Determine whether a point is inside a given polygon (list of (x,y) pairs).
    Returns True or False. Uses ray casting (source: geospatialpython.com).
    """
    n = len(poly)
    inside = False

    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x,p1y = p2x,p2y
    return inside

def extract_zipcode_data():
    if not os.path.isdir('zipcodes_nt'):
        with zipfile.ZipFile('zipcodes_nt.zip') as f:
            f.extractall("./zipcodes_nt")

def properties_by_zipcode(file_prefix):
    """
    Build a JSON file grouping all properties by zip code.
    """
    sf = shapefile.Reader('zipcodes_nt/ZIPCODES_NT_POLY')
    reverse_coordinate_projection = pyproj.Proj(proj = 'lcc', datum = 'NAD83',
                                    lat_1 = 41.71666666666667, lat_2 = 42.68333333333333,
                                    lat_0 = 41.0, lon_0 = -71.5,
                                    x_0 = 200000.0, y_0 = 750000.0)

    ZIPFIELD = 0 # Constant for the zipcode field.

    # Load all residences in Boston.
    properties = json.load(open('properties.geojson', 'r'))
    residences = [p for p in properties.items() if p[1]['properties']['type'] == 'Residential']

    # Convert shapefile to dictionary one time.
    # The shapefile actually does not contain unique zipcode data so we have to make sure to have multipolygons.
    # For now, just ignore the list.
    blacklist = ['01434', '01082', '02532', '01002', '01039', '01050', '02467', '01096', '01026', '01011', '01247', '01010', '01235', '01008']

    zipcode_polygons = {}
    for sr in sf.iterShapeRecords():
        zc = sr.record[ZIPFIELD] # zip code
        if zc in blacklist:
            continue # FIX THIS
        polygon = []
        for x,y in sr.shape.points:
            lng, lat = reverse_coordinate_projection(x, y, inverse=True)
            polygon.append((lat, lng))

        zipcode_polygons[zc] = polygon

    # Map a list of residences to their zip codes.
    zipcodes = {zc:[] for zc in zipcode_polygons}
    for k, residence in tqdm(residences):
        res_lat, res_lng = residence['geometry']['coordinates']
        for zc, polygon in zipcode_polygons.items():
            if point_in_poly(res_lat, res_lng, polygon):
                zipcodes[zc].append((k, residence))
                break

    with open(file_prefix + '.json', 'w') as f:
        f.write(json.dumps(zipcodes))

def percentages_csv_to_json(file_prefix):
    rows = open(file_prefix + '.csv', 'r').read().split("\n")
    fields = rows[0].split("\t")
    rows = [list(zip(fields, row.split("\t"))) for row in tqdm(rows[1:])]
    zip_to_percentages = {}
    for r in rows:
        zip_to_percentages[r[0][1]] = {
            'total': int(r[3][1]),
            'schools': dict([(f,float(v)) for (f,v) in r[4:] if float(v) > 0])
          }
    txt = json.dumps(zip_to_percentages, indent=2)
    open(file_prefix + '.json', 'w').write(txt)

def students_simulate(file_prefix_properties, file_prefix_percentages, file_prefix_students):
    properties = json.loads(open(file_prefix_properties + '.json', 'r').read())
    percentages = json.loads(open(file_prefix_percentages + '.json', 'r').read())
    features = []
    for zip in percentages.keys() & properties.keys():
        for location in tqdm(random.sample(properties[zip], percentages[zip]['total'])):
            geometry = location[1]['geometry']
            (x, y) = (geometry['coordinates'][0], geometry['coordinates'][1])
            geometry['coordinates'][1] = x
            geometry['coordinates'][0] = y
            props = {}
            features.append(geojson.Feature(geometry=geometry, properties=props))
    open(file_prefix_students + '.geojson', 'w').write(geojson.dumps(geojson.FeatureCollection(features), indent=2))
    return geojson.FeatureCollection(features)

def main():
    extract_zipcode_data()
    properties_by_zipcode('properties-by-zipcode')
    percentages_csv_to_json('student-zip-school-percentages')
    students = students_simulate('properties-by-zipcode', 'student-zip-school-percentages', 'students')
    open('students.html', 'w').write(geoleaflet.html(students))

## eof