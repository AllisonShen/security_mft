import pandas as pd
import numpy as np
import os

filepath = "/content/drive/MyDrive/security_mft/output/1123202101/parse_result_temp_1123202101.csv"
types_fileobject = ["new_file_fileobject", "changed_file_fileobject", "deleted_file_fileobject", "modified_file_fileobject", "original_fileobject", "renamed_file_fileobject"]
shown_columns = ["fileobject_id", "filename","atime", "crtime", "ctime", "mtime"]
output_path = "/content/drive/MyDrive/security_mft/output/"
# output_path = "./output/"
seed = "0224202201"


def filter_by_type(filepath, types_fileobject, shown_columns):
  df = pd.read_csv(filepath)
  df_output = pd.DataFrame()
  # print(df.head())
  for type_fileobject in types_fileobject:
    # print(type_fileobject)
    df_filter_by_type = df.loc[df[type_fileobject] == 1]
    print(df_filter_by_type.head())
    df_filter_by_type = df_filter_by_type[shown_columns]
    df_filter_by_type["type_fileobject"] = type_fileobject[:-11]
    print(df_filter_by_type.head())
    df_output = df_output.append(df_filter_by_type, ignore_index=True)
    # print(df_output.head())
  return df_output

df_output = filter_by_type(filepath, types_fileobject, shown_columns)

#save the results to a CSV file
csv_filename = f"{output_path}filter_{os.path.basename(filepath)[:-11]}_{seed}.csv"
print(csv_filename)
df_output.to_csv (csv_filename, index = False, header=True)
df_output.head()