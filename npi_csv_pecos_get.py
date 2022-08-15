from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
import glob, os
import sqlite3
import shutil
import urllib.request, urllib.error
import pandas as pd
import time
import math

# https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data-viewer?_format=csv
# https://data.cms.gov/resources/order-and-referring-data-dictionary

# PECOS manages practice medicare enrollment into these categories. (?)

# PARTB - Indicates that provider can refer to Part B. (Outpatient [Doctor vists] medical coverage)
# DME   - Indicates that provider can order Durable Medical Equipment.
# HHA   - Indicates that provider can refer to Home Health Agency. (Nurses/Aide comes to you)
# PMD   - Indicates that provider can order Power Mobility Devices.

# Function to download PECOS data.
def download_and_unzip(url, extract_to='.'):
    try:
        http_response = urlopen(url)
        print("PECOS fetch successful.")
        print("Preparing extraction...")
        zipfile = ZipFile(BytesIO(http_response.read()))
        print("Extracting...")
        zipfile.extractall(path=extract_to)
    except urllib.error.HTTPError as e:
        # Return code error (e.g. 404, 501, ...)
        print('HTTPError: {}'.format(e.code))
    except urllib.error.URLError as e:
        # Not an HTTP-specific error (e.g. connection refused)
        print('URLError: {}'.format(e.reason))
        return

# Fetch currently available data.
print("----------- Fetching Data -----------")
download_and_unzip("https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data-viewer?_format=csv","npidata") # Download file for the month

# Manage downloaded/extracted files.
print("Extraction complete.\nManaging files...")
files = glob.glob('./npidata/*Order*')
for file in files:
    if os.path.exists(file):
        shutil.move(file,"./pecos.csv")
        
print("File management complete.")

# Rebuild database.
print("\n----------- Updating database -----------")
st = time.time()
conn = sqlite3.connect('./db/npi.db')
et = time.time() - st
print("Connetion to DB complete after", round(et,2), "seconds.")
print("Dropping table...")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS pecos")
et = time.time() - st
print("Drop table complete after",round(et,2),"seconds.")
chunkn = 1
file = glob.glob('./pecos.csv')

# Grab row count for CSV -> SQLite print feedback
def row_count(file):
    with open(file, 'rb') as f:
        for i, l in enumerate(f):
            pass
    return i
print("Preparing CSV -> SQLite...")

# Grab row count for print feedback.
rows = row_count('./pecos.csv')
chunks = 20000
totalchunks = math.ceil(rows/chunks)

print("\n----------- CSV -> SQLite -----------")
# Add CSV to SQLite database
for npi_data in pd.read_csv('pecos.csv',chunksize=chunks, low_memory=False,keep_default_na=False):
    ct = time.time()
    npi_data.to_sql("pecos", conn, if_exists='append', index=False)
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
cur.execute("Create INDEX PecosIdx1 ON pecos([NPI])")
et = time.time() - ist
print("Idx1 creation complete after",round(et,2),"seconds.")
it = time.time()
cur.execute("Create INDEX PecosIdx2 ON pecos([DME])")
et = time.time() - it
print("Idx2 creation complete after",round(et,2),"seconds.")

conn.close()
et = time.time() - ist
print("Index creation complete after",round(et,2),"seconds.")

# Remove unused CSV files
print("\nRemoving CSV files...")
files = glob.glob('./*.csv')
for file in files:
    if os.path.exists(file):
        os.remove(file)
print("Removal finished.")

# Script complete
et = time.time() - st
minutes, seconds = divmod(et, 60)
print("\nBuild complete after "+str(math.floor(minutes))+"m "+str(math.floor(seconds))+"s.")