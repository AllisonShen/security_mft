import pandas as pd
import sqlite3 as sq

pd.set_option('display.max_rows',None)
pd.set_option('display.max_columns',None)


sql_data = "deleted.db"
conn = sq.connect(sql_data)
df_read_sql = pd.read_sql("select * from deleted_files", conn)

csv_filename = f"deleted.csv"
df_read_sql.to_csv (csv_filename, index = False, header=True)

print(df_read_sql.head(100))