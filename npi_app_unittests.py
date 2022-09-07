import npi_app
import unittest

# https://realpython.com/python-testing/#testing-for-web-frameworks-like-django-and-flask


# ALL tests besides invalid input need to be performed with the following (4) scenarios:
# Four possible scenarios of APIs being up/down
# nAPIdown == 0 && pAPIdown == 0
# nAPIdown == 1 && pAPIdown == 0
# nAPIdown == 0 && pAPIdown == 1
# nAPIdown == 1 && pAPIdown == 1
# Denoted by x4

# Search terms
# -- NPI --
# Empty      | Invalid
# 123        | Invalid
# abc        | Invalid
# 1235398777 | API Exception
# 1234567890 | No results
# 1104392323 | Results
# 1235497587 | FULL RESULTS (All Columns)
#
# --- NAME ---
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
#
# ---- PHONE ----
# Empty         | Invalid
# ab            | Invalid
# 123           | Invalid
# 0005551234    | No results
# 5122604900    | Results
# 000-555-1234  | No Results
# 512-260-4900  | Results
# 1234567890    | Results with Exceptions

# The following tests need to be performed:

# ------ NPI SEARCH -----
# Invalid Input:        |
# NPI != 10             |
# Empty Field           |
#                       |
# Valid Iniput:         |
# No Results    x4      |
# Results       x4      |
# -----------------------


# ------ DOCTOR NAME AND STATE ------
# Invalid Input                     |
# Name (< 3 chars)                  |
# Empty Field                       |
#                                   |
# Valid inputs that return:         |  
# --- LAST ---                      |
# No results    x4                  |
# Results       x4                  |
#                                   |
# --- LAST + STATE ---              |
# No results    x4                  |
# Results       x4                  |
#                                   |
# --- FIRST + LAST ---              |
# No results    x4                  |
# Results       x4                  |
#                                   |
# --- FIRST + LAST + STATE ---      |
# No results    x4                  |
# Results       x4                  |
# -----------------------------------
#     
# ------- PHONE NUMBER SEARCH -------
# Invalid Input:                    |
# Characters/Symbols (Strip)        |
# Digits != 10                      |
#                                   |
# Valid input that returns:         |
# No results    x4                  |
# Results       x4                  |
# -----------------------------------