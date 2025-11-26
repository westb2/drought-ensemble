import os

year_0 = "/glade/derecho/scratch/bwest/drought-ensemble/domains/potomac/testing/raw_runs/fc2a5b1d5cf4b8279c7d6a98de84df89f0bc21961f7fd18bac11228fec55ac9c"
year_1 = "/glade/derecho/scratch/bwest/drought-ensemble/domains/potomac/testing/raw_runs/c6a8270c59d4b1edfca7b7ea99723a58e219f902b69b3d6b1fa8ba8db8b82387"
year_2 = "/glade/derecho/scratch/bwest/drought-ensemble/domains/potomac/testing/raw_runs/67af0c575def0eb3b36403eb3b1cc5f7c5af80d7a9ab86c2946749024619ec5c"

os.system(f"ncrcat -D 1 -O ../domains/potomac/testing/raw_runs/fc2a5b1d5cf4b8279c7d6a98de84df89f0bc21961f7fd18bac11228fec55ac9c/run.out.00001.nc ../domains/potomac/testing/raw_runs/c6a8270c59d4b1edfca7b7ea99723a58e219f902b69b3d6b1fa8ba8db8b82387/run.out.00001.nc ../domains/potomac/testing/raw_runs/67af0c575def0eb3b36403eb3b1cc5f7c5af80d7a9ab86c2946749024619ec5c/run.out.00001.nc ./output.nc")

# ncrcat -D 1 -O ../domains/potomac/testing/raw_runs/fc2a5b1d5cf4b8279c7d6a98de84df89f0bc21961f7fd18bac11228fec55ac9c/run.out.00001.nc ../domains/potomac/testing/raw_runs/c6a8270c59d4b1edfca7b7ea99723a58e219f902b69b3d6b1fa8ba8db8b82387/run.out.00001.nc ../domains/potomac/testing/raw_runs/67af0c575def0eb3b36403eb3b1cc5f7c5af80d7a9ab86c2946749024619ec5c/run.out.00001.nc ./output.nc





