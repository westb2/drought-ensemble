GILA_RUN_NAME = "GILA"
GILA_REFERENCE_GAGE = '09430500'
GILA_HUC_ID = '15040001'
GILA_START_YEAR = 1988
GILA_END_YEAR = 1989
LENGTH_IN_MONTHS = 6
END_MONTH = 10
START_MONTH = 10 - LENGTH_IN_MONTHS%12
START_YEAR = GILA_END_YEAR - (LENGTH_IN_MONTHS+2)%12
GILA_END_DATE = f"{GILA_END_YEAR}-10-01"

GILA_START_DATE = f"{GILA_START_YEAR}-10-01"



CURRENT_RUN_NAME = GILA_RUN_NAME
CURRENT_REFERENCE_GAGE = GILA_REFERENCE_GAGE
CURRENT_HUC_ID = GILA_HUC_ID
CURRENT_START_YEAR = GILA_START_YEAR
CURRENT_END_YEAR = GILA_END_YEAR
CURRENT_FULL_RUN_NAME = f"{CURRENT_RUN_NAME}_{CURRENT_START_YEAR}_to_{CURRENT_END_YEAR}"
CURRENT_START_DATE = GILA_START_DATE
CURRENT_END_DATE = GILA_END_DATE

P = 4
Q = 4