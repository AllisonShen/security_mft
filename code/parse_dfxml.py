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


import xml.etree.ElementTree as ET
from lxml import etree


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

output_path =f"{conf['output_path']}/{seed}" 
try: 
    os.mkdir(output_path) 
    print(f"Directory {output_path} created")
except OSError as error: 
    print(error) 

mode = conf['mode']

# print(pathToDxml)
# print(output_path)
print(f"mode: {mode}")

#parameter settings

#start time
start_time = datetime.now()

setDuplicate = set()
parentNodeInfo = dict()

#parameter settings end

def updt(total, progress):
    """
    Displays or updates a console progress bar.

    Original source: https://stackoverflow.com/a/15860757/1391441
    """
    barLength, status = 20, ""
    progress = float(progress) / float(total)
    if progress >= 1.:
        progress, status = 1, "\r\n"
    block = int(round(barLength * progress))
    text = "\r[{}] {:.0f}% {}".format(
        "#" * block + "-" * (barLength - block), round(progress * 100, 0),
        status)
    sys.stdout.write(text)
    sys.stdout.flush()
def parseDxml_lxml(pathToFile):
  start_time = datetime.now()

  tree = etree.parse(pathToFile)
  root = tree.getroot()
  df, byteRunDf = showInfo_lxml(root)

  csv_filename = f"{output_path}/parse_result_{os.path.basename(pathToFile)[:-6]}_{seed}.csv"
  csv_filename_byte_run = f"{output_path}/parse_result_{os.path.basename(pathToFile)[:-6]}_byte_runs_{seed}.csv"
  df.to_csv (csv_filename, index = False, header=True)
  byteRunDf.to_csv (csv_filename_byte_run, index = False, header=True)
  print(f"output_path: {csv_filename}")
  print(f"output_path_byte_run: {csv_filename_byte_run}")
  end_time = datetime.now()
  print(f"Duration of parsing data for {os.path.basename(pathToFile)[:-6]}: {end_time - start_time}")
  return csv_filename_byte_run

def dictAssign(tempDict, key, item):
  # print(f"{tempDict}")
  # print(f"{key}")
  # print(f"{item}")
  global setDuplicate
  global parentNodeInfo
  nodeIter = 1
  #if duplicate
  if(key in tempDict):
    while True:
      if(f"{key}_{nodeIter}" in tempDict):
        nodeIter = nodeIter+1
      else:
        break
    # if(tempDict[key]):
    setDuplicate.add(key)
    # print(parentNodeInfo)
    strFirst = f"{key}_{nodeIter}"
    strSpecify = f"{key}_{nodeIter}"
    tempDict[strSpecify] = item
  else:
    tempDict[key] = item
    nodeIter = 0

  return tempDict, nodeIter

def rename(s):
  s = re.sub(r'{.+}', '', s)
  # print(s)
  return s
def showInfo_lxml(root):
  test = 0
  listColumns = ['fileobject_id']
  df = pd.DataFrame(columns=listColumns)
  byteRunDf = pd.DataFrame(columns=listColumns)
  fileobjects = root.findall('.//{http://www.forensicswiki.org/wiki/Category:Digital_Forensics_XML}fileobject')
  for fileobject_id, fileobject in enumerate(fileobjects):
    tempDict = {}
    byteRunTempDict = {}
    # tempDict['fileobject_id'] = fileobject_id
    
    tempDict = dictAssign(tempDict,"fileobject_id",fileobject_id)[0]
    
    for node in fileobject.iter():
      if(rename(node.tag) == "byte_run"):
        byteRunTempDict["fileobject_id"] = fileobject_id
        byteRunTempDict[rename(node.tag)] = node.text

        for key, item in node.attrib.items():
          byteRunTempDict[rename(key)] = item
        byteRunDf = byteRunDf.append(byteRunTempDict, ignore_index=True)

      else:
        global parentNodeInfo
        if(node.getparent() is not None):
          # if(key in tempDict.keys())
          parentNodeInfo[rename(node.tag)] = rename(node.getparent().tag)
        else:
          parentNodeInfo[rename(node.tag)] = None

        # if(mode == 'test'):
        #   pass
          # if(test < 1):
          #   print(f"id: {fileobject_id}, tag: {rename(node.tag)}")
          #   print(f"id: {fileobject_id}, text: {node.text}")
          #   print(f"id: {fileobject_id}, attributes: {node.attrib}")
        # print(rename(node.tag))
        # tempDict[rename(node.tag)] = node.text
        tempDict, nodeIter = dictAssign(tempDict,rename(node.tag),node.text)

        # tempDict['attrib'] = node.attrib
        if(node.attrib): #if the attrib exists
          for key, item in node.attrib.items():
            # print(f"attrib: key: {key}, item: {item}")
            # tempDict = dictAssign(tempDict,rename(key),item)
            if(nodeIter != 0):
              tempDict[f'{rename(key)}_{rename(node.tag)}_{nodeIter}'] = item
            else:
              tempDict[f'{rename(key)}_{rename(node.tag)}'] = item
    df = df.append(tempDict, ignore_index=True)
    
    test+=1

    updt(len(fileobjects), fileobject_id + 1)
    if(mode == 'test'):
      if(test>20):
        print(f"fileobject 0 ~ {fileobject_id} is done. Then break...")
        break

  return df, byteRunDf

#main
test = 0
for eachFile in glob.glob(f"{pathToDxml}/*.dfxml"):
  print(f"parsing {eachFile} ...")
  # if (os.path.exists(f"{pathToDxml}/parse_result_{os.path.basename(eachFile)[:-6]}.csv")):
  #   print(f"{pathToDxml}/parse_result_{os.path.basename(eachFile)[:-6]}.csv exists, move to next dfxml file.")
  #   continue
  
  # print(f"size (bytes): {os.path.getsize(eachFile)}")
  # print(f"basename (no extention): {os.path.basename(eachFile)[:-6]}")
  last_output_csv_file = parseDxml_lxml(eachFile)
  test+=1
  if(mode == "test"):
    if(test==0):
      break
print(f"the following columns has duplicated values: {setDuplicate}")
print(f"value of the len(setDuplicate): {len(setDuplicate)}")

#show duration
end_time_total = datetime.now()
print('Duration of finishing parsing all dfxml files: {}'.format(end_time_total - start_time))

#test result

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
# if(mode == "test"):
#   filepath = glob.glob(f"{path}/parse_result_fourth_fifth.csv")[0]#"/content/drive/MyDrive/security_mft/dfxml_files/parse_result_fourth_fifth.csv"
# else:
#   filepath = glob.glob(f"{pathToDxml}/*.csv")[0]#"/content/drive/MyDrive/security_mft/output/parse_result_fourth_fifth.csv"
filepath = last_output_csv_file
print(filepath)
df = pd.read_csv(filepath)
print(f"How many columns: {len(df.columns)}")
print(f"column names: {df.columns}")
print(df.head(50))