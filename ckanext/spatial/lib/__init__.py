import logging
import ckantoolkit as tk

from ckanext.spatial.model import PackageExtent
from shapely.geometry import shape


from ckanext.spatial.geoalchemy_common import (WKTElement, ST_Transform,
                                               compare_geometry_fields,
                                               )
config = tk.config

log = logging.getLogger(__name__)


def get_srid(crs):
    """Returns the SRID for the provided CRS definition
    The CRS can be defined in the following formats
    - urn:ogc:def:crs:EPSG::4326
    - EPSG:4326
    - 4326
    """

    if ":" in crs:
        crs = crs.split(":")
        srid = crs[len(crs) - 1]
    else:
        srid = crs

    return int(srid)


def save_package_extent(package_id, geometry = None, srid = None):
       package_id: Package unique identifier
       geometry: a Python object implementing the Python Geo Interface
                (i.e a loaded GeoJSON object)
       srid: The spatial reference in which the geometry is provided.
             If None, it defaults to the DB srid.

       Will throw ValueError if the geometry object does not provide a geo interface.

       The responsibility for calling model.Session.commit() is left to the
       caller.
    '''
    db_srid = int(config.get('ckan.spatial.srid', '4326'))


    existing_package_extent = Session.query(PackageExtent).filter(PackageExtent.package_id==package_id).first()

    if geometry:
        geom_obj = shape(geometry)

        if not srid:
            srid = db_srid

        package_extent = PackageExtent(package_id=package_id,
                                       the_geom=WKTElement(geom_obj.wkt, srid))

    # Check if extent exists
    if existing_package_extent:

        # If extent exists but we received no geometry, we'll delete the existing one
        if not geometry:
            existing_package_extent.delete()
            log.debug('Deleted extent for package %s' % package_id)
        else:
            # Check if extent changed
            if not compare_geometry_fields(package_extent.the_geom, existing_package_extent.the_geom):
                # Update extent
                existing_package_extent.the_geom = package_extent.the_geom
                existing_package_extent.save()
                log.debug('Updated extent for package %s' % package_id)
            else:
                log.debug('Extent for package %s unchanged' % package_id)
    elif geometry:
        # Insert extent
        Session.add(package_extent)
        log.debug('Created new extent for package %s' % package_id)

def validate_bbox(bbox_values):
    '''
    Ensures a bbox is expressed in a standard dict.

    bbox_values may be:
           a string: "-4.96,55.70,-3.78,56.43"
           or a list [-4.96, 55.70, -3.78, 56.43]
           or a list of strings ["-4.96", "55.70", "-3.78", "56.43"]

    ordered as MinX, MinY, MaxX, MaxY.

    Returns a dict with the keys:

       {
            "minx": -4.96,
            "miny": 55.70,
            "maxx": -3.78,
            "maxy": 56.43
        }

    If there are any problems parsing the input it returns None.
    """

    if isinstance(bbox_values, str):
        bbox_values = bbox_values.split(",")

    if len(bbox_values) != 4:
        return None

    try:
        bbox = {}
        bbox["minx"] = float(bbox_values[0])
        bbox["miny"] = float(bbox_values[1])
        bbox["maxx"] = float(bbox_values[2])
        bbox["maxy"] = float(bbox_values[3])
    except ValueError:
        return None

    return bbox


def fit_bbox(bbox_dict):
    """
    Ensures that all coordinates in a bounding box
    fall within -180, -90, 180, 90 degrees

    Accepts a dict with the following keys:

       {
            "minx": -4.96,
            "miny": 55.70,
            "maxx": -3.78,
            "maxy": 56.43
        }

    """

    def _adjust_longitude(value):
        if value < -180 or value > 180:
            value = value % 360
            if value < -180:
                value = 360 + value
            elif value > 180:
                value = -360 + value
        return value

    def _adjust_latitude(value):
        if value < -90 or value > 90:
            value = value % 180
            if value < -90:
                value = 180 + value
            elif value > 90:
                value = -180 + value
        return value

    return {
        "minx": _adjust_longitude(bbox_dict["minx"]),
        "maxx": _adjust_longitude(bbox_dict["maxx"]),
        "miny": _adjust_latitude(bbox_dict["miny"]),
        "maxy": _adjust_latitude(bbox_dict["maxy"]),
    }


def fit_linear_ring(lr):

    bbox = {
        "minx": lr[0][0],
        "maxx": lr[2][0],
        "miny": lr[0][1],
        "maxy": lr[2][1],
    }

    bbox = fit_bbox(bbox)

    return [
        (bbox["minx"], bbox["maxy"]),
        (bbox["minx"], bbox["miny"]),
        (bbox["maxx"], bbox["miny"]),
        (bbox["maxx"], bbox["maxy"]),
        (bbox["minx"], bbox["maxy"]),
    ]
