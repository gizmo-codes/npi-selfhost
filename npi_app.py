# App Description Here 👯‍♂️
from flask import Flask, render_template, request, jsonify, Response
import npyi
from npyi.npi import search
import requests
from requests.structures import CaseInsensitiveDict
from flask_cors import CORS
from pygtail import Pygtail
import sqlite3
import logging, os, sys, re, time, npi_setup

# TODO
# Remove stripped input from frontend as well.

# https://www.pythontutorial.net/python-concurrency/python-threading/
# https://stackoverflow.com/questions/17035077/logging-to-multiple-log-files-from-different-classes-in-python
# https://docs.python.org/3/tutorial/inputoutput.html

# App Name
npi_app = Flask(__name__)
CORS(npi_app)

# App settings
# npi_app.config["SECRET_KEY"] = ""
npi_app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", True)
npi_app.config["JSON_AS_ASCII"] = False

# Grab settings from INI file.
settings = npi_setup.getSettings()
log_path = settings[0]
db_path = settings[1]
ip_addr = settings[2]
port = settings[3]
dataset = settings[4]
ajax_url = settings[5]

# Diable Flask Logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
npi_app.logger.disabled = True
log.disabled = True

# Log path(s)
DEV_LOG = log_path+'/npi.log'
USER_LOG = log_path+'/user.log'
# Database path
db = db_path+'/npi.db'

# Log function for multiple logs
def setup_logger(name, log_file, formatter, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.FileHandler(log_file)        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


# Dev feedback logger
dev_log = setup_logger('dev_log', DEV_LOG, logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
# User feedback logger
user_log = setup_logger('user_log', USER_LOG, logging.Formatter('%(message)s'))

# Set PECOS API URL with NPI keyword.
pecos_api_url = "https://data.cms.gov/data-api/v1/dataset/"+dataset+"/data?column=DME%2CNPI&keyword="

# API to check for matching NPI number.
@npi_app.route('/npi_check', methods=['POST'])
def npi_check():
    # Local Variables
    nAPIdown = 0
    pAPIdown = 0
    x = 0
    rows = {}

    # Start time for logging/output.
    st = time.time()
    dev_log.debug('npi_check Begun')

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
            dev_log.info("Invalid NPI number [%s]: %s digits provided." %(npinumber,len(npinumber)))
            user_log.info("Invalid NPI number [%s]: %s digits provided." %(npinumber,len(npinumber)))
            user_log.info('log-end')
            return "<span style='color: red;'>NPI number must be <b>exactly 10 digits</b></span>.<br>You provided [%s]: %s digits." %(npinumber,len(npinumber))

        # Log Feedback
        user_log.info("Beginning search for NPI: %s" %(npinumber))

        # try NPPES api call.
        try:
            # Alternative formatting, without wrapper.
            # response = requests.get("https://npiregistry.cms.hhs.gov/api/?number=%s&enumeration_type=&taxonomy_description=&first_name=&use_first_name_alias=&last_name=&organization_name=&address_purpose=&city=&state=&postal_code=&country_code=&limit=&skip=&pretty=&version=2.1" %npinumber)
            # response = response.json()
            response = search(search_params={'number': npinumber})
        # NPPES API down, use local (SQL) data.
        except requests.exceptions.RequestException as e:
            dev_log.info("[NPI] NPPES exception: %s" %e)
            response = {}
            response['result_count'] = 0
            nAPIdown = 1
            con = sqlite3.connect(db)
            cur = con.cursor()
            dev_log.debug('NPPES NPI SQL Query start')
            cur.execute("select * from npi where NPI=%s" %(npinumber))
            dev_log.debug('NPPES NPI SQL Query end')
            rows = cur.fetchall()
            con.close()
        # NPI number is deactivated and information is no longer available.
        except npyi.exceptions.NPyIException as e:
            return "<span style='color: red;'>Given NPI number [</span>%s<span style='color: red;'>] is valid but deactivated, no information available.</span>" %npinumber

        # No results
        if response['result_count'] == 0 and (nAPIdown == 0 and pAPIdown == 0) or (len(rows) == 0 and nAPIdown == 1) or (len(rows) == 0 and pAPIdown == 1):
            user_log.info("No results")
            user_log.info("log-end")
            result = "<span style='color: red;'>No results found</span> for NPI: %s" %npinumber
            return result

        # Set PECOS API url with NPI keyword. 
        url = pecos_api_url + str(npinumber)


        # try PECOS API
        try:
            # PECOS api call.
            pecosresponse = requests.get(url=url,headers=headers)
            
            # Check if API is returning empty data.
            if pecosresponse:
                pecosdata = pecosresponse.json()
            else:
                raise requests.exceptions.RequestException
            
            # NPPES API and PECOS API functioning.
            if nAPIdown == 0 and pAPIdown == 0:
                npireturns = resp_formatting(pecosdata, response, x)

            # ONLY NPPES API down.
            else:
                user_log.info("\n-- NPPES API DOWN --\n-- Using local NPPES data... --")
                npireturns = rows_formatting(pecosdata,rows,x)
            elapsed_time = query_time(st)
            resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
            dev_log.debug('npi_check End')
            #print("npi_check end")
            user_log.info("Adding Healthcare Worker [ID: '%s']" %npinumber)
            user_log.info("Data complete")
            user_log.info('log-end')
            return resp
            #return response
        # PECOS API down.
        except requests.exceptions.RequestException as e:
            dev_log.info("[NPI] PECOS exception: %s" %e)

            # Only PECOS API down, use local (SQL) data.
            if nAPIdown == 0:
                user_log.info("\n-- PECOS API DOWN --\n-- Using local PECOS data... --")

                # Grab PECOS data from local SQL DB.
                con = sqlite3.connect(db)
                cur = con.cursor()
                dev_log.debug('NPI SQL Query start')
                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                dev_log.debug('NPI SQL Query end')
                pecosrows = cur.fetchall()

                # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                if len(pecosrows) == 0:
                    pecos = {'DME': "NO", 'NPI': npinumber}
                    npireturns = resp_formatting(pecos, response, x)
                    elapsed_time = query_time(st)
                    resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                    dev_log.debug('npi_check End')
                    user_log.info("Adding Healthcare Worker [ID: '%s']" %npinumber)
                    user_log.info("Data complete")
                    user_log.info('log-end')
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
                    elapsed_time = query_time(st)
                    resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                    dev_log.debug('npi_check End')
                    user_log.info("Adding Healthcare Worker [ID: '%s']" %npinumber)
                    user_log.info("Data complete")
                    user_log.info('log-end')
                    return resp
            # Both NPPES and PECOS api down, use local (SQL) data for both.
            else:
                user_log.info("\n-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --")

                # Grab NPPES and PECOS from local SQL DB.
                con = sqlite3.connect(db)
                cur = con.cursor()
                dev_log.debug('NPPES & PECOS NPI SQL Query start')
                # NPPES data.
                cur.execute("select * from npi where [NPI]=%s" %(npinumber))
                npirows = cur.fetchall()
                # PECOS data.
                cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                pecosrows = cur.fetchall()
                dev_log.debug('NPPES & PECOS NPI SQL Query end')

                # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                if len(npirows) == 0:
                    user_log.info("No results found for NPI: %s" %npinumber)
                    user_log.info('log-end')
                    return "<span style='color: red;'>No results found</span> for NPI: %s" %npinumber
                # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                else:
                    # No matching local PECOS data found for given NPI, set PECOS data as empty.
                    if len(pecosrows) == 0:
                        pecosdata = {}
                        npireturns = rows_formatting(pecosdata, npirows, x)
                        elapsed_time = query_time(st)
                        resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                        dev_log.debug('npi_check End')
                        user_log.info("Adding Healthcare Worker [ID: '%s']" %npinumber)
                        user_log.info("Data complete")
                        user_log.info('log-end')
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
                        elapsed_time = query_time(st)
                        resp = jsonify('<table id=respTable><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                        #resp = jsonify('<table>' + npireturns + '</table><br><font color=red>Elapsed Time: ' + str(elapsed_time) + ' seconds</font>')

                        dev_log.debug('npi_check End')
                        user_log.info("Adding Healthcare Worker [ID: '%s']" %npinumber)
                        user_log.info("Data complete")
                        user_log.info('log-end')
                        return resp
    else:
        npinumber = request.form['NPINUMBER']

        # Stripping everything that is not a letter.
        npinumber = re.sub(r"[^0-9]", "",npinumber)
        npinumber = re.sub(r'\s+', '', npinumber)

        dev_log.error('NPINUMBER was not 10 digits')
        user_log.info("Invalid NPI number [%s]: %s digits provided." %(npinumber,len(npinumber)))
        user_log.info('log-end')
        return "<span style='color: red;'>NPI number must be <b>exactly 10 digits</b></span>.<br>You provided [%s]: %s digits." %(npinumber,len(npinumber))


# API to check for matching doctor name.
@npi_app.route('/doc_check', methods=['POST'])
def doc_check():

    # Local variables
    rows = {}
    nAPIdown = 0 # NPPES API is up = 0
    pAPIdown = 0 # PECOS API is up = 0
    count = 1 # Used for displaying feedback
    logcount = 1 # Used for logging/feedback
    x = 0 # Used for position in JSON results
    npireturns_all = ""
    DOCTOR_FIRSTNAME = ""
    DOCTOR_LASTNAME = ""
    DOC_STATE = ""

    # Start time for logging/output.
    st = time.time()
    dev_log.debug('doc_check Begun')

    # Headers for API calls.
    headers = set_headers()

    # Doctor name must be at least 3 letters.
    if "DOCTORNAME" in request.form and len(request.form['DOCTORNAME']) > 2:

        # Sanitizing input:
        # Removes extra (>1) spaces from middle of the string if they exist.
        # Strips beginning and end of string of spaces.
        # "  Hello     World   " -> "Hello World"
        doc_input = ' '.join(request.form["DOCTORNAME"].split())

        # Last OR Last + State given.
        if " " not in doc_input:
            DOCTOR_LASTNAME = re.sub(r"[^a-zA-Z0-9]", "",request.form["DOCTORNAME"].upper()) # Only last name given
            if len(DOCTOR_LASTNAME) == 0:
                user_log.info("Input empty after removing invalid characters.")
                user_log.info('log-end')
                return "<span style='color: red;'>Input empty after removing invalid characters. Please use A-Z a-z.</span>"

            # Last + State given.
            if "STATE" in request.form and len(request.form['STATE']) == 2:
                DOC_STATE = re.sub(r"[^a-zA-Z0-9]", "",request.form['STATE'].upper())
                user_log.info("Beginning name search | Last Name + State: %s %s" %(DOCTOR_FIRSTNAME,DOC_STATE))
                try:
                    response = search(search_params={'last_name': DOCTOR_LASTNAME, 'state' : DOC_STATE},limit=50)
                    dev_log.debug('DOCTOR NAME SEARCH (LAST + STATE) RETURNED: %s' %response)
                # NPPES API down.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[DOC] NPPES exception: %s" %e)
                    response = {}
                    response['result_count'] = 0
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s' AND ([Provider Business Mailing Address State Name]='%s' OR [Provider Business Practice Location Address State Name]='%s')" %(DOCTOR_LASTNAME, DOC_STATE, DOC_STATE))
                    rows = cur.fetchall()
                    con.close()
            elif "STATE" in request.form and len(request.form['STATE']) != 2 and len(request.form['STATE']) != 0:
                state = request.form['STATE']
                dev_log.info("Invalid state given: [%s]" %state)
                return "<span style='color: red;'>Invalid state given:</span> [<span style='color: red;'>%s</span>] Use 2 letter abbreviations only." %state
            # Last name only.
            else:
                user_log.info("Beginning name search | Last name: %s" %(DOCTOR_LASTNAME))
                try:
                    response = search(search_params={'last_name': DOCTOR_LASTNAME},limit=50)
                    dev_log.debug('DOCTOR NAME SEARCH (LAST) RETURNED: %s' %response)
                # NPPES API down.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[DOC] NPPES exception: %s" %e)
                    response = {}
                    response['result_count'] = 0
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s'" %(DOCTOR_LASTNAME))
                    rows = cur.fetchall()
                    con.close()
                    
        # First + Last OR First + Last + State
        else:
            # Removes extra spaces from beginning, middle, and end of name.
            doc_full = ' '.join(request.form["DOCTORNAME"].split())

            # Splits by the remaining single space left between the names.
            DOCTORFULLNAME = doc_full.split(" ")

            # API is case sensitive, needs upper here.
            # Remove anything that isn't a character.
            DOCTOR_FIRSTNAME = re.sub(r"[^a-zA-Z0-9]", "",DOCTORFULLNAME[0].upper())
            DOCTOR_LASTNAME = re.sub(r"[^a-zA-Z0-9]", "",DOCTORFULLNAME[1].upper())

            # First + Last + State given.
            if "STATE" in request.form and len(request.form['STATE']) == 2:
                DOC_STATE = re.sub(r"[^a-zA-Z0-9]", "",request.form['STATE'].upper())
                user_log.info("Beginning name search | Full name + State: %s %s - %s" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME,DOC_STATE))
                try:
                    response = search(search_params={'first_name': DOCTOR_FIRSTNAME, 'last_name': DOCTOR_LASTNAME, 'state' : DOC_STATE},limit=50)
                    dev_log.debug('DOCTOR NAME SEARCH WITH (FIRST + LAST + STATE) RETURNED: %s' %response)
                # NPPES API down.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[DOC] NPPES exception: %s" %e)
                    response = {}
                    response['result_count'] = 0
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)]='%s' AND [Provider First Name]='%s' AND ([Provider Business Mailing Address State Name]='%s' OR [Provider Business Practice Location Address State Name]='%s')" %(DOCTOR_LASTNAME,DOCTOR_FIRSTNAME, DOC_STATE, DOC_STATE))
                    rows = cur.fetchall()
                    con.close()
            # First + Last given.
            else:
                user_log.info("Beginning name search | Full name: %s %s" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME))
                try:
                    response = search(search_params={'first_name': DOCTOR_FIRSTNAME, 'last_name': DOCTOR_LASTNAME},limit=50)
                    dev_log.debug('DOCTOR NAME SEARCH (FIRST + LAST) RETURNED: %s' %response)
                # NPPES API down.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[DOC] NPPES exception: %s" %e)
                    response = {}
                    response['result_count'] = 0
                    nAPIdown = 1
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('SQL Query start')
                    cur.execute("select * from npi where [Provider Last Name (Legal Name)] = '%s' AND [Provider First Name] = '%s'" %(DOCTOR_LASTNAME,DOCTOR_FIRSTNAME))
                    rows = cur.fetchall()
                    con.close()

        # No results found for query.
        if response['result_count'] == 0 and nAPIdown == 0 and pAPIdown == 0 or (len(rows) == 0 and nAPIdown == 1) or (len(rows) == 0 and pAPIdown == 1):
            if DOC_STATE and DOCTOR_FIRSTNAME and DOCTOR_LASTNAME:
                user_log.info("No doctor found by the name '%s %s' in '%s'" %(DOCTOR_FIRSTNAME, DOCTOR_LASTNAME, DOC_STATE))
                user_log.info('log-end')
                return "<span style='color: red;'><b>No doctor found</b></span> by the name '<b>%s %s</b>' in '<b>%s</b>'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME, DOC_STATE)
            elif DOC_STATE and DOCTOR_LASTNAME and not DOCTOR_FIRSTNAME:
                user_log.info("No doctor found by the name '%s' in '%s'" %(DOCTOR_LASTNAME, DOC_STATE))
                user_log.info('log-end')
                return "<span style='color: red;'><b>No doctor found</b></span> by the name '<b>%s</b>' in '<b>%s</b>'" %(DOCTOR_LASTNAME, DOC_STATE)
            elif DOCTOR_FIRSTNAME and not DOC_STATE:
                user_log.info("No doctor found by the name '%s %s'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME))
                user_log.info('log-end')
                return "<span style='color: red;'><b>No doctor found</b></span> by the name '<b>%s %s</b>'" %(DOCTOR_FIRSTNAME,DOCTOR_LASTNAME)
            else:
                user_log.info("No doctor found by the name '%s'" %(DOCTOR_LASTNAME))
                user_log.info('log-end')
                return "<span style='color: red;'><b>No doctor found</b></span> by the name '<b>%s</b>'" %(DOCTOR_LASTNAME)

        # Results recieved.
        else:
            # TODO
            # Consider that once we hit the NPPES api and it returns data -- It's done. We don't call it again.
            # Therefore the nAPIdown check should only need to happen once.
            # However PECOS is called for each NPI returned from NPPES so it is called (potentially) several times.

            # if else is needed, as we have different data structures depending on if the search is done
            # Remotely  - 'for results in response['results']:
            # OR
            # Locally   - 'for row in rows:

            # Four possible scenarios of APIs being up/down
            # nAPIdown == 0 && pAPIdown == 0
            # nAPIdown == 1 && pAPIdown == 0
            # nAPIdown == 0 && pAPIdown == 1
            # nAPIdown == 1 && pAPIdown == 1

            # NPPES API UP
            # nAPIdown == 0 >> Deal with scenarios:
            # nAPIdown == 0 && pAPIdown == 0
            # nAPIdown == 0 && pAPIdown == 1
            if nAPIdown == 0:
                # For each entry that had a matching phone number.
                for results in response['results']:
                    #print("RESULTS:",results)
                    npinumber = results['number']
                    #print("Adding Healthcare Worker",count)
                    user_log.info("Adding Healthcare Worker [ID: '%s'] %s" %(str(npinumber),count))
                    count=count+1

                    # Set PECOS API url with NPI keyword.
                    url = pecos_api_url + str(npinumber)

                    # try PECOS API if it has not already failed.
                    if pAPIdown == 0:
                        try:
                            # PECOS api call.
                            pecosresponse = requests.get(url=url,headers=headers)

                            # Check if API is returning empty data.
                            if pecosresponse:
                                pecosdata = pecosresponse.json()
                            else:
                                raise requests.exceptions.RequestException

                            npireturns = resp_formatting(pecosdata, response, x)
                            x = x + 1
                            dev_log.debug('Appending data... [%s]' %logcount)
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

                        # PECOS API down.
                        except requests.exceptions.RequestException as e:
                            dev_log.info("[DOC] PECOS exception: %s" %e)
                            pAPIdown = 1

                            user_log.info("\n-- PECOS API DOWN --\n-- Using local PECOS data... --")

                            # Grab PECOS data from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            dev_log.debug('SQL Query start')
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()

                            # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                            if len(pecosrows) == 0:
                                pecos = {'DME': "NO", 'NPI': npinumber}
                                npireturns = resp_formatting(pecos, response, x)
                                x = x + 1
                                dev_log.debug('Appending data... [%s]' %logcount)
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
                                
                                dev_log.debug('Appending data... [%s]' %logcount)
                                x = x + 1
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns


                    # pAPIdown = 1, prevent PECOS API call as it has already failed
                    else:
                        user_log.info("\n-- PECOS API DOWN --\n-- Using local PECOS data... --")

                        # Grab PECOS data from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        dev_log.debug('PECOS SQL Query start')
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        pecosrows = cur.fetchall()
                        dev_log.debug('PECOS SQL Query end')

                        # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                        if len(pecosrows) == 0:
                            pecos = {'DME': "NO", 'NPI': npinumber}
                            npireturns = resp_formatting(pecos, response, x)
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
                            x = x + 1
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
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
                            x = x + 1
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns


                user_log.info("Data complete\nDisplaying %s healthcare workers." %str(count-1))
                dev_log.debug('phone_check End')
                elapsed_time = query_time(st)
                resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                user_log.info('log-end')
                return resp
            
            # NPPES API down.
            # nAPIdown == 1 >> Deal with scenarios:
            # nAPIdown == 1 && pAPIdown == 0
            # nAPIdown == 1 && pAPIdown == 1
            else:
                # For each entry that had a matching name.
                for row in rows:
                    npinumber = row[0]
                    #print("Adding Healthcare Worker",count)
                    user_log.info("Adding Healthcare Worker [ID: '%s'] %s" %(npinumber,count))
                    count=count+1
                    
                    # Set variables for local use
                    response = {}
                    response['result_count'] = 0

                    # Set PECOS API url with NPI keyword.
                    url = pecos_api_url + str(rows[x][0])

                    # try PECOS API if it has not already failed.
                    if pAPIdown == 0:
                        try:
                            # PECOS api call.
                            pecosresponse = requests.get(url=url,headers=headers)
                            
                            # Check if API is returning empty data.
                            if pecosresponse:
                                pecosdata = pecosresponse.json()
                            else:
                                raise requests.exceptions.RequestException

                            # Only NPPES api down.
                            # nAPIdown == 1 && pAPIdown == 0
                            user_log.info("\n-- NPPES API DOWN --\n-- Using local NPPES data... --")
                            npireturns = rows_formatting(pecosdata,rows,x)
                            x = x + 1
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

                        # PECOS API down. nAPIdown == 1 && pAPIdown == 1
                        except requests.exceptions.RequestException as e:
                            dev_log.info("[PHONE] PECOS exception: %s" %e)
                            pAPIdown = 1
                            user_log.info("\n-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --")

                            # Grab NPPES and PECOS from local SQL DB.
                            con = sqlite3.connect(db)
                            cur = con.cursor()
                            dev_log.debug('SQL Query start')
                            # NPPES data.
                            npirows = rows
                            # PECOS data.
                            cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                            pecosrows = cur.fetchall()

                            # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                            if len(npirows) == 0:
                                user_log.info("No results found for given NPI number %s" %npinumber)
                                user_log.info('log-end')
                                return "No results found for given NPI number %s" %npinumber
                                
                            # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                            else:
                                # No matching local PECOS data found for given NPI, set PECOS data as empty.
                                if len(pecosrows) == 0:
                                    pecosdata = {}
                                    npireturns = rows_formatting(pecosdata, npirows, x)
                                    x = x + 1
                                    
                                    dev_log.debug('Appending data... [%s]' %logcount)
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
                    # nAPIdown == 1 && pAPIdown == 1
                    else:
                        user_log.info("\n-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --")

                        # Grab NPPES and PECOS from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        dev_log.debug('Local NPI & PECOS SQL Query start')
                        # NPPES data.
                        npirows = rows
                        # PECOS data.
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        pecosrows = cur.fetchall()
                        dev_log.debug('Local NPI & PECOS SQL Query end')

                        # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                        if len(npirows) == 0:
                            user_log.info("No results found for given NPI number %s" %npinumber)
                            user_log.info("log-end")
                            return "No results found for given NPI number %s" %npinumber
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
                                
                                dev_log.debug('Appending data... [%s]' %logcount)
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

                user_log.info("Data complete\nDisplaying %s healthcare workers." %str(count-1))
                dev_log.debug('phone_check End')
                elapsed_time = query_time(st)
                resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
                user_log.info("log-end")
                return resp
    # Doctor name was less than 3 letters.
    else:
        user_log.info("Doctor name must be at least 3 letters.")
        user_log.info("log-end")
        return "<span style='color: red;'>Doctor Name must be <b>at least 3 letters</b></span>"


# API to check matching phone number.
@npi_app.route('/phone_check', methods=['POST'])
def phone_check():
    # Declare local variables.
    nAPIdown = 0 # NPPES API is up = 0
    pAPIdown = 0 # PECOS API is up = 0
    x = 0
    count = 1
    logcount = 1
    rows = {}
    npireturns_all = ""

    # Start time for logging/output.
    st = time.time()
    dev_log.debug('phone_check Begun')

    # Headers for API calls.
    headers = set_headers()

    # If phone number is between 10 and 12 digits continue.
    if "PHONENUMBER" in request.form:

        # User input -> Phone number stripped of anything but digits.
        # TODO this should be communicated on the frontend, not dealt with on the backend.
        # We should simply not allow characters. 0-9 & dashes '-' only.
        phonenumber = request.form['PHONENUMBER']
        origphone = phonenumber
        phonenumber = re.sub(r"[^0-9]", '', phonenumber)
        p = phonenumber
        o = origphone

        # Add dashes for user feedback and readability
        if len(phonenumber) > 3 and len(phonenumber) <=6:
            p = phonenumber
            p = '-'.join([phonenumber[0:3],phonenumber[3:]])
        if len(phonenumber) > 6:
            p = phonenumber
            p = '-'.join([phonenumber[:3], phonenumber[3:6], phonenumber[6:]])
        if len(phonenumber) != 10 and len(phonenumber) != 0:
            user_log.info("Invalid phone number: %s" %p)
            user_log.info('log-end')
            return "<span style='color: red;'>%s</span> is not a valid phone number." %p
        elif len(phonenumber) == 0:
            user_log.info("Invalid phone number: %s" %o)
            user_log.info('log-end')
            return "<span style='color: red;'>%s</span> is not a valid phone number." %o


        user_log.info("Beginning search for phone number %s" %p)

        # Establish DB connection for local query.
        con = sqlite3.connect(db)
        cur = con.cursor()
        
        dev_log.debug('Phone# SQL Query start')
        cur.execute("select * from npi where [Provider Business Mailing Address Telephone Number]=%s OR [Provider Business Practice Location Address Telephone Number]=%s" %(phonenumber,phonenumber))
        
        # Matching NPPES (doctor) data for given phone number.
        rows = cur.fetchall()
        con.close()
        dev_log.debug('Phone# SQL Query end')

        # No results returned from query
        if len(rows) == 0:
            user_log.info("No results found for phone number: %s" %p)
            user_log.info('log-end')
            return "<span style='color: red;'>No results found</span> for phone number: %s" %p

        # Phone number search is NOT supported by NPPES API, therefore, we do this search locally regardless of weather the API is up or not.
        # The benefit to hitting the NPPES API after is having the most up to date healthcare information fetched per NPI you recieved from your
        # local results.
        # This will only be beneficial if the doctor data was updated ~within the past month.

        # Given the mission critical nature of the app, it seems worth it to perform the local + API NPPES query even though it is
        # redundant if the doctor information is up to date.

        # Four possible scenarios of APIs being up/down
        # nAPIdown == 0 && pAPIdown == 0
        # nAPIdown == 1 && pAPIdown == 0
        # nAPIdown == 0 && pAPIdown == 1
        # nAPIdown == 1 && pAPIdown == 1

        # For each entry that had a matching phone number.
        for row in rows:
            npinumber = row[0]
            #print(npinumber)
            #print("Adding Healthcare Worker",count)
            user_log.info("Adding Healthcare Worker [ID: '%s'] %s" %(str(npinumber),count))
            count=count+1

            # try NPPES api call if it has NOT failed before.
            if nAPIdown == 0:
                try:
                    response = search(search_params={'number': npinumber})
                # NPPES API down, use local (SQL) data.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[PHONE] NPPES exception: %s" %e)
                    response = {}
                    response['result_count'] = 0
                    nAPIdown = 1
                # NPI number is deactivated and information is no longer available.
                except npyi.exceptions.NPyIException as e:
                    dev_log.info("[PHONE] npyi exception:\n%s\nRemoving entry..." %e)
                    rows.remove(row)
                    count = count - 1
                    continue

            # Prevent NPPES API call as it has already failed.
            # No need to get the local data again here as we did that earlier.
            else:
                # Set varaibles for local search.
                response = {}
                response['result_count'] = 0

            # Set PECOS API url with NPI keyword.
            url = pecos_api_url + str(npinumber)

            # try PECOS API if it has not already failed.
            # pAPIdown == 0 >> Deal with scenarios:
            # nAPIdown == 0 && pAPIdown == 0
            # nAPIdown == 1 && pAPIdown == 0 
            if pAPIdown == 0:
                try:
                    # PECOS api call.
                    pecosresponse = requests.get(url=url,headers=headers)
                    
                    # Check if API is returning empty data.
                    if pecosresponse:
                        pecosdata = pecosresponse.json()
                    else:
                        raise requests.exceptions.RequestException

                    # NPPES API and PECOS API functioning.
                    # nAPIdown == 0 && pAPIdown == 0
                    if nAPIdown == 0 and pAPIdown == 0:
                        npireturns = resp_formatting(pecosdata, response, x)

                    # ONLY NPPES API down.
                    # nAPIdown == 1 && pAPIdown == 0
                    else:
                        user_log.info("\n-- NPPES API DOWN --\n-- Using local NPPES data... --")
                        npireturns = rows_formatting(pecosdata,rows,x)
                        x = x + 1
                    
                    dev_log.debug('Appending data... [%s]' %logcount)
                    logcount = logcount+1
                    npireturns_all = npireturns_all + npireturns

                # PECOS API down.
                # Deal with given data then never enter this exception again.
                except requests.exceptions.RequestException as e:
                    dev_log.info("[PHONE] PECOS exception: %s" %e)
                    pAPIdown = 1

                    # Only PECOS API down, use local (SQL) data.
                    # nAPIdown == 0 && pAPIdown == 1
                    if nAPIdown == 0:
                        user_log.info("\n-- PECOS API DOWN --\n-- Using local PECOS data... --")

                        # Grab PECOS data from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        dev_log.debug('SQL Query start')
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        dev_log.debug('SQL Query end')
                        pecosrows = cur.fetchall()

                        # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                        if len(pecosrows) == 0:
                            pecos = {'DME': "NO", 'NPI': npinumber}
                            npireturns = resp_formatting(pecos, response, x)
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
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
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns
                            

                    # Both NPPES and PECOS api down, use local (SQL) data for both.
                    # nAPIdown == 1 && pAPIdown == 1
                    else:
                        user_log.info("\n-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --")

                        # Grab NPPES and PECOS from local SQL DB.
                        con = sqlite3.connect(db)
                        cur = con.cursor()
                        dev_log.debug('SQL Query start')
                        # NPPES data.
                        npirows = rows
                        # PECOS data.
                        cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                        pecosrows = cur.fetchall()
                        dev_log.debug('SQL Query End')

                        # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                        if len(npirows) == 0:
                            user_log.info("No results found for phone number: %s" %p)
                            user_log.info('log-end')
                            return "<span style='color: red;'>No results found</span> for phone number: %s" %p
                        # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                        else:
                            # No matching local PECOS data found for given NPI, set PECOS data as empty.
                            if len(pecosrows) == 0:
                                pecosdata = {}
                                npireturns = rows_formatting(pecosdata, npirows, x)
                                
                                dev_log.debug('Appending data... [%s]' %logcount)
                                x = x + 1
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

                                dev_log.debug('Appending data... [%s]' %logcount)
                                x = x + 1
                                logcount = logcount+1
                                npireturns_all = npireturns_all + npireturns

            # Prevent PECOS API call as it has already failed
            # pAPIdown = 1 >> Deal with scenarios:
            # nAPIdown == 0 && pAPIdown == 1
            # nAPIdown == 1 && pAPIdown == 1
            else:
                # Only PECOS API down, use local (SQL) data.
                # pAPIdown == 1 && nAPIdown == 0
                if nAPIdown == 0:
                    user_log.info("\n-- PECOS API DOWN --\n-- Using local PECOS data... --")

                    # Grab PECOS data from local SQL DB.
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('PECOS SQL Query start')
                    cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                    pecosrows = cur.fetchall()
                    dev_log.debug('PECOS SQL Query end')

                    # Local PECOS SQL DB returned no rows, send DME of "NO" for current NPI hit from NPPES.
                    if len(pecosrows) == 0:
                        pecos = {'DME': "NO", 'NPI': npinumber}
                        npireturns = resp_formatting(pecos, response, x)
                        
                        dev_log.debug('Appending data... [%s]' %logcount)
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
                        
                        dev_log.debug('Appending data... [%s]' %logcount)
                        logcount = logcount+1
                        npireturns_all = npireturns_all + npireturns

                # Both NPPES and PECOS api down, use local (SQL) data for both.
                # nAPIdown == 1 && pAPIdown == 1
                else:
                    user_log.info("\n-- NPPES AND PECOS API DOWN --\n-- Using local NPPPES & PECOS data... --")

                    # Grab NPPES and PECOS from local SQL DB.
                    con = sqlite3.connect(db)
                    cur = con.cursor()
                    dev_log.debug('Local NPI & PECOS SQL Query start')
                    # NPPES data.
                    npirows = rows
                    # PECOS data.
                    cur.execute("select * from pecos where [NPI]=%s" %(npinumber))
                    pecosrows = cur.fetchall()
                    dev_log.debug('Local NPI & PECOS SQL Query end')

                    # Local NPPES SQL DB returned no rows, therefore no matching doctor by given NPI number.
                    if len(npirows) == 0:
                        user_log.info("No results found for phone number: %s" %p)
                        user_log.info('log-end')
                        return "<span style='color: red;'>No results found</span> for phone number: %s" %p
                    # Local NPPES SQL DB returned rows, check for PECOS data mathcing given NPI.
                    else:
                        # No matching local PECOS data found for given NPI, set PECOS data as empty.
                        if len(pecosrows) == 0:
                            pecosdata = {}
                            npireturns = rows_formatting(pecosdata, npirows, x)
                            dev_log.debug('Appending data... [%s]' %logcount)
                            x = x + 1
                            logcount=logcount+1
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
                            
                            dev_log.debug('Appending data... [%s]' %logcount)
                            x = x + 1
                            logcount = logcount+1
                            npireturns_all = npireturns_all + npireturns

        user_log.info("Data complete\nDisplaying %s healthcare workers." %str(count-1))
        dev_log.debug('phone_check End')
        elapsed_time = query_time(st)
        resp = jsonify('<table id="respTable"><thead><tr id=sticky><th>NPI</th><th class=fitwidth>Name</th><th>Credential</th><th class=fitwidth>Practice #</th><th class=fitwidth>Mailing #</th><th class=fitwidth>Fax</th><th>Primary Practice</th><th>Mailing Address</th><th class=fitwidth>Other Practice</th><th>PECOS</th><th class=maxwidth>Email</th></tr></thead>' + npireturns_all + '</table><br><font color=red>Execution Time: ' + str(round(elapsed_time,2)) + ' seconds</font>')
        user_log.info('log-end')
        return resp


# Helper function for formatting SQL returns (NPPES API down).
def rows_formatting(pecosdata, rows, x):

    # Default PECOS value.
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
    npi = str(rows[x][0])
    last_name = rows[x][5]
    first_name = rows[x][6]
    middle_name = rows[x][7]
    credential = rows[x][10]
    mailing_addr_1 = rows[x][20]
    mailing_addr_2 = rows[x][21]
    mailing_city = rows[x][22]
    mailing_state = rows[x][23]
    mailing_postal = rows[x][24]
    mailing_phone = rows[x][26]
    mailing_fax = rows[x][27]
    primary_addr_1 = rows[x][28]
    primary_addr_2 = rows[x][29]
    primary_city = rows[x][30]
    primary_state = rows[x][31]
    primary_postal = rows[x][32]
    primary_phone = rows[x][34]
    primary_fax = rows[x][35]
    other_addr = ""
    endpoint = ""

    # Set primary fax as mailing fax if primary fax DNE.
    if primary_fax == "" and mailing_fax != "":
        primary_fax = mailing_fax

    # Combine appropriate data.
    full_name = " ".join([first_name, middle_name, last_name])
    full_primary_addr = " ".join([primary_addr_1, primary_addr_2, primary_city, primary_state, primary_postal])
    full_mailing_addr = " ".join([mailing_addr_1, mailing_addr_2, mailing_city, mailing_state, mailing_postal])


    # [NPI] [Name] [Credential] [Practice #] [Mailing #] [Fax] [Primary Practice] [Mailing Address] [Other Practice] [PECOS] [Email]
    # Return complete HTML row.
    npireturns = \
    "<tr><td class=fitwidth>" + npi + "</td>" + \
    "<td class=fitwidth>" + full_name + "</td>" + \
    "<td>" + credential + "</td>" + \
    "<td class=fitwidth>" + primary_phone + "</td>" + \
    "<td class=fitwidth>" + mailing_phone + "</td>" + \
    "<td class=fitwidth>" + primary_fax + "</td>" + \
    "<td>" + full_primary_addr + "</td>" + \
    "<td>" + full_mailing_addr + "</td>" + \
    "<td>" + other_addr + "</td>" + \
    "<td class=pecos>" + str(PECOS) + "</td>" + \
    "<td class=maxwidth>" + endpoint + "</td></tr>"
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

    # ----- Set appropriate data. -----
    # NPI
    npi = str(response['results'][x]['number'])

    # eMail
    if "endpoints" in response['results'][x]:
        if response['results'][x]['endpoints']:
            endpoint = response['results'][x]['endpoints'][0]['endpoint']
        else:
            endpoint = ""
    else:
        endpoint = ""

    # Credential: i.e. D.O., MSN, APRN, FNP-C etc.
    if "credential" in response['results'][x]['basic']:
        credential = response['results'][x]['basic']['credential']
    else:
        credential = ""

    # Name
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
    full_name = " ".join([first_name, middle_name, last_name])

    # Other Location
    # practiceLocations is any address besides 'Primary' and 'Mailing'
    if "practiceLocations" in response['results'][x]:
        if response['results'][x]['practiceLocations']: 
            if "address_2" in response['results'][x]['practiceLocations']:
                address2 = response['results'][x]['practiceLocations'][0]['address_2']
            else:
                address2 = ""
            other_addr = response['results'][x]['practiceLocations'][0]['address_1'] + " " + \
            address2 + " " + \
            response['results'][x]['practiceLocations'][0]['city'] + " " + \
            response['results'][x]['practiceLocations'][0]['state'] + " " + \
            response['results'][x]['practiceLocations'][0]['postal_code']
        else: other_addr = ""
    else:
        other_addr = ""

    # Primary address.
    # ['addresses'][0] is always primary address.
    if response['results'][x]['addresses'][0]:
        if  'address_1' in response['results'][x]['addresses'][0]:
            addr = response['results'][x]['addresses'][0]['address_1']
        else:
            addr = ""
        if "city" in response['results'][x]['addresses'][0]:
            city = response['results'][x]['addresses'][0]['city']
        else:
            city = ""
        if "state" in response['results'][x]['addresses'][0]:
            state = response['results'][x]['addresses'][0]['state']
        else:
            state = ""
        if "postal_code" in response['results'][x]['addresses'][0]:
            postal_code = response['results'][x]['addresses'][0]['postal_code']
        else:
            postal_code = ""
        
        # Full primary practice address.
        primary_addr = " ".join([addr, city, state, postal_code])

        if "telephone_number" in response['results'][x]['addresses'][0]:
            primary_phone = response['results'][x]['addresses'][0]['telephone_number']
        else:
            primary_phone = ""
        if "fax_number" in response['results'][x]['addresses'][0]:
            primary_fax = response['results'][x]['addresses'][0]['fax_number']
        else:
            primary_fax = ""
    else:
        primary_addr = ""

    # Mailing address.
    # ['addresses'][1] is always mailing address.
    if response['results'][x]['addresses'][1]:
        if  'address_1' in response['results'][x]['addresses'][1]:
            addr = response['results'][x]['addresses'][1]['address_1']
        else:
            addr = ""
        if "city" in response['results'][x]['addresses'][1]:
            city = response['results'][x]['addresses'][1]['city']
        else:
            city = ""
        if "state" in response['results'][x]['addresses'][1]:
            state = response['results'][x]['addresses'][1]['state']
        else:
            state = ""
        if "postal_code" in response['results'][x]['addresses'][1]:
            postal_code = response['results'][x]['addresses'][1]['postal_code']
        else:
            postal_code = ""

        # Full mailing address.
        mailing_addr = " ".join([addr, city, state, postal_code])

        if "telephone_number" in response['results'][x]['addresses'][1]:
            mailing_phone = response['results'][x]['addresses'][1]['telephone_number']
        else:
            mailing_phone = ""
        if "fax_number" in response['results'][x]['addresses'][1]:
            mailing_fax = response['results'][x]['addresses'][1]['fax_number']
        else:
            mailing_fax = ""
    else:
       mailing_addr = ""

    # Replace primary fax number with mailing fax if primary fax DNE.
    if primary_fax == "" and mailing_fax != "":
        primary_fax = mailing_fax
    # --------------------------------

    # [NPI] [Name] [Credential] [Practice #] [Mailing #] [Fax] [Primary Practice] [Mailing Address] [Other Practice] [PECOS] [Email]
    # Return complete HTML row.
    npireturns = \
    "<tr><td class=fitwidth>" + npi + "</td>" + \
    "<td class=fitwidth>" + full_name + "</td>" + \
    "<td>" + credential + "</td>" + \
    "<td class=fitwidth>" + primary_phone + "</td>" + \
    "<td class=fitwidth>" + mailing_phone + "</td>" + \
    "<td class=fitwidth>" + primary_fax + "</td>" + \
    "<td>" + primary_addr + "</td>" + \
    "<td>" + mailing_addr + "</td>" + \
    "<td>" + other_addr + "</td>" + \
    "<td class=pecos>" + pecosdata.get('DME') + "</td>" + \
    "<td class=maxwidth>" + endpoint + "</td></tr>"
    return npireturns

# Helper function for time passed during query.
def query_time(st):
    et = time.time()
    elapsed_time = et - st
    return elapsed_time

# Header helper function.
def set_headers():
    headers = CaseInsensitiveDict()
    headers["Accept"] = "*/*"
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Methods"] = "DELETE, POST, GET, OPTIONS"
    return headers

# Post landing page & alternative page.
@npi_app.route('/', methods=['POST', 'GET'])
@npi_app.route('/npi', methods=['POST', 'GET'])
def npi():
    dev_log.debug('Web Landing Page accessed')
    if request.method == 'POST':
        return render_template('npi.html')
    else:
        return render_template('npi.html')

# Access logs
@npi_app.route('/logs')
def entry_point():
	return render_template('log.html')

# API call to load previous logs on page load
@npi_app.route('/loadlogs')
def cmon():
	def full_log():
		full = open(USER_LOG, 'r')
		lines = full.readlines()
		lines.reverse()
		for line in lines:
			if line.strip() == "log-end":
				yield '<hr style="width:50%;height:0.5px;text-align:left;margin:5px;margin-left:0px;">'
			else:
				yield '<li>' + str(line) + '</li>\n'
		full.close()
	return Response(full_log(), mimetype= 'text/event-stream')

# 'Live' logging
@npi_app.route('/log')
def progress_log():
    def generate():
        for line in Pygtail(USER_LOG, every_n=1):
            if line.strip('\n') == "log-end":
                yield 'data: <hr style="width:50%;height:0.5px;text-align:left;margin:5px;margin-left:0px;"> \n\n'
            else:
                    yield "data:" + str(line) + "\n\n"
    return Response(generate(), mimetype= 'text/event-stream')

cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None
if ip_addr == '127.0.0.1':
    protocol = "http://"
    print("Server running on:",protocol+ip_addr+":"+port)
else:
    print("Server running on:",ajax_url)

if __name__ == '__main__':
    npi_app.run(host=ip_addr, port=port, threads=8, debug=True, use_reloader=False)
    #waitress-serve --listen=*:port npi_app:npi_app
    #npi_app.run(host='0.0.0.0', port=port, threads=8, debug=True, use_reloader=False)
    #npi_app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)