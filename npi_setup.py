from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import configparser
import os

def createConfig(path):
    """
    Create a config file
    """
    config = configparser.ConfigParser()

    # PECOS Section
    config.add_section("PECOS")
    print("Fetching pecos dataset...")
    dataset = getPecosAPI()
    print("Fetch complete")
    config.set("PECOS", "endpoint", dataset)
    print("Pecos endpiont set [%s]" %dataset)

    # General Section
    config.add_section("GENERAL")
    config.set("GENERAL", "log_path", "./logs")
    print("Log path set [./logs]")
    config.set("GENERAL", "db_path", "./db")
    print("DB path set [./db]")
    config.set("GENERAL", "ip_addr", "127.0.0.1")
    print("IP address set [127.0.0.1]")
    config.set("GENERAL", "ajax_url", "127.0.0.1")
    print("AJAX URL set [127.0.0.1]")
    config.set("GENERAL", "port", "5755")
    print("Port set [5755]")

    with open(path, "w") as config_file:
        config.write(config_file)

# Scrape API dataset from web.
def getPecosAPI():
    GetAPIURL = "https://data.cms.gov/provider-characteristics/medicare-provider-supplier-enrollment/order-and-referring/api-docs"
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument("--headless")
    #options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=options)
    driver.get(GetAPIURL)
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME,"DatasetApiDocsPage__content")))
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.findChildren('table')

    my_table = tables[0]

    rows = my_table.findChildren(['th', 'tr'])
    cells = rows[0].findChildren('td')
    dataset = (cells[0].string)
    return dataset

# Attempt to fix saved endpoint by fetching a new one.
def setPecosAPI():
    grabbed = False
    ConfigFile = "NPI.ini"
    config = configparser.ConfigParser()
    config.read(ConfigFile)

    # Verify Section/Option exists.
    if config.has_section("PECOS"):
        if not config.has_option("PECOS", "endpoint"):
            print("Endpoint missing: grabbing new endpoint...")
            updated_endpoint = getPecosAPI()
            config.set("PECOS", "endpoint", updated_endpoint)
            with open('NPI.ini', 'w') as configfile:
                config.write(configfile)
                print("Endpoint updated to [%s]!" %updated_endpoint)
            grabbed = True
        else:
            print("Local endpoint exists.")
    else:
        print("Missing section and endpoint: grabbing new endpoint...")
        config.add_section("PECOS")
        updated_endpoint = getPecosAPI()
        config.set("PECOS", "endpoint", updated_endpoint)
        with open('NPI.ini', 'w') as configfile:
            config.write(configfile)
            print("Endpoint updated to [%s]!" %updated_endpoint)
        grabbed = True

    # Grab saved + scraped endpoint if not already grabbed.
    pecos_ini_endpoint = config.get("PECOS", "endpoint")
    if grabbed == False:
        print("Retrieving pecos endpoint...")
        updated_endpoint = getPecosAPI()
        print(updated_endpoint, "retrieved.")
    
    # Compare saved endpoint to grabbed endpoint.
    if updated_endpoint != pecos_ini_endpoint:
        print("Endpoints do not match.\nPecos endpoint: %s\nSaved endpoint: %s\nUpdating endpoint..." %(updated_endpoint, pecos_ini_endpoint))
        config['PECOS']['endpoint'] = updated_endpoint
        with open('NPI.ini', 'w') as configfile:
            config.write(configfile)
        print("Endpoint updated to [%s]!" %updated_endpoint)
    else:
        print("Endpoint matches most recent.")

def getPecosINI():
    ConfigFile = "NPI.ini"
    config = configparser.ConfigParser()

    # Attempt grabbing locally saved PECOS api dataset.
    try:
        print("Fetching saved endpoint...")
        config.read(ConfigFile)
        pecos_ini_endpoint = config.get("PECOS", "endpoint")
        print("Endpoint set successfully.")
        return pecos_ini_endpoint
    # If grab failed, attempt to fix it.
    except:
        print("Fetch failed.")
        setPecosAPI()
        config.read(ConfigFile)
        pecos_ini_endpoint = config.get("PECOS", "endpoint")
        return pecos_ini_endpoint

def getSettings():
    # Setup Config File
    ConfigFile = "NPI.ini"
    if not os.path.exists(ConfigFile):
        print("Creating ini file...")
        createConfig(ConfigFile)
    config = configparser.ConfigParser()
    config.read(ConfigFile)

    # Verify necessacary paths exist.
    log_path = config["GENERAL"]["log_path"]
    if not os.path.exists(log_path):
        os.makedirs(log_path)
        # Creates new dev log.
        with open(log_path+'/npi.log', 'w') as fp:
            print("[./logs/dev.log] file created.")
            pass
        with open(log_path+'/user.log', 'w') as fp:
            print("[./logs/user.log] file created.")
            pass

    db_path = config["GENERAL"]["db_path"]
    if not os.path.exists(db_path):
        os.makedirs(db_path)
        print("[db] folder created.")
        # Create database...

    # Other settings
    ip_addr = config["GENERAL"]["ip_addr"]
    port = config["GENERAL"]["port"]
    dataset = config["PECOS"]["endpoint"]
    ajax_url = config["GENERAL"]["ajax_url"]

    print("Setup complete.")
    return log_path, db_path, ip_addr, port, dataset, ajax_url

