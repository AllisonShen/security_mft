#!/usr/bin/env python3
#
# adiff.py:
# record sector content changes for deleted files in
# sequential disk snapshots
#
# 10/6-26/15: (jhj) original coding...
# 11/04/15: (jhj) removed idifference summary flag - was crashing on M57-pat
# 11/10/15: (jhj) fixed DFXML parser bug (added handling for continuation byte_run(s)
# 02/29/16: (jhj) misc cleanup
# 04/06/16: (jhj) fixed bug (added 'byte_run_' exclusion)
# 04/28/16: (jhj) added deleted.db creation and cleaning code
# 05/04/16: (jhj) add resident/nonresident parsing and db entry;
#                 add frag counter parsing and db entry;
#                 add progress counters
# 06/06/16: (jhj) fixed temp.dfxml parsing bug: some entries have two data blocks, so
#                     look for original_fileobject tag before processing

# for debugging
#import pdb
#pdb.set_trace()
#

import os
import sys
import hashlib
import sqlite3
import binascii
from datetime import datetime
from lxml import objectify as xml_objectify
import yaml
import pandas as pd
import numpy as np
import glob
import hashlib
import re
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
output_path =f"{conf['output_path']}" 

try: 
    os.mkdir(output_path) 
    print(f"Directory {output_path} created")
except OSError as error: 
    print(error) 

output_path =f"{conf['output_path']}{seed}" 
try: 
    os.mkdir(output_path) 
    print(f"Directory {output_path} created")
except OSError as error: 
    print(error) 

mode = conf['mode']
one_file_path = conf['dfxml_path']
IDIFF2_PATH= conf['IDIFF2_PATH']
BLOCK_SIZE=conf['BLOCK_SIZE'] # 512,4096,... use image drive block size
SECTOR_SIZE = conf['SECTOR_SIZE']
IMAGE_LIST= conf['IMAGE_LIST']
HAVE_TEMP_DFXML= conf['HAVE_TEMP_DFXML'] 

### User-set vars...
# IDIFF2_PATH='/media/khan/resident_files/dfxml-master/python/idifference2.py'
# BLOCK_SIZE=512 # 512,4096,... use image drive block size
# SECTOR_SIZE = 512
# IMAGE_LIST=[ '/media/khan/CNIT523/project/fourth.img',
#         '/media/khan/CNIT523/project/fifth.img',
#         '/media/khan/CNIT523/project/sixth.img',
#         '/media/khan/CNIT523/project/seventh.img']
# HAVE_TEMP_DFXML= False # True if you already have a temp.dfxml file (idiff output for images 1-2), otherwise False; saves time


### end User-set vars
start_time = datetime.now()
setDuplicate = set()
parentNodeInfo = dict()

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
def xml_to_dict(xml_str):
    """ Convert xml to dict, using lxml v3.4.2 xml processing library """
    def xml_to_dict_recursion(xml_object):
        dict_object = xml_object.__dict__
        if not dict_object:
            return xml_object
        for key, value in dict_object.items():
            dict_object[key] = xml_to_dict_recursion(value)
        return dict_object
    return xml_to_dict_recursion(xml_objectify.fromstring(xml_str))
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
def find_deleted(i1,i2):
    # find deleted files using idiff then parsing dfxml outfile
    ### run idiff, write output to temp file - note that we are not catching errors from idifference2.py... (we should)
    if (HAVE_TEMP_DFXML == False): # if you already have a temp.dfxml file, set above to True to skip this (slow) step
        cmd='python3 '+IDIFF2_PATH+' -x temp.dfxml '+i1+' '+i2
        print('Running: '+cmd)
        os.system(cmd)
    ### parse dfxml for deleted files and byte runs; put into sqlite db
    # FYI, db schema:
    #   CREATE TABLE deleted_files(
    #     img TEXT,
    #     filename TEXT,
    #     resident BOOLEAN,
    #     offset INTEGER,
    #     frags INTEGER,
    #     md5 TEXT);
    # open db
    conn_c = sqlite3.connect("deleted.db")
    c = conn_c.cursor()
    # crude (but fast?) method follows; comment out if better method is implemented (XTREE?)
    counter = 0
    img = i1 # set image identifier, img = (TEXT) = path to image_i1
    f_img = open(i1,'rb') # open image file for subsequent sector hashing

    #open temp.dfxml
    pathToFile = 'temp.dfxml'
    start_time = datetime.now()
    tree = etree.parse(pathToFile)
    root = tree.getroot()
    test = 0
    listColumns = ['fileobject_id']
    df = pd.DataFrame(columns=listColumns)
    byteRunDf = pd.DataFrame(columns=listColumns)
    fileobjects = root.findall('.//{http://www.forensicswiki.org/wiki/Category:Digital_Forensics_XML}fileobject')
    for fileobject_id, fileobject in enumerate(fileobjects):
        tempDict = {}
        byteRunTempDict = {}
        frags=0 # initialize
        ready_to_parse = False
        tempDict = dictAssign(tempDict,"fileobject_id",fileobject_id)[0]
        for node in fileobject.iter():
            saved_img_offset = 0 #initialize
            if(rename(node.tag) == "byte_run"):
                byteRunTempDict = {} #initilize byterun dict
                byteRunTempDict["fileobject_id"] = fileobject_id
                byteRunTempDict[rename(node.tag)] = node.text

                for key, item in node.attrib.items():
                  byteRunTempDict[rename(key)] = item
                byteRunDf = byteRunDf.append(byteRunTempDict, ignore_index=True)

                #more 
                value = "resident"
                resident = False
                # if value in byteRunTempDict:
                #     if('deleted_file_fileobject' in tempDict):
                #         if(int(tempDict['deleted_file_fileobject'])==1):
                #             print("Find deleted file & resident file!")
                #             resident = True
                if(("type" in byteRunTempDict) and ("deleted_file_fileobject" in tempDict)):
                    if(byteRunTempDict['type']=="resident"):
                        resident = True
                if("original_fileobject" in tempDict):
                    ready_to_parse = True
                if(ready_to_parse == True):
                    if "img_offset" in byteRunTempDict:
                        frags+=1
                    if "filename" in tempDict:
                        filename = tempDict['filename']
                    if "byte_run" in byteRunTempDict:
                        if "fill" not in byteRunTempDict:
                            if (("uncompressed_len" in byteRunTempDict) and ("file_offset" in byteRunTempDict)):
                                file_offset = int(byteRunTempDict['file_offset'])
                                offset = saved_img_offset + file_offset
                                length = int(byteRunTempDict['uncompressed_len'])
                            else:
                                offset = int(byteRunTempDict['img_offset'])
                                length = int(byteRunTempDict['len'])
                                saved_img_offset = offset
                            md5 = compute_sector_md5(f_img,offset) # params are an open file handle and offset in bytes
                            print(f"First Insert: img,filename,resident,offset,frags,md5:")
                            print(f"{img}, {filename}, {resident}, {offset}, {frags}, {md5}")
                            insert_values = (img,filename,resident,offset,frags,md5)
                            c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
                            length = length - SECTOR_SIZE # will be greater than 0 if more than one sector in this byte run
                            while length > 0:
                                offset = offset+SECTOR_SIZE
                                md5 = compute_sector_md5(f_img,offset)
                                # print(f"Second Insert: img,filename,resident,offset,frags,md5:")
                                # print(f"{img}, {filename}, {resident}, {offset}, {frags}, {md5}")
                                insert_values = (img,filename,resident,offset,frags,md5)
                                c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
                                length = length - SECTOR_SIZE # will still be greater than 0 if more sectors in this byte run
            else:
                global parentNodeInfo
                if(node.getparent() is not None):
                    # if(key in tempDict.keys())
                    parentNodeInfo[rename(node.tag)] = rename(node.getparent().tag)
                else:
                    parentNodeInfo[rename(node.tag)] = None
                tempDict, nodeIter = dictAssign(tempDict,rename(node.tag),node.text)
            if(node.attrib): #if the attrib exists
                for key, item in node.attrib.items():
                # print(f"attrib: key: {key}, item: {item}")
                # tempDict = dictAssign(tempDict,rename(key),item)
                    if(nodeIter != 0):
                        tempDict[f'{rename(key)}_{rename(node.tag)}_{nodeIter}'] = item
                    else:
                        tempDict[f'{rename(key)}_{rename(node.tag)}'] = item
        df = df.append(tempDict, ignore_index=True)
        # all results for one fileobject done

        if('deleted_file_fileobject' in tempDict):
            if(int(tempDict['deleted_file_fileobject'])==1):
                print("Find deleted file!")
                counter+=1 # this and next line to show processing progress
                print(f"processing deleted file {counter} from the whole file")
                print(str(counter)+'\r',end="")

        test +=1
        updt(len(fileobjects), fileobject_id + 1)
        if(mode == 'test'):
            if(test>20):
                print(f"fileobject 0 ~ {fileobject_id} is done. Then break...")
                break
    # return df, byteRunDf
    csv_filename = f"{output_path}/parse_result_{os.path.basename(pathToFile)[:-6]}_{seed}.csv"
    csv_filename_byte_run = f"{output_path}/parse_result_{os.path.basename(pathToFile)[:-6]}_byte_runs_{seed}.csv"
    df.to_csv (csv_filename, index = False, header=True)
    byteRunDf.to_csv (csv_filename_byte_run, index = False, header=True)
    print(f"output_path: {csv_filename}")
    print(f"output_path_byte_run: {csv_filename_byte_run}")
    end_time = datetime.now()
    print(f"Duration of parsing data for {os.path.basename(pathToFile)[:-6]}: {end_time - start_time}")
    print(f"csv_filename_byte_run: {csv_filename_byte_run}")

    conn_c.commit()
    conn_c.close()
    f_img.close()
    print('\n')



    # with open('temp.dfxml','r') as fi:


    #     print('Processing files in temp.dfxml (NOTE: 0 size files are counted but not loaded into DB):')
    #     for line in fi:
    #         if 'delta:deleted_file="1"' in line: # process a deleted file line (one element in the DFXML file)
    #             counter+=1 # this and next line to show processing progress
    #             print(f"processing deleted file {counter} from the whole file")
    #             print(str(counter)+'\r',end="")
    #             if('type="resident"' in line): #resident = True/ False (BOOLEAN)
    #                 resident = True
    #             else:
    #                 resident = False
    #             frags=0 # initialize
    #             ready_to_parse = False
    #             for item in line.split("<"):
    #                 if 'delta:original_fileobject' in item:
    #                     ready_to_parse = True
    #                     continue
    #                 if ready_to_parse:
    #                     if ('img_offset="' in item):
    #                         frags+=1
    #                     if ("filename>" in item) and ("/filename" not in item):
    #                         filename = item [ len("filename>") : ] #filename after >...
    #                     if ("byte_run" in item) and ("byte_runs" not in item) and ("byte_run_" not in item): # won't write to DB if no byte_run (prob size=0)
    #                         xml_string = item
    #                         print(xml_to_dict(xml_string))
    #                         item_values = item.split('"')
    #                         if (item_values[2] == ' fill=') and (item_values[3] == '0'): # byte_run of all zeros not worth tracking
    #                             break # breaks out of the "for item" loop
    #                         if ((item_values[0] == 'byte_run file_offset=') and (item_values[2] == ' uncompressed_len=')): # continuation byte_run
    #                             print(f"print item_values[1]: {item_values[1]}")
    #                             print(f"print item_values[3]: {item_values[3]}")

    #                             file_offset = int(item_values[1])

    #                             offset = saved_img_offset + file_offset #initilization problem? with saved_img_offset
    #                             length = int(item_values[3])

    #                             # if(length < 700): #only process non-resident files
    #                             #     continue
    #                         else:
    #                             if(int(item_values[1])<700): #only process non-resident files
    #                                 print(f"Ignore, this is a resident file with length {item_values[1]} <700")
    #                                 continue
    #                             offset = int(item_values[5]) # "img_offset" value in the DFXML file
    #                             print(f"print item_values[5]: {item_values[5]}")
    #                             print(f"print item_values[7]: {item_values[7]}")
    #                             isINT = True
    #                             try:
    #                                 int(item_values[7])
    #                             except ValueError:
    #                                 isINT = False
    #                             if isINT:
    #                                 length = int(item_values[7]) # "uncompressed_len" value in the DFXML file
    #                             else:
    #                                 print(f"parsing error: img_offset is a string {item_values[7]}, jump to the next value {item_values[9]}")
    #                                 length = item_values[9]
                                
    #                             saved_img_offset = offset # save the base offset for continuation byte_run(s)
    #                         md5 = compute_sector_md5(f_img,offset) # params are an open file handle and offset in bytes
    #                         print(f"First Insert: img,filename,resident,offset,frags,md5:")
    #                         print(f"{img}, {filename}, {resident}, {offset}, {frags}, {md5}")
    #                         insert_values = (img,filename,resident,offset,frags,md5)
    #                         c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
    #                         length = length - SECTOR_SIZE # will be greater than 0 if more than one sector in this byte run
    #                         while length > 0:
    #                             offset = offset+SECTOR_SIZE
    #                             md5 = compute_sector_md5(f_img,offset)
    #                             # print(f"Second Insert: img,filename,resident,offset,frags,md5:")
    #                             # print(f"{img}, {filename}, {resident}, {offset}, {frags}, {md5}")
    #                             insert_values = (img,filename,resident,offset,frags,md5)
    #                             c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
    #                             length = length - SECTOR_SIZE # will still be greater than 0 if more sectors in this byte run
    # # close db and img file
    # conn_c.commit()
    # conn_c.close()
    # f_img.close()
    # print('\n')

def compute_sector_md5(fh,offset):
    fh.seek(offset) # seek takes bytes
    sector_contents = fh.read(SECTOR_SIZE) # assumes read returns binary (bytes object)
    r = hashlib.md5(sector_contents).digest()
    r_string = (str(binascii.b2a_hex(r)))[2:-1]
    return r_string

def hash_subsequent(img):
    print('Processing: '+img)
    counter = 0
    print('Processing sectors in deleted.db:')
    # hash sectors from base image deleted files as they exist in subsequent images
    f_img = open(img,'rb') # open image file for subsequent sector hashing
    conn_c = sqlite3.connect("deleted.db")
    c = conn_c.cursor()
    query="SELECT filename,resident,offset,frags from deleted_files where img=\""+IMAGE_LIST[0]+"\";" # get rows from first (base) image only
    c.execute(query)
    for row in c.fetchall():
        counter+=1
        print(str(counter)+'\r',end="")
        filename,resident,offset,frags = row
        md5 = compute_sector_md5(f_img,offset)
        insert_values = (img,filename,resident,offset,frags,md5)
        c.execute('INSERT into deleted_files VALUES (?,?,?,?,?,?)', insert_values)
    conn_c.commit()
    conn_c.close()
    f_img.close()
    print('\n')

if __name__ == "__main__":
    #<?xml version="1.0" encoding="UTF-8"?>
#     xml_string = """<Response><NewOrderResp>
# <IndustryType>Test</IndustryType><SomeData><SomeNestedData1>1234</SomeNestedData1>
# <SomeNestedData2>3455</SomeNestedData2></SomeData></NewOrderResp></Response>"""

#     print(xml_to_dict(xml_string))
    # run: python3 adiff.py &>console.log
    # need better option handling, help/usage
    print('Start: '+str(datetime.now()))
    # create or clean deleted.db as necessary
    if not (os.path.isfile('deleted.db')): # create db file if it does not exist
        #cmd='sqlite3 deleted.db < create_deleted.sql'
        cmd='sqlite3 deleted.db "CREATE TABLE deleted_files(img TEXT, filename TEXT, resident BOOLEAN, offset INTEGER, frags INTEGER, md5 TEXT);"'
        print('Running: '+cmd)
        os.system(cmd)
    else: # empty the db file if it does exist
        cmd='sqlite3 deleted.db "DELETE from deleted_files;"'
        print('Running: '+cmd)
        os.system(cmd)
    find_deleted(IMAGE_LIST[0],IMAGE_LIST[1])
    for i in range(1,len(IMAGE_LIST)): # hash sectors in other images and store in DB
        hash_subsequent(IMAGE_LIST[i])
    print('Stop: '+str(datetime.now()))

