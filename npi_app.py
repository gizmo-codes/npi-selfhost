# App Description Here 👯‍♂️
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify
import time
from npyi.npi import search
import requests
from requests.structures import CaseInsensitiveDict
from flask_cors import CORS
import re
import logging
import sqlite3

#TODO: double space between names makes it broken

logging.basicConfig(filename='npi.log', level=logging.DEBUG)
logging.debug('Program initialized')

# Set database path.
db = './db/npi.db'

npi_app = Flask(__name__)
CORS(npi_app)

# API to check for matching NPI number.
@npi_app.route('/npi_check', methods=['POST'])
def npi_check():
    # Local Variables
    isLocal = 0
    x = 0
    rows = {}
    today = date.today()

    # Time stamps for logging/output.
    st = time.time()
    current_time = get_time()
    logging.debug('npi_check Begun %s %s' %(today,current_time))

    # Headers for API calls.
    headers = set_headers()

    # If the user entered >4 numbers into the NPI field, continue.
    if "NPINUMBER" in request.form and len(request.form['NPINUMBER']) > 4:
        # User input NPI number.
        npinumber = request.form['NPINUMBER']

        # Stripping everything that is not a letter.
        npinumber = re.sub(r"[^0-9]", "",npinumber)
        npinumber = re.sub(r'\s+', '', npinumber)

        # NPI numbers are required to be exactly 10 digits.
        if len(npinumber) != 10:
            logging.error('%s NPINUMBER was not 10 digits' %npinumber)
            print("Invalid NPI number [%s]: %s digits provided." %(npinumber,len(npinumber)))
            return "<span style='color: red;'>NPI number must be exactly 10 digits</span>.<br>You provided [%s]: %s digits." %(npinumber,len(npinumber))

        # Log Feedback
        print("Beginning search for NPI: %s" %(npinumber))

        # try NPPES api call.
        try:
            response = search(search_params={'number': npinumber})

        # NPPES API down, use local (SQL) data.
        except requests.exceptions.RequestException as e:
            print("[NPI] NPPES exception:",e)
            response = {}
            response['result_count'] = 0
            isLocal = 1
            con = sqlite3.connect(db)
            cur = con.cursor()
            current_time = get_time()
            logging.debug('NPPES NPI SQL Query start %s %s' %(today,current_time))
            cur.execute("select * from npi where NPI=%s" %(npinumber))
            current_time = get_time()
            logging.debug('NPPES NPI SQL Query end %s %s' %(today,current_time))
            rows = cur.fetchall()
            con.close()

        # No results
        if response['result_count'] == 0 and isLocal == 0 or (len(rows) == 0 and isLocal == 1):
            print("No results")
            return "<span style='color: red;'>No results found</span> for NPI: %s" %npinumber

        # NPPES API working: Set PECOS API query to NPI# recieved from the NPPES API call.
        if isLocal == 0:   
            url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(response['results'][0]['number'])

        # NPPES API NOT working: Set PECOS API query to NPI# recieved from the local NPPES SQL data.
        else: 
            url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(rows[x][0])

        # try PECOS API
        try:
            # PECOS api call.
            pecosresponse = requests.get(url=url,headers=headers)
            pecosdata = pecosresponse.json()

            # NPPES API and PECOS API functioning.
            if isLocal == 0:
                npireturns = resp_formatting(pecosdata, response, x)

            # ONLY NPPES API down.
            else:
                print("-- NPPES API DOWN --\n-- Using local NPPES data... --\n")
                npireturns = rows_formatting(pecosdata,rows,x)
            et = time.time()
            elapsed_time = et - st
            resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
            current_time = get_time()
            logging.debug('npi_check End %s %s' %(today,current_time))
            #print("npi_check end")
            print("Adding Healthcare Worker [ID: "+str(npinumber)+"]")
            print("Data complete")
            return resp
        # PECOS API down.
        except requests.exceptions.RequestException as e:
            print("[NPI] PECOS exception:",e)

            # Only PECOS API down, use local (SQL) data.
            if isLocal == 0:
                print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                # Grab PECOS data from local SQL DB.
                con = sqlite3.connect(db)
                cur = con.cursor()
                logging.debug('NPI SQL Query start %s %s' %(today,current_time))
                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                logging.debug('NPI SQL Query end %s %s' %(today,current_time))
                pecosrows = cur.fetchall()

                # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                if len(pecosrows) == 0:
                    pecos = {'DME': "NO", 'NPI': npinumber}
                    npireturns = resp_formatting(pecos, response, x)
                    et = time.time()
                    elapsed_time = et - st
                    resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                    current_time = get_time()
                    logging.debug('npi_check End %s %s' %(today,current_time))
                    print("Adding Healthcare Worker [ID: "+str(npinumber)+"]")
                    print("Data complete")

                    return resp
                # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                else:
                    for row in pecosrows:
                            # DME data is the 5th column, so element[4].
                            PECOS = row[4]
                            if PECOS == 'Y':
                                pecos = {'DME': "YES", 'NPI': npinumber}
                            else:
                                pecos = {'DME': "NO", 'NPI': npinumber}
                    npireturns = resp_formatting(pecos,response,x)
                    et = time.time()
                    elapsed_time = et - st
                    resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                    current_time = get_time()
                    logging.debug('npi_check End %s %s' %(today,current_time))
                    print("Adding Healthcare Worker [ID: "+str(npinumber)+"]")
                    print("Data complete")

                    return resp
            # Both NPPES and PECOS api down, use local (SQL) data for both.
            else:
                print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                # Grab NPPES and PECOS from local SQL DB.
                con = sqlite3.connect(db)
                cur = con.cursor()
                current_time = get_time()
                logging.debug('NPPES & PECOS NPI SQL Query start %s %s' %(today,current_time))
                # NPPES data.
                cur.execute("select * from npi where [NPI]=%s" %(npinumber))
                npirows = cur.fetchall()
                # PECOS data.
                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                pecosrows = cur.fetchall()
                current_time = get_time()
                logging.debug('NPPES & PECOS NPI SQL Query end %s %s' %(today,current_time))

                # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                if len(npirows) == 0:
                    print("No results")
                    return "<span style='color: red;'>No results found</span> for NPI: %s" %npinumber
                # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                else:
                    # No matching local PECOS data found for given NPI, set PECOS data as empty.
                    if len(pecosrows) == 0:
                        pecosdata = {}
                        npireturns = rows_formatting(pecosdata, npirows, x)
                        et = time.time()
                        elapsed_time = et - st
                        resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                        current_time = get_time()
                        logging.debug('npi_check End %s %s' %(today,current_time))
                        print("Adding Healthcare Worker [ID: "+str(npinumber)+"]")
                        print("Data complete")
                        return resp
                    # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                    else:
                        for row in pecosrows:
                            # DME data is the 5th column, so element[4].
                            PECOS = row[4]
                            if PECOS == 'Y':
                                pecos = {'DME': "YES", 'NPI': npinumber}
                            else:
                                pecos = {'DME': "NO", 'NPI': npinumber}
                        npireturns = rows_formatting(pecos,npirows,x)
                        et = time.time()
                        elapsed_time = et - st
                        resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                        #resp = jsonify('<table>' + npireturns + '</table><br><font color=red>Elapsed Time: ' + str(elapsed_time) + ' seconds</font>')
                        now = datetime.now()
                        current_time = now.strftime("%H:%M:%S")
                        logging.debug('npi_check End %s %s' %(today,current_time))

                        print("Adding Healthcare Worker [ID: "+str(npinumber)+"]")
                        print("Data complete")

                        return resp
    else:
        npinumber = request.form['NPINUMBER']
        logging.error('%s NPINUMBER was not 10 digits' %npinumber)
        print("Invalid NPI number [%s]: %s digits provided." %(npinumber,len(npinumber)))
        return "<span style='color: red;'>NPI number must be exactly 10 digits</span>.<br>You provided [%s]: %s digits." %(npinumber,len(npinumber))

# API to check matching phone number.
# TODO Delete spaces from user input.
@npi_app.route('/phone_check', methods=['POST'])
def phone_check():
    # Declare local variables.
    isLocal = 0
    nAPIdown = 0 # NPPES API is up = 0
    pAPIdown = 0 # PECOS API is up = 0
    x = 0
    count = 1
    logcount = 1
    rows = {}

    # Time stamps for logging/output.
    st = time.time()
    today = date.today()
    current_time = get_time()
    logging.debug('phone_check Begun %s %s' %(today,current_time))

    # Headers for API calls.
    headers = set_headers()

    # If phone number is between 10 and 12 digits continue.
    if "PHONENUMBER" in request.form:

        # User input -> Phone number stripped of anything but digits.
        phonenumber = request.form['PHONENUMBER']
        phonenumber = re.sub(r"[^0-9]", '', phonenumber)
        p = phonenumber

        # Add dashes for user feedback and readability
        if len(phonenumber) > 3 and len(phonenumber) <=6:
            p = phonenumber
            p = '-'.join([phonenumber[0:3],phonenumber[3:]])
        if len(phonenumber) > 6:
            p = phonenumber
            p = '-'.join([phonenumber[:3], phonenumber[3:6], phonenumber[6:]])
        if len(phonenumber) != 10:
            print("Invalid phone number: %s" %p)
            return "<span style='color: red;'>%s</span> is not a valid phone number." %p

        print("Beginning search for phone number %s" %p)
             
        npireturns_all = ""
        con = sqlite3.connect(db)
        cur = con.cursor()
        current_time = get_time()
        logging.debug('Phone# SQL Query start %s %s' %(today,current_time))
        cur.execute("select * from npi where [Provider Business Mailing Address Telephone Number]=%s OR [Provider Business Practice Location Address Telephone Number]=%s" %(phonenumber,phonenumber))
        rows = cur.fetchall()
        con.close()
        current_time = get_time()
        con.close()
        logging.debug('Phone# SQL Query end %s %s' %(today,current_time))
        if len(rows) == 0:
            print("No results")
            return "<span style='color: red;'>No results found</span> for phone number: %s" %p

        # For each entry that had a matching phone number.
        for row in rows:
            npinumber = row[0]
            #print(npinumber)
            #print("Adding Healthcare Worker",count)
            print("Adding Healthcare Worker [ID: "+str(npinumber)+"]",count)
            count=count+1
            # try NPPES api call if it has NOT failed before.
            if nAPIdown == 0:
                try:
                    response = search(search_params={'number': npinumber})
                # NPPES API down, use local (SQL) data.
                except requests.exceptions.RequestException as e:
                    print("[PHONE] NPPES exception:",e)
                    response = {}
                    response['result_count'] = 0
                    isLocal = 1
                    nAPIdown = 1

            # Prevent NPPES API call as it has already failed.
            else:
                response = {}
                response['result_count'] = 0
                nAPIdown = 1
                isLocal = 1

            # No results -- this should never happen, given that if a phone number is found, and NPI should exist.
            # But if it does... Move on.
            if response['result_count'] == 0 and isLocal == 0 or (len(rows) == 0 and isLocal == 1):
                continue


            # NPPES API working: Set PECOS API query to NPI# recieved from the NPPES API call.
            if isLocal == 0:   
                #print(len(response))
                #print(response)
                url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(response['results'][0]['number'])

            # NPPES API NOT working: Set PECOS API query to NPI# recieved from the local NPPES SQL data.
            else: 
                url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(rows[x][0])

            # try PECOS API if it has not already failed.
            if pAPIdown == 0:
                try:
                    # PECOS api call.
                    pecosresponse = requests.get(url=url,headers=headers)
                    pecosdata = pecosresponse.json()

                    # NPPES API and PECOS API functioning.
                    if isLocal == 0:
                        npireturns = resp_formatting(pecosdata, response, x)

                    # ONLY NPPES API down.
                    else:
                        print("-- NPPES API DOWN --\n-- Using local NPPES data... --\n")
                        npireturns = rows_formatting(pecosdata,rows,x)
                        x = x + 1
                    current_time = get_time()
                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                    logcount = logcount+1
                    npireturns_all = npireturns_all + npireturns

                # PECOS API down.
                except requests.exceptions.RequestException as e:
                    print("[PHONE] PECOS exception:",e)
                    pAPIdown = 1

                    # Only PECOS API down, use local (SQL) data.
                    if isLocal == 0:
                        print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                        # Grab PECOS data from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        logging.debug('SQL Query start %s %s' %(today,current_time))
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        pecosrows = cur.fetchall()

                        # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                        if len(pecosrows) == 0:
                            pecos = {'DME': "NO", 'NPI': npinumber}
                            npireturns = resp_formatting(pecos, response, x)
                            current_time = get_time()
                            logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

                        # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                        else:
                            for row in pecosrows:
                                    # DME data is the 5th column, so element[4].
                                    PECOS = row[4]
                                    if PECOS == 'Y':
                                        pecos = {'DME': "YES", 'NPI': npinumber}
                                    else:
                                        pecos = {'DME': "NO", 'NPI': npinumber}
                            npireturns = resp_formatting(pecos,response,x)
                            current_time = get_time()
                            logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns
                            

                    # Both NPPES and PECOS api down, use local (SQL) data for both.
                    else:
                        print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                        # Grab NPPES and PECOS from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        logging.debug('SQL Query start')
                        # NPPES data.
                        npirows = rows
                        # PECOS data.
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        pecosrows = cur.fetchall()
                        logging.debug('SQL Query End')

                        # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                        if len(npirows) == 0:
                            print("No results")
                            return "<span style='color: red;'>No results found</span> for phone number: %s" %p
                        # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                        else:
                            # No matching local PECOS data found for given NPI, set PECOS data as empty.
                            if len(pecosrows) == 0:
                                pecosdata = {}
                                npireturns = rows_formatting(pecosdata, npirows, x)
                                x = x + 1
                                current_time = get_time()
                                logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                            # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                            else:
                                for row in pecosrows:
                                    # DME data is the 5th column, so element[4].
                                    PECOS = row[4]
                                    if PECOS == 'Y':
                                        pecos = {'DME': "YES", 'NPI': npinumber}
                                    else:
                                        pecos = {'DME': "NO", 'NPI': npinumber}

                                npireturns = rows_formatting(pecos,npirows,x)
                                x = x + 1
                                npireturns_all = npireturns_all + npireturns

            # pAPIdown = 1, prevent PECOS API call as it has already failed
            else:
                # Only PECOS API down, use local (SQL) data.
                if isLocal == 0:
                    print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                    # Grab PECOS data from local SQL DB.
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    logging.debug('PECOS SQL Query start %s %s' %(today,current_time))
                    cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                    pecosrows = cur.fetchall()
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    logging.debug('PECOS SQL Query start %s %s' %(today,current_time))

                    # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                    if len(pecosrows) == 0:
                        pecos = {'DME': "NO", 'NPI': npinumber}
                        npireturns = resp_formatting(pecos, response, x)
                        current_time = get_time()
                        logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                        logcount = logcount+1
                        npireturns_all = npireturns_all + npireturns

                    # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                    else:
                        for row in pecosrows:
                                # DME data is the 5th column, so element[4].
                                PECOS = row[4]
                                if PECOS == 'Y':
                                    pecos = {'DME': "YES", 'NPI': npinumber}
                                else:
                                    pecos = {'DME': "NO", 'NPI': npinumber}
                        npireturns = resp_formatting(pecos,response,x)
                        current_time = get_time()
                        logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                        logcount = logcount+1
                        npireturns_all = npireturns_all + npireturns

                # Both NPPES and PECOS api down, use local (SQL) data for both.
                else:
                    print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                    # Grab NPPES and PECOS from local SQL DB.
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    logging.debug('Local NPI & PECOS SQL Query start %s %s' %(today,current_time))
                    # NPPES data.
                    npirows = rows
                    # PECOS data.
                    cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                    pecosrows = cur.fetchall()
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    logging.debug('Local NPI & PECOS SQL Query end %s %s' %(today,current_time))

                    # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                    if len(npirows) == 0:
                        print("No results")
                        return "<span style='color: red;'>No results found</span> for phone number: %s" %p
                    # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                    else:
                        # No matching local PECOS data found for given NPI, set PECOS data as empty.
                        if len(pecosrows) == 0:
                            pecosdata = {}
                            npireturns = rows_formatting(pecosdata, npirows, x)
                            x = x + 1
                            npireturns_all = npireturns_all + npireturns

                        # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                        else:
                            for row in pecosrows:
                                # DME data is the 5th column, so element[4].
                                PECOS = row[4]
                                if PECOS == 'Y':
                                    pecos = {'DME': "YES", 'NPI': npinumber}
                                else:
                                    pecos = {'DME': "NO", 'NPI': npinumber}

                            npireturns = rows_formatting(pecos,npirows,x)
                            x = x + 1
                            current_time = get_time()
                            logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

        print("Data complete\nDisplaying",count-1,"healthcare workers.")
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        logging.debug('phone_check End %s %s' %(today,current_time))
        et = time.time()
        elapsed_time = et - st
        resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
        return resp

# API to check for matching doctor name.
@npi_app.route('/doc_check', methods=['POST'])
def doc_check():

    # Local variables
    isLocal = 0
    logcount = 1
    rows = {}
    nAPIdown = 0 # NPPES API is up = 0
    pAPIdown = 0 # PECOS API is up = 0
    count = 1
    x = 0
    npireturns_all = ""
    DOCTOR_FIRSTNAME = ""
    DOCTOR_LASTNAME = ""

    # Time stamps for logging/output.
    st = time.time()
    today = date.today()
    current_time = get_time()
    logging.debug('doc_check Begun %s %s' %(today,current_time))

    # Headers for API calls.
    headers = set_headers()

    # Doctor name must be at least 3 letters.
    if "DOCTORNAME" in request.form and len(request.form['DOCTORNAME']) > 3:

        # Sanitizing input:
        # Removes extra (>1) spaces from middle of the string if they exist.
        # Strips beginning and end of string of spaces.
        # "  Hello     World   " -> "Hello World"
        doc_input = ' '.join(request.form["DOCTORNAME"].split())

        # If only last name is provided (no spaces), do last name query.
        if " " not in doc_input:
            DOCTOR_LASTNAME = re.sub(r"[^a-zA-Z0-9]", "",request.form["DOCTORNAME"].upper()) # Only last name given
            print("Beginning name search | Last name: %s" %(DOCTOR_LASTNAME))
            if "STATE" in request.form and len(request.form['STATE']) > 1:
                DOC_STATE = re.sub(r"[^a-zA-Z0-9]", "",request.form['STATE'].upper())
                print("Beginning name search | Last Name + State: %s %s" %(DOCTOR_FIRSTNAME,DOC_STATE))
                try:
                    response = search(search_params={'last_name': DOCTOR_LASTNAME, 'state' : DOC_STATE},limit=50)
                    logging.debug('DOCTOR NAME SEARCH WITH STATE RETURNED: %s ' %response)
                except requests.exceptions.RequestException as e:
                    print("[DOC] NPPES exception:",e)
                    response = {}
                    response['result_count'] = 0
                    isLocal = 1
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    logging.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s' AND ([Provider Business Mailing Address State Name]='%s' OR [Provider Business Practice Location Address State Name]='%s')" %(DOCTOR_LASTNAME, DOC_STATE, DOC_STATE))
                    rows = cur.fetchall()
                    con.close()
            else:
                try:
                    response = search(search_params={'last_name': DOCTOR_LASTNAME},limit=50)
                    logging.debug('DOCTOR NAME SEARCH WITH LAST NAME ONLY RETURNED: %s ' %response)
                except requests.exceptions.RequestException as e:
                    print("[DOC] NPPES exception:",e)
                    response = {}
                    response['result_count'] = 0
                    isLocal = 1 
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    logging.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s'" %(DOCTOR_LASTNAME))
                    rows = cur.fetchall()
                    con.close()
        else:
            # Removes extra spaces from beginning, middle, and end of name.
            doc_full = ' '.join(request.form["DOCTORNAME"].split())

            # Splits by the remaining single space left between the names.
            DOCTORFULLNAME = doc_full.split(" ")

            # API is case sensitive, needs upper here.
            # String anything that isn't a character.
            DOCTOR_FIRSTNAME = re.sub(r"[^a-zA-Z0-9]", "",DOCTORFULLNAME[0].upper())
            DOCTOR_LASTNAME = re.sub(r"[^a-zA-Z0-9]", "",DOCTORFULLNAME[1].upper())

            if "STATE" in request.form and len(request.form['STATE']) > 1:
                DOC_STATE = re.sub(r"[^a-zA-Z0-9]", "",request.form['STATE'].upper())
                print("Beginning name search | Full name + State: %s %s - %s" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME,DOC_STATE))
                try:
                    response = search(search_params={'first_name': DOCTOR_FIRSTNAME, 'last_name': DOCTOR_LASTNAME, 'state' : DOC_STATE},limit=50)
                    logging.debug('DOCTOR NAME SEARCH WITH FIRST AND LAST NAME WITH STATE RETURNED: %s ' %response)
                except requests.exceptions.RequestException as e:
                    print("[DOC] NPPES exception:",e)
                    response = {}
                    response['result_count'] = 0
                    isLocal = 1 
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    logging.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s' AND [Provider First Name]='%s' AND ([Provider Business Mailing Address State Name]='%s' OR [Provider Business Practice Location Address State Name]='%s')" %(DOCTOR_LASTNAME,DOCTOR_FIRSTNAME, DOC_STATE, DOC_STATE))
                    rows = cur.fetchall()
                    con.close()
            else:
                print("Beginning name search | Full name: %s %s" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME))
                try:
                    response = search(search_params={'first_name': DOCTOR_FIRSTNAME, 'last_name': DOCTOR_LASTNAME},limit=50)
                    logging.debug('DOCTOR NAME SEARCH WITH FIRST AND LAST NAME RETURNED: %s ' %response)
                except requests.exceptions.RequestException as e:
                    print("[DOC] NPPES exception:",e)
                    response = {}
                    response['result_count'] = 0
                    isLocal = 1
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    logging.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)] = '%s' AND [Provider First Name] = '%s'" %(DOCTOR_LASTNAME,DOCTOR_FIRSTNAME))
                    rows = cur.fetchall()
                    con.close()

        if response['result_count'] == 0 and isLocal == 0 or (len(rows) == 0 and isLocal == 1):
            print("No results")
            return "<span style='color: red;'>No doctor found</span> by the name '%s %s'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME)

        # NPPES API Down
        else:
            # NPPES API UP
            if isLocal == 0:
                # For each entry that had a matching phone number.
                for results in response['results']:
                    npinumber = results['number']
                    #print("Adding Healthcare Worker",count)
                    print("Adding Healthcare Worker [ID: "+str(npinumber)+"]",count)
                    count=count+1
                    # try NPPES api call if it has NOT failed before.
                    if nAPIdown == 0:
                        try:
                            response = search(search_params={'number': npinumber})
                        # NPPES API down, use local (SQL) data.
                        except requests.exceptions.RequestException as e:
                            print("[PHONE] NPPES exception:",e)
                            response = {}
                            response['result_count'] = 0
                            isLocal = 1
                            nAPIdown = 1

                    # Prevent NPPES API call as it has already failed.
                    else:
                        response = {}
                        response['result_count'] = 0
                        nAPIdown = 1
                        isLocal = 1

                     # This should never happen if a phone number is found -- an NPI should exist...
                     # However if for some reason it does... Move on.
                    if response['result_count'] == 0 and isLocal == 0 or (len(rows) == 0 and isLocal == 1):
                        continue

                    # NPPES API working: Set PECOS API query to NPI# recieved from the NPPES API call.
                    if isLocal == 0:   
                        url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(response['results'][0]['number'])

                    # NPPES API NOT working: Set PECOS API query to NPI# recieved from the local NPPES SQL data.
                    else: 
                        url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(rows[x][0])

                    # try PECOS API if it has not already failed.
                    if pAPIdown == 0:
                        try:
                            # PECOS api call.
                            pecosresponse = requests.get(url=url,headers=headers)
                            pecosdata = pecosresponse.json()

                            # NPPES API and PECOS API functioning.
                            if isLocal == 0:
                                npireturns = resp_formatting(pecosdata, response, x)

                            # ONLY NPPES API down.
                            else:
                                print("-- NPPES API DOWN --\n-- Using local NPPES data... --\n")
                                npireturns = rows_formatting(pecosdata,rows,x)
                                x = x + 1
                            current_time = get_time()
                            logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

                        # PECOS API down.
                        except requests.exceptions.RequestException as e:
                            print("[DOC] PECOS exception:",e)
                            pAPIdown = 1

                            # Only PECOS API down, use local (SQL) data.
                            if isLocal == 0:
                                print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                                # Grab PECOS data from local SQL DB.
                                con = sqlite3.connect(db)
                                cur = con.cursor()
                                logging.debug('SQL Query start %s %s' %(today,current_time))
                                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                                pecosrows = cur.fetchall()

                                # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                                if len(pecosrows) == 0:
                                    pecos = {'DME': "NO", 'NPI': npinumber}
                                    npireturns = resp_formatting(pecos, response, x)
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1
                                    npireturns_all = npireturns_all + npireturns

                                # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                else:
                                    for row in pecosrows:
                                            # DME data is the 5th column, so element[4].
                                            PECOS = row[4]
                                            if PECOS == 'Y':
                                                pecos = {'DME': "YES", 'NPI': npinumber}
                                            else:
                                                pecos = {'DME': "NO", 'NPI': npinumber}
                                    npireturns = resp_formatting(pecos,response,x)
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1
                                    npireturns_all = npireturns_all + npireturns

                            # Both NPPES and PECOS api down, use local (SQL) data for both.
                            else:
                                print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                                # Grab NPPES and PECOS from local SQL DB.
                                con = sqlite3.connect(db)
                                cur = con.cursor()
                                logging.debug('SQL Query start')
                                # NPPES data.
                                npirows = rows
                                # PECOS data.
                                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                                pecosrows = cur.fetchall()

                                # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                                if len(npirows) == 0:
                                    print("No results")
                                    return "<span style='color: red;'>No doctor found</span> by the name '%s %s'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME)

                                # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                                else:
                                    # No matching local PECOS data found for given NPI, set PECOS data as empty.
                                    if len(pecosrows) == 0:
                                        pecosdata = {}
                                        npireturns = rows_formatting(pecosdata, npirows, x)
                                        x = x + 1
                                        current_time = get_time()
                                        logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                        logcount = logcount+1
                                        npireturns_all = npireturns_all + npireturns

                                    # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                    else:
                                        for row in pecosrows:
                                            # DME data is the 5th column, so element[4].
                                            PECOS = row[4]
                                            if PECOS == 'Y':
                                                pecos = {'DME': "YES", 'NPI': npinumber}
                                            else:
                                                pecos = {'DME': "NO", 'NPI': npinumber}

                                        npireturns = rows_formatting(pecos,npirows,x)
                                        x = x + 1
                                        npireturns_all = npireturns_all + npireturns

                    # pAPIdown = 1, prevent PECOS API call as it has already failed
                    else:
                        # Only PECOS API down, use local (SQL) data.
                        if isLocal == 0:
                            print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                            # Grab PECOS data from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('PECOS SQL Query start %s %s' %(today,current_time))
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('PECOS SQL Query start %s %s' %(today,current_time))

                            # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                            if len(pecosrows) == 0:
                                pecos = {'DME': "NO", 'NPI': npinumber}
                                npireturns = resp_formatting(pecos, response, x)
                                current_time = get_time()
                                logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                            # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                            else:
                                for row in pecosrows:
                                        # DME data is the 5th column, so element[4].
                                        PECOS = row[4]
                                        if PECOS == 'Y':
                                            pecos = {'DME': "YES", 'NPI': npinumber}
                                        else:
                                            pecos = {'DME': "NO", 'NPI': npinumber}
                                npireturns = resp_formatting(pecos,response,x)
                                current_time = get_time()
                                logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                        # Both NPPES and PECOS api down, use local (SQL) data for both.
                        else:
                            print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                            # Grab NPPES and PECOS from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('Local NPI & PECOS SQL Query start %s %s' %(today,current_time))
                            # NPPES data.
                            npirows = rows
                            # PECOS data.
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('Local NPI & PECOS SQL Query end %s %s' %(today,current_time))

                            # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                            if len(npirows) == 0:
                                print("No results")
                                return "<span style='color: red;'>No doctor found</span> by the name '%s %s'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME)
                            # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                            else:
                                # No matching local PECOS data found for given NPI, set PECOS data as empty.
                                if len(pecosrows) == 0:
                                    pecosdata = {}
                                    npireturns = rows_formatting(pecosdata, npirows, x)
                                    x = x + 1
                                    npireturns_all = npireturns_all + npireturns

                                # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                else:
                                    for row in pecosrows:
                                        # DME data is the 5th column, so element[4].
                                        PECOS = row[4]
                                        if PECOS == 'Y':
                                            pecos = {'DME': "YES", 'NPI': npinumber}
                                        else:
                                            pecos = {'DME': "NO", 'NPI': npinumber}

                                    npireturns = rows_formatting(pecos,npirows,x)
                                    x = x + 1
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1
                                    npireturns_all = npireturns_all + npireturns

                print("Data complete\nDisplaying",count-1,"healthcare workers.")
                now = datetime.now()
                current_time = now.strftime("%H:%M:%S")
                logging.debug('phone_check End %s %s' %(today,current_time))
                et = time.time()
                elapsed_time = et - st
                resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                return resp

            else:
                # For each entry that had a matching name.
                for row in rows:
                    npinumber = row[0]
                    #print("Adding Healthcare Worker",count)
                    print("Adding Healthcare Worker [ID: "+str(npinumber)+"]",count)
                    count=count+1
                    # try NPPES api call if it has NOT failed before.
                    if nAPIdown == 0:
                        try:
                            response = search(search_params={'number': npinumber})
                        # NPPES API down, use local (SQL) data.
                        except requests.exceptions.RequestException as e:
                            print("[PHONE] NPPES exception:",e)
                            response = {}
                            response['result_count'] = 0
                            isLocal = 1
                            nAPIdown = 1

                    # Prevent NPPES API call as it has already failed.
                    else:
                        response = {}
                        response['result_count'] = 0
                        nAPIdown = 1
                        isLocal = 1

                    # This should never happen if a phone number is found -- an NPI should exist.
                    # However if it does happen... Move on.
                    if response['result_count'] == 0 and isLocal == 0 or (len(rows) == 0 and isLocal == 1):
                        continue

                    # NPPES API working: Set PECOS API query to NPI# recieved from the NPPES API call.
                    if isLocal == 0:   
                        url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(response['results'][0]['number'])

                    # NPPES API NOT working: Set PECOS API query to NPI# recieved from the local NPPES SQL data.
                    else: 
                        url = "https://data.cms.gov/data-api/v1/dataset/0824b6d0-14ad-47a0-94e2-f317a3658317/data?column=DME%2CNPI&keyword=" + str(rows[x][0])

                    # try PECOS API if it has not already failed.
                    if pAPIdown == 0:
                        try:
                            # PECOS api call.
                            pecosresponse = requests.get(url=url,headers=headers)
                            pecosdata = pecosresponse.json()

                            # NPPES API and PECOS API functioning.
                            if isLocal == 0:
                                npireturns = resp_formatting(pecosdata, response, x)

                            # ONLY NPPES API down.
                            else:
                                print("-- NPPES API DOWN --\n-- Using local NPPES data... --\n")
                                npireturns = rows_formatting(pecosdata,rows,x)
                                x = x + 1
                            current_time = get_time()
                            logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

                        # PECOS API down.
                        except requests.exceptions.RequestException as e:
                            print("[PHONE] PECOS exception:",e)
                            pAPIdown = 1

                            # Only PECOS API down, use local (SQL) data.
                            if isLocal == 0:
                                print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                                # Grab PECOS data from local SQL DB.
                                con = sqlite3.connect(db)
                                cur = con.cursor()
                                logging.debug('SQL Query start %s %s' %(today,current_time))
                                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                                pecosrows = cur.fetchall()

                                # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                                if len(pecosrows) == 0:
                                    pecos = {'DME': "NO", 'NPI': npinumber}
                                    npireturns = resp_formatting(pecos, response, x)
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1
                                    npireturns_all = npireturns_all + npireturns

                                # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                else:
                                    for row in pecosrows:
                                            # DME data is the 5th column, so element[4].
                                            PECOS = row[4]
                                            if PECOS == 'Y':
                                                pecos = {'DME': "YES", 'NPI': npinumber}
                                            else:
                                                pecos = {'DME': "NO", 'NPI': npinumber}
                                    npireturns = resp_formatting(pecos,response,x)
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1

                            # Both NPPES and PECOS api down, use local (SQL) data for both.
                            else:
                                print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                                # Grab NPPES and PECOS from local SQL DB.
                                con = sqlite3.connect(db)
                                cur = con.cursor()
                                logging.debug('SQL Query start')
                                # NPPES data.
                                npirows = rows
                                # PECOS data.
                                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                                pecosrows = cur.fetchall()

                                # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                                if len(npirows) == 0:
                                    return "No results found for given doctor NPI number %s" %npinumber
                                    
                                # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                                else:
                                    # No matching local PECOS data found for given NPI, set PECOS data as empty.
                                    if len(pecosrows) == 0:
                                        pecosdata = {}
                                        npireturns = rows_formatting(pecosdata, npirows, x)
                                        x = x + 1
                                        current_time = get_time()
                                        logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                        logcount = logcount+1
                                        npireturns_all = npireturns_all + npireturns

                                    # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                    else:
                                        for row in pecosrows:
                                            # DME data is the 5th column, so element[4].
                                            PECOS = row[4]
                                            if PECOS == 'Y':
                                                pecos = {'DME': "YES", 'NPI': npinumber}
                                            else:
                                                pecos = {'DME': "NO", 'NPI': npinumber}

                                        npireturns = rows_formatting(pecos,npirows,x)
                                        x = x + 1
                                        npireturns_all = npireturns_all + npireturns

                    # pAPIdown = 1, prevent PECOS API call as it has already failed
                    else:
                        # Only PECOS API down, use local (SQL) data.
                        if isLocal == 0:
                            print("-- PECOS API DOWN --\n-- Using local PECOS data... --\n")

                            # Grab PECOS data from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('PECOS SQL Query start %s %s' %(today,current_time))
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('PECOS SQL Query start %s %s' %(today,current_time))

                            # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                            if len(pecosrows) == 0:
                                pecos = {'DME': "NO", 'NPI': npinumber}
                                npireturns = resp_formatting(pecos, response, x)
                                current_time = get_time()
                                logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                            # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                            else:
                                for row in pecosrows:
                                        # DME data is the 5th column, so element[4].
                                        PECOS = row[4]
                                        if PECOS == 'Y':
                                            pecos = {'DME': "YES", 'NPI': npinumber}
                                        else:
                                            pecos = {'DME': "NO", 'NPI': npinumber}
                                npireturns = resp_formatting(pecos,response,x)
                                current_time = get_time()
                                logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                        # Both NPPES and PECOS api down, use local (SQL) data for both.
                        else:
                            print("-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --\n")

                            # Grab NPPES and PECOS from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('Local NPI & PECOS SQL Query start %s %s' %(today,current_time))
                            # NPPES data.
                            npirows = rows
                            # PECOS data.
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()
                            now = datetime.now()
                            current_time = now.strftime("%H:%M:%S")
                            logging.debug('Local NPI & PECOS SQL Query end %s %s' %(today,current_time))

                            # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                            if len(npirows) == 0:
                                return "No results found for given doctor NPI number %s" %npinumber
                            # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                            else:
                                # No matching local PECOS data found for given NPI, set PECOS data as empty.
                                if len(pecosrows) == 0:
                                    pecosdata = {}
                                    npireturns = rows_formatting(pecosdata, npirows, x)
                                    x = x + 1
                                    npireturns_all = npireturns_all + npireturns

                                # Local PECOS SQL DB returned rows, set appropriate key value pair based on returned data.
                                else:
                                    for row in pecosrows:
                                        # DME data is the 5th column, so element[4].
                                        PECOS = row[4]
                                        if PECOS == 'Y':
                                            pecos = {'DME': "YES", 'NPI': npinumber}
                                        else:
                                            pecos = {'DME': "NO", 'NPI': npinumber}

                                    npireturns = rows_formatting(pecos,npirows,x)
                                    x = x + 1
                                    current_time = get_time()
                                    logging.debug('Appending data... [%s] %s %s' %(logcount,today,current_time))
                                    logcount = logcount+1
                                    npireturns_all = npireturns_all + npireturns

                print("Data complete\nDisplaying",count-1,"healthcare workers.")
                now = datetime.now()
                current_time = now.strftime("%H:%M:%S")
                logging.debug('phone_check End %s %s' %(today,current_time))
                et = time.time()
                elapsed_time = et - st
                resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                return resp
    # Doctor name was less than 3 letters.
    else:
        return "<span style='color: red;'>Doctor Name must be at least 3 letters</span>"

# Helper function for formatting SQL returns (NPPES API down).
def rows_formatting(pecosdata, rows, x):
    PECOS = "NO"
    # PECOS API returns a list of a single dictionary for some reason (??)
    if isinstance (pecosdata, list) and pecosdata:
        pecosdata = pecosdata[0]
    # Dictionary from local PECOS SQL return (PECOS API down).
    if isinstance (pecosdata, dict) and pecosdata:
        for key in pecosdata:
            if "DME" in key:
                #print(".get DME:",pecosdata.get('DME'))
                PECOS = pecosdata.get('DME')
                if PECOS == "Y":
                    PECOS = "YES"

    # Set approprite data.
    npi_number = str(rows[x][0])
    first_name = rows[x][6]
    middle_name = rows[x][7]
    last_name = rows[x][5]
    telephone_number = rows[x][26]
    telephone_numberp = rows[x][34]
    fax_numberp = rows[x][35]
    fax_numberm = rows[x][27]
    maddress1 = rows[x][20]
    maddress2 = rows[x][21]
    mcity = rows[x][22]
    mstate = rows[x][23]
    mpostal = rows[x][24]
    paddress1 = rows[x][28]
    paddress2 = rows[x][29]
    pcity = rows[x][30]
    pstate = rows[x][31]
    ppostal = rows[x][32]
    credential = rows[x][10]
    primaryPractice = ""
    endpoint = ""
    
    npireturns = "<tr><td class=fitwidth>" + npi_number + "</td>" + "<td class=fitwidth>" + first_name + \
    " " + middle_name + " " + last_name + "</td>" + "<td>" + credential + "</td>" + "<td class=fitwidth>" + telephone_number + "</td>" + \
    "<td class=fitwidth>" + telephone_numberp + "</td>" + "<td class=fitwidth>" + fax_numberp + \
    "</td>" + "<td>" + paddress1 + " " + paddress2 + " " + pcity + \
    " " + pstate + " " + ppostal + "</td>" + \
    "<td>" + maddress1 + " " + maddress2 + " " + mcity + \
    " " + mstate + " " + mpostal + "</td>" + "<td>" + primaryPractice + "</td>" + \
    "<td class=pecos>" + str(PECOS) + "</td>" + "<td class=maxwidth>" + endpoint + "</td>" + "</tr>"
    return npireturns

# Response formatting helper function (NPPES API up).
def resp_formatting(pecosdata, response, x):
    # Set default DME value of NO
    PECOS = {"DME" : "NO"}
    # PECOS API returns a list of a single dictionary for some reason (??)
    if isinstance (pecosdata, list) and pecosdata:
        pecosdata = pecosdata[0]
    # Dictionary from local PECOS SQL return (PECOS API down).
    if isinstance (pecosdata, dict) and pecosdata:
        for key in pecosdata:
            if "DME" in key:
                PECOS = pecosdata.get('DME')
                #print(pecosdata.get('DME'))
                if PECOS == "Y" or PECOS == "YES":
                    pecosdata = {"DME" : "YES"}
    # If it is not a dict/list with >=1 element, it is empty, therefore use default value set above.
    else:
        pecosdata = PECOS

    # Set appropriate data.
    if "endpoints" in response['results'][x]:
        endpoint = response['results'][x]['endpoints'][0]['endpoint']
    else:
        endpoint = "UNKNOWN"
    if "credential" in response['results'][x]['basic']:
        credential = response['results'][x]['basic']['credential']
    else:
        credential = "UNKNOWN"
    if "first_name" in response['results'][0]['basic']:
        first_name = response['results'][x]['basic']['first_name']
    else:
        first_name = ""
    if "middle_name" in response['results'][x]['basic']:
        middle_name = response['results'][x]['basic']['middle_name']
    else:
        middle_name = ""
    if "last_name" in response['results'][x]['basic']:
        last_name = response['results'][x]['basic']['last_name']
    else:
        last_name = ""
    if "fax_number" in response['results'][x]['addresses'][0]:
        fax_number=response['results'][x]['addresses'][0]['fax_number']
    else:
        fax_number="UNKNOWN"
    if "fax_number" in response['results'][x]['addresses'][1]:
        fax_numberp=response['results'][x]['addresses'][1]['fax_number']
    else:
        fax_numberp=fax_number
    if "telephone_number" in response['results'][x]['addresses'][0]:
        telephone_number=response['results'][x]['addresses'][0]['telephone_number']
    else:
        telephone_number="NO #"
    if "telephone_number" in response['results'][x]['addresses'][1]:
        telephone_numberp=response['results'][x]['addresses'][1]['telephone_number']
    else:
        telephone_numberp="NO #"
    if "practiceLocations" in response['results'][x]:
        primaryPractice = response['results'][x]['practiceLocations'][0]['address_1'] + " " + \
        response['results'][x]['practiceLocations'][0]['address_2'] + " " + \
        response['results'][x]['practiceLocations'][0]['city'] + " " + \
        response['results'][x]['practiceLocations'][0]['state'] + " " + \
        response['results'][x]['practiceLocations'][0]['postal_code']
    else:
        primaryPractice = ""
    npireturns = "<tr><td class=fitwidth>" + str(response['results'][x]['number']) + "</td>" + "<td class=fitwidth>" + first_name + \
    " " + middle_name + " " + last_name + "</td>" + "<td>" + credential + "</td>" + "<td class=fitwidth>" + telephone_number + "</td>" + \
    "<td class=fitwidth>" + telephone_numberp + "</td>" + "<td class=fitwidth>" + fax_numberp + \
    "</td>" + "<td>" + response['results'][x]['addresses'][0]['address_1'] + " " + response['results'][x]['addresses'][0]['address_2'] + " " + response['results'][x]['addresses'][0]['city'] + \
    " " + response['results'][x]['addresses'][0]['state'] + " " + response['results'][x]['addresses'][0]['postal_code'] + "</td>" + \
    "<td>" + response['results'][x]['addresses'][1]['address_1'] + " " + response['results'][x]['addresses'][1]['address_2'] + " " + response['results'][x]['addresses'][1]['city'] + \
    " " + response['results'][x]['addresses'][1]['state'] + " " + response['results'][x]['addresses'][1]['postal_code'] + "</td>" + "<td>" + primaryPractice + "</td>" + \
    "<td class=pecos>" + pecosdata.get('DME') + "</td>" + "<td class=maxwidth>" + endpoint + "</td>" + "</tr>"
    return npireturns

# Helper function to get local NPPES data
def get_local_nppes_data():
    print(".")

# Helper function to get local PECOS data
def get_local_pecos_data():
    print(".")

# Helper function for current time.
def get_time():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    return current_time

# Header helper function.
def set_headers():
    headers = CaseInsensitiveDict()
    headers["Accept"] = "*/*"
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Methods"] = "DELETE, POST, GET, OPTIONS"
    return headers

# TODO Make this the hopepage in addition.
# Post landing page.
@npi_app.route('/npi', methods=['POST', 'GET'])
def npi():
    logging.debug('Web Landing Page accessed')
    if request.method == 'POST':
        return render_template('npi.html')
    else:
        return render_template('npi.html')

if __name__ == '__main__':
    npi_app.run(host='74.103.169.112', port=5755, threads=8, debug=True)
    #npi_app.run(host='0.0.0.0', port=5755, threads=8, debug=True)
    #npi_app.run(host='0.0.0.0', port=5755, debug=True)