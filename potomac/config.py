CURRENT_RUN_NAME = "POTOMAC"
CURRENT_REFERENCE_GAGE = '01607500'
CURRENT_HUC_ID = '02070001'
CURRENT_START_YEAR = "1998"
CURRENT_END_YEAR = "1999"
CURRENT_START_DATE = f"{CURRENT_START_YEAR}-10-01"
CURRENT_END_DATE = f"{CURRENT_END_YEAR}-10-01"
CURRENT_OUTLET_YX = (135,65)

DOMAIN_NAME = f"{CURRENT_RUN_NAME}_{CURRENT_START_YEAR}_to_{CURRENT_END_YEAR}"
# I got these numbers from: https://waterdata.usgs.gov/va/nwis/water_use?format=html_table&rdb_compression=file&wu_area=State+Total&wu_year=ALL&wu_county=091&wu_category=IT&wu_county_nms=Highland%2BCounty&wu_category_nms=Irrigation%252C%2BTotal
# They are the consumptive use for irrigation across all of virginia
# this needs to be 1 million times smaller because I forgot to divide by the size of the grid cell
VIRGINIA_CONSUMPTIVE_USE_MGAL_PER_DAY = 16.03
VIRGINA_CONSUMPTIVE_USE_M3_PER_DAY = 4404.8838 * VIRGINIA_CONSUMPTIVE_USE_MGAL_PER_DAY
VIRGINIA_AREA_KM2 = 110785.67
GRID_CELL_AREA_KM2 = 1.0
GRID_CELL_CONSUMPTIVE_USE_M_PER_DAY = VIRGINA_CONSUMPTIVE_USE_M3_PER_DAY / VIRGINIA_AREA_KM2 * GRID_CELL_AREA_KM2
GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR = GRID_CELL_CONSUMPTIVE_USE_M_PER_DAY / 24.0

# For now use 1 inch per week because that is a number a lot of crops need
GRID_CELL_CONSUMPTIVE_USE_M_PER_HOUR = 0.00015119

P = 4
Q = 4