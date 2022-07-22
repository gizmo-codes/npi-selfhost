from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import glob, os
import sqlite3
import shutil
import urllib.request, urllib.error
from dateutil.relativedelta import relativedelta
import pandas as pd
import time
import math

# https://download.cms.gov/nppes/NPI_Files.html

# Function to download monthly NPPES data.
def download_and_unzip(url,mon,year, extract_to='.'):
    try:
        http_response = urlopen(url)
        print(mon + "-" + year + " fetch successful.")
        print("Preparing extraction...")
        zipfile = ZipFile(BytesIO(http_response.read()))
        print("Extracting...")
        zipfile.extractall(path=extract_to)
    except urllib.error.HTTPError as e:
        # Return code error (e.g. 404, 501, ...)
        # If the above try failed, attempt to grab previous months data.
        print('HTTPError: {}'.format(e.code))
        print(mon + "-" + year + " fetch FAILED.")
        previousDate = datetime.now() - relativedelta(months=1)
        prevMonth = previousDate.strftime("%B")
        prevYear = previousDate.strftime("%Y")
        print("Attempting to fetch previous month (" + prevMonth+"-"+prevYear+")")
        download_and_unzip("https://download.cms.gov/nppes/NPPES_Data_Dissemination_" + prevMonth + "_" + prevYear  + ".zip",prevMonth,prevYear,"npidata") # Download file for the month
    except urllib.error.URLError as e:
        # Not an HTTP-specific error (e.g. connection refused)
        print('URLError: {}'.format(e.reason))


# Get current (full) month and 4 digit year
nowDate = datetime.now()
nowMonth = nowDate.strftime("%B")
nowYear = nowDate.strftime("%Y")
# Fetch current (month/year) data.
print("----------- Fetching Data -----------")
download_and_unzip("https://download.cms.gov/nppes/NPPES_Data_Dissemination_" + nowMonth + "_" + nowYear  + ".zip",nowMonth,nowYear,"npidata") # Download file for the month

# Manage downloaded/extracted files.
print("Extraction complete.\nManaging files...")
files = glob.glob('./npidata/*FileHeader*')
for file in files:
    if os.path.exists(file):
        os.remove(file)

files = glob.glob('./npidata/*npidata*')
for file in files:
    if os.path.exists(file):
        shutil.move(file,"./npi.csv")

files = glob.glob('./npidata/*')
for file in files:
    if os.path.exists(file):
        os.remove(file)
print("File management complete.")

# Rebuild database.
print("\n----------- Updating database -----------")
st = time.time()
conn = sqlite3.connect('./db/npi.db')
et = time.time() - st
print("Connetion to DB complete after", round(et,2), "seconds.")
print("Dropping table...")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS npi")
et = time.time() - st
print("Drop table complete after",round(et,2),"seconds.")
chunkn = 1
file = glob.glob('./npi.csv')

# Grab row count for CSV -> SQLite print feedback
def row_count(file):
    with open(file, 'rb') as f:
        for i, l in enumerate(f):
            pass
    return i
print("Preparing CSV -> SQLite...")

# Grab row count for print feedback.
rows = row_count('./npi.csv')
chunks = 30000
totalchunks = math.ceil(rows/chunks)

print("\n----------- CSV -> SQLite -----------")
# Add CSV to SQLite database
for npi_data in pd.read_csv('npi.csv',chunksize=chunks, low_memory=False,keep_default_na=False):
    ct = time.time()
    npi_data.to_sql("npi", conn, if_exists='append', index=False)
    et = time.time() - ct
    pct = chunkn/totalchunks
    print("Chunk ("+str(chunkn)+"/"+str(totalchunks)+") "+str(round(pct*100,2))+"% complete:",round(et,2),"seconds.")
    #print("Chunk ("+str(chunkn)+"/"+str(totalchunks)+") "+str(round(pct*100,2))+"% complete.")
    chunkn = chunkn+1
et = time.time() - st
print("CSV -> SQLite complete after",round(et,2),"seconds.")

# Create indexes on newly built database
print("\n----------- Creating Index(s) -----------")
ist = time.time()
cur.execute("Create INDEX Idx1 ON npi([Provider Business Mailing Address Telephone Number])")
et = time.time() - ist
print("Idx1 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx2 ON npi([Provider Business Practice Location Address Telephone Number])")
et = time.time() - it
print("Idx2 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx3 ON npi([NPI])")
et = time.time() - it
print("Idx3 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx4 ON npi([Provider First Name])")
et = time.time() - it
print("Idx4 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx5 ON npi([Provider Last Name (Legal Name)])")
et = time.time() - it
print("Idx5 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx6 ON npi([Provider Business Mailing Address State Name])")
et = time.time() - it
print("Idx6 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX Idx7 ON npi([Provider Business Practice Location Address State Name])")
et = time.time() - it
print("Idx7 creation complete after",round(et,2),"seconds.")
conn.close()
et = time.time() - ist
print("Index creation complete after",round(et,2),"seconds.")

# Remove unused CSV files.
print("\nRemoving CSV files...")
files = glob.glob('./*.csv')
for file in files:
    if os.path.exists(file):
        os.remove(file)
print("Removal finihsed.")

# Script complete
et = time.time() - st
minutes, seconds = divmod(et, 60)
print("\nBuild complete after "+str(math.floor(minutes))+"m "+str(math.floor(seconds))+"s.")