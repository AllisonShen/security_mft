import yaml
import pandas as pd
import numpy as np
import os
import glob
import sys
import hashlib
import re
from datetime import datetime
import time
import re

# Load config file for experiment
try:
    config_path = sys.argv[1]
    # print(config_path)
    seed = int(sys.argv[2])
    # print(seed)
    conf = yaml.load(open(config_path,'r'))
    # print(conf)
    
except:
    print('Usage: python3 run_exp.py <config file path> <seed>')
    sys.exit()

exp_name = conf['exp_name']+'_sd_'+str(seed)
print('Experiment:')
print('\t',exp_name)

np.random.seed(seed)


pathToDxml = conf['data_path']

output_path =f"{conf['output_path']}{seed}/" 
# try: 
#     os.mkdir(output_path) 
#     print(f"Directory {output_path} created")
# except OSError as error: 
#     print(error) 

mode = conf['mode']

# print(pathToDxml)
# print(output_path)
print(f"mode: {mode}")


for eachFile in glob.glob(f"{output_path}/*{seed}.csv"):
  print(f"analyzing {eachFile} ...")
  df = pd.read_csv(eachFile)
  for column in df.columns:
    df_count_values = df[column].value_counts()
    print(df_count_values)
    csv_filename = f"{output_path}/{os.path.basename(eachFile)[:-6]}_analysis.csv"
    df_count_values.to_csv (csv_filename, index = False, header=True)

