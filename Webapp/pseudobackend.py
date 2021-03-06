import mariadb
import pandas as pd
import sys

import os
import sqlite3
import time

try:
    connn = mariadb.connect(
        user="root",
        password="admin1234",
        host="127.0.0.1",
        port=3306,
    )
except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

# Get Cursor not used
cur = connn.cursor()

#moved to outside to mimic actual backend (cant set up until we have packets)
query = """select history.cells.KeyTime, Location, CellNo, VoltValue, ResistValue, TempValue, TotalVolt, TotalCurrent, AmbientTemp from history.cells, info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId and history.bankdata.KeyTime = history.cells.KeyTime and info.bankinfo.BankId = history.cells.BankId"""

#used for battery life (parameterizing this is actually slower)
query2 = """select history.bankdata.KeyTime, Location, AmbientTemp from info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId"""

#used for map with live data (will also include the colors) not currently used as trimming was done with a normal query and pandas filters
query3 = """select history.cells.KeyTime, Location from history.cells, info.bankinfo 
        where info.bankinfo.BankId = history.cells.BankId and KeyTime in (select max(KeyTime) from history.cells, info.bankinfo 
                                                                            where info.bankinfo.BankId = history.cells.BankId group by Location)"""
                                                                            

df1 = pd.read_sql_query(query, connn)

#CurrentBaseline.csv is our battery commisioning feature
df2 = pd.read_csv("CurrentBaseline.csv")
df2.columns = ["Location", "CellNo","VoltMean", "ResistMean", "TempMean"]

df3 = df1.groupby(["KeyTime","Location"], as_index=False).mean()
#calculates temp per location and keytime
df3=df3.rename(columns = {'TempValue':'TempValuetest'})

#result = pd.merge(df1, df2 on=["Location","CellNo"])
result = df1.merge(df2[["Location", "CellNo","ResistMean"]],on=["Location","CellNo"]).merge(df3[["KeyTime","Location","TempValuetest"]],on=["KeyTime","Location"])

#all normal tags are blue, I separated all different tags into columns to avoid stacking errors (this could be useful?)
#ease of changing tagnames
tagnames = ["+-30% Resist", "AmbT > 30", "Cell Temp > AmbT + 3", "Cell Temp > Temp avg + 3", "Cell Temp > 25"]

result[tagnames[0]] = "clear"
result[tagnames[1]] = "clear"
result[tagnames[2]] = "clear"
result[tagnames[3]] = "clear"
result[tagnames[4]] = "clear"

#though this looks repeatative it is ALOT faster than the for loop
#tag number 1 30% deviation from set means (adjacent cells to this one need to be logged)
result.loc[(result["ResistValue"] <= .70*result["ResistMean"]) | (result["ResistValue"] >= 1.3*result["ResistMean"]), tagnames[0]] = "Medium Alert" #"+-30% Resist"
#tag number 2 ambient temp > 30 (current none in our dataset)
result.loc[(result["AmbientTemp"] > 30), tagnames[1]] = "High Alert" #"AmbT > 30"
#tag number 3 cell > total temp + 3
result.loc[(result["TempValue"] > 3+result["AmbientTemp"]), tagnames[2]] = "High Alert" #"Cell Temp > AmbT+3"
#tag 4 (idk what ripple current is yet)
#result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:
result.loc[(result["TempValue"] > 3+ result["TempValuetest"]), tagnames[4]] = "High Alert"
#tag 5
result.loc[(result["TempValue"] > 25), tagnames[4]] = "Medium Alert" #"Cell Temp > 25"

#setting up locs for map
#locs = pd.read_csv("Locs.csv")

#this is made so the website can be constantly querying to check if works with live data
ambientdataframe = pd.read_sql_query(query2, connn)

if os.path.exists("testdb.db"):
    os.remove("testdb.db")
conn = sqlite3.connect("testdb.db", check_same_thread=False)
result.drop(["ResistMean"], axis=1)
result.to_sql("test", con=conn, if_exists='append', index=False)

ambientdataframe.to_sql("test2", con=conn, if_exists='append', index=False)

def getdb(conn):
    #this will simply return the a query of a db (made to better mimic an actual system when we have the packets and a separate backend)
    result = pd.read_sql_query("Select * FROM test where KeyTime", conn)
    result["KeyTime"]=result.KeyTime.astype('datetime64[ns]')
    return result

def getambient(conn):
    #this will simply return the a query of a db (made to better mimic an actual system when we have the packets and a separate backend)
    ambientdataframe = pd.read_sql_query("Select * From test2", conn)
    ambientdataframe["KeyTime"]=ambientdataframe.KeyTime.astype('datetime64[ns]')
    return ambientdataframe


#start = time.time()
#print(getdb(conn))
#end = time.time()
#print(end - start)

#print(getambient(conn))