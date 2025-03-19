import os
import shutil
import parflow as pf

def do_new_run(domain_name, run_name):
    domains_folder = "domains/outputs/"
    shutil.copytree(f"{domains_folder}/{domain_name}", f"{domains_folder}/{domain_name}_{run_name}")
    pf.load_run(f"{domains_folder}/{domain_name}_{run_name}/{run_name}.yaml")