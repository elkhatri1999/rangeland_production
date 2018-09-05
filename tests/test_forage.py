"""InVEST forage model tests."""

import unittest
import tempfile
import shutil
import os
import sys

import numpy
from osgeo import osr
from osgeo import gdal

import pygeoprocessing

SAMPLE_DATA = "C:/Users/ginge/Documents/NatCap/sample_inputs"
REGRESSION_DATA = "C:/Users/ginge/Documents/NatCap/regression_test_data"

_TARGET_NODATA = -1.0
_IC_NODATA = numpy.finfo('float32').min

numpy.random.seed(100)


def create_random_raster(target_path, lower_bound, upper_bound):
    """Create a small raster of random floats.

    The raster will have 10 rows and 10 columns and will be in the
    unprojected coordinate system WGS 1984. The values in the raster
    will be between `lower_bound` (included) and `upper_bound`
    (excluded).

    Parameters:
        target_path (string): path to result raster
        lower_bound (float): lower limit of range of random values
            (included)
        upper_bound (float): upper limit of range of random values
            (excluded)

    Returns:
        None
    """
    geotransform = [0, 1, 0, 44.5, 0, 1]
    n_cols = 10
    n_rows = 10
    n_bands = 1
    datatype = gdal.GDT_Float32
    projection = osr.SpatialReference()
    projection.SetWellKnownGeogCS('WGS84')
    driver = gdal.GetDriverByName('GTiff')
    target_raster = driver.Create(
        target_path.encode('utf-8'), n_cols, n_rows, n_bands,
        datatype)
    target_raster.SetProjection(projection.ExportToWkt())
    target_raster.SetGeoTransform(geotransform)
    target_band = target_raster.GetRasterBand(1)
    target_band.SetNoDataValue(_TARGET_NODATA)

    random_array = numpy.random.uniform(
        lower_bound, upper_bound, (n_rows, n_cols))
    target_band.WriteArray(random_array)
    target_raster = None


def create_complementary_raster(
        raster1_path, raster2_path, result_raster_path):
    """Create a raster to sum inputs to 1.

    The sum of the two input rasters and the result raster will be
    1.

    Parameters:
        raster1_path (string): path to raster of floast between 0 and 1
        raster2_path (string): path to raster of floast between 0 and 1
        result_raster_path (string): path to result raster

    Modifies:
        the raster indicated by `result_raster_path

    Returns:
        None
    """
    def complement_op(input1, input2):
        """Generate an array that adds to 1 with input1 and input2."""
        result_raster = numpy.empty(input1.shape, dtype=numpy.float32)
        result_raster[:] = _TARGET_NODATA
        valid_mask = (
            (input1 != _TARGET_NODATA)
            & (input2 != _TARGET_NODATA))

        result_raster[valid_mask] = (
            1. - (input1[valid_mask] + input2[valid_mask]))
        return result_raster

    pygeoprocessing.raster_calculator(
        [(path, 1) for path in [raster1_path, raster2_path]],
        complement_op, result_raster_path, gdal.GDT_Float32,
        _TARGET_NODATA)


def insert_nodata_values_into_raster(target_raster, nodata_value):
    """Insert nodata at arbitrary locations in `target_raster`."""
    def insert_op(prior_copy):
        modified_copy = prior_copy
        n_vals = numpy.random.randint(
            0, (prior_copy.shape[0] * prior_copy.shape[1]))
        insertions = 0
        while insertions < n_vals:
            row = numpy.random.randint(0, prior_copy.shape[0])
            col = numpy.random.randint(0, prior_copy.shape[1])
            modified_copy[row, col] = nodata_value
            insertions += 1
        return modified_copy

    prior_copy = os.path.join(
        os.path.dirname(target_raster), 'prior_to_insert_nodata.tif')
    shutil.copyfile(target_raster, prior_copy)

    pygeoprocessing.raster_calculator(
        [(prior_copy, 1)],
        insert_op, target_raster,
        gdal.GDT_Float32, nodata_value)

    os.remove(prior_copy)


def create_constant_raster(target_path, fill_value):
    """Create a single-pixel raster with value `fill_value`."""
    geotransform = [0, 1, 0, 44.5, 0, 1]
    n_cols = 1
    n_rows = 1
    n_bands = 1
    datatype = gdal.GDT_Float32
    projection = osr.SpatialReference()
    projection.SetWellKnownGeogCS('WGS84')
    driver = gdal.GetDriverByName('GTiff')
    target_raster = driver.Create(
        target_path.encode('utf-8'), n_cols, n_rows, n_bands,
        datatype)
    target_raster.SetProjection(projection.ExportToWkt())
    target_raster.SetGeoTransform(geotransform)
    target_band = target_raster.GetRasterBand(1)
    target_band.SetNoDataValue(_TARGET_NODATA)
    target_band.Fill(fill_value)
    target_raster = None


def insert_nodata_values_into_array(target_array, nodata_value):
    """Insert nodata at arbitrary locations in `target_array`."""
    modified_array = target_array
    n_vals = numpy.random.randint(
        0, (target_array.shape[0] * target_array.shape[1]))
    insertions = 0
    while insertions < n_vals:
        row = numpy.random.randint(0, target_array.shape[0])
        col = numpy.random.randint(0, target_array.shape[1])
        modified_array[row, col] = nodata_value
        insertions += 1
    return modified_array


class foragetests(unittest.TestCase):
    """Regression tests for InVEST forage model."""

    def setUp(self):
        """Create temporary workspace directory."""
        self.workspace_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up remaining files."""
        shutil.rmtree(self.workspace_dir)

    @staticmethod
    def generate_base_args(workspace_dir):
        """Generate a base sample args dict for forage model."""
        args = {
            'workspace_dir': workspace_dir,
            'results_suffix': "",
            'starting_month': 1,
            'starting_year': 2016,
            'n_months': 22,
            'aoi_path': os.path.join(
                SAMPLE_DATA, 'Manlai_soum_WGS84.shp'),
            'bulk_density_path': os.path.join(
                SAMPLE_DATA, 'soil', 'bulkd.tif'),
            'ph_path': os.path.join(
                SAMPLE_DATA, 'soil', 'phihox_sl3.tif'),
            'clay_proportion_path': os.path.join(
                SAMPLE_DATA, 'soil', 'clay.tif'),
            'silt_proportion_path': os.path.join(
                SAMPLE_DATA, 'soil', 'silt.tif'),
            'sand_proportion_path': os.path.join(
                SAMPLE_DATA, 'soil', 'sand.tif'),
            'monthly_precip_path_pattern': os.path.join(
                SAMPLE_DATA, 'CHIRPS_div_by_10',
                'chirps-v2.0.<year>.<month>.tif'),
            'min_temp_path_pattern': os.path.join(
                SAMPLE_DATA, 'temp', 'wc2.0_30s_tmin_<month>.tif'),
            'max_temp_path_pattern': os.path.join(
                SAMPLE_DATA, 'temp', 'wc2.0_30s_tmax_<month>.tif'),
            'site_param_table': os.path.join(
                SAMPLE_DATA, 'site_parameters.csv'),
            'site_param_spatial_index_path': os.path.join(
                SAMPLE_DATA, 'site_index.tif'),
            'veg_trait_path': os.path.join(SAMPLE_DATA, 'pft_trait.csv'),
            'veg_spatial_composition_path_pattern': os.path.join(
                SAMPLE_DATA, 'pft<PFT>.tif'),
            'animal_trait_path': os.path.join(
                SAMPLE_DATA, 'animal_trait_table.csv'),
            'animal_mgmt_layer_path': os.path.join(
                SAMPLE_DATA,
                'sheep_units_density_2016_monitoring_area_WGS84.shp'),
            'initial_conditions_dir': os.path.join(
                SAMPLE_DATA, 'initialization_data'),
        }
        return args

    def assert_all_values_in_raster_within_range(
            self, raster_to_test, minimum_acceptable_value,
            maximum_acceptable_value, nodata_value):
        """Test that `raster_to_test` contains values within acceptable range.

        The values within `raster_to_test` that are not null must be
        greater than or equal to `minimum_acceptable_value` and
        less than or equal to `maximum_acceptable_value`.

        Raises:
            AssertionError if values are outside acceptable range

        Returns:
            None
        """
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                raster_to_test):
            if len(raster_block[raster_block != nodata_value]) == 0:
                continue
            min_val = numpy.amin(
                raster_block[raster_block != nodata_value])
            self.assertGreaterEqual(
                min_val, minimum_acceptable_value,
                msg="Raster contains values smaller than acceptable "
                + "minimum: {}, {}".format(raster_to_test, min_val))
            max_val = numpy.amax(
                raster_block[raster_block != nodata_value])
            self.assertLessEqual(
                max_val, maximum_acceptable_value,
                msg="Raster contains values larger than acceptable "
                + "maximum: {}, {}".format(raster_to_test, max_val))

    def assert_all_values_in_array_within_range(
            self, array_to_test, minimum_acceptable_value,
            maximum_acceptable_value, nodata_value):
        """Test that `array_to_test` contains values within acceptable range.

        The values within `array_to_test` that are not null must be
        greater than or equal to `minimum_acceptable_value` and
        less than or equal to `maximum_acceptable_value`.

        Raises:
            AssertionError if values are outside acceptable range

        Returns:
            None
        """
        if len(array_to_test[array_to_test != nodata_value]) == 0:
            return
        min_val = numpy.amin(
            array_to_test[array_to_test != nodata_value])
        self.assertGreaterEqual(
            min_val, minimum_acceptable_value,
            msg="Array contains values smaller than acceptable minimum")
        max_val = numpy.amax(
            array_to_test[array_to_test != nodata_value])
        self.assertLessEqual(
            max_val, maximum_acceptable_value,
            msg="Array contains values larger than acceptable maximum")

    @unittest.skip("did not run the whole model, running unit tests only")
    def test_model_runs(self):
        """Launch forage model, ensure it runs!."""
        from natcap.invest import forage

        if not os.path.exists(SAMPLE_DATA):
            self.fail(
                "Sample input directory not found at %s" % SAMPLE_DATA)

        args = foragetests.generate_base_args(self.workspace_dir)
        forage.execute(args)

    def test_shortwave_radiation(self):
        """Test calculation of shortwave radiation outside the atmosphere.

        Use one set of inputs, including a raster with known latitude, to test
        the function `_shortwave radiation` against a result calculated by
        hand.

        Raises:
            AssertionError if the raster created by `_shortwave_radiation`
                contains more than one unique value
            AssertionError if the value returned by `_shortwave_radiation' is
                not within 0.01 of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage
        fill_value = 0
        template_raster = os.path.join(
            self.workspace_dir, 'template_raster.tif')

        create_constant_raster(template_raster, fill_value)

        month = 5
        shwave_path = os.path.join(self.workspace_dir, 'shwave.tif')
        forage._shortwave_radiation(template_raster, month, shwave_path)

        # assert the value in the raster `shwave_path` is equal to value
        # calculated by hand
        result_set = set()
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                shwave_path):
            result_set.update(numpy.unique(raster_block))
        self.assertEqual(
            len(result_set), 1,
            msg="One unique value expected in shortwave radiation raster")
        test_result = list(result_set)[0]
        self.assertAlmostEqual(
            test_result, 990.7401, delta=0.01,
            msg="Test result does not match expected value")

    def test_calc_ompc(self):
        """Test the function `_calc_ompc` against value calculated by hand.

        Use one set of inputs to test the estimation of total organic
        matter against a result calculated by hand.

        Raises:
            AssertionError if the raster created by `_calc_ompc`
                contains more than one unique value
            AssertionError if the value returned by `_calc_ompc' is
                not within 0.0001 of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        som1c_2_path = os.path.join(self.workspace_dir, 'som1c_2.tif')
        som2c_2_path = os.path.join(self.workspace_dir, 'som2c_2.tif')
        som3c_path = os.path.join(self.workspace_dir, 'som3c.tif')
        bulk_d_path = os.path.join(self.workspace_dir, 'bulkd.tif')
        edepth_path = os.path.join(self.workspace_dir, 'edepth.tif')

        create_constant_raster(som1c_2_path, 42.109)
        create_constant_raster(som2c_2_path, 959.1091)
        create_constant_raster(som3c_path, 588.0574)
        create_constant_raster(bulk_d_path, 1.5)
        create_constant_raster(edepth_path, 0.2)

        ompc_path = os.path.join(self.workspace_dir, 'ompc.tif')

        forage._calc_ompc(
            som1c_2_path, som2c_2_path, som3c_path, bulk_d_path, edepth_path,
            ompc_path)

        # assert the value in the raster `ompc_path` is equal to value
        # calculated by hand
        result_set = set()
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                ompc_path):
            result_set.update(numpy.unique(raster_block))
        self.assertEqual(
            len(result_set), 1,
            msg="One unique value expected in organic matter raster")
        test_result = list(result_set)[0]
        self.assertAlmostEqual(
            test_result, 0.913304, delta=0.0001,
            msg="Test result does not match expected value")

    def test_calc_afiel(self):
        """Test the function `_calc_afiel` against value calculated by hand.

        Use one set of inputs to test the estimation of field capacity against
        a result calculated by hand.

        Raises:
            AssertionError if the raster created by `_calc_afiel`
                contains more than one unique value
            AssertionError if the value returned by `_calc_afiel' is
                not within 0.0001 of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        sand_path = os.path.join(self.workspace_dir, 'sand.tif')
        silt_path = os.path.join(self.workspace_dir, 'silt.tif')
        clay_path = os.path.join(self.workspace_dir, 'clay.tif')
        ompc_path = os.path.join(self.workspace_dir, 'ompc.tif')
        bulkd_path = os.path.join(self.workspace_dir, 'bulkd.tif')

        create_constant_raster(sand_path, 0.39)
        create_constant_raster(silt_path, 0.41)
        create_constant_raster(clay_path, 0.2)
        create_constant_raster(ompc_path, 0.913304)
        create_constant_raster(bulkd_path, 1.5)

        afiel_path = os.path.join(self.workspace_dir, 'afiel.tif')

        forage._calc_afiel(
            sand_path, silt_path, clay_path, ompc_path, bulkd_path, afiel_path)

        # assert the value in the raster `afiel_path` is equal to value
        # calculated by hand
        result_set = set()
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                afiel_path):
            result_set.update(numpy.unique(raster_block))
        self.assertEqual(
            len(result_set), 1,
            msg="One unique value expected in field capacity raster")
        test_result = list(result_set)[0]
        self.assertAlmostEqual(
            test_result, 0.30895, delta=0.0001,
            msg="Test result does not match expected value")

    def test_calc_awilt(self):
        """Test the function `_calc_awilt` against value calculated by hand.

        Use one set of inputs to test the estimation of wilting point against
        a result calculated by hand.

        Raises:
            AssertionError if the raster created by `_calc_awilt`
                contains more than one unique value
            AssertionError if the value returned by `_calc_awilt' is
                not within 0.0001 of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        sand_path = os.path.join(self.workspace_dir, 'sand.tif')
        silt_path = os.path.join(self.workspace_dir, 'silt.tif')
        clay_path = os.path.join(self.workspace_dir, 'clay.tif')
        ompc_path = os.path.join(self.workspace_dir, 'ompc.tif')
        bulkd_path = os.path.join(self.workspace_dir, 'bulkd.tif')

        create_constant_raster(sand_path, 0.39)
        create_constant_raster(silt_path, 0.41)
        create_constant_raster(clay_path, 0.2)
        create_constant_raster(ompc_path, 0.913304)
        create_constant_raster(bulkd_path, 1.5)

        awilt_path = os.path.join(self.workspace_dir, 'awilt.tif')

        forage._calc_awilt(
            sand_path, silt_path, clay_path, ompc_path, bulkd_path, awilt_path)

        # assert the value in the raster `awilt_path` is equal to value
        # calculated by hand
        result_set = set()
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                awilt_path):
            result_set.update(numpy.unique(raster_block))
        self.assertEqual(
            len(result_set), 1,
            msg="One unique value expected in wilting point raster")
        test_result = list(result_set)[0]
        self.assertAlmostEqual(
            test_result, 0.201988, delta=0.0001,
            msg="Test result does not match expected value")

    def test_afiel_awilt(self):
        """Test that values calculated by `_afiel_awilt` are reasonable.

        Use the function `_afiel_awilt` to calculate field capacity and wilting
        point from randomly generated inputs. Test that calculated field
        capacity and calculated wilting point are in the range [0.01, 0.9].
        Introduce nodata values into the input rasters and test that calculated
        field capacity and wilting point remain in the range [0.01, 0.9].
        Test the function with known values against results calculated by hand.

        Raises:
            AssertionError if a result from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if a result from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        site_param_table = {1: {'edepth': 0.2}}
        pp_reg = {
            'afiel_1_path': os.path.join(self.workspace_dir, 'afiel_1.tif'),
            'afiel_2_path': os.path.join(self.workspace_dir, 'afiel_2.tif'),
            'afiel_3_path': os.path.join(self.workspace_dir, 'afiel_3.tif'),
            'afiel_4_path': os.path.join(self.workspace_dir, 'afiel_4.tif'),
            'afiel_5_path': os.path.join(self.workspace_dir, 'afiel_5.tif'),
            'afiel_6_path': os.path.join(self.workspace_dir, 'afiel_6.tif'),
            'afiel_7_path': os.path.join(self.workspace_dir, 'afiel_7.tif'),
            'afiel_8_path': os.path.join(self.workspace_dir, 'afiel_8.tif'),
            'afiel_9_path': os.path.join(self.workspace_dir, 'afiel_9.tif'),
            'awilt_1_path': os.path.join(self.workspace_dir, 'awilt_1.tif'),
            'awilt_2_path': os.path.join(self.workspace_dir, 'awilt_2.tif'),
            'awilt_3_path': os.path.join(self.workspace_dir, 'awilt_3.tif'),
            'awilt_4_path': os.path.join(self.workspace_dir, 'awilt_4.tif'),
            'awilt_5_path': os.path.join(self.workspace_dir, 'awilt_5.tif'),
            'awilt_6_path': os.path.join(self.workspace_dir, 'awilt_6.tif'),
            'awilt_7_path': os.path.join(self.workspace_dir, 'awilt_7.tif'),
            'awilt_8_path': os.path.join(self.workspace_dir, 'awilt_8.tif'),
            'awilt_9_path': os.path.join(self.workspace_dir, 'awilt_9.tif')
            }

        site_index_path = os.path.join(self.workspace_dir, 'site_index.tif')
        som1c_2_path = os.path.join(self.workspace_dir, 'som1c_2.tif')
        som2c_2_path = os.path.join(self.workspace_dir, 'som2c_2.tif')
        som3c_path = os.path.join(self.workspace_dir, 'som3c.tif')
        sand_path = os.path.join(self.workspace_dir, 'sand.tif')
        silt_path = os.path.join(self.workspace_dir, 'silt.tif')
        clay_path = os.path.join(self.workspace_dir, 'clay.tif')
        bulk_d_path = os.path.join(self.workspace_dir, 'bulkd.tif')

        create_random_raster(site_index_path, 1, 1)
        create_random_raster(som1c_2_path, 35., 55.)
        create_random_raster(som2c_2_path, 500., 1500.)
        create_random_raster(som3c_path, 300., 600.)
        create_random_raster(sand_path, 0., 0.5)
        create_random_raster(silt_path, 0., 0.5)
        create_random_raster(bulk_d_path, 0.8, 1.8)
        create_complementary_raster(sand_path, silt_path, clay_path)

        minimum_acceptable_value = 0.01
        maximum_acceptable_value = 0.7
        nodata_value = _TARGET_NODATA

        forage._afiel_awilt(
            site_index_path, site_param_table, som1c_2_path,
            som2c_2_path, som3c_path, sand_path, silt_path, clay_path,
            bulk_d_path, pp_reg)

        for key, path in pp_reg.iteritems():
            self.assert_all_values_in_raster_within_range(
                path, minimum_acceptable_value,
                maximum_acceptable_value, nodata_value)

        for input_raster in [
                site_index_path, som1c_2_path, som2c_2_path, som3c_path,
                sand_path, silt_path, clay_path, bulk_d_path]:
            insert_nodata_values_into_raster(input_raster, _TARGET_NODATA)
            forage._afiel_awilt(
                site_index_path, site_param_table, som1c_2_path,
                som2c_2_path, som3c_path, sand_path, silt_path, clay_path,
                bulk_d_path, pp_reg)
            for key, path in pp_reg.iteritems():
                self.assert_all_values_in_raster_within_range(
                    path, minimum_acceptable_value,
                    maximum_acceptable_value, nodata_value)

        # known inputs
        site_param_table = {1: {'edepth': 0.111}}
        create_random_raster(som1c_2_path, 40, 40)
        create_random_raster(som2c_2_path, 744, 744)
        create_random_raster(som3c_path, 444, 444)
        create_random_raster(sand_path, 0.4, 0.4)
        create_random_raster(silt_path, 0.1, 0.1)
        create_random_raster(bulk_d_path, 0.81, 0.81)
        create_complementary_raster(sand_path, silt_path, clay_path)

        known_afiel_1 = 0.47285
        known_awilt_1 = 0.32424
        known_afiel_4 = 0.47085
        known_awilt_6 = 0.32132
        tolerance = 0.0001

        forage._afiel_awilt(
            site_index_path, site_param_table, som1c_2_path,
            som2c_2_path, som3c_path, sand_path, silt_path, clay_path,
            bulk_d_path, pp_reg)

        self.assert_all_values_in_raster_within_range(
            pp_reg['afiel_1_path'], known_afiel_1 - tolerance,
            known_afiel_1 + tolerance, nodata_value)
        self.assert_all_values_in_raster_within_range(
            pp_reg['awilt_1_path'], known_awilt_1 - tolerance,
            known_awilt_1 + tolerance, nodata_value)
        self.assert_all_values_in_raster_within_range(
            pp_reg['afiel_4_path'], known_afiel_4 - tolerance,
            known_afiel_4 + tolerance, nodata_value)
        self.assert_all_values_in_raster_within_range(
            pp_reg['awilt_6_path'], known_awilt_6 - tolerance,
            known_awilt_6 + tolerance, nodata_value)

    def test_persistent_params(self):
        """Test that values calculated by `persistent_params` are reasonable.

        Use the function `persistent_params` to calculate wc, eftext, p1co2_2,
        fps1s3, and fps2s3 from randomly generated inputs. Test that each of
        the calculated quantities are within the range [0, 1].  Introduce
        nodata values into the inputs and test that calculated values
        remain inside the specified ranges. Test the function with known inputs
        against values calculated by hand.

        Raises:
            AssertionError if a result from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if a result from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        site_param_table = {
            1: {
                'peftxa': numpy.random.uniform(0.15, 0.35),
                'peftxb': numpy.random.uniform(0.65, 0.85),
                'p1co2a_2': numpy.random.uniform(0.1, 0.2),
                'p1co2b_2': numpy.random.uniform(0.58, 0.78),
                'ps1s3_1': numpy.random.uniform(0.58, 0.78),
                'ps1s3_2': numpy.random.uniform(0.02, 0.04),
                'ps2s3_1': numpy.random.uniform(0.58, 0.78),
                'ps2s3_2': numpy.random.uniform(0.001, 0.005),
                'omlech_1': numpy.random.uniform(0.01, 0.05),
                'omlech_2': numpy.random.uniform(0.06, 0.18)},
                }

        pp_reg = {
            'afiel_1_path': os.path.join(self.workspace_dir, 'afiel_1.tif'),
            'awilt_1_path': os.path.join(self.workspace_dir, 'awilt.tif'),
            'wc_path': os.path.join(self.workspace_dir, 'wc.tif'),
            'eftext_path': os.path.join(self.workspace_dir, 'eftext.tif'),
            'p1co2_2_path': os.path.join(self.workspace_dir, 'p1co2_2.tif'),
            'fps1s3_path': os.path.join(self.workspace_dir, 'fps1s3.tif'),
            'fps2s3_path': os.path.join(self.workspace_dir, 'fps2s3.tif'),
            'orglch_path': os.path.join(self.workspace_dir, 'orglch.tif'),
        }

        site_index_path = os.path.join(self.workspace_dir, 'site_index.tif')
        sand_path = os.path.join(self.workspace_dir, 'sand.tif')
        clay_path = os.path.join(self.workspace_dir, 'clay.tif')

        create_random_raster(site_index_path, 1, 1)
        create_random_raster(sand_path, 0., 0.5)
        create_random_raster(clay_path, 0., 0.5)
        create_random_raster(pp_reg['afiel_1_path'], 0.5, 0.9)
        create_random_raster(pp_reg['awilt_1_path'], 0.01, 0.49)

        acceptable_range_dict = {
            'wc_path': {
                'minimum_acceptable_value': 0.01,
                'maximum_acceptable_value': 0.89,
                'nodata_value': _TARGET_NODATA,
                },
            'eftext_path': {
                'minimum_acceptable_value': 0.15,
                'maximum_acceptable_value': 0.775,
                'nodata_value': _IC_NODATA,
                },
            'p1co2_2_path': {
                'minimum_acceptable_value': 0.1,
                'maximum_acceptable_value': 0.59,
                'nodata_value': _IC_NODATA,
                },
            'fps1s3_path': {
                'minimum_acceptable_value': 0.58,
                'maximum_acceptable_value': 0.8,
                'nodata_value': _IC_NODATA,
                },
            'fps2s3_path': {
                'minimum_acceptable_value': 0.58,
                'maximum_acceptable_value': 0.7825,
                'nodata_value': _IC_NODATA,
                },
            'orglch_path': {
                'minimum_acceptable_value': 0.01,
                'maximum_acceptable_value': 0.14,
                'nodata_value': _IC_NODATA,
                },
        }

        forage._persistent_params(
            site_index_path, site_param_table, sand_path, clay_path, pp_reg)

        for path, ranges in acceptable_range_dict.iteritems():
            self.assert_all_values_in_raster_within_range(
                pp_reg[path], ranges['minimum_acceptable_value'],
                ranges['maximum_acceptable_value'],
                ranges['nodata_value'])

        for input_raster in [
                site_index_path, sand_path, clay_path]:
            insert_nodata_values_into_raster(input_raster, _TARGET_NODATA)
            forage._persistent_params(
                site_index_path, site_param_table, sand_path, clay_path,
                pp_reg)

            for path, ranges in acceptable_range_dict.iteritems():
                self.assert_all_values_in_raster_within_range(
                    pp_reg[path], ranges['minimum_acceptable_value'],
                    ranges['maximum_acceptable_value'],
                    ranges['nodata_value'])

        # known inputs
        site_param_table[1]['peftxa'] = 0.2
        site_param_table[1]['peftxb'] = 0.7
        site_param_table[1]['p1co2a_2'] = 0.18
        site_param_table[1]['p1co2b_2'] = 0.65
        site_param_table[1]['ps1s3_1'] = 0.59
        site_param_table[1]['ps1s3_2'] = 0.03
        site_param_table[1]['ps2s3_1'] = 0.61
        site_param_table[1]['ps2s3_2'] = 0.0022
        site_param_table[1]['omlech_1'] = 0.022
        site_param_table[1]['omlech_2'] = 0.12

        create_random_raster(sand_path, 0.22, 0.22)
        create_random_raster(clay_path, 0.22, 0.22)
        create_random_raster(pp_reg['afiel_1_path'], 0.56, 0.56)
        create_random_raster(pp_reg['awilt_1_path'], 0.4, 0.4)

        known_value_dict = {
            'wc_path': {
                'value': 0.16,
                'nodata_value': _TARGET_NODATA,
                },
            'eftext_path': {
                'value': 0.354,
                'nodata_value': _IC_NODATA,
                },
            'p1co2_2_path': {
                'value': 0.323,
                'nodata_value': _IC_NODATA,
                },
            'fps1s3_path': {
                'value': 0.5966,
                'nodata_value': _IC_NODATA,
                },
            'fps2s3_path': {
                'value': 0.61048,
                'nodata_value': _IC_NODATA,
                },
            'orglch_path': {
                'value': 0.0484,
                'nodata_value': _IC_NODATA,
                },
        }
        tolerance = 0.0001

        forage._persistent_params(
            site_index_path, site_param_table, sand_path, clay_path,
            pp_reg)

        for path, values in known_value_dict.iteritems():
            self.assert_all_values_in_raster_within_range(
                pp_reg[path], values['value'] - tolerance,
                values['value'] + tolerance, values['nodata_value'])

    def test_aboveground_ratio(self):
        """Test that values calculated by `_aboveground_ratio` are valid.

        Use the function `_aboveground_ratio` to calculate the C/N or P
        ratio of decomposing aboveground material from random inputs. Test
        that the calculated ratio, agdrat, is within the range [1, 150].
        Introduce nodata values into the inputs and test that calculated
        agdrat remains inside the range [1, 150]. Calculate aboveground
        ratio from known inputs and compare to result calculated by hand.

        Raises:
            AssertionError if agdrat from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if agdrat from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        array_shape = (10, 10)

        tca = numpy.random.uniform(300, 700, array_shape)
        anps = numpy.random.uniform(1, numpy.amin(tca), array_shape)
        pcemic_1 = numpy.random.uniform(12, 20, array_shape)
        pcemic_2 = numpy.random.uniform(3, 11, array_shape)
        pcemic_3 = numpy.random.uniform(0.001, 0.1, array_shape)
        cemicb = (pcemic_2 - pcemic_1) / pcemic_3

        minimum_acceptable_agdrat = 2.285
        maximum_acceptable_agdrat = numpy.amax(pcemic_1)
        agdrat_nodata = _TARGET_NODATA

        agdrat = forage._aboveground_ratio(
            anps, tca, pcemic_1, pcemic_2, pcemic_3, cemicb)

        self.assert_all_values_in_array_within_range(
            agdrat, minimum_acceptable_agdrat, maximum_acceptable_agdrat,
            agdrat_nodata)

        for input_array in [anps, tca]:
            insert_nodata_values_into_array(input_array, _TARGET_NODATA)
            agdrat = forage._aboveground_ratio(
                anps, tca, pcemic_1, pcemic_2, pcemic_3, cemicb)

            self.assert_all_values_in_array_within_range(
                agdrat, minimum_acceptable_agdrat, maximum_acceptable_agdrat,
                agdrat_nodata)
        for input_array in [pcemic_1, pcemic_2, pcemic_3, cemicb]:
            insert_nodata_values_into_array(input_array, _IC_NODATA)
            agdrat = forage._aboveground_ratio(
                anps, tca, pcemic_1, pcemic_2, pcemic_3, cemicb)

            self.assert_all_values_in_array_within_range(
                agdrat, minimum_acceptable_agdrat, maximum_acceptable_agdrat,
                agdrat_nodata)

        # known inputs
        tca = numpy.full(array_shape, 413)
        anps = numpy.full(array_shape, 229)
        pcemic_1 = numpy.full(array_shape, 17.4)
        pcemic_2 = numpy.full(array_shape, 3.2)
        pcemic_3 = numpy.full(array_shape, 0.04)
        cemicb = numpy.full(array_shape, -20)

        known_agdrat = 3.2
        tolerance = 0.0001

        agdrat = forage._aboveground_ratio(
            anps, tca, pcemic_1, pcemic_2, pcemic_3, cemicb)

        self.assert_all_values_in_array_within_range(
            agdrat, known_agdrat - tolerance, known_agdrat + tolerance,
            agdrat_nodata)


    def test_structural_ratios(self):
        """Test that values calculated by `_structural_ratios` are valid.

        Use the function `_structural_ratios` to calculate rnewas_1_1,
        rnewas_1_2, rnewas_2_1, rnewas_2_2, rnewbs_1_2, and rnewbs_2_2 from
        randomly generated inputs. Test that each of the calculated quantities
        are within the range [1, 1500].  Introduce nodata values into the
        inputs and test that calculated values remain inside the specified
        ranges.

        Raises:
            AssertionError if rnewas_1_1 is outside the range [1, 1500]
            AssertionError if rnewas_1_2 is outside the range [1, 1500]
            AssertionError if rnewas_2_1 is outside the range [1, 1500]
            AssertionError if rnewas_2_2 is outside the range [1, 1500]
            AssertionError if rnewbs_1_1 is outside the range [1, 1500]
            AssertionError if rnewbs_2_2 is outside the range [1, 1500]
            AssertionError if rnewbs_2_1 is outside the range [1, 1500]
            AssertionError if rnewbs_2_2 is outside the range [1, 1500]

        Returns:
            None
        """
        from natcap.invest import forage

        site_param_table = {
            1: {
                'pcemic1_2_1': numpy.random.uniform(5, 12),
                'pcemic1_1_1': numpy.random.uniform(13, 23),
                'pcemic1_3_1': numpy.random.uniform(0.01, 0.05),
                'pcemic2_2_1': numpy.random.uniform(5, 12),
                'pcemic2_1_1': numpy.random.uniform(13, 23),
                'pcemic2_3_1': numpy.random.uniform(0.01, 0.05),
                'rad1p_1_1': numpy.random.uniform(8, 16),
                'rad1p_2_1': numpy.random.uniform(2, 5),
                'rad1p_3_1': numpy.random.uniform(2, 5),
                'varat1_1_1': numpy.random.uniform(12, 16),
                'varat22_1_1': numpy.random.uniform(15, 25),

                'pcemic1_2_2': numpy.random.uniform(90, 110),
                'pcemic1_1_2': numpy.random.uniform(170, 230),
                'pcemic1_3_2': numpy.random.uniform(0.0005, 0.0025),
                'pcemic2_2_2': numpy.random.uniform(75, 125),
                'pcemic2_1_2': numpy.random.uniform(200, 300),
                'pcemic2_3_2': numpy.random.uniform(0.0005, 0.0025),
                'rad1p_1_2': numpy.random.uniform(200, 300),
                'rad1p_2_2': numpy.random.uniform(3, 7),
                'rad1p_3_2': numpy.random.uniform(50, 150),
                'varat1_1_2': numpy.random.uniform(125, 175),
                'varat22_1_2': numpy.random.uniform(350, 450)},
                }

        sv_reg = {
            'strucc_1_path': os.path.join(self.workspace_dir, 'strucc_1.tif'),
            'struce_1_1_path': os.path.join(
                self.workspace_dir, 'struce_1_1.tif'),
            'struce_1_2_path': os.path.join(
                self.workspace_dir, 'struce_1_2.tif'),

        }
        site_index_path = os.path.join(self.workspace_dir, 'site_index.tif')
        create_random_raster(site_index_path, 1, 1)
        create_random_raster(sv_reg['strucc_1_path'], 120, 180)
        create_random_raster(sv_reg['struce_1_1_path'], 0.5, 1)
        create_random_raster(sv_reg['struce_1_2_path'], 0.1, 0.5)

        pp_reg = {
            'rnewas_1_1_path': os.path.join(
                self.workspace_dir, 'rnewas_1_1.tif'),
            'rnewas_1_2_path': os.path.join(
                self.workspace_dir, 'rnewas_1_2.tif'),
            'rnewas_2_1_path': os.path.join(
                self.workspace_dir, 'rnewas_2_1.tif'),
            'rnewas_2_2_path': os.path.join(
                self.workspace_dir, 'rnewas_2_2.tif'),
            'rnewbs_1_1_path': os.path.join(
                self.workspace_dir, 'rnewbs_1_1.tif'),
            'rnewbs_1_2_path': os.path.join(
                self.workspace_dir, 'rnewbs_1_2.tif'),
            'rnewbs_2_1_path': os.path.join(
                self.workspace_dir, 'rnewbs_2_1.tif'),
            'rnewbs_2_2_path': os.path.join(
                self.workspace_dir, 'rnewbs_2_2.tif'),
        }

        minimum_acceptable_value = 1
        maximum_acceptable_value = 1500
        nodata_value = _TARGET_NODATA

        forage._structural_ratios(
            site_index_path, site_param_table, sv_reg, pp_reg)

        for key, path in pp_reg.iteritems():
            self.assert_all_values_in_raster_within_range(
                path, minimum_acceptable_value,
                maximum_acceptable_value, nodata_value)

        for input_raster in [
                site_index_path, sv_reg['strucc_1_path'],
                sv_reg['struce_1_1_path'], sv_reg['struce_1_2_path']]:
            insert_nodata_values_into_raster(input_raster, _TARGET_NODATA)
            forage._structural_ratios(
                site_index_path, site_param_table, sv_reg, pp_reg)

            for key, path in pp_reg.iteritems():
                self.assert_all_values_in_raster_within_range(
                    path, minimum_acceptable_value,
                    maximum_acceptable_value, nodata_value)

    def test_yearly_tasks(self):
        """Test that `_yearly_tasks` return reasonable values.

        Use `_yearly_tasks` to calculate annual precipitation and annual
        atmospheric N deposition from random inputs. Test that the function
        fails if fewer than 12 months of precipitation are supplied. Test that
        the function fails if the dates of precipitation inputs do not fill
        the 12 months surrounding the current month. Test that annual
        precipitation falls inside the range [0, 72]. Test that annual
        atmospheric N deposition falls inside the range [0, 37]. Introduce
        nodata values into input rasters and test that atmospheric N deposition
        remains within the specified range.

        Raises:
            AssertionError if `_yearly_tasks` does not fail with fewer than 12
                months of precipitation rasters supplied
            AssertionError if `_yearly_tasks` does not fail with precipitation
                rasters supplied not within 12 months of current month
            AssertionError if a result from random inputs is outside the
                known possible range given the range of inputs

        Returns:
            None
        """
        from natcap.invest import forage

        month_index = numpy.random.randint(0, 100)
        site_index_path = os.path.join(self.workspace_dir, 'site_index.tif')
        site_param_table = {
            1: {
                'epnfa_1': numpy.random.uniform(0, 1),
                'epnfa_2': numpy.random.uniform(0, 0.5),
                }
            }

        complete_aligned_inputs = {
            'precip_{}'.format(month): os.path.join(
                self.workspace_dir, 'precip_{}.tif'.format(month)) for
            month in xrange(month_index, month_index + 12)
        }

        year_reg = {
            'annual_precip_path': os.path.join(
                self.workspace_dir, 'annual_precip.tif'),
            'baseNdep_path': os.path.join(self.workspace_dir, 'baseNdep.tif')
        }

        create_random_raster(site_index_path, 1, 1)
        for key, path in complete_aligned_inputs.iteritems():
            create_random_raster(path, 0, 6)

        # fewer than 12 months of precip rasters
        modified_inputs = complete_aligned_inputs.copy()
        removed_key = modified_inputs.pop('precip_{}'.format(
            numpy.random.randint(month_index, month_index + 12)))
        with self.assertRaises(ValueError):
            forage._yearly_tasks(
                site_index_path, site_param_table, modified_inputs,
                month_index, year_reg)

        # 12 months of precip rasters supplied, but outside 12 month window of
        # current month
        modified_inputs['precip_{}'.format(month_index + 13)] = os.path.join(
            'precip_{}.tif'.format(month_index + 13))
        with self.assertRaises(ValueError):
            forage._yearly_tasks(
                site_index_path, site_param_table, modified_inputs,
                month_index, year_reg)

        # complete intact inputs
        minimum_acceptable_annual_precip = 0
        maximum_acceptabe_annual_precip = 72
        precip_nodata = _TARGET_NODATA

        minimum_acceptable_Ndep = 0
        maximum_acceptable_Ndep = 37
        Ndep_nodata = _TARGET_NODATA

        forage._yearly_tasks(
            site_index_path, site_param_table, complete_aligned_inputs,
            month_index, year_reg)
        self.assert_all_values_in_raster_within_range(
            year_reg['annual_precip_path'], minimum_acceptable_annual_precip,
            maximum_acceptabe_annual_precip, precip_nodata)
        self.assert_all_values_in_raster_within_range(
            year_reg['baseNdep_path'], minimum_acceptable_Ndep,
            maximum_acceptable_Ndep, Ndep_nodata)

        input_raster_list = [site_index_path] + [
            path for key, path in complete_aligned_inputs.iteritems()]
        for input_raster in input_raster_list:
            insert_nodata_values_into_raster(input_raster, _TARGET_NODATA)
            forage._yearly_tasks(
                site_index_path, site_param_table, complete_aligned_inputs,
                month_index, year_reg)
            self.assert_all_values_in_raster_within_range(
                year_reg['annual_precip_path'],
                minimum_acceptable_annual_precip,
                maximum_acceptabe_annual_precip, precip_nodata)
            self.assert_all_values_in_raster_within_range(
                year_reg['baseNdep_path'], minimum_acceptable_Ndep,
                maximum_acceptable_Ndep, Ndep_nodata)

    def test_reference_evapotranspiration(self):
        """Test that `_reference_evapotranspiration` returns valid results.

        Use the function `_reference_evapotranspiration` to calculate reference
        evapotranspiration (ET) from random inputs. Test that the calculated
        reference ET is within the range [0, 32]. Introduce nodata values into
        the inputs and test that the result remains inside the range [0, 31].
        Test the function with known inputs against a value calculated by hand.

        Raises:
            AssertionError if evapotranspiration from random inputs is outside
                the known possible range given the range of inputs
            AssertionError if evapotranspiration from known inputs is outside
                the range [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        max_temp_path = os.path.join(self.workspace_dir, 'max_temp.tif')
        min_temp_path = os.path.join(self.workspace_dir, 'min_temp.tif')
        shwave_path = os.path.join(self.workspace_dir, 'shwave.tif')
        fwloss_4_path = os.path.join(self.workspace_dir, 'fwloss_4.tif')

        create_random_raster(max_temp_path, 21, 40)
        create_random_raster(min_temp_path, -20, 20)
        create_random_raster(shwave_path, 0, 1125)
        create_random_raster(fwloss_4_path, 0, 1)

        pevap_path = os.path.join(self.workspace_dir, 'pevap.tif')

        minimum_acceptable_ET = 0
        maximum_acceptable_ET = 32
        ET_nodata = _TARGET_NODATA

        forage._reference_evapotranspiration(
            max_temp_path, min_temp_path, shwave_path, fwloss_4_path,
            pevap_path)

        self.assert_all_values_in_raster_within_range(
            pevap_path, minimum_acceptable_ET, maximum_acceptable_ET,
            ET_nodata)

        insert_nodata_values_into_raster(max_temp_path, _IC_NODATA)
        insert_nodata_values_into_raster(min_temp_path, _IC_NODATA)
        insert_nodata_values_into_raster(shwave_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(fwloss_4_path, _IC_NODATA)

        forage._reference_evapotranspiration(
            max_temp_path, min_temp_path, shwave_path, fwloss_4_path,
            pevap_path)

        self.assert_all_values_in_raster_within_range(
            pevap_path, minimum_acceptable_ET, maximum_acceptable_ET,
            ET_nodata)

        # known inputs
        create_random_raster(max_temp_path, 23, 23)
        create_random_raster(min_temp_path, -2, -2)
        create_random_raster(shwave_path, 880, 880)
        create_random_raster(fwloss_4_path, 0.6, 0.6)

        known_ET = 9.5465
        tolerance = 0.0001

        forage._reference_evapotranspiration(
            max_temp_path, min_temp_path, shwave_path, fwloss_4_path,
            pevap_path)

        self.assert_all_values_in_raster_within_range(
            pevap_path, known_ET - tolerance, known_ET + tolerance,
            ET_nodata)

    def test_potential_production(self):
        """Test that `_potential_production` returns valid results.

        Use the function `_potential_production` to calculate h2ogef_1 and
        total potential production from random inputs. Test that h2ogef_1, the
        limiting factor of water availability on growth, is inside the range
        [0.009, 1]. Test that total production is inside the range [0, 675].
        Introduce nodata values into inputs and test that h2ogef_1 and
        potential production remain inside the specified ranges.

        Raises:
            AssertionError if h2ogef_1 is outside the range [0.009, 1]
            AssertionError if total potential production is outside the range
                [0, 675]

        Returns:
            None
        """
        from natcap.invest import forage

        month_index = 10
        current_month = 6
        pft_id_set = set([1, 2])

        aligned_inputs = {
            'site_index': os.path.join(self.workspace_dir, 'site_index.tif'),
            'max_temp_{}'.format(current_month): os.path.join(
                self.workspace_dir, 'max_temp.tif'),
            'min_temp_{}'.format(current_month): os.path.join(
                self.workspace_dir, 'min_temp.tif'),
            'precip_{}'.format(month_index): os.path.join(
                self.workspace_dir, 'precip.tif'),
        }
        create_random_raster(aligned_inputs['site_index'], 1, 1)
        create_random_raster(
            aligned_inputs['max_temp_{}'.format(current_month)], 10, 30)
        create_random_raster(
            aligned_inputs['min_temp_{}'.format(current_month)], -10, 9)
        create_random_raster(
            aligned_inputs['precip_{}'.format(month_index)], 0, 6)

        for pft_i in pft_id_set:
            aligned_inputs['pft_{}'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'pft_{}.tif'.format(pft_i))
            create_random_raster(
                aligned_inputs['pft_{}'.format(pft_i)], 0, 1)

        site_param_table = {
            1: {
                'pmxbio': numpy.random.uniform(500, 700),
                'pmxtmp': numpy.random.uniform(-0.0025, 0),
                'pmntmp': numpy.random.uniform(0, 0.01),
                'fwloss_4': numpy.random.uniform(0, 1),
                'pprpts_1': numpy.random.uniform(0, 1),
                'pprpts_2': numpy.random.uniform(0.5, 1.5),
                'pprpts_3': numpy.random.uniform(0, 1),
            }
        }
        veg_trait_table = {}
        for pft_i in pft_id_set:
            veg_trait_table[pft_i] = {
                'ppdf_1': numpy.random.uniform(10, 30),
                'ppdf_2': numpy.random.uniform(31, 50),
                'ppdf_3': numpy.random.uniform(0, 1),
                'ppdf_4': numpy.random.uniform(0, 10),
                'biok5': numpy.random.uniform(0, 2000),
                'prdx_1': numpy.random.uniform(0.1, 0.6),
                'growth_months': ['3', '4', '5', '6'],
            }

        sv_reg = {
            'strucc_1_path': os.path.join(self.workspace_dir, 'strucc_1.tif'),
        }
        create_random_raster(sv_reg['strucc_1_path'], 0, 200)
        for pft_i in pft_id_set:
            sv_reg['aglivc_{}_path'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'aglivc_{}.tif'.format(pft_i))
            create_random_raster(
                sv_reg['aglivc_{}_path'.format(pft_i)], 0, 50)
            sv_reg['stdedc_{}_path'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'stdedc_{}.tif'.format(pft_i))
            create_random_raster(
                sv_reg['stdedc_{}_path'.format(pft_i)], 0, 50)
            sv_reg['avh2o_1_{}_path'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'avh2o_1_{}.tif'.format(pft_i))
            create_random_raster(
                sv_reg['avh2o_1_{}_path'.format(pft_i)], 0, 3.5)

        pp_reg = {
            'wc_path': os.path.join(self.workspace_dir, 'wc.tif')
        }
        create_random_raster(pp_reg['wc_path'], 0.01, 0.9)

        month_reg = {}
        for pft_i in pft_id_set:
            month_reg['h2ogef_1_{}'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'h2ogef_1_{}.tif'.format(pft_i))
            month_reg['tgprod_pot_prod_{}'.format(pft_i)] = os.path.join(
                self.workspace_dir, 'tgprod_pot_prod_{}.tif'.format(pft_i))

        minimum_acceptable_h2ogef_1 = 0.009
        maximum_acceptable_h2ogef_1 = 1

        minimum_acceptable_potential_production = 0
        maximum_acceptable_potential_production = 675

        forage._potential_production(
            aligned_inputs, site_param_table, current_month, month_index,
            pft_id_set, veg_trait_table, sv_reg, pp_reg, month_reg)

        for pft_i in pft_id_set:
            self.assert_all_values_in_raster_within_range(
                month_reg['h2ogef_1_{}'.format(pft_i)],
                minimum_acceptable_h2ogef_1,
                maximum_acceptable_h2ogef_1, _TARGET_NODATA)
            self.assert_all_values_in_raster_within_range(
                month_reg['tgprod_pot_prod_{}'.format(pft_i)],
                minimum_acceptable_potential_production,
                maximum_acceptable_potential_production, _TARGET_NODATA)

        insert_nodata_values_into_raster(
            aligned_inputs['site_index'], _TARGET_NODATA)
        insert_nodata_values_into_raster(
            aligned_inputs['max_temp_{}'.format(current_month)],
            -9999)
        insert_nodata_values_into_raster(
            aligned_inputs['min_temp_{}'.format(current_month)],
            _IC_NODATA)
        insert_nodata_values_into_raster(
            aligned_inputs['pft_{}'.format(list(pft_id_set)[0])],
            _TARGET_NODATA)
        insert_nodata_values_into_raster(
            sv_reg['aglivc_{}_path'.format(list(pft_id_set)[0])], _IC_NODATA)
        insert_nodata_values_into_raster(
            sv_reg['avh2o_1_{}_path'.format(list(pft_id_set)[1])],
            _TARGET_NODATA)
        insert_nodata_values_into_raster(pp_reg['wc_path'], _TARGET_NODATA)

        forage._potential_production(
            aligned_inputs, site_param_table, current_month, month_index,
            pft_id_set, veg_trait_table, sv_reg, pp_reg, month_reg)

        for pft_i in pft_id_set:
            self.assert_all_values_in_raster_within_range(
                month_reg['h2ogef_1_{}'.format(pft_i)],
                minimum_acceptable_h2ogef_1,
                maximum_acceptable_h2ogef_1, _TARGET_NODATA)
            self.assert_all_values_in_raster_within_range(
                month_reg['tgprod_pot_prod_{}'.format(pft_i)],
                minimum_acceptable_potential_production,
                maximum_acceptable_potential_production, _TARGET_NODATA)

    def test_calc_favail_P(self):
        """Test that `_calc_favail_P` returns valid results.

        Use the function `_calc_favail_P` to calculate the intermediate
        parameter favail_P from random inputs.  Test that favail_P is
        inside the range [0, 1]. Introduce nodata values into inputs and test
        that favail_P remains inside the range [0, 1]. Test the function with
        known inputs against values calculated by hand.

        Raises:
            AssertionError if favail_P from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if favail_ from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        sv_reg = {
            'minerl_1_1_path': os.path.join(
                self.workspace_dir, 'minerl_1_1.tif')
        }
        param_val_dict = {
            'favail_4': os.path.join(self.workspace_dir, 'favail_4.tif'),
            'favail_5': os.path.join(self.workspace_dir, 'favail_5.tif'),
            'favail_6': os.path.join(self.workspace_dir, 'favail_6.tif'),
            'favail_2': os.path.join(self.workspace_dir, 'favail_2.tif'),
        }

        create_random_raster(sv_reg['minerl_1_1_path'], 3, 8)
        create_random_raster(param_val_dict['favail_4'], 0, 1)
        create_random_raster(param_val_dict['favail_5'], 0, 1)
        create_random_raster(param_val_dict['favail_6'], 1, 3)

        forage._calc_favail_P(sv_reg, param_val_dict)

        minimum_acceptable_favail_P = 0
        maximum_acceptable_favail_P = 1

        self.assert_all_values_in_raster_within_range(
            param_val_dict['favail_2'],
            minimum_acceptable_favail_P,
            maximum_acceptable_favail_P, _IC_NODATA)

        for input_raster in [
                sv_reg['minerl_1_1_path'], param_val_dict['favail_4'],
                param_val_dict['favail_5'], param_val_dict['favail_6']]:
            insert_nodata_values_into_raster(input_raster, _IC_NODATA)
            forage._calc_favail_P(sv_reg, param_val_dict)
            self.assert_all_values_in_raster_within_range(
                param_val_dict['favail_2'],
                minimum_acceptable_favail_P,
                maximum_acceptable_favail_P, _IC_NODATA)

        # known inputs
        create_random_raster(sv_reg['minerl_1_1_path'], 4.5, 4.5)
        create_random_raster(param_val_dict['favail_4'], 0.2, 0.2)
        create_random_raster(param_val_dict['favail_5'], 0.5, 0.5)
        create_random_raster(param_val_dict['favail_6'], 2.3, 2.3)

        known_favail_2 = 0.5
        tolerance = 0.0001

        forage._calc_favail_P(sv_reg, param_val_dict)
        self.assert_all_values_in_raster_within_range(
            param_val_dict['favail_2'],
            known_favail_2 - tolerance, known_favail_2 + tolerance,
            _IC_NODATA)

    def test_raster_sum(self):
        """Test the treatment of nodata values by `raster_sum`.

        Use the function `raster_sum` to calculate the sum across pixels
        in three rasters containing nodata.  Test that when
        nodata_remove=False, the result also contains nodata values. Test
        that when nodata_remove=True, nodata pixels are treated as zero.

        Raises:
            AssertionError if result raster does not contain nodata values
                in same position as input rasters

        Returns:
            None
        """
        from natcap.invest import forage

        num_rasters = numpy.random.randint(1, 10)
        raster_list = [
            os.path.join(self.workspace_dir, '{}.tif'.format(r)) for r in
            xrange(num_rasters)]

        for input_raster in raster_list:
            create_random_raster(input_raster, 1, 1)

        input_nodata = -999
        target_path = os.path.join(self.workspace_dir, 'result.tif')
        target_nodata = -9.99

        # input rasters include no nodata values
        forage.raster_sum(
            raster_list, input_nodata, target_path, target_nodata,
            nodata_remove=False)
        self.assert_all_values_in_raster_within_range(
            target_path, num_rasters, num_rasters, target_nodata)

        forage.raster_sum(
            raster_list, input_nodata, target_path, target_nodata,
            nodata_remove=True)
        self.assert_all_values_in_raster_within_range(
            target_path, num_rasters, num_rasters, target_nodata)

        # one input raster includes nodata values
        insert_nodata_values_into_raster(raster_list[0], input_nodata)

        forage.raster_sum(
            raster_list, input_nodata, target_path, target_nodata,
            nodata_remove=False)
        self.assert_all_values_in_raster_within_range(
            target_path, num_rasters, num_rasters, target_nodata)

        # assert that raster_list[0] and target_path include nodata
        # values in same locations
        input_including_nodata = gdal.OpenEx(raster_list[0])
        result_including_nodata = gdal.OpenEx(target_path)
        input_band = input_including_nodata.GetRasterBand(1)
        result_band = result_including_nodata.GetRasterBand(1)
        input_array = input_band.ReadAsArray()
        result_array = result_band.ReadAsArray()

        sum_input_mask = numpy.sum(input_array[input_array == input_nodata])
        sum_result_mask = numpy.sum(input_array[result_array == target_nodata])

        self.assertEqual(
            sum_input_mask, sum_result_mask,
            msg="Result raster must contain nodata values in same " +
            "position as input")

        input_band = None
        result_band = None
        input_including_nodata = None
        result_including_nodata = None

        forage.raster_sum(
            raster_list, input_nodata, target_path, target_nodata,
            nodata_remove=True)

        # assert that minimum value in target_path is num_rasters - 1
        for offset_map, raster_block in pygeoprocessing.iterblocks(
                target_path):
            if len(raster_block[raster_block != target_nodata]) == 0:
                continue
            min_val = numpy.amin(
                raster_block[raster_block != target_nodata])
            self.assertGreaterEqual(
                min_val, (num_rasters - 1),
                msg="Raster appears to contain nodata values")

    def test_calc_available_nutrient(self):
        """Test that `_calc_available_nutrient` returns valid results.

        Use the function `_calc_available_nutrient` to calculate available
        nutrient from random results. Test that the calculated nutrient
        available is inside the range [0, 323]. Introduce nodata values into
        inputs and test that available nutrient remains inside the range
        [0, 323]. Test the function with known values against values calculated
        by hand.

        Raises:
            AssertionError if a result from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if a result from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        pft_i = numpy.random.randint(0, 4)
        pft_param_dict = {
            'snfxmx_1': numpy.random.uniform(0, 1),
            'nlaypg': numpy.random.randint(1, 10),
        }
        sv_reg = {
            'bglivc_{}_path'.format(pft_i): os.path.join(
                self.workspace_dir, 'bglivc_path.tif'),
            'crpstg_1_{}_path'.format(pft_i): os.path.join(
                self.workspace_dir, 'crpstg_1_{}.tif'.format(pft_i)),
            'crpstg_2_{}_path'.format(pft_i): os.path.join(
                self.workspace_dir, 'crpstg_2_{}.tif'.format(pft_i)),
        }
        for iel in [1, 2]:
            for lyr in xrange(1, 11):
                sv_reg['minerl_{}_{}_path'.format(lyr, iel)] = os.path.join(
                    self.workspace_dir, 'minerl_{}_{}.tif'.format(lyr, iel))
                create_random_raster(
                    sv_reg['minerl_{}_{}_path'.format(lyr, iel)], 0, 5)

        site_param_table = {
            1: {
                'rictrl': numpy.random.uniform(0.005, 0.02),
                'riint': numpy.random.uniform(0.6, 1),
                }
            }
        site_index_path = os.path.join(self.workspace_dir, 'site_index.tif')
        favail_path = os.path.join(self.workspace_dir, 'favail.tif')
        tgprod_path = os.path.join(self.workspace_dir, 'tgprod.tif')

        create_random_raster(site_index_path, 1, 1)
        create_random_raster(sv_reg['bglivc_{}_path'.format(pft_i)], 90, 180)
        create_random_raster(sv_reg['crpstg_1_{}_path'.format(pft_i)], 0, 3)
        create_random_raster(sv_reg['crpstg_2_{}_path'.format(pft_i)], 0, 1)
        create_random_raster(favail_path, 0, 1)
        create_random_raster(tgprod_path, 0, 675)

        eavail_path = os.path.join(self.workspace_dir, 'eavail.tif')

        minimum_acceptable_eavail = 0
        maximum_acceptable_evail = 323

        for iel in [1, 2]:
            forage._calc_available_nutrient(
                pft_i, iel, pft_param_dict, sv_reg, site_param_table,
                site_index_path, favail_path, tgprod_path, eavail_path)

            self.assert_all_values_in_raster_within_range(
                eavail_path, minimum_acceptable_eavail,
                maximum_acceptable_evail, _TARGET_NODATA)

        insert_nodata_values_into_raster(site_index_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(
            sv_reg['minerl_1_1_path'], _TARGET_NODATA)
        insert_nodata_values_into_raster(
            sv_reg['bglivc_{}_path'.format(pft_i)], _TARGET_NODATA)
        insert_nodata_values_into_raster(tgprod_path, _TARGET_NODATA)

        for iel in [1, 2]:
            forage._calc_available_nutrient(
                pft_i, iel, pft_param_dict, sv_reg, site_param_table,
                site_index_path, favail_path, tgprod_path, eavail_path)

            self.assert_all_values_in_raster_within_range(
                eavail_path, minimum_acceptable_eavail,
                maximum_acceptable_evail, _TARGET_NODATA)

        # known inputs
        create_random_raster(sv_reg['bglivc_{}_path'.format(pft_i)], 100, 100)
        create_random_raster(
            sv_reg['crpstg_1_{}_path'.format(pft_i)], 0.8, 0.8)
        create_random_raster(
            sv_reg['crpstg_2_{}_path'.format(pft_i)], 0.8, 0.8)
        create_random_raster(favail_path, 0.3, 0.3)
        create_random_raster(tgprod_path, 300, 300)

        for iel in [1, 2]:
            for lyr in xrange(1, 11):
                create_random_raster(
                    sv_reg['minerl_{}_{}_path'.format(lyr, iel)], 1, 1)

        pft_param_dict['snfxmx_1'] = 0.4
        pft_param_dict['nlaypg'] = 4

        site_param_table[1]['rictrl'] = 0.013
        site_param_table[1]['riint'] = 0.65

        known_N_avail = 49.9697
        known_P_avail = 1.9697
        tolerance = 0.0001

        iel = 1
        eavail_path = os.path.join(self.workspace_dir, 'eavail_N.tif')
        forage._calc_available_nutrient(
            pft_i, iel, pft_param_dict, sv_reg, site_param_table,
            site_index_path, favail_path, tgprod_path, eavail_path)

        self.assert_all_values_in_raster_within_range(
            eavail_path, known_N_avail - tolerance,
            known_N_avail + tolerance, _TARGET_NODATA)

        iel = 2
        eavail_path = os.path.join(self.workspace_dir, 'eavail_P.tif')
        forage._calc_available_nutrient(
            pft_i, iel, pft_param_dict, sv_reg, site_param_table,
            site_index_path, favail_path, tgprod_path, eavail_path)

        self.assert_all_values_in_raster_within_range(
            eavail_path, known_P_avail - tolerance,
            known_P_avail + tolerance, _TARGET_NODATA)

    def test_calc_nutrient_demand(self):
        """Test that `_calc_nutrient_demand` returns reasonable results.

        Use the function `_calc_nutrient_demand` to calculate demand for
        one nutrient by one plant functional type. Test that the calculated
        demand is in the range [???].  Introduce nodata values into inputs
        and test that calculated demand remains in the range [???]. Test
        against a result calculated by hand for known inputs.

        Raises:
            AssertionError if demand from random inputs is outside the
                known possible range given the range of inputs
            AssertionError if demand from known inputs is outside the range
                [known result += 0.0001]

        Returns:
            None
        """
        from natcap.invest import forage

        biomass_production_path = os.path.join(
            self.workspace_dir, 'biomass_production.tif')
        fraction_allocated_to_roots_path = os.path.join(
            self.workspace_dir, 'fraction_allocated_to_roots.tif')
        cercrp_min_above_path = os.path.join(
            self.workspace_dir, 'cercrp_min_above.tif')
        cercrp_min_below_path = os.path.join(
            self.workspace_dir, 'cercrp_min_below.tif')
        demand_path = os.path.join(
            self.workspace_dir, 'demand.tif')

        # run with random inputs
        create_random_raster(biomass_production_path, 0, 675)
        create_random_raster(fraction_allocated_to_roots_path, 0.01, 0.99)
        create_random_raster(cercrp_min_above_path, 8, 16)
        create_random_raster(cercrp_min_below_path, 8, 16)

        minimum_acceptable_demand = 0
        maximum_acceptable_demand = 33.75

        forage._calc_nutrient_demand(
            biomass_production_path, fraction_allocated_to_roots_path,
            cercrp_min_above_path, cercrp_min_below_path, demand_path)

        self.assert_all_values_in_raster_within_range(
            demand_path, minimum_acceptable_demand,
            maximum_acceptable_demand, _TARGET_NODATA)

        # insert nodata values into inputs
        insert_nodata_values_into_raster(
            biomass_production_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(
            fraction_allocated_to_roots_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(cercrp_min_above_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(cercrp_min_below_path, _TARGET_NODATA)

        forage._calc_nutrient_demand(
            biomass_production_path, fraction_allocated_to_roots_path,
            cercrp_min_above_path, cercrp_min_below_path, demand_path)

        self.assert_all_values_in_raster_within_range(
            demand_path, minimum_acceptable_demand,
            maximum_acceptable_demand, _TARGET_NODATA)

        # run with known inputs
        create_random_raster(biomass_production_path, 300, 300)
        create_random_raster(fraction_allocated_to_roots_path, 0.4, 0.4)
        create_random_raster(cercrp_min_above_path, 15, 15)
        create_random_raster(cercrp_min_below_path, 9, 9)

        known_demand = 10.1333
        tolerance = 0.0001

        forage._calc_nutrient_demand(
            biomass_production_path, fraction_allocated_to_roots_path,
            cercrp_min_above_path, cercrp_min_below_path, demand_path)

        self.assert_all_values_in_raster_within_range(
            demand_path, known_demand - tolerance, known_demand + tolerance,
            _TARGET_NODATA)

    def test_calc_provisional_fracrc(self):
        """Test that `calc_provisional_fracrc` returns reasonable results.

        Use the function `calc_provisional_fracrc` to calculate fracrc_p, the
        fraction of carbon allocated to roots. Test that fracrc_p calculated
        from random inputs is inside the valid range given the range
        of inputs. Introduce nodata values into inputs and test that fracrc_p
        remains inside the valid range. Test the function with known inputs
        against values calculated by hand.

        Raises:
            AssertionError if fracrc_p from random inputs is outside the range
                of valid values given the range of inputs
            AssertionError if fracrc_p from known inputs is not within 0.0001
                of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        array_shape = (10, 10)

        annual_precip = numpy.random.uniform(22, 100, array_shape)
        frtcindx = numpy.random.randint(0, 2, array_shape)
        bgppa = numpy.random.uniform(100, 200, array_shape)
        bgppb = numpy.random.uniform(2, 12, array_shape)
        agppa = numpy.random.uniform(-40, -10, array_shape)
        agppb = numpy.random.uniform(2, 12, array_shape)
        cfrtcw_1 = numpy.random.uniform(0.4, 0.8, array_shape)
        cfrtcw_2 = numpy.random.uniform(0.01, 0.38, array_shape)
        cfrtcn_1 = numpy.random.uniform(0.4, 0.8, array_shape)
        cfrtcn_2 = numpy.random.uniform(0.01, 0.38, array_shape)

        minimum_acceptable_fracrc_p = 0.205
        maximum_acceptable_fracrc_p = 0.97297

        fracrc_p = forage.calc_provisional_fracrc(
            annual_precip, frtcindx, bgppa, bgppb, agppa, agppb,
            cfrtcw_1, cfrtcw_2, cfrtcn_1, cfrtcn_2)
        self.assert_all_values_in_array_within_range(
            fracrc_p, minimum_acceptable_fracrc_p,
            maximum_acceptable_fracrc_p, _TARGET_NODATA)

        insert_nodata_values_into_array(annual_precip, _TARGET_NODATA)
        fracrc_p = forage.calc_provisional_fracrc(
            annual_precip, frtcindx, bgppa, bgppb, agppa, agppb,
            cfrtcw_1, cfrtcw_2, cfrtcn_1, cfrtcn_2)
        self.assert_all_values_in_array_within_range(
            fracrc_p, minimum_acceptable_fracrc_p,
            maximum_acceptable_fracrc_p, _TARGET_NODATA)

        # known values
        annual_precip = numpy.full(array_shape, 42)
        bgppa = numpy.full(array_shape, 101)
        bgppb = numpy.full(array_shape, 4.2)
        agppa = numpy.full(array_shape, -12)
        agppb = numpy.full(array_shape, 3.2)
        cfrtcw_1 = numpy.full(array_shape, 0.4)
        cfrtcw_2 = numpy.full(array_shape, 0.33)
        cfrtcn_1 = numpy.full(array_shape, 0.76)
        cfrtcn_2 = numpy.full(array_shape, 0.02)

        insert_nodata_values_into_array(annual_precip, _TARGET_NODATA)

        known_fracrc_p_frtcindx_0 = 0.69385
        known_fracrc_p_frtcindx_1 = 0.3775
        tolerance = 0.0001

        frtcindx = numpy.full(array_shape, 0)
        fracrc_p = forage.calc_provisional_fracrc(
            annual_precip, frtcindx, bgppa, bgppb, agppa, agppb,
            cfrtcw_1, cfrtcw_2, cfrtcn_1, cfrtcn_2)
        self.assert_all_values_in_array_within_range(
            fracrc_p, known_fracrc_p_frtcindx_0 - tolerance,
            known_fracrc_p_frtcindx_0 + tolerance, _TARGET_NODATA)

        frtcindx = numpy.full(array_shape, 1)
        fracrc_p = forage.calc_provisional_fracrc(
            annual_precip, frtcindx, bgppa, bgppb, agppa, agppb,
            cfrtcw_1, cfrtcw_2, cfrtcn_1, cfrtcn_2)
        self.assert_all_values_in_array_within_range(
            fracrc_p, known_fracrc_p_frtcindx_1 - tolerance,
            known_fracrc_p_frtcindx_1 + tolerance, _TARGET_NODATA)

    def test_calc_ce_ratios(self):
        """Test that `calc_ce_ratios` returns reasonable results.

        Use the funciton `calc_ce_ratios` to calculate minimum and maximum
        carbon to nutrient ratios. Test that ratios calculated from random
        inputs are within the range of valid values given the range of
        inputs. Introduce nodata values into inputs and test that results
        remain within valid ranges. Calculate the ratios from known inputs
        against results calculated by hand.

        Raises:
            AssertionError if calculated ratios are outside the range of
                valid results given range of random inputs
            AssertionError if calculated ratios are not within 0.0001 of
                values calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        pramn_1_path = os.path.join(self.workspace_dir, 'pramn_1.tif')
        pramn_2_path = os.path.join(self.workspace_dir, 'pramn_2.tif')
        aglivc_path = os.path.join(self.workspace_dir, 'aglivc.tif')
        biomax_path = os.path.join(self.workspace_dir, 'biomax.tif')
        pramx_1_path = os.path.join(self.workspace_dir, 'pramx_1.tif')
        pramx_2_path = os.path.join(self.workspace_dir, 'pramx_2.tif')
        prbmn_1_path = os.path.join(self.workspace_dir, 'prbmn_1.tif')
        prbmn_2_path = os.path.join(self.workspace_dir, 'prbmn_2.tif')
        prbmx_1_path = os.path.join(self.workspace_dir, 'prbmx_1.tif')
        prbmx_2_path = os.path.join(self.workspace_dir, 'prbmx_2.tif')
        annual_precip_path = os.path.join(
            self.workspace_dir, 'annual_precip.tif')
        create_random_raster(pramn_1_path, 20, 50)
        create_random_raster(pramn_2_path, 52, 70)
        create_random_raster(aglivc_path, 20, 400)
        create_random_raster(biomax_path, 300, 500)
        create_random_raster(pramx_1_path, 51, 100)
        create_random_raster(pramx_2_path, 70, 130)
        create_random_raster(prbmn_1_path, 30, 70)
        create_random_raster(prbmn_2_path, 0, 0.2)
        create_random_raster(prbmx_1_path, 40, 70)
        create_random_raster(prbmx_2_path, 0, 0.4)
        create_random_raster(annual_precip_path, 22, 100)

        pft_i = numpy.random.randint(0, 5)
        iel = numpy.random.randint(1, 3)

        month_reg = {
            'cercrp_min_above_{}_{}'.format(iel, pft_i): os.path.join(
                self.workspace_dir,
                'cercrp_min_above_{}_{}.tif'.format(iel, pft_i)),
            'cercrp_max_above_{}_{}'.format(iel, pft_i): os.path.join(
                self.workspace_dir,
                'cercrp_max_above_{}_{}.tif'.format(iel, pft_i)),
            'cercrp_min_below_{}_{}'.format(iel, pft_i): os.path.join(
                self.workspace_dir,
                'cercrp_min_below_{}_{}.tif'.format(iel, pft_i)),
            'cercrp_max_below_{}_{}'.format(iel, pft_i): os.path.join(
                self.workspace_dir,
                'cercrp_max_below_{}_{}.tif'.format(iel, pft_i)),
        }

        acceptable_range_dict = {
            'cercrp_min_above_{}_{}'.format(iel, pft_i): {
                'minimum_acceptable_value': 25.3333,
                'maximum_acceptable_value': 70.,
            },
            'cercrp_max_above_{}_{}'.format(iel, pft_i): {
                'minimum_acceptable_value': 25.,
                'maximum_acceptable_value': 130.,
            },
            'cercrp_min_below_{}_{}'.format(iel, pft_i): {
                'minimum_acceptable_value': 30.,
                'maximum_acceptable_value': 90.,
            },
            'cercrp_max_below_{}_{}'.format(iel, pft_i): {
                'minimum_acceptable_value': 40.,
                'maximum_acceptable_value': 110.,
            },
        }
        forage.calc_ce_ratios(
            pramn_1_path, pramn_2_path, aglivc_path, biomax_path,
            pramx_1_path, pramx_2_path, prbmn_1_path, prbmn_2_path,
            prbmx_1_path, prbmx_2_path, annual_precip_path, month_reg,
            pft_i, iel)
        for path, ranges in acceptable_range_dict.iteritems():
            self.assert_all_values_in_raster_within_range(
                month_reg[path], ranges['minimum_acceptable_value'],
                ranges['maximum_acceptable_value'], _TARGET_NODATA)

        insert_nodata_values_into_raster(aglivc_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(prbmn_1_path, _IC_NODATA)
        insert_nodata_values_into_raster(annual_precip_path, _TARGET_NODATA)
        forage.calc_ce_ratios(
            pramn_1_path, pramn_2_path, aglivc_path, biomax_path,
            pramx_1_path, pramx_2_path, prbmn_1_path, prbmn_2_path,
            prbmx_1_path, prbmx_2_path, annual_precip_path, month_reg,
            pft_i, iel)
        for path, ranges in acceptable_range_dict.iteritems():
            self.assert_all_values_in_raster_within_range(
                month_reg[path], ranges['minimum_acceptable_value'],
                ranges['maximum_acceptable_value'], _TARGET_NODATA)

        # known inputs
        create_random_raster(pramn_1_path, 22, 22)
        create_random_raster(pramn_2_path, 55, 55)
        create_random_raster(aglivc_path, 321, 321)
        create_random_raster(biomax_path, 300, 300)
        create_random_raster(pramx_1_path, 46, 46)
        create_random_raster(pramx_2_path, 78, 78)
        create_random_raster(prbmn_1_path, 52, 52)
        create_random_raster(prbmn_2_path, 0.18, 0.18)
        create_random_raster(prbmx_1_path, 42, 42)
        create_random_raster(prbmx_2_path, 0.33, 0.33)
        create_random_raster(annual_precip_path, 77.22, 77.22)

        known_value_dict = {
            'cercrp_min_above_{}_{}'.format(iel, pft_i): 55.,
            'cercrp_max_above_{}_{}'.format(iel, pft_i): 78.,
            'cercrp_min_below_{}_{}'.format(iel, pft_i): 65.8996,
            'cercrp_max_below_{}_{}'.format(iel, pft_i): 67.4826,
        }
        tolerance = 0.0001

        insert_nodata_values_into_raster(aglivc_path, -999)
        insert_nodata_values_into_raster(prbmn_1_path, _IC_NODATA)
        insert_nodata_values_into_raster(annual_precip_path, -9)
        forage.calc_ce_ratios(
            pramn_1_path, pramn_2_path, aglivc_path, biomax_path,
            pramx_1_path, pramx_2_path, prbmn_1_path, prbmn_2_path,
            prbmx_1_path, prbmx_2_path, annual_precip_path, month_reg,
            pft_i, iel)
        for path, value in known_value_dict.iteritems():
            self.assert_all_values_in_raster_within_range(
                month_reg[path], value - tolerance,
                value + tolerance, _TARGET_NODATA)

    def test_calc_revised_fracrc(self):
        """Test that `calc_revised_fracrc` returns reasonable results.

        Use the function `calc_revised_fracrc` to calculate fracrc_r, the
        revised fraction of carbon allocated to roots. Test that fracrc_r
        calculated from random inputs is within the range of valid values
        according to the range of inputs. Introduce nodata values into
        inputs and test that fracrc_r remains within the valid range.
        Test fracrc_r calculated from known inputs against the result
        calculated by hand.

        Raises:
            AssertionError if fracrc_r calculated from random inputs is
                outside the range of valid values
            AssertionError if fracrc_r from known inputs is not within
                0.0001 of the value calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        frtcindx_path = os.path.join(self.workspace_dir, 'frtcindx.tif')
        fracrc_p_path = os.path.join(self.workspace_dir, 'fracrc_p.tif')
        totale_1_path = os.path.join(self.workspace_dir, 'totale_1.tif')
        totale_2_path = os.path.join(self.workspace_dir, 'totale_2.tif')
        demand_1_path = os.path.join(self.workspace_dir, 'demand_1.tif')
        demand_2_path = os.path.join(self.workspace_dir, 'demand_2.tif')
        h2ogef_1_path = os.path.join(self.workspace_dir, 'h2ogef_1.tif')
        cfrtcw_1_path = os.path.join(self.workspace_dir, 'cfrtcw_1.tif')
        cfrtcw_2_path = os.path.join(self.workspace_dir, 'cfrtcw_2.tif')
        cfrtcn_1_path = os.path.join(self.workspace_dir, 'cfrtcn_1.tif')
        cfrtcn_2_path = os.path.join(self.workspace_dir, 'cfrtcn_2.tif')
        fracrc_r_path = os.path.join(self.workspace_dir, 'fracrc_r.tif')

        create_random_raster(fracrc_p_path, 0.2, 0.95)
        create_random_raster(totale_1_path, 0, 320)
        create_random_raster(totale_2_path, 0, 52)
        create_random_raster(demand_1_path, 1, 34)
        create_random_raster(demand_2_path, 1, 34)
        create_random_raster(h2ogef_1_path, 0.01, 0.9)
        create_random_raster(cfrtcw_1_path, 0.4, 0.8)
        create_random_raster(cfrtcw_2_path, 1.01, 0.39)
        create_random_raster(cfrtcn_1_path, 0.4, 0.8)
        create_random_raster(cfrtcn_2_path, 1.01, 0.39)

        minimum_acceptable_fracrc_r = 0.01
        maximum_acceptable_fracrc_r = 0.999

        create_random_raster(frtcindx_path, 0, 0)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, minimum_acceptable_fracrc_r,
            maximum_acceptable_fracrc_r, _TARGET_NODATA)

        create_random_raster(frtcindx_path, 1, 1)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, minimum_acceptable_fracrc_r,
            maximum_acceptable_fracrc_r, _TARGET_NODATA)

        insert_nodata_values_into_raster(fracrc_p_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(totale_2_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(demand_1_path, _TARGET_NODATA)
        insert_nodata_values_into_raster(cfrtcw_2_path, _IC_NODATA)

        create_random_raster(frtcindx_path, 0, 0)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, minimum_acceptable_fracrc_r,
            maximum_acceptable_fracrc_r, _TARGET_NODATA)

        create_random_raster(frtcindx_path, 1, 1)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, minimum_acceptable_fracrc_r,
            maximum_acceptable_fracrc_r, _TARGET_NODATA)

        # known values
        create_random_raster(fracrc_p_path, 0.7, 0.7)
        create_random_raster(totale_1_path, 10, 10)
        create_random_raster(totale_2_path, 157, 157)
        create_random_raster(demand_1_path, 14, 14)
        create_random_raster(demand_2_path, 30, 30)
        create_random_raster(h2ogef_1_path, 0.7, 0.7)
        create_random_raster(cfrtcw_1_path, 0.7, 0.7)
        create_random_raster(cfrtcw_2_path, 0.36, 0.36)
        create_random_raster(cfrtcn_1_path, 0.47, 0.47)
        create_random_raster(cfrtcn_2_path, 0.33, 0.33)

        known_fracrc_r_frtcindx_0 = 0.7
        known_fracrc_r_frtcindx_1 = 0.462
        tolerance = 0.0001

        create_random_raster(frtcindx_path, 0, 0)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, known_fracrc_r_frtcindx_0 - tolerance,
            known_fracrc_r_frtcindx_0 + tolerance, _TARGET_NODATA)

        create_random_raster(frtcindx_path, 1, 1)
        forage.calc_revised_fracrc(
            frtcindx_path, fracrc_p_path, totale_1_path, totale_2_path,
            demand_1_path, demand_2_path, h2ogef_1_path, cfrtcw_1_path,
            cfrtcw_2_path, cfrtcn_1_path, cfrtcn_2_path, fracrc_r_path)
        self.assert_all_values_in_raster_within_range(
            fracrc_r_path, known_fracrc_r_frtcindx_1 - tolerance,
            known_fracrc_r_frtcindx_1 + tolerance, _TARGET_NODATA)

    def test_grazing_effect(self):
        """Test grazing effect on aboveground production and root:shoot ratio.

        Use the function `grazing_effect_on_aboveground_production` to
        calculate agprod, revised aboveground production including the
        effects of grazing. Use the function `grazing_effect_on_root_shoot` to
        calculate rtsh, root:shoot ratio including the effects of grazing.
        Test that agprod and rtsh match values calculated by hand. Introduce
        nodata values into inputs and ensure that calculated agprod and rtsh
        still match value calculated by hand.

        Raises:
            AssertionError if agprod is not within 0.0001 of value
                calculated by hand
            AssertionError if rtsh if not within 0.0001 of value calculated by
                hand

        Returns:
            None
        """
        from natcap.invest import forage

        array_shape = (3, 3)

        # known values
        tgprod = numpy.full(array_shape, 500)
        fracrc = numpy.full(array_shape, 0.62)
        flgrem = numpy.full(array_shape, 0.16)
        gremb = numpy.full(array_shape, 0.02)

        tolerance = 0.0001

        grzeff = numpy.full(array_shape, 1)
        agprod_grzeff_1 = 122.816
        rtsh_grzeff_1 = 1.63158
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_1 - tolerance, agprod_grzeff_1 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_1 - tolerance, rtsh_grzeff_1 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 2)
        agprod_grzeff_2 = 240.6828
        rtsh_grzeff_2 = 1.818
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_2 - tolerance, agprod_grzeff_2 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_2 - tolerance, rtsh_grzeff_2 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 3)
        agprod_grzeff_3 = 190
        rtsh_grzeff_3 = 1.818
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_3 - tolerance, agprod_grzeff_3 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_3 - tolerance, rtsh_grzeff_3 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 4)
        agprod_grzeff_4 = 190
        rtsh_grzeff_4 = 0.9968
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_4 - tolerance, agprod_grzeff_4 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_4 - tolerance, rtsh_grzeff_4 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 5)
        agprod_grzeff_5 = 240.6828
        rtsh_grzeff_5 = 0.9968
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_5 - tolerance, agprod_grzeff_5 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_5 - tolerance, rtsh_grzeff_5 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 6)
        agprod_grzeff_6 = 122.816
        rtsh_grzeff_6 = 0.9968
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_6 - tolerance, agprod_grzeff_6 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_6 - tolerance, rtsh_grzeff_6 + tolerance,
            _TARGET_NODATA)

        insert_nodata_values_into_array(fracrc, _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 4)
        agprod_grzeff_4 = 190
        rtsh_grzeff_4 = 0.9968
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_4 - tolerance, agprod_grzeff_4 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_4 - tolerance, rtsh_grzeff_4 + tolerance,
            _TARGET_NODATA)

        grzeff = numpy.full(array_shape, 2)
        agprod_grzeff_2 = 240.6828
        rtsh_grzeff_2 = 1.818
        agprod = forage.grazing_effect_on_aboveground_production(
            tgprod, fracrc, flgrem, grzeff)
        rtsh = forage.grazing_effect_on_root_shoot(
            fracrc, flgrem, grzeff, gremb)
        self.assert_all_values_in_array_within_range(
            agprod, agprod_grzeff_2 - tolerance, agprod_grzeff_2 + tolerance,
            _TARGET_NODATA)
        self.assert_all_values_in_array_within_range(
            rtsh, rtsh_grzeff_2 - tolerance, rtsh_grzeff_2 + tolerance,
            _TARGET_NODATA)

    def test_calc_tgprod_final(self):
        """Test that `calc_tgprod_final` reproduces results calculated by hand.

        Use the function `calc_tgprod_final` to calculate tgprod, final total
        prodcution from root:shoot ratio and aboveground production. Test that
        calculated tgprod matches results calculated by hand.

        Raises:
            AssertionError if tgprod is not within 0.0001 of the value
                calculated by hand

        Returns:
            None
        """
        from natcap.invest import forage

        array_size = (3, 3)
        # known values
        rtsh = numpy.full(array_size, 0.72)
        agprod = numpy.full(array_size, 333)

        known_tgprod = 572.76
        tolerance = 0.0001
        tgprod = forage.calc_tgprod_final(rtsh, agprod)
        self.assert_all_values_in_array_within_range(
            tgprod, known_tgprod - tolerance, known_tgprod + tolerance,
            _TARGET_NODATA)
