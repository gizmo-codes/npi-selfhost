<!-- ABOUT THE PROJECT -->
## [NPI Checker](https://npi.omzig.dev)

NPI Checker is a web app that allows you to search for practice information pertaining to any doctor in the United States.
Doctor information is then combined with another query that fetches the doctor's accepted insurance.
Both sets of information are then combined and displayed to the user in a table.

You can search by following:
* NPI number
  - This is unique 10 digit identifier given to medical personnel.
* Last Name
* Last Name and State
* First and Last Name
* First, Last Name, and State
* Telephone Number

Live version is available here: [NPI Checker](https://npi.omzig.dev)

### Built using:
* Python
* jQuery
* HTML/CSS/JS
* SQLite
* Docker

### TODO: (**Currently Implementing Unit Testing**)
- Multi-thread log writing to keep formatting/readability.
- Pipelines (CI/CD).
- Automated unit testing.


### Changelog
#### (9/7/22)
- Heavily refactored code:
  - Removed unreachable blocks.
  - Removed redundant code.
  - Removed/reorganized if-else statements in a more efficient manner.
- Added exception handling for deactivated NPI's.
- Improved input validation
  - State field is now limited to 2 letters
- Improved comments and added explanations for certain implementations.
- Streamlined both formatting function that makes the constructed table row much more readable and easier to work with or modify.

##### (8/30/22)
- Updated new order and referring (insurance) API link.

##### (8/29/22)
- Live logging implemented. Accessed via <npi checker url>/logs -- Example: [https://npi.omzig.dev/logs](https://npi.omzig.dev/logs)
 
##### (8/23/22)
- Fixed API errors caused by previous formatting changes being reverted.
  
##### (8/22/22)
- Fixed API errors caused by formatting changes on their end.
- Updated new API link provided by NPPES
  
##### (8/15/22)
  - Changed docker image to python:3.9-slim -- Cut size of compiled image by ~75%
  
##### (8/1/22)
  - Added basic log page. Accessed via <npi checker url>/logs -- Example: [https://npi.omzig.dev/logs](https://npi.omzig.dev/logs)
  
##### (7/29/22)
  - Added README for project use.
  
##### (7/25/22)
  - Added improved user feedback when searches are invalid.
  
##### (7/24/22)
  - Implemented https
  - Improved input validation/sanitization
  
##### (7/23)
  - Improved input validation/sanitization
  
##### (7/22)
  - Initial Commit
  - Updated logging statements
