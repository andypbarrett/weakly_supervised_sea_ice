import ee
import geemap
import matplotlib.pyplot as plt
import time

try:        
    # Initialize with your own project - Please specify your own project name.
    ee.Initialize(project = "utsa-spring2024")
except:
# Authenticate
    ee.Authenticate()
    # Initialize with your own project - Please specify your own project name.
    ee.Initialize(project = "utsa-spring2024")

import os
from datetime import datetime
import geopandas as gpd
import shapely.geometry
import numpy as np
import yaml
import gportal
import json
import os, glob
import requests
from datetime import datetime, timedelta

import cartopy.crs as ccrs
import cartopy.feature as cfeature

import warnings
warnings.filterwarnings("ignore")

def read_config(fn):
    from yaml.scanner import ScannerError

    try:
        with open(fn, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f'Could not file config file: {fn}')
    except ScannerError:
        raise ValueError(f'Bad yaml file: {fn}')

    if config is None:
        raise ValueError(f'config is None read from: {fn}')

    return config

import requests
import geopandas as gpd
from shapely.geometry import Polygon
import geopandas as gpd
import pandas as pd
import rasterio
from rasterio import features
import cdsapi
import xarray as xr
from shapely.ops import unary_union

def calculate_overlap_area(gdf1, gdf2, proj):
    
    # Reproject both to a metres-based CRS for accurate area calculation
    g1 = gdf1.to_crs(proj)
    g2 = gdf2.to_crs(proj)

    # Dissolve all polygons in gdf1 into one geometry
    union1 = unary_union(g1.geometry)
    union2 = unary_union(g2.geometry)  # also dissolve gdf2 if multi-polygon

    # Compute intersection
    overlap_geom = union1.intersection(union2)
    overlap_m2   = overlap_geom.area

    return overlap_m2 / union1.area
    # return {
    #     'overlap_m2':       round(overlap_m2, 2),
    #     'overlap_km2':      round(overlap_m2 / 1e6, 6),
    #     'overlap_pct_gdf1': round(overlap_m2 / union1.area * 100, 4),
    #     'overlap_pct_gdf2': round(overlap_m2 / union2.area * 100, 4),
    #     'overlap_geom':     overlap_geom,
    # }

def add_HH(img):
    bands = img.bandNames() # First band ('HH' or 'VV')
    band = ['HH']
    norm = img.select(band).divide(img.select('angle')).rename('HH_norm')
    img2 = img.addBands(norm, overwrite=True) #.select('HH_norm')
    return img2

def add_HV(img):
    bands = img.bandNames() # First band ('HH' or 'VV')
    band = ['HV']
    norm = img.select(band).divide(img.select('angle')).rename('HV_norm')
    img2 = img.addBands(norm, overwrite=True) #.select('HH_norm')
    return img2

def add_coverage(img):    
    tol = 1000
    overlap = img.geometry().intersection(extent, tol)
    ratio = overlap.area(tol).divide(extent.area(tol)) #overlap.area(tol).divide(img.geometry().area(tol))
    return img.set({'coverage_ratio': ratio})
    
def add_area(img):    
    tol = 1000    
    return img.set({'coverage_area': img.geometry().area(tol)})

def filter_full_coverage(collection, roi, th = 1, tol = 100):

    collection = collection.filterBounds(roi)
    
    def compute_coverage(image):
        # Intersect scene footprint with ROI
        scene_geom    = image.geometry(maxError=tol)
        intersection  = scene_geom.intersection(roi, maxError=tol)
        covered_area  = intersection.area(maxError=tol)
        # Coverage ratio: 1.0 = full coverage, <1.0 = partial
        coverage = covered_area.divide(roi.area(tol))
        return image.set('coverage_ratio', coverage)

    # Map coverage computation over the collection
    with_coverage = collection.map(compute_coverage)

    fully_covered = with_coverage.filter(ee.Filter.gte('coverage_ratio', th))
    return fully_covered
    
def add_chart_id(gdf):
    
    fields = ['CT', 'CA', 'CB', 'CC', 'CN', 'SA', 'SB', 'SC', 'CD', 'FA', 'FB', 'FC', 'POLY_TYPE'] #gdf.keys()[3:-6]
    codes = []
    poly_id = []
    N = 0

    for i in range(0, len(gdf)):
        cd = ""
        for f in fields:
            try:
                cd += gdf.loc[i, f] + ";"
            except:
                cd += "-9;"

        gdf.loc[i, "code"] = cd
        
        if cd not in codes:
            codes.append(cd)
            N += 1
            gdf.loc[i, "poly_id"] = N
            poly_id.append(N)
        else:
            idx = np.where(np.array(codes) == cd)[0][0]
            gdf.loc[i, "poly_id"] = poly_id[idx]

        
    return gdf

def get_chart_id(table, unique_id):
    fields = ['poly_id', 'CT', 'CA', 'CB', 'CC', 'CN', 'SA', 'SB', 'SC', 'CD', 'FA', 'FB', 'FC', 'POLY_TYPE']
    code0 = ""
    for s in fields:
        if s != fields[-1]:
            code0 += s + ";"
        else:
            code0 += s
    codes = [code0]
    for n in unique_id:
        codes.append(str(int(n)) + ";" + table[table["poly_id"] == n].reset_index(drop=True).loc[0, "code"][:-1])
        
    return codes


def download_img(img, proj, pixel_size, extent, out_tif):
    # proj2 = ee.Projection(proj).atScale(pixel_size)  # example: 1 km resolution
    # img_reproj = img.reproject(proj2)

    url = img.getDownloadURL({
        'scale': pixel_size,
        'crs': proj,
        'region': extent,
        'format': 'GEO_TIFF'
    })
    
    # Download file
    response = requests.get(url)
    with open(out_tif, "wb") as f:
        f.write(response.content)
    
    print(f"Saved to {out_tif}")


def rectangle_to_gdf(coords, crs):
    """
    coords: list of 5 (x, y) or (lon, lat) tuples
    crs: CRS string, e.g., 'EPSG:4326' or 'EPSG:3408'
    """
    poly = Polygon(coords)
    return gpd.GeoDataFrame({"id": [1]}, geometry=[poly], crs=crs)

def save_chart_tif(ref_tif, chart_tif, chart2):
    # rst_fn = "output.tif"
    rst = rasterio.open(ref_tif)
    ref_img = rst.read(1)
    meta = rst.meta.copy()
    meta.update(compress='lzw')
    
    with rasterio.open(chart_tif, 'w+', **meta) as out:
        out_arr = out.read(1)
    
        # this is where we create a generator of geom, value pairs to use in rasterizing
        shapes = ((geom,value) for geom, value in zip(chart2.geometry, chart2.poly_id))
    
        burned = features.rasterize(shapes=shapes, fill=0, out=out_arr, transform=out.transform)
        out.write_band(1, burned)
        print(f"Saved to {chart_tif}")

def get_extent(center, distance, proj):
    # center = [lon, lat]
    geometry = ee.Geometry.Point(center[0], center[1])    
    # if proj == "EPSG:3857":
    #     extent = geometry.buffer(distance = distance).bounds()
    #     dp = appropriate_resolution(center, pixel_size)
    # else:
    extent = geometry.buffer(distance = distance, proj = proj).bounds(proj = proj)
    
    return extent


def get_S1_array(center, t1, t2, pixel_size = 60, distance = 100000, proj = "EPSG:3409"):
    # proj - EPSG:3409 (EASE South); EPSG:3976 (NSIDC south polar stereo); EPSG:3857 (Web Mercator)

    geometry = ee.Geometry.Point(center[0], center[1])
    
    if proj == "EPSG:3857":
        extent = geometry.buffer(distance = distance).bounds()
        dp = appropriate_resolution(center, pixel_size)
    else:
        extent = geometry.buffer(distance = distance, proj = proj).bounds(proj = proj)
        dp = pixel_size

def empty(*args, **kwargs): return ""

def retrieve_hourly_ERA5_bbox(years, months, days, hours, bbox, object):
    c = cdsapi.Client(quiet=True, wait_until_complete=False, delete=True, progress=False, warning_callback = empty, sleep_max=10)
    # dataset to read
    dataset = 'reanalysis-era5-single-levels'
    # flag to download data
    # download_flag = False
    variables = [
        '10m_u_component_of_wind', '10m_v_component_of_wind', '2m_temperature', 'skin_temperature', "total_column_cloud_liquid_water", "total_column_water_vapour"
        # 'sea_ice_cover', '2m_temperature', 'sea_ice_cover', 'surface_pressure', 'skin_temperature', 'instantaneous_10m_wind_gust', 
    ]

    # u10m_rotated, v10m_rotated, t2m, skt, tcwv, tclw -> In the AI4Arctic Dataset

    # bbox: [north, west, south, east]
    params = {
        'format': 'netcdf',
        'product_type': 'reanalysis',
        'variable': variables,
        'year': years,
        'month': months,
        'day': days,
        'time': hours,
        'grid': [0.2, 0.1],
        'area': [bbox[0], bbox[1], bbox[2], bbox[3]]
        }

    # retrieves the path to the file
    # target = 'download.nc'
    if object == None:
        print("Please provide the correct file name!")
        # fl = c.retrieve(dataset, params).download()
        # ds = xr.open_dataset(fl)
        # return ds, fl
    else:
        c.retrieve(dataset, params, object)

def rotate_vector(u, v, lon, ref_lon = 0, hemi = "NH"):
    # Latitude & longitude grid to polar grid
    # ref_lon: longitude of center bottom
    if hemi == "NH":
        angle = (lon-ref_lon)*np.pi/180 # rotation angle (radian)
    else:
        angle = -(lon-ref_lon)*np.pi/180
    u2 = u*np.cos(angle) - v*np.sin(angle)
    v2 = u*np.sin(angle) + v*np.cos(angle)
    return u2, v2

def hour_rounder(t):
    return (t.replace(second=0, microsecond=0, minute=0, hour=t.hour)
               +timedelta(hours=t.minute//30))

def get_intersection(gdf1, gdf2, proj, simplify = True, tolerance = 5000):
    # Calculate intersection area between two polygons
    if simplify:
        gdf1 = simplify_gdf(gdf1, proj = proj, tolerance = tolerance)
        gdf2 = simplify_gdf(gdf2, proj = proj, tolerance = tolerance)
    else:
        gdf1 = gdf1.to_crs(proj)
        gdf2 = gdf2.to_crs(proj)
    intersection = gpd.overlay(gdf1, gdf2, how="intersection")
    
    intersection["overlap_area"] = intersection.geometry.area
    total_overlap_area = intersection["overlap_area"].sum()
    area1 = gdf1.to_crs(proj).geometry.area.sum()
    percent_overlap = (total_overlap_area / area1) * 100
    return percent_overlap.item()

def simplify_gdf(gdf, proj = "EPSG:3413", tolerance=5000):
    gdf_simplified = gdf.to_crs(proj).copy()
    gdf_simplified['geometry'] = gdf.geometry.simplify(tolerance = tolerance, preserve_topology = True)   # prevents self-intersections
    # print(f'Vertex count before: {sum(len(g.exterior.coords) for g in gdf.geometry if hasattr(g, "exterior"))}')
    # print(f'Vertex count after : {sum(len(g.exterior.coords) for g in gdf_simplified.geometry if hasattr(g, "exterior"))}')
    return gdf_simplified

def get_overlap_chart(lat0, lon0, extent_gdf, folder, chart_folder, startdate, enddate, proj, th = 80, simplify = True):
    chart_ids = []
    dfc = pd.DataFrame()
    i = 0

    files = glob.glob(supp_folder + f"*_extent.shp")
    
    for file in files:        
        name = os.path.basename(file)
        agency = name.split("_")[0]
        chart_id = name.split("_")[1]

        if agency == "NIC":
            # frac = 100
            polygon = gpd.read_file(file).to_crs(proj)
            frac = get_intersection(extent_gdf.to_crs(proj), polygon, proj, simplify, tolerance = 20000)
            del polygon
        else:
            polygon = gpd.read_file(file).to_crs(proj)
            frac = get_intersection(extent_gdf.to_crs(proj), polygon, proj, simplify, tolerance = 5000)
            del polygon
            # r = 80
        
        if frac >= th:            
            dfc.loc[i, "agency"] = agency
            dfc.loc[i, "chart_id"] = chart_id
            dfc.loc[i, "lat"] = lat0
            dfc.loc[i, "lon"] = lon0
            dfc.loc[i, "radius"] = distance
            dfc.loc[i, "fraction"] = frac
            dfc.loc[i, "folder"] = chart_folder + agency
            # dfc.loc[i, "first_date"] = date.strftime("%Y%m%d")
            i += 1  
    
    # Make folder to download ice chart tiff files
    subfolder = folder + f"Chart/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
    if not os.path.exists(subfolder):
        os.makedirs(subfolder)
    dfc.to_csv(f"{subfolder}/Chart_list_{str(int(lat0)).zfill(2)}_{str(int(lon0))}.csv")

    return dfc

def filter_dfc(dfc, target = None):
    if len(dfc) > 0:
      if target == None:
          if 'DMI' in np.unique(dfc['agency']):
              dfc = dfc[dfc['agency'] == "DMI"].reset_index(drop = True) #.loc[:1, :]
          elif 'NOAA' in np.unique(dfc['agency']):
              dfc = dfc[dfc['agency'] == "NOAA"].reset_index(drop = True)
          else:
              dfc = dfc[dfc['agency'] == "NIC"].reset_index(drop = True)
      else:
          dfc = dfc[dfc['agency'] == target].reset_index(drop = True)
    else:
      pass
    return dfc

def read_tif(file):
    with rasterio.open(file) as rst:
        array = rst.read(1)
        array[array == 0] = np.nan
    return array

def unique_value(lists):
    list_unique = []
    for item in lists:
        if item not in list_unique:
            list_unique.append(item)
    return list_unique

def find_nearest_chart(S1_file, chart_list, dsec = 15):
    # S1_time = datetime.strptime(os.path.basename(S1_file).split("_")[-1][:-4], "%Y%m%dT%H%M%S")
    S1_time = datetime.strptime(S1_file, "%Y%m%dT%H%M%S")
    proceed = False
    for c in chart_list:
        chart_time = datetime.strptime(os.path.basename(c).split("_")[2], "%Y%m%d")
        if abs(S1_time - chart_time).days < dsec:
            target = c
            dsec = abs(S1_time - chart_time).days
            proceed = True
    if proceed:
        return target
    else:
        return None

def grid_swath_data(vals, lons, lats, areadef, radius=20e3, nanval=0, label=None):
    # Grid the data to an areadef

    swathdef = get_pyresample_swathdef(lons=lons, lats=lats)

    resampler = NumpyBilinearResampler(swathdef, areadef, radius)

    if label is not None:
        print(f'resampling swath data ({label})...', end='', flush=True)
    with warnings.catch_warnings(record=True) as warning_list:
        gridded = resampler.resample(vals).astype(np.float32)

        for warning in warning_list:
            message = warning.message

            # Ignore proj messages about using CRS codes
            if isinstance(message, UserWarning) and 'converting to a PROJ string' in str(message):
                pass
            else:
                print(f'warning: {message}')

    if label is not None:
        print('done', flush=True)

    # Set NaN values
    if nanval is not None:
        gridded[gridded == nanval] = np.nan

    return gridded

def get_pyresample_area_def(gridid):
    """Return the pyresample module's AreaDefinition for a specified grid"""
    try:
        assert gridid in GRIDID_AREADEFS.keys()
    except AssertionError:
        raise ValueError(f'No AreaDefinition information for: {gridid}')

    gridid_area_def = GRIDID_AREADEFS[gridid]
    area_def = AreaDefinition(
        gridid_area_def['area_id'],
        gridid_area_def['description'],
        gridid_area_def['proj_id'],
        gridid_area_def['projection'],
        gridid_area_def['width'],
        gridid_area_def['height'],
        gridid_area_def['area_extent'],
    )

    return area_def

##### PARAMETERS ####################################################
# Configuration file
fn = "./config.yaml"
config = read_config(fn)

# Set up start date & time interval (look for ice charts for every ddays)
global folder, supp_folder, chart_folder
folder = config['times_dir']
chart_folder = config['chart_dir']
supp_folder = config['supp_dir']
overwrite = config['overwrite']

proj = config['crs'] #'EPSG:3413' #'EPSG:3408'
pixel_size = config['pixel_size'] #160
r = config['radius_pixel']
distance = pixel_size * r - pixel_size/2 #120000 # Radius of extent from the center (lon0, lat0)
target_chart = config['target_chart']

POLARIZATION = config['POLARIZATION'] #'HH'
INSTRUMENT_MODE = config['INSTRUMENT_MODE'] #'EW'
PLATFORM = config['PLATFORM']

# Earliest date: 2024/08/10
startdate = config['times_date0'] #'2025-01-01'
enddate = config['times_date1'] #'2026-01-01'

start_index = config['starti']

from scipy.ndimage import zoom
from pyresample import geometry, kd_tree, bilinear
from netCDF4 import Dataset
from pyresample import geometry, kd_tree
from pyresample.geometry import AreaDefinition, SwathDefinition
from pyresample.bilinear import NumpyBilinearResampler

def combine_to_netcdf(lat0, lon0, time0, sar_id, amsr_files, era5_file, chart_id, proj = 'EPSG:3413', scale = 4, overwrite = False):

    nc_dir = folder + f"NetCDF/{chart_id}/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
    if not os.path.exists(nc_dir):
      os.makedirs(nc_dir)
    
    nc_name = f"{nc_dir}/{sar_id}.nc"
    
    subfolder = f"{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
    chart_list = glob.glob(folder + f"Chart/{subfolder}/{chart_id}_{time0[:4]}*.tif")
    
    chart_file = find_nearest_chart(time0, chart_list)
    
    
    if ((os.path.exists(nc_name) == False) or (overwrite)) and (chart_file != None) and (os.path.exists(nc_dir)):   
        with Dataset(nc_name, "w", format="NETCDF4") as nc:   
            
            array_chart = zoom(read_tif(chart_file), zoom=scale, order=0)
        
            table = pd.read_csv(chart_file.replace(".tif", ".csv"), index_col = 0)
            unique_id = np.unique(table['poly_id'])
            codes = get_chart_id(table, unique_id)
            
            S1_hh = f"{folder}/S1/{subfolder}/S1_HH_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}_{time0}.tif"
            hh = zoom(read_tif(S1_hh), zoom=scale, order=1)
        
            S1_hv = f"{folder}/S1/{subfolder}/S1_HV_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}_{time0}.tif"
            hv = zoom(read_tif(S1_hv), zoom=scale, order=1)
        
            S1_angle = f"{folder}/S1/{subfolder}/S1_angle_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}_{time0}.tif"
            angle = zoom(read_tif(S1_angle), zoom=scale, order=1)
            
            S1_x = f"{folder}/S1/{subfolder}/S1_x_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.tif"
            xx = zoom(read_tif(S1_x), zoom=scale, order=1)
        
            S1_y = f"{folder}/S1/{subfolder}/S1_y_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.tif"
            yy = zoom(read_tif(S1_y), zoom=scale, order=1)  
        
            x_min = np.nanmin(xx)
            x_max = np.nanmax(xx)
            y_min = np.nanmin(yy)
            y_max = np.nanmax(yy)
    
            nxs, nys = xx.shape
            nxp, nyp = 256, 256
    
            areas_def = geometry.AreaDefinition(
                area_id=proj,
                description="Arctic Polar Stereographic",
                proj_id=proj,
                projection=proj.upper(),
                width=nxs,
                height=nys,
                area_extent=(x_min, y_min, x_max, y_max)
            )
        
            areap_def = geometry.AreaDefinition(
                area_id=proj,
                description="Arctic Polar Stereographic",
                proj_id=proj,
                projection=proj.upper(),
                width=nxp,
                height=nyp,
                area_extent=(x_min, y_min, x_max, y_max)
            )
    
            ###### X-Y DIMENSION DEFINITION (X, Y, LAT, LON) ###################################
            # S1 SAR grid
            nc.createDimension("y", xx.shape[0])
            nc.createDimension("x", xx.shape[1])
        
            # AMSR & ERA5 grid
            nc.createDimension("yp", nyp)
            nc.createDimension("xp", nxp)
    
            ys = nc.createVariable("y", "f4", ("y",))
            xs = nc.createVariable("x", "f4", ("x",))
            xs[:] = xx[0, :]
            ys[:] = yy[:, 0]
        
            yp = nc.createVariable("yp", "f4", ("yp",))
            xp = nc.createVariable("xp", "f4", ("xp",))
            yp[:] = areap_def.projection_y_coords
            xp[:] = areap_def.projection_x_coords
    
            lat = nc.createVariable("latitude", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            lon = nc.createVariable("longitude", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            lon[:, :] = areas_def.get_lonlats()[0]
            lat[:, :] = areas_def.get_lonlats()[1]
    
            latp = nc.createVariable("latitude_p", "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
            lonp = nc.createVariable("longitude_p", "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
            lonp[:, :] = areap_def.get_lonlats()[0]
            latp[:, :] = areap_def.get_lonlats()[1]
    
            ##### WRITE CHART DATA ####################################################
            polygon_icechart = nc.createVariable("polygon_icechart", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            polygon_icechart[:, :] = array_chart
            nc.ice_chart_polygon_code = np.array(codes, dtype="S")
            polygon_icechart.description = "Polygon icechart - the polygon ids are gridded in native Sentinel-1 SAR geometry- and resolution"
            polygon_icechart.icechart_id = os.path.basename(chart_file)
    
            ##### WRITE SAR DATA ####################################################
            sar_grid_hh = nc.createVariable("sar_grid_hh", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            sar_grid_hh[:, :] = hh
            sar_grid_hh.polarisation = "HH"
            sar_grid_hh.upstream_id = sar_id
            sar_grid_hh.description = "Sigma0 in dB"
            sar_grid_hh.min = np.nanmin(hh)
            sar_grid_hh.max = np.nanmax(hh)
    
            sar_grid_hv = nc.createVariable("sar_grid_hv", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            sar_grid_hv[:, :] = hv
            sar_grid_hv.polarisation = "HV"
            sar_grid_hv.upstream_id = sar_id
            sar_grid_hv.description = "Sigma0 in dB"
            sar_grid_hv.min = np.nanmin(hv)
            sar_grid_hv.max = np.nanmax(hv)
            
            sar_grid_angle = nc.createVariable("sar_grid_incidenceangle", "f4", ("y", "x"), zlib=True, fill_value=np.nan)
            sar_grid_angle[:, :] = angle
        
            ##### AMSR2 data conversion ##############################################
    
            # Find AMSR2 file with the lagest coverage
            amsr_cover = 0
            amsr_target = amsr_files[0]
            for amsr_file in amsr_files:
                with xr.open_dataset(amsr_file) as ds_amsr:        
                    lat_varname = 'Latitude of Observation Point for 89A'
                    lon_varname = 'Longitude of Observation Point for 89A'
                    lat_amsr = np.array(ds_amsr.variables[lat_varname])[:, ::2]
                    lon_amsr = np.array(ds_amsr.variables[lon_varname])[:, ::2]
                
                    swath_amsr = geometry.SwathDefinition(lons=lon_amsr, lats=lat_amsr)
                    resampler = NumpyBilinearResampler(swath_amsr, areap_def, 50000)
                    val_varname = f"Brightness Temperature (res06,89.0GHz,H)"
                    val = np.array(ds_amsr.variables[val_varname])
                    gridded = resampler.resample(val)
                    gridded[gridded == 0] = np.nan
                    ac = np.count_nonzero(~np.isnan(gridded))/(nxp * nyp)
                    if ac > amsr_cover:
                        amsr_cover = ac
                        amsr_target = amsr_file
                        # print(amsr_cover, amsr_target)
    
            # Apply the maximum-coverage amsr file (amsr_target)
            with xr.open_dataset(amsr_target) as ds_amsr:
                lat_varname = 'Latitude of Observation Point for 89A'
                lon_varname = 'Longitude of Observation Point for 89A'
                lat_amsr = np.array(ds_amsr.variables[lat_varname])[:, ::2]
                lon_amsr = np.array(ds_amsr.variables[lon_varname])[:, ::2]
            
                swath_amsr = geometry.SwathDefinition(lons=lon_amsr, lats=lat_amsr)
                resampler = NumpyBilinearResampler(swath_amsr, areap_def, 50000)
                
                channels = ["6.9", "7.3", "10.7", "18.7", "23.8", "36.5", "89.0"]
                for cha in channels:
                    for pol in ["V", "H"]:
                        val_varname = f"Brightness Temperature (res06,{cha}GHz,{pol})"
                        val = np.array(ds_amsr.variables[val_varname])
                        gridded = resampler.resample(val) #.astype(np.float32)
                        gridded[gridded == 0] = np.nan
        
                        amsr_grid = nc.createVariable("btemp_" + cha.replace(".", "_") + pol.lower(), "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
                        amsr_grid[:, :] = gridded
                        amsr_grid.AMSR2_swaths = os.path.basename(amsr_target)
                        amsr_grid.min = np.nanmin(gridded)
                        amsr_grid.max = np.nanmax(gridded)
                        amsr_grid.description = f"Brightness temperature in K at {cha}GHz. Polarization: {pol}."
        
            ##### ERA5 data conversion ################################################
            with xr.open_dataset(era5_file) as ds_era:
                lon, lat = np.meshgrid(np.array(ds_era.variables["longitude"]), np.array(ds_era.variables["latitude"]))
                swath_era = geometry.SwathDefinition(lons=lon, lats=lat)
                resampler = NumpyBilinearResampler(swath_era, areap_def, 100000)
    
                if proj == "EPSG:3413":
                    ref_lon = -45
                else:
                    ref_lon = 0
            
                u10 = np.array(ds_era.variables['u10'])
                v10 = np.array(ds_era.variables['v10'])        
                u10r, v10r = rotate_vector(u10, v10, lon, ref_lon = ref_lon)
                u10r_grid = resampler.resample(u10r)
                v10r_grid = resampler.resample(v10r)
                
                era_grid_u = nc.createVariable("u10m_rotated", "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
                era_grid_u[:, :] = u10r_grid
                era_grid_u.units = ds_era['u10'].units
                era_grid_u.long_name = ds_era['u10'].long_name
        
                era_grid_v = nc.createVariable("v10m_rotated", "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
                era_grid_v[:, :] = v10r_grid
                era_grid_v.units = ds_era['v10'].units
                era_grid_v.long_name = ds_era['v10'].long_name
                # ac = np.count_nonzero(~np.isnan(v10r_grid))/(nxp * nyp)
                # print("ERA5: ", ac)
        
                for field in ["t2m", "skt", "tcwv", "tclw"]:
                    val = np.array(ds_era.variables[field])
                    gridded = resampler.resample(val)
                    era_grid = nc.createVariable(field, "f4", ("yp", "xp"), zlib=True, fill_value=np.nan)
                    era_grid[:, :] = gridded
                    era_grid.units = ds_era[field].units
                    era_grid.long_name = ds_era[field].long_name
                    
        print("DONE ==>> ", nc_name, "\n")
        
    else:
        print("SKIP .... ", nc_name, "\n") 

#####################################################################
valid_latlon = pd.read_csv(f"valid_latlon_r{r}_filter_10_25.csv", index_col = 0)
lats = valid_latlon["lat"].values
lons = valid_latlon["lon"].values
orbits = valid_latlon["orbit"].values

for k in range(start_index, len(valid_latlon)):

    ##### Latitude and longitude initialization #############################
    lat0 = float(lats[k]) #66 #lats[order]
    lon0 = float(lons[k]) #58 #lons[order]
    orbit0 = orbits[k]
    center = [lon0, lat0]
    extent = get_extent(center, distance, proj)

    coord = np.array(extent.transform(proj='EPSG:4326', maxError=10).getInfo()['coordinates'][0])
    lon_max, lat_max = np.nanmax(coord, axis = 0)
    lon_min, lat_min = np.nanmin(coord, axis = 0)

    # Create polygon from EPSG:3413 coordinates
    coords = extent.getInfo()['coordinates']
    coords2 = [(xys[0], xys[1]) for xys in coords[0]]
    
    # Build GeoDataFrame
    extent_gdf = rectangle_to_gdf(coords2, proj)
    dfc = get_overlap_chart(lat0, lon0, extent_gdf, folder, chart_folder, startdate, enddate, proj, th = 100)
    dfc = filter_dfc(dfc, target = target_chart)
    
    # Process only existing folders
    process = True
    if len(dfc) > 0:
      chart_id = dfc.loc[0, "agency"] +"_" + dfc.loc[0, "chart_id"]
      print(chart_id)
      nc_dir = folder + f"NetCDF/{chart_id}/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
      if os.path.exists(nc_dir):
        nc_list = glob.glob(nc_dir + f"/*_{startdate[:4]}*.nc")
        print(nc_dir, " --> Number of files: ", len(nc_list))
        process = True
      else:
        process = True
    else:
      process = False
    
    
    if process:
    
      source = "COPERNICUS/S1_GRD"
      collection = ee.ImageCollection(source)\
        .filter(ee.Filter.eq('instrumentMode', INSTRUMENT_MODE))\
        .filter(ee.Filter.eq('platform_number', PLATFORM))\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'HH'))\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'HV'))\
        .filterDate(startdate, enddate)\
        .filter(ee.Filter.eq('relativeOrbitNumber_start', int(orbit0)))\
        .filterBounds(extent)
      ##########################################################################
      
      # S1 = S1.map(add_HH)
      S1 = filter_full_coverage(collection, extent, th = 1)
      num = S1.size().getInfo()
      print(f"{k} / {len(valid_latlon)} row, {lat0}, {lon0}; {startdate} - {enddate}; Number of S1 images: ", num)
      # print(S1.aggregate_array("coverage_ratio").getInfo())
      
      files = S1.aggregate_array("system:id").getInfo() 
      coverages = S1.aggregate_array("coverage_ratio").getInfo() 
      
      first = True
      df = pd.DataFrame({'S1_id': files, 'coverage_ratio': coverages})
      df['lat'] = lat0
      df['lon'] = lon0
      df['proj'] = proj
      df.to_csv(folder + f"S1/S1{PLATFORM}_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.csv")
      
      if len(nc_list) == len(files) and overwrite == False:
        files = []
      
      for f in files[:]:
          time0 = f.split("_")[-5]
          date0 = time0[:8]
          
          print(f, date0)
          
          ### ====== Sentinel-1 images =====
          img = ee.Image(f).setDefaultProjection(proj)
      
          band_coord = ee.Image.pixelCoordinates(proj)
          img = img.addBands(band_coord)
          
          # img_hh = img.select('HH').clip(extent)
          # img_hv = img.select('HV').clip(extent)
          # img_angle = img.select('angle').clip(extent)
          # img_xx = img.select('x').clip(extent)
          # img_yy = img.select('y').clip(extent)
      
          if first:
              bands = ['HH', 'HV', 'angle', 'x', 'y']
              first = False
          else:
              bands = ['HH', 'HV', 'angle']
      
          # Make folder to download ice chart tiff files
          subfolder = folder + f"S1/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
          if not os.path.exists(subfolder):
              os.makedirs(subfolder)
              
          for band in bands:
              img2 = img.select(band).clip(extent)
              if band in ['x', 'y']:
                  out_tif = f"{subfolder}/S1_{band}_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.tif"
              else:
                  out_tif = f"{subfolder}/S1_{band}_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}_{time0}.tif"
                  
              if os.path.exists(out_tif) == False or overwrite:
                  # geemap.ee_to_geotiff(img2, out_tif, bands =  resolution = pixel_size, crs = proj, quiet = True)
                  # geemap.ee_export_image(img2, filename=out_tif, scale=pixel_size, region=extent, crs = proj, file_per_band=False)
                  download_img(img2, proj, pixel_size, extent, out_tif)
      
          ### ===== Ice Chart =====
          for i in range(0, len(dfc)):
              charts = os.listdir(dfc.loc[i, "folder"])
              for chart in charts:
                  if (abs(datetime.strptime(chart.split("_")[2], "%Y%m%d") - datetime.strptime(date0, "%Y%m%d")).days < 7) & (chart.split("_")[1] == dfc.loc[i, "chart_id"]):
                      chartname = glob.glob(os.path.join(dfc.loc[i, "folder"], chart) + "/*.shp")[0]
                      polygon = gpd.read_file(chartname).to_crs(proj)
                      polygon = add_chart_id(polygon)
                      # chart2 = chart.clip(extent_gdf).reset_index(drop = True)
              
                      # Make folder to download ice chart tiff files
                      subfolder = folder + f"Chart/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
                      if not os.path.exists(subfolder):
                          os.makedirs(subfolder)
                      
                      chart_tif = f"{subfolder}/{chart}_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.tif"
                      if os.path.exists(chart_tif) == False or overwrite:
                          save_chart_tif(out_tif, chart_tif, polygon)
                      table = pd.DataFrame(polygon.drop(columns="geometry"))        
                      table.to_csv(chart_tif.replace(".tif", ".csv"))
                      chart_id = chart[:-9]
          
          ### ===== AMSR =====
          # [min lon, min lat, max lon, max lat]
          bbox_amsr=[lon_min-1, lat_min-0.5, lon_max+1, lat_max+0.5] #[lon0-2, lat0-1, lon0+2, lat0+1]
          amsr_cnt = 0
          dh = 3
          
          while amsr_cnt == 0:
              start_time = datetime.strptime(f"{time0}", "%Y%m%dT%H%M%S") - timedelta(seconds = 3600*dh)
              end_time = datetime.strptime(f"{time0}", "%Y%m%dT%H%M%S") + timedelta(seconds = 3600*dh)
              res = gportal.search(
                  dataset_ids=['11001002'],
                  # 'L2-Sea Ice Concentration（SIC)': ['11002013', '11002006'];
                  # 'L1R-Brightness temperature（TB）': ['11001002']
                  # L1R Brightness temp: ['11001002'],  # l1r - see gportal.datasets()
                  start_time=start_time,
                  end_time=end_time,
                  bbox=bbox_amsr
              )
              
              # Select full coverage AMSR2 swaths
              swaths = [product.to_dict(flatten_properties=True) for product in res.products()]
              if len(swaths) > 0:
                amsr_gdf = gpd.GeoDataFrame.from_features(swaths, crs="EPSG:4326")
                
                roi_gdf = shapely.geometry.box(*bbox_amsr)
                full_coverage = amsr_gdf[amsr_gdf.covers(roi_gdf)]
            
                amsr_cnt = len(full_coverage) # res.matched()
                
              print(f"Matched for {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {end_time.strftime('%Y-%m-%d %H:%M:%S')}: {amsr_cnt}")    
              dh += 1
              
          amsr_iden = full_coverage["identifier"].values[0]
      
          products = res.products()
          scratch = folder + "AMSR/"
  
          amsr_files = []
          for product in res.products():
              # print(product.data_url)   
              
              if product.id == amsr_iden:
                out_file = os.path.join(scratch, product.id + ".nc")
                
                amsr_files.append(out_file)
                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    print(f"file {out_file} exists, skipping download")
                    # return out_file
                else:
                    response = requests.get(product.data_url)
                
                    os.makedirs(scratch, exist_ok=True)
                    
                    if response.status_code == 200:
                        with open(out_file, 'wb') as file:
                            file.write(response.content)
                        print(f'AMSR ({out_file}) downloaded successfully')
      
          ### ===== ERA5 =====
          # [90, -180, 0, 180] [north, west, south, east]
          bbox_era5=[lat_max+1, lon_min-2, lat_min-1, lon_max+2] #[lon_min-1, lat_max+0.5, lon_max+1, lat_min-0.5]
          t = hour_rounder(datetime.strptime(f"{time0}", "%Y%m%dT%H%M%S"))
          years = [f"{str(t.year).zfill(4)}"]
          months = [f"{str(t.month).zfill(2)}"]
          days = [f"{str(t.day).zfill(2)}"]
          hours = [f"{str(t.hour).zfill(2)}:00"]
      
          subfolder = folder + f"ERA5/{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}"
          if not os.path.exists(subfolder):
              os.makedirs(subfolder)
          file_era5 = f"{subfolder}/ERA5_{time0}_{str(int(lat0)).zfill(2)}_{str(int(lon0)).zfill(3)}.nc"
          if os.path.exists(file_era5):
              print(f"ERA5 skipped - {file_era5}")
          else:
              retrieve_hourly_ERA5_bbox(years, months, days, hours, bbox_era5, file_era5)
              print(f"ERA5 downloaded - {file_era5}")
  
          #### COMBINE to NC file #####            
          sar_id = os.path.basename(f)
          combine_to_netcdf(lat0, lon0, time0, sar_id, amsr_files, file_era5, chart_id, overwrite = overwrite)
      
      print("================================================================")