from logging import exception
from turtle import pensize
from xml.dom import ValidationErr
import pytest
import os
import sys
import re

# https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from npi_app import npi_app,npyi
# response = npi_app.test_client().get("/npi")
# print(response.status_code)

@pytest.fixture()
def app():
    app = npi_app
    app.config.update({
        "TESTING": True,
    })
    # other setup can go here
    yield app
    # clean up / reset resources here

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

# Test NPI api call "/npi_check"
# -- NPI --
# Empty      | Invalid
# 123        | Invalid
# abc        | Invalid
# 1235398777 | API Exception
# 1234567890 | No results
# 1104392323 | Results
@pytest.mark.parametrize(
    "npi,valid,results",
    [
        ("", False, False),          # Invalid
        ("123", False, False),       # Invalid
        ("abc", False, False),       # Invalid
        ("1235398777", True, False), # Exception (npyi.exceptions.NPyIException)
        ("1234567890", True, False), # No Results
        ("1104392323", True, True),  # Results
    ]
)
def test_npi_api(client, npi, valid, results):
    # Given
    data = {
        "npi": npi
    }

    # When
    response = client.post("/npi_check", data={
        "NPINUMBER": data["npi"]
        #"NPINUMBER": "1234567890"
    })
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    front = soup.get_text()
    #print("soup:",soup)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0
    #print("Results returned:",str(results))

    # 1 result from NPI search.
    if results == True:
        assert results == 1
    if (results == False and valid == True) or (valid == False and results == False):
        assert results == 0
    # Specific exception handling is not working for this test
    if npi == "1235398777":
        assert front == "Given NPI number [1235398777] is valid but deactivated, no information available."



# Test Doctor API call "/doc_check"
# --- Name + State ---
# Empty             | Invalid
# ab                | Invalid
# Cuartas           | Last (Results)
# Cuartasi          | Last (No Results)
# Cuartas PA        | Last + State (Results)
# Cuartasi PA       | Last + State (No Results)
# Mary Cuartas      | First + Last (Results)
# Ham Bone          | First + Last (No Results)
# Mary Cuartas CO   | First + Last + State (Results)
# Ham Bone DE       | First + Last + State (No Results)

@pytest.mark.parametrize(
    "name,state,valid,results",
    [
        ("", "", False, False),               # Invalid
        ("ab", "", False, False),             # Invalid
        ("Cuartas", "", True, True),          # Valid + Results       (Last)
        ("Cuartasi", "", True, False),        # Valid + No Results    (Last)
        ("Cuartas", "PA", True, True),        # Valid + Results       (Last + State)
        ("Cuartasi", "PA", True, False),      # Valid + No Results    (Last + State)
        ("Mary Cuartas", "", True, True),     # Valid + Results       (First + Last)
        ("Ham Bone", "", True, False),        # Valid + No Results    (First + Last)
        ("Mary Cuartas", "CO", True, True),   # Valid + Results       (First + Last + State)
        ("Ham Bone", "DE", True, False),      # Valid + No Results    (First + Last + State)

    ]
)
def test_doctor_api(client, name, state, valid, results):
    # Given
    data = {
        "name": name,
        "state": state
    }

    # When
    response = client.post("/doc_check", data={
        "DOCTORNAME": data["name"],
        "STATE": data["state"]
        #"NPINUMBER": "1234567890"
    })
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    front = soup.get_text()
    #print("soup:",soup)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0

    # Test results
    if results == True:
        assert results >= 1
    if valid == False and results == False and len(name) <3:
        assert results == 0 and front == "Doctor Name must be at least 3 letters"
    if valid == True and results == False and len(state) == 0:
        assert results == 0 and front == "No doctor found by the name '%s'" %name.upper()
    if valid == True and results == False and len(state) > 0:
        assert results == 0 and front == "No doctor found by the name '%s' in '%s'" %(name.upper(), state.upper())

    # This cannot be tested within the API call as this is done on the HTML/JS side
    #if valid == False and results == False and len(name) == 0:
        #print("\nF F 0 name: %s, len: %s" %(name, len(name)))
        #assert results == 0 and front == "Doctor Name filed is blank."

# ---- PHONE ----
# Empty         | Invalid
# ab            | Invalid
# 123           | Invalid
# 0005551234    | No results
# 5122604900    | Results
# 000-555-1234  | No Results
# 512-260-4900  | Results
# 1234567890    | Results with Exceptions
@pytest.mark.parametrize(
    "phone,valid,results",
    [
        ("", False, False),               # Invalid
        ("ab", False, False),             # Invalid
        ("123", False, False),            # Invalid
        ("0005551234", True, False),      # Valid + No Results
        ("5122604900", True, True),       # Valid + Results
        ("000-555-1234", True, False),    # Valid + No Results
        ("512-260-4900", True, True),     # Valid + Results
        ("1234567890", True, True),       # Valid + Results + Exception

    ]
)
def test_phone_api(client, phone, valid, results):
    # Given
    data = {
        "phone": phone,
    }

    # When
    response = client.post("/phone_check", data={
        "PHONENUMBER": data["phone"],
    })
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    front = soup.get_text()
    #print("soup:",soup)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0

    # Original
    o = phone

    # Stripped
    phone = re.sub(r"[^0-9]", '', phone)
    p = phone


    # Add dashes for user feedback and readability
    if len(phone) > 3 and len(phone) <=6:
        p = '-'.join([phone[0:3],phone[3:]])
    if len(phone) > 6:
        p = '-'.join([phone[:3], phone[3:6], phone[6:]])

    # Test results
    if results == True:
        assert results >= 1
    if valid == False and results == False and len(p) != 10 and len(p) != 0:
        assert results == 0 and front == "%s is not a valid phone number." %p
    if valid == False and results == False and len(p) == 0:
        assert results == 0 and front == "%s is not a valid phone number." %o
    if valid == True and results == False:
        assert results == 0 and front == "No results found for phone number: %s" %p

def LOCAL_npi_api(client):
    # Given
    data = {
        "npi": "1235398777"
    }

    # When
    response = client.test_client().post("/npi_check", data={
        "NPINUMBER": data["npi"]
    })
    npi = data["npi"]
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    print("soup:",soup)
    front = soup.get_text()
    print("front:",front)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0
    print("Results returned:",str(results))

        

def test_npi_get(client):
    response = client.get("/npi")
    assert response.status_code == 200


#test_npi_api(npi_app)
#test_npi_get(npi_app)
#test_exception(npi_app)
#test_npi_api_local(npi_app)

#pytest --no-header -v