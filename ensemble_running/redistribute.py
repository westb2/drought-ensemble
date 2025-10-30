import configparser
import subsettools as st

def get_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    return config

domain_name = "potomac"
TESTING = False
wetness_types = ["dry","average"]
config_file = f"/glade/derecho/scratch/bwest/drought-ensemble/domains/{domain_name}/config.ini"
config = get_config(config_file)
if TESTING:
    base_path = f"/glade/derecho/scratch/bwest/drought-ensemble/domains/{domain_name}/testing/inputs"
else:
    base_path = f"/glade/derecho/scratch/bwest/drought-ensemble/domains/{domain_name}/inputs"

P = int(config.get('DEFAULT', 'P'))
Q = int(config.get('DEFAULT', 'Q'))

for wetness_type in wetness_types:
    runscript_path= f"{base_path}/{domain_name}_{wetness_type}/run.yaml"
    print(runscript_path)
    runscript_path = st.dist_run(
            topo_p=P,
            topo_q=Q,
            runscript_path=runscript_path,
            dist_clim_forcing=True,
        )