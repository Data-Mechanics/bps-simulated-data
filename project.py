import numpy as np
from sklearn.cluster import KMeans
from rtree import index
import pickle
from tqdm import tqdm
import geoql, geojson
from copy import deepcopy

# Want a function that takes as input 
# set of geojson points, set of geojson linestrings

# points is a list of (x, y) coordinates
# linestrings is a list of geojson linestrings representing streets

def project(p1, l1, l2):
    # find projection of p1 onto line between l1 and l2
    p1 = np.array(p1)
    l1 = np.array(l1)
    l2 = np.array(l2)

    line = l2 - l1
    vec = p1 - l1
    #print(l1, l2, vec, line, line.dot(line), flush=True)
    return l1 + (vec.dot(line) / line.dot(line)) * line  # Projects vec onto line

def normal(p1, l1, l2):
    p1 = np.array(p1)
    l1 = np.array(l1)
    l2 = np.array(l2)

    proj = project_point_to_segment(p1, l1, l2)
    return proj - p1

def project_point_to_segment(p1, l1, l2):
    p1 = np.array(p1)
    l1 = np.array(l1)
    l2 = np.array(l2)

    proj = project(p1, l1, l2)
    v1 = proj - l1
    v2 = proj - l2

    # v1 and v2 face in opposite directions if the dot product is negative 
    if v1.dot(v2) <= 0:
        return proj
    elif np.dot(v1, v1) <= np.dot(v2, v2): # proj not on segment
        return l1
    else: # distance from point to l2 is smaller
        return l2

def rTreeify(obj):
    '''takes geojson FeatureCollection of linestrings and constructs rTree'''
    tree = index.Index()
    tree_keys = {}
    i = 0
    for j, lstr in enumerate(obj.features):
        for p in lstr.geometry.coordinates:
            tree_keys[str(i)] = j
            x, y = p[0], p[1]
            tree.insert(i,(x,y,x,y))
            i += 1

    return tree, tree_keys

def find_intersection(obj, tree, tree_keys, p, r):
    ''' Finds all points in the rtree tree in the bounding box centered on p with
        radius r '''
    lat, lon = p
    result = set()
    for i in tqdm(list(tree.intersection((lat-r, lon-r, lat+r, lon+r)))):
        result.add(tree_keys[str(i)])

    result = list(result)
    result.sort()
    obj.features = [obj.features[j] for j in result]

    return obj

# UNFINISHED
def project_points_to_linestrings(points, linestrings):
    # Todo: Implement rtrees to find line points within certain distance

    projections = []
    tree, tree_keys = rTreeify(linestrings)

    for lat,lon in tqdm(points[9:11]):
        p = np.array([lat, lon])
        lstr_copy = deepcopy(linestrings)
        lstr_copy = find_intersection(lstr_copy, tree, tree_keys, p, 0.01)
        lstr_copy = geoql.features_keep_within_radius(lstr_copy, [lon,lat], 0.5, 'miles')
        min_proj = (10000, [0,0])
        for lstr in lstr_copy.features:
            segments = lstr.geometry.coordinates
            for i in range(len(segments)-1):
                if np.linalg.norm(np.array(segments[i+1]) - np.array(segments[i])) == 0:
                    continue
                norm = normal(p, segments[i], segments[i+1])
                dist = norm.dot(norm)
                if dist < min_proj[0]:
                    proj = project_point_to_segment(p, segments[i], segments[i+1])
                    min_proj = [dist, proj, np.array(segments[i]), np.array(segments[i+1])]
        projections.append(min_proj)

    return [p[1:] for p in projections]

def load_road_segments(fname):
    linestrings = geojson.loads(open(fname, 'r').read())
    linestrings.features = [seg for seg in linestrings.features if seg.type=='Feature']
    return linestrings

def generate_student_stops(student_points, numStops=5000, loadFrom=None):

    # get means from picle or generate
    if loadFrom:
        means = pickle.load(open(loadFrom, 'rb'))

    else:
        # load student coordinates from students datafile to list of coordinates
        points = [student_points['features'][i]['geometry']['coordinates'][0] for i in range(len(student_points['features']))]
    
        #generate means
        kmeans = KMeans(n_clusters=numStops, random_state=0)
        means = kmeans.fit(points).cluster_centers_

    # get linestrings from roadsegments
    linestrings = load_road_segments('example_extract_missing.geojson')

    #return means, linestrings
    return means, project_points_to_linestrings(means, linestrings)

import time
start = time.time()
points, stops = generate_student_stops([], loadFrom='kmeans')
end = time.time()
with open('timelog', 'w') as f:
    f.write(str(end-start))

with open('stops', 'wb') as f:
    f.write(pickle.dumps(stops))
