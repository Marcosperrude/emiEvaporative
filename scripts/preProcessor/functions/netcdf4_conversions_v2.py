# Author: Igor Tibúrcio @ LCQAr
# Date: 2024-05-16

import xarray as xr
import rioxarray as rxr
import pyproj
import numpy as np
from pathlib import Path

# O seguinte artigo vai ajudar a compreender conversões de unidades para WRF
# https://fabienmaussion.info/2018/01/06/wrf-projection/#:~:text=you%20have%20to%20use%20the,salem.

# TODO: Aparentemente não é esse sistema de coordenadas que Latitude e Longitude estão

# Aparentemente o pyproj não consegue converter as coordenadas corretamente
# Aparentemente, o método com GDAL também não deu certo kkkkk

# Não sei o que pode ser, pois convertendo o raster no QGIS funciona


# def convert_altproj_to_wgs84(
#         lat: np.array,
#         lon: np.array,
#         xcent: float | int,
#         ycent: float | int
#     ):
#     mapstr = f'+proj=merc +a=6370000.0 +b=6370000.0 +lat_ts=33 +lon_0=0'
#     inProj = pyproj.Proj(mapstr)              # Projecting to WRF mercator spherical compat.
#     outProj = pyproj.Proj('EPSG:4326')        # WGS84 (EPSG:4326)

#     # Convert to meshgrid
#     lon, lat = np.meshgrid(lon, lat)

#     # Convert to Equatorial Mercator again
#     x_prelim, y_prelim = inProj(lon, lat)

#     # Convert to WGS84
#     transformer = pyproj.Transformer.from_proj(inProj, outProj, always_xy=True)
#     lon, lat = transformer.transform(x_prelim, y_prelim)

#     return lat, lon

def ioapiCoords(ds):
    # Latlon
    lonI = ds.XORIG
    latI = ds.YORIG
    
    # Cell spacing 
    xcell = ds.XCELL
    ycell = ds.YCELL
    ncols = ds.NCOLS
    nrows = ds.NROWS

    x = np.arange(lonI,(lonI+ncols*xcell),xcell)
    y = np.arange(latI,(latI+nrows*ycell),ycell)

    return x, y
    
    # xv, yv = np.meshgrid(lon,lat)
    # return xv,yv,lon,lat

def convert_equatmerc_to_wgs84(
        x: np.array,
        y: np.array,
        gamma: int | float,
        xcent: int | float,
        ycent: int | float,
        xorig: int | float,
        yorig: int | float
    ):
    """Convert CMAQ spherical projection to WGS84

    References:
    	Ref 1: https://cjcoats.github.io/ioapi/GRIDS.html#horiz
        Ref 2: https://proj.org/en/9.4/usage/projections.html
        Ref 3: https://github.com/barronh/recipes/blob/master/OpenCMAQInArcGIS.md
        Ref 4 (Ellipsoid): https://www.cmascenter.org/sa-tools/documentation/4.2/html/grids_ellipsoids_map_proj.html

    EQUATORIAL MERCATOR
        PROJ_ALPHA is the latitude of true scale.
        PROJ_BETA is unused.
        PROJ_GAMMA is the longitude of the central meridian.
        (X_CENT,Y_CENT) are the (lon ,lat) coordinates for the center (0,0) of the Cartesian coordinate system.
        Coordinate units are meters.
        GCTP projection 5.

    Parameters
    ----------
    x : np.array
        1D X array, in meters
    y : np.array
        1D Y array, in meters
    gamma : int | float
        Gamma parameter
    xcent : int | float
        Central meridian (in degree if no angular unit specified)
    ycent : int | float
        Latitude of origin (in degree if no angular unit specified)
    xorig : int | float
        False easting (always in meters)
    yorig : int | float
        False northing (always in meters)

    Returns
    -------
    Tuple(np.array, np.array)
        Latitude and Longitude 1D array
    """
    
    # pyproj
    # mapstr = f'+proj=merc +a=6370000.0 +b=6370000.0 +lat_ts=33 +lon_0=0'
    # inProj = pyproj.Proj(mapstr)              # Projecting to WRF mercator spherical compat.

    # Calculating false easting and northing (ref 3)

    # Adding projecting (considering Equatorial Mercator projection from CMAQ) - Refs 1, 2, 3, and 4
    mapstr = f'+proj=merc +lon_0={xcent} +lat_0={ycent} +lat_ts=0'
    inProj = pyproj.Proj(mapstr)
    outProj = pyproj.Proj("EPSG:4326")

    # using Pyproj
    _x, _y = np.meshgrid(x, y)

    transformer = pyproj.Transformer.from_proj(inProj, outProj)

    lon, lat = transformer.transform(_x, _y)

    return lon[:,0], lat[0,:]

    # using GDAL
    # # GDAL
    # in_srs = osr.SpatialReference()
    # in_srs.ImportFromProj4(mapstr)
    # out_srs = osr.SpatialReference()
    # out_srs.ImportFromEPSG(4326)

    # # Convert to meshgrid
    # lon, lat = np.meshgrid(lon, lat)

    # # Convert to Equatorial Mercator again
    # x_prelim, y_prelim = inProj(lon, lat)

    # # Convert to WGS84
    # transformer = osr.CoordinateTransformation(in_srs, out_srs)
    # for i in range(lon.shape[0]):
    #     for j in range(lon.shape[1]):
    #         lon[i,j], lat[i,j], _ = transformer.TransformPoint(x_prelim[i,j], y_prelim[i,j])
    #
    # return lon[:,0], lat[0,:]

def brain_to_latlng(
        ds: xr.Dataset,
        lat_var_name='Latitude',
        lon_var_name='Longitude',
        coord_epsg='4326'
    ) -> xr.Dataset:
    """Converts brain NetCDF "row, col" based to "lat, lon" based

    Parameters
    ----------
    ds : xr.Dataset
        Brain dataset row, col based. Must contain lat lan info

    lat_var_name : str, optional
        Latitude var name on dataset, 'Latitude' by default

    lon_var_name : str, optional
        Longitude var name on dataset, 'Longitude' by default

    coord_epsg : str, optional
        Coordinate system EPSG code, '4326' (WGS84) by default

    Returns
    -------
    xr.Dataset
        Brain dataset lat, lon based:

        Dimentions: (all dimentions + x and y in lat and lon coordinates)
        Data variables:
            [list of all data variables]
    """

    x, y = ioapiCoords(ds)

    lat_converted, lon_converted = convert_equatmerc_to_wgs84(
        # ds.Latitude.values[:,0], 
        # ds.Longitude.values[0,:],
        x,
        y,
        ds.P_GAM,
        ds.XCENT,
        ds.YCENT,
        ds.XORIG,
        ds.YORIG
    )

    # Selecting lat/lon data
    # lat = ds[lat_var_name][:,0].values
    lat = lat_converted
    lat_attrs = {
        'long_name': 'latitude',
        'standard_name': 'latitude',
        'units': 'degrees_north'}

    # lon = ds[lon_var_name][0,:].values
    lon = lon_converted
    lon_attrs = {
        'long_name': 'longitude', 
        'standard_name': 'longitude', 
        'units': 'degrees_east'}

    # Selecting EPSG coords
    coord = f'EPSG:{coord_epsg}'

    # Selecting dims
    dims = list(ds.dims)
    data_dims = {}
    
    for dim in dims:
        if dim == 'ROW':
            data_dims['lat'] = xr.DataArray(
                lat, name='lat', dims='lat', attrs=lat_attrs)
        elif dim == 'COL':
            data_dims['lon'] = xr.DataArray(
                lon, name='lon', dims='lon', attrs=lon_attrs)
        else:
            data_dims[dim] = xr.DataArray(
                ds[dim].values,
                name=dim,
                dims=dim,
                attrs=ds[dim].attrs
            )

    # Selecting vars
    vars = list(ds.keys())
    data_vars = {}

    for var in vars:
        # Associating dims to vars
        var_dims = list(ds[var].dims)
        new_var_dims = []

        for var_dim in var_dims:
            if var_dim == 'ROW':
                new_var_dims.append('lat')
            elif var_dim == 'COL':
                new_var_dims.append('lon')
            else:
                new_var_dims.append(var_dim)

        del var_dims
            
        data_vars[var] = (
            new_var_dims, 
            ds[var].values, 
            ds[var].attrs, 
            ds[var].encoding
        )


    # Selecting attributes
    attrs = list(ds.attrs)
    data_attrs = {}

    for attr in attrs:
        data_attrs[attr] = ds.attrs[attr]

    resp_ds = (xr
            .Dataset(data_vars=data_vars, coords=data_dims, attrs=data_attrs)
            .rio.write_crs(coord))

    return resp_ds