from osgeo import gdal
import sys

path = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\uploads\csis_b41343a8-aaf8-46c7-ae63-b4490fba4e9c\GBJC_2010_mean_Resample.tif"
ds = gdal.Open(path)
if ds:
    print(f"OK: {ds.RasterXSize}x{ds.RasterYSize}, bands={ds.RasterCount}, proj={bool(ds.GetProjection())}")
else:
    print("FAILED: gdal.Open returned None")

path2 = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\CoastalBlueCarbon_input\GBJC_2010_mean_Resample.tif"
ds2 = gdal.Open(path2)
if ds2:
    print(f"Original OK: {ds2.RasterXSize}x{ds2.RasterYSize}, bands={ds2.RasterCount}, proj={bool(ds2.GetProjection())}")
