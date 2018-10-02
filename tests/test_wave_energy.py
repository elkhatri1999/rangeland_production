"""Module for Testing the InVEST Wave Energy module."""
import unittest
import tempfile
import shutil
import os
import csv
import re

import numpy
import numpy.testing
from shapely.geometry import Polygon
from shapely.geometry import Point
import pygeoprocessing.testing
from pygeoprocessing.testing import sampledata

from osgeo import gdal
from osgeo import osr, ogr

SAMPLE_DATA = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'invest-test-data', 'wave_energy',
    'input')
REGRESSION_DATA = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'invest-test-data', 'wave_energy')


def _make_dummy_files(workspace_dir):
    """Within workspace, make intermediate and output folders with dummy files.

    Parameters:
        workspace_dir: path to workspace for creating intermediate/output folder.

    Returns:
        None.
    """
    intermediate_files = ['WEM_InputOutput_Pts.shp',
                          'aoi_clipped_to_extract_uri.shp']

    raster_files = ['wp_rc.tif', 'wp_kw.tif', 'capwe_rc.tif',
                    'capwe_mwh.tif', 'npv_rc.tif', 'npv_usd.tif']
    vector_files = ['GridPts_prj.shp', 'LandPts_prj.shp']
    table_files = ['capwe_rc.csv', 'wp_rc.csv', 'npv_rc.csv']
    output_files = raster_files + vector_files + table_files

    for folder, folder_files in zip(['intermediate', 'output'],
                                    [intermediate_files, output_files]):
        folder_path = os.path.join(workspace_dir, folder)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for file_name in folder_files:
                with open(os.path.join(folder_path, file_name), 'wb') as open_file:
                    open_file.write('')


class WaveEnergyUnitTests(unittest.TestCase):
    """Unit tests for the Wave Energy module."""

    def setUp(self):
        """Overriding setUp function to create temp workspace directory."""
        # this lets us delete the workspace after its done no matter the
        # the rest result
        self.workspace_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Overriding tearDown function to remove temporary directory."""
        shutil.rmtree(self.workspace_dir)

    def test_pixel_size_transform(self):
        """WaveEnergy: testing pixel size transform helper function.

        Function name is : 'pixel_size_based_on_coordinate_transform'.
        """
        from natcap.invest.wave_energy import wave_energy

        srs = sampledata.SRS_WILLAMETTE
        srs_wkt = srs.projection
        spat_ref = osr.SpatialReference()
        spat_ref.ImportFromWkt(srs_wkt)

        # Define a Lat/Long WGS84 projection
        epsg_id = 4326
        reference = osr.SpatialReference()
        proj_result = reference.ImportFromEPSG(epsg_id)
        # Get projection as WKT
        latlong_proj = reference.ExportToWkt()
        # Set origin to use for setting up geometries / geotransforms
        latlong_origin = (-70.5, 42.5)

        # Pixel size helper for defining lat/long pixel size
        def pixel_size(x): return (x, -1. * x)

        # Get a point from the clipped data object to use later in helping
        # determine proper pixel size
        matrix = numpy.array([[1, 1, 1, 1], [1, 1, 1, 1]])
        input_path = os.path.join(self.workspace_dir, 'input_raster.tif')
        # Create raster to use as testing input
        raster_uri = pygeoprocessing.testing.create_raster_on_disk(
            [matrix], latlong_origin, latlong_proj, -1.0,
            pixel_size(0.033333), filename=input_path)

        raster_gt = pygeoprocessing.geoprocessing.get_raster_info(raster_uri)['geotransform']
        point = (raster_gt[0], raster_gt[3])
        raster_wkt = latlong_proj

        # Create a Spatial Reference from the rasters WKT
        raster_sr = osr.SpatialReference()
        raster_sr.ImportFromWkt(raster_wkt)

        # A coordinate transformation to help get the proper pixel size of
        # the reprojected raster
        coord_trans = osr.CoordinateTransformation(raster_sr, spat_ref)
        # Call the function to test
        result = wave_energy.pixel_size_based_on_coordinate_transform(
            raster_uri, coord_trans, point)

        expected_res = (5553.933063, 1187.370813)

        # Compare
        for res, exp in zip(result, expected_res):
            pygeoprocessing.testing.assert_close(res, exp)

    def test_count_pixels_groups(self):
        """WaveEnergy: testing 'count_pixels_groups' function."""
        from natcap.invest.wave_energy import wave_energy

        raster_uri = os.path.join(self.workspace_dir, 'pixel_groups.tif')
        srs = sampledata.SRS_WILLAMETTE

        group_values = [1, 3, 5, 7]
        matrix = numpy.array([[1, 3, 5, 9], [3, 7, 1, 5], [2, 4, 5, 7]])

        # Create raster to use for testing input
        raster_uri = pygeoprocessing.testing.create_raster_on_disk(
            [matrix], srs.origin, srs.projection, -1, srs.pixel_size(100),
            datatype=gdal.GDT_Int32, filename=raster_uri)

        results = wave_energy.count_pixels_groups(raster_uri, group_values)

        expected_results = [2, 2, 3, 2]

        for res, exp_res in zip(results, expected_results):
            pygeoprocessing.testing.assert_close(res, exp_res, 1e-6)

    def test_calculate_percentiles_from_raster(self):
        """WaveEnergy: testing 'calculate_percentiles_from_raster' function."""
        from natcap.invest.wave_energy import wave_energy

        raster_uri = os.path.join(self.workspace_dir, 'percentile.tif')
        srs = sampledata.SRS_WILLAMETTE

        matrix = numpy.arange(1, 101)
        matrix = matrix.reshape(10, 10)
        raster_uri = pygeoprocessing.testing.create_raster_on_disk(
            [matrix], srs.origin, srs.projection, -1, srs.pixel_size(100),
            datatype=gdal.GDT_Int32, filename=raster_uri)

        percentiles = [0, 25, 50, 75]

        results = wave_energy.calculate_percentiles_from_raster(
            raster_uri, percentiles)

        expected_results = [1, 26, 51, 76]

        for res, exp_res in zip(results, expected_results):
            self.assertEqual(res, exp_res)

    def test_create_percentile_ranges(self):
        """WaveEnergy: testing 'create_percentile_ranges' function."""
        from natcap.invest.wave_energy import wave_energy

        percentiles = [20, 40, 60, 80]
        units_short = " m/s"
        units_long = " speed of a bullet in m/s"
        start_value = "5"

        result = wave_energy.create_percentile_ranges(
            percentiles, units_short, units_long, start_value)

        exp_result = ["5 - 20 speed of a bullet in m/s",
                      "20 - 40 m/s", "40 - 60 m/s", "60 - 80 m/s",
                      "Greater than 80 m/s"]

        for res, exp_res in zip(result, exp_result):
            self.assertEqual(res, exp_res)

    def test_calculate_distance(self):
        """WaveEnergy: testing 'calculate_distance' function."""
        from natcap.invest.wave_energy import wave_energy

        srs = sampledata.SRS_WILLAMETTE
        pos_x = srs.origin[0]
        pos_y = srs.origin[1]

        set_one = numpy.array([
            [pos_x, pos_y], [pos_x, pos_y - 100], [pos_x, pos_y - 200]])
        set_two = numpy.array([
            [pos_x + 100, pos_y], [pos_x + 100, pos_y - 100],
            [pos_x + 100, pos_y - 200]])

        result_dist, result_id = wave_energy.calculate_distance(
            set_one, set_two)

        expected_result_dist = [100, 100, 100]
        expected_result_id = [0, 1, 2]

        for res, exp_res in zip(result_dist, expected_result_dist):
            self.assertEqual(res, exp_res)
        for res, exp_res in zip(result_id, expected_result_id):
            self.assertEqual(res, exp_res)

    def test_clip_datasource_layer_polygons(self):
        """WaveEnergy: testing clipping polygons from polygons."""
        from natcap.invest.wave_energy import wave_energy

        aoi_path = os.path.join(REGRESSION_DATA, 'aoi_proj_to_extract.shp')
        extract_path = os.path.join(SAMPLE_DATA, 'WaveData',
                                    'Global_extract.shp')

        result_path = os.path.join(self.workspace_dir, 'aoi_proj_clipped.shp')
        wave_energy.clip_datasource_layer(aoi_path, extract_path, result_path)

        expected_path = os.path.join(REGRESSION_DATA, 'aoi_proj_clipped.shp')
        pygeoprocessing.testing.assert_vectors_equal(
            result_path, expected_path, 1e-6)

    def test_clip_datasource_layer_points(self):
        """WaveEnergy: testing clipping points from polygons."""
        from natcap.invest.wave_energy import wave_energy

        srs = sampledata.SRS_WILLAMETTE

        pos_x = srs.origin[0]
        pos_y = srs.origin[1]
        fields_pt = {'id': 'int', 'myattr': 'string'}
        attrs_one = [
            {'id': 1, 'myattr': 'hello'}, {'id': 2, 'myattr': 'bye'},
            {'id': 3, 'myattr': 'highbye'}]

        fields_poly = {'id': 'int'}
        attrs_poly = [{'id': 1}]
        # Create geometry for the points, which will get clipped
        geom_one = [
            Point(pos_x + 20, pos_y - 20), Point(pos_x + 40, pos_y - 20),
            Point(pos_x + 100, pos_y - 20)]
        # Create geometry for the polygons, which will be used to clip
        geom_two = [Polygon(
            [(pos_x, pos_y), (pos_x + 60, pos_y), (pos_x + 60, pos_y - 60),
             (pos_x, pos_y - 60), (pos_x, pos_y)])]

        shape_to_clip_uri = os.path.join(self.workspace_dir, 'shape_to_clip.shp')
        # Create the point shapefile
        shape_to_clip_uri = pygeoprocessing.testing.create_vector_on_disk(
            geom_one, srs.projection, fields_pt, attrs_one,
            vector_format='ESRI Shapefile', filename=shape_to_clip_uri)

        binding_shape_uri = os.path.join(self.workspace_dir, 'binding_shape.shp')
        # Create the polygon shapefile
        binding_shape_uri = pygeoprocessing.testing.create_vector_on_disk(
            geom_two, srs.projection, fields_poly, attrs_poly,
            vector_format='ESRI Shapefile', filename=binding_shape_uri)

        output_path = os.path.join(self.workspace_dir, 'vector.shp')
        # Call the function to test
        wave_energy.clip_datasource_layer(
            shape_to_clip_uri, binding_shape_uri, output_path)

        # Create the expected point shapefile
        fields_pt = {'id': 'int', 'myattr': 'string'}
        attrs_one = [{'id': 1, 'myattr': 'hello'}, {'id': 2, 'myattr': 'bye'}]
        geom_three = [Point(pos_x + 20, pos_y - 20),
                      Point(pos_x + 40, pos_y - 20)]
        # Need to save the expected shapefile in a sub folder since it must
        # have the same layer name / filename as what it will be compared
        # against.
        if not os.path.isdir(os.path.join(self.workspace_dir, 'exp_vector')):
            os.mkdir(os.path.join(self.workspace_dir, 'exp_vector'))

        expected_uri = os.path.join(self.workspace_dir, 'exp_vector', 'vector.shp')
        expected_shape = pygeoprocessing.testing.create_vector_on_disk(
            geom_three, srs.projection, fields_pt, attrs_one,
            vector_format='ESRI Shapefile', filename=expected_uri)

        pygeoprocessing.testing.assert_vectors_equal(
            output_path, expected_shape, 1e-6)

    def test_clip_datasouce_layer_no_intersection(self):
        """WaveEnergy: testing 'clip_datasource_layer' w/ no intersection."""
        from natcap.invest.wave_energy import wave_energy

        srs = sampledata.SRS_WILLAMETTE

        pos_x = srs.origin[0]
        pos_y = srs.origin[1]
        fields_pt = {'id': 'int', 'myattr': 'string'}
        attrs_one = [{'id': 1, 'myattr': 'hello'}]

        fields_poly = {'id': 'int'}
        attrs_poly = [{'id': 1}]
        # Create geometry for the points, which will get clipped
        geom_one = [
            Point(pos_x + 220, pos_y - 220)]
        # Create geometry for the polygons, which will be used to clip
        geom_two = [Polygon(
            [(pos_x, pos_y), (pos_x + 60, pos_y), (pos_x + 60, pos_y - 60),
             (pos_x, pos_y - 60), (pos_x, pos_y)])]

        shape_to_clip_uri = os.path.join(self.workspace_dir, 'shape_to_clip.shp')
        # Create the point shapefile
        shape_to_clip_uri = pygeoprocessing.testing.create_vector_on_disk(
            geom_one, srs.projection, fields_pt, attrs_one,
            vector_format='ESRI Shapefile', filename=shape_to_clip_uri)

        binding_shape_uri = os.path.join(self.workspace_dir, 'binding_shape.shp')
        # Create the polygon shapefile
        binding_shape_uri = pygeoprocessing.testing.create_vector_on_disk(
            geom_two, srs.projection, fields_poly, attrs_poly,
            vector_format='ESRI Shapefile', filename=binding_shape_uri)

        output_path = os.path.join(self.workspace_dir, 'vector.shp')
        # Call the function to test
        self.assertRaises(
            wave_energy.IntersectionError, wave_energy.clip_datasource_layer,
            shape_to_clip_uri, binding_shape_uri, output_path)

    def test_create_attribute_csv_table(self):
        """WaveEnergy: testing 'create_attribute_csv_table' function."""
        from natcap.invest.wave_energy import wave_energy

        table_uri = os.path.join(self.workspace_dir, 'att_csv_file.csv')
        fields = ['id', 'height', 'length']
        data = {1: {'id': 1, 'height': 10, 'length': 15},
                0: {'id': 0, 'height': 10, 'length': 15},
                2: {'id': 2, 'height': 10, 'length': 15}}

        wave_energy.create_attribute_csv_table(table_uri, fields, data)

        exp_rows = [{'id': '0', 'height': '10', 'length': '15'},
                    {'id': '1', 'height': '10', 'length': '15'},
                    {'id': '2', 'height': '10', 'length': '15'}]

        result_file = open(table_uri, 'rU')

        csv_reader = csv.DictReader(result_file)
        for row, exp_row in zip(csv_reader, exp_rows):
            self.assertDictEqual(row, exp_row)

        result_file.close()

    def test_load_binary_wave_data(self):
        """WaveEnergy: testing 'load_binary_wave_data' function."""
        from natcap.invest.wave_energy import wave_energy

        wave_file_uri = os.path.join(REGRESSION_DATA, 'example_ww3_binary.bin')

        result = wave_energy.load_binary_wave_data(wave_file_uri)

        exp_res = {'periods': numpy.array(
            [.375, 1, 1.5, 2.0], dtype=numpy.float32),
                   'heights': numpy.array([.375, 1], dtype=numpy.float32),
                   'bin_matrix': {
                       (102, 370): numpy.array(
                           [[0, 0, 0, 0], [0, 9, 3, 30]], dtype=numpy.float32),
                       (102, 371): numpy.array(
                           [[0, 0, 0, 0], [0, 0, 3, 27]], dtype=numpy.float32)}
                  }

        for key in ['periods', 'heights']:
            numpy.testing.assert_array_equal(result[key], exp_res[key])

        for key in [(102, 370), (102, 371)]:
            numpy.testing.assert_array_equal(
                result['bin_matrix'][key], exp_res['bin_matrix'][key])


class WaveEnergyRegressionTests(unittest.TestCase):
    """Regression tests for the Wave Energy module."""

    def setUp(self):
        """Overriding setUp function to create temp workspace directory."""
        # this lets us delete the workspace after its done no matter the
        # the rest result
        self.workspace_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Overriding tearDown function to remove temporary directory."""
        shutil.rmtree(self.workspace_dir)

    @staticmethod
    def generate_base_args(workspace_dir):
        """Generate an args list that is consistent across regression tests."""
        args = {
            'workspace_dir': workspace_dir,
            'wave_base_data_uri': os.path.join(SAMPLE_DATA, 'WaveData'),
            'analysis_area_uri': 'West Coast of North America and Hawaii',
            'machine_perf_uri': os.path.join(
                SAMPLE_DATA, 'Machine_Pelamis_Performance.csv'),
            'machine_param_uri': os.path.join(
                SAMPLE_DATA, 'Machine_Pelamis_Parameter.csv'),
            'dem_uri': os.path.join(SAMPLE_DATA, 'resampled_global_dem.tif')
        }
        return args

    def test_valuation(self):
        """WaveEnergy: testing valuation component."""
        from natcap.invest.wave_energy import wave_energy

        args = WaveEnergyRegressionTests.generate_base_args(self.workspace_dir)
        args['aoi_uri'] = os.path.join(SAMPLE_DATA, 'AOI_WCVI.shp')
        args['valuation_container'] = True
        args['land_gridPts_uri'] = os.path.join(SAMPLE_DATA,
                                                'LandGridPts_WCVI.csv')
        args['machine_econ_uri'] = os.path.join(SAMPLE_DATA,
                                                'Machine_Pelamis_Economic.csv')
        args['number_of_machines'] = 28

        # Testing if intermediate/output were overwritten
        _make_dummy_files(args['workspace_dir'])

        wave_energy.execute(args)

        raster_results = [
            'wp_rc.tif', 'wp_kw.tif', 'capwe_rc.tif', 'capwe_mwh.tif',
            'npv_rc.tif', 'npv_usd.tif']

        for raster_path in raster_results:
            pygeoprocessing.testing.assert_rasters_equal(
                os.path.join(args['workspace_dir'], 'output', raster_path),
                os.path.join(REGRESSION_DATA, 'valuation', raster_path),
                1e-6)

        vector_results = ['GridPts_prj.shp', 'LandPts_prj.shp']

        for vector_path in vector_results:
            WaveEnergyRegressionTests._assert_point_vectors_equal(
                os.path.join(args['workspace_dir'], 'output', vector_path),
                os.path.join(REGRESSION_DATA, 'valuation', vector_path))

        table_results = ['capwe_rc.csv', 'wp_rc.csv', 'npv_rc.csv']

        for table_path in table_results:
            pygeoprocessing.testing.assert_csv_equal(
                os.path.join(args['workspace_dir'], 'output', table_path),
                os.path.join(REGRESSION_DATA, 'valuation', table_path))

    def test_aoi_no_val(self):
        """WaveEnergy: testing Biophysical component w AOI but w/o valuation."""
        from natcap.invest.wave_energy import wave_energy

        args = WaveEnergyRegressionTests.generate_base_args(self.workspace_dir)
        args['aoi_uri'] = os.path.join(SAMPLE_DATA, 'AOI_WCVI.shp')

        wave_energy.execute(args)

        raster_results = [
            'wp_rc.tif', 'wp_kw.tif', 'capwe_rc.tif', 'capwe_mwh.tif']

        for raster_path in raster_results:
            pygeoprocessing.testing.assert_rasters_equal(
                os.path.join(args['workspace_dir'], 'output', raster_path),
                os.path.join(REGRESSION_DATA, 'aoi', raster_path),
                1e-6)

        table_results = ['capwe_rc.csv', 'wp_rc.csv']

        for table_path in table_results:
            pygeoprocessing.testing.assert_csv_equal(
                os.path.join(args['workspace_dir'], 'output', table_path),
                os.path.join(REGRESSION_DATA, 'aoi', table_path),
                1e-6)

    def test_no_aoi_or_val(self):
        """WaveEnergy: testing Biophysical component w/o AOI or valuation."""
        from natcap.invest.wave_energy import wave_energy

        args = WaveEnergyRegressionTests.generate_base_args(self.workspace_dir)

        wave_energy.execute(args)

        raster_results = [
            'wp_rc.tif', 'wp_kw.tif', 'capwe_rc.tif', 'capwe_mwh.tif']

        for raster_path in raster_results:
            pygeoprocessing.testing.assert_rasters_equal(
                os.path.join(args['workspace_dir'], 'output', raster_path),
                os.path.join(REGRESSION_DATA, 'noaoi', raster_path),
                1e-6)

        table_results = ['capwe_rc.csv', 'wp_rc.csv']

        for table_path in table_results:
            pygeoprocessing.testing.assert_csv_equal(
                os.path.join(args['workspace_dir'], 'output', table_path),
                os.path.join(REGRESSION_DATA, 'noaoi', table_path),
                1e-6)

    def test_valuation_suffix(self):
        """WaveEnergy: testing suffix through Valuation."""
        from natcap.invest.wave_energy import wave_energy

        args = WaveEnergyRegressionTests.generate_base_args(self.workspace_dir)
        args['aoi_uri'] = os.path.join(SAMPLE_DATA, 'AOI_WCVI.shp')
        args['valuation_container'] = True
        args['land_gridPts_uri'] = os.path.join(SAMPLE_DATA, 'LandGridPts_WCVI.csv')
        args['machine_econ_uri'] = os.path.join(SAMPLE_DATA, 'Machine_Pelamis_Economic.csv')
        args['number_of_machines'] = 28
        args['suffix'] = 'val'

        wave_energy.execute(args)

        raster_results = [
            'wp_rc_val.tif', 'wp_kw_val.tif', 'capwe_rc_val.tif',
            'capwe_mwh_val.tif', 'npv_rc_val.tif', 'npv_usd_val.tif']

        for raster_path in raster_results:
            self.assertTrue(os.path.exists(
                os.path.join(args['workspace_dir'], 'output', raster_path)))

        vector_results = ['GridPts_prj_val.shp', 'LandPts_prj_val.shp']

        for vector_path in vector_results:
            self.assertTrue(os.path.exists(
                os.path.join(args['workspace_dir'], 'output', vector_path)))

        table_results = ['capwe_rc_val.csv', 'wp_rc_val.csv', 'npv_rc_val.csv']

        for table_path in table_results:
            self.assertTrue(os.path.exists(
                os.path.join(args['workspace_dir'], 'output', table_path)))

    @staticmethod
    def _assert_point_vectors_equal(a_uri, b_uri):
        """Assert that two point geometries in the vectors are equal.

        Parameters:
            a_uri (str): a URI to an OGR vector.
            b_uri (str): a URI to an OGR vector.

        Returns:
            None.

        Raises:
            AssertionError when the two point geometries are not equal up to
            desired precision (default is 6).
        """
        a_shape = ogr.Open(a_uri)
        a_layer = a_shape.GetLayer(0)
        a_feat = a_layer.GetNextFeature()

        b_shape = ogr.Open(b_uri)
        b_layer = b_shape.GetLayer(0)
        b_feat = b_layer.GetNextFeature()

        while a_feat is not None:
            # Get coordinates from point geometry and store them in a list
            a_geom = a_feat.GetGeometryRef()
            a_geom_list = re.findall(r'\d+\.\d+', a_geom.ExportToWkt())
            a_geom_list = [float(x) for x in a_geom_list]

            b_geom = b_feat.GetGeometryRef()
            b_geom_list = re.findall(r'\d+\.\d+', b_geom.ExportToWkt())
            b_geom_list = [float(x) for x in b_geom_list]

            try:
                numpy.testing.assert_array_almost_equal(a_geom_list, b_geom_list)
            except AssertionError:
                a_feature_fid = a_feat.GetFID()
                b_feature_fid = b_feat.GetFID()
                raise AssertionError(
                    'Geometries are not equal in feature %s, '
                    'regression feature %s in layer 0' % (
                        a_feature_fid, b_feature_fid))
            a_feat = None
            b_feat = None
            a_feat = a_layer.GetNextFeature()
            b_feat = b_layer.GetNextFeature()

        a_shape = None
        b_shape = None
