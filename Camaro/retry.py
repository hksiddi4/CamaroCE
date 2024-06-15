import fitz
import csv
import json
import requests
import time
import http.client, urllib
import sys
from variables import *

def extractPDF(contentsGet, vin):
    try:
        with open(f"{year}/temp.pdf", "wb") as f:
            f.write(contentsGet.content)
        doc = fitz.open(f"{year}/temp.pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        with open(f"{year}/RETRY.txt", "a") as f:
            f.write(str(vin + "\n"))
        return None

def extractInfo(text, vin):
    global foundVIN
    if text is None:
        print("Received None text. Skipping this VIN.")
        # Write VIN to RETRY.txt file
        with open(f"{year}/RETRY.txt", "a") as f:
            f.write(str(vin + "\n"))
        return

    # Write VIN to txt file
    with open(f"{year}/camaro_{year}.txt", "a") as f:
        f.write(str(vin + "\n"))
    # Append only the last 6 digits of the VIN to the list and file
    skip_camaro.append(int(vin[-6:]))
    with open(f"{year}/skip_camaro.txt", "a") as file:
        file.write(str(vin[-6:]) + "\n")

    foundVIN += 1
    lines = text.split('\n')
    info = {}
    
    # Define the order of fields
    field_order = ["vin", "year", "model", "body", "trim", "engine", "transmission", "drivetrain",
                   "exterior_color", "msrp", "dealer", "location", "ordernum", "json", "all_rpos"]
    
    info["vin"] = vin
    info["model"] = "CAMARO"
    info["drivetrain"] = "RWD"
    info["body"] = "COUPE"
    for i, line in enumerate(lines):
        if f"{year} CAMARO " in line or f"{year} COUPE CAMARO " in line or f"{year} CABRIOLET CAMARO " in line:
            model_info = ' '.join(line.strip().split())
            info["year"] = model_info[:4].strip()
            modeltrim = model_info[4:].strip().split()
            info["trim"] = ' '.join(modeltrim[1:]).replace(" CONVERTIBLE", "").replace(" COUPE", "").replace("CAMARO ", "")
        if "PRICE*" in line:
            info["msrp"] = lines[i + 1].strip()
        if "DELIVERED" in line:
            info["dealer"] = lines[i + 1].strip().replace("\u2013", "-")
            info["location"] = lines[i + 3].strip()
            json_data = lines[i + 7:i + 11]
            all_json = json.loads(' '.join(json_data))
            info["json"] = all_json
            all_rpos = all_json.get("Options",[])
            all_rpos_filt = [item for item in all_rpos if item]
            info["all_rpos"] = all_rpos_filt

            for item in all_rpos_filt:
                if item in body_dict:
                    info["body"] = body_dict[item]
                if item in colors_dict:
                    info["exterior_color"] = colors_dict[item]
                if item in engines_dict:
                    info["engine"] = engines_dict[item]
                if item in trans_dict:
                    info["transmission"] = trans_dict[item]
                    if info["engine"] == "2.0L Turbo, 4-cylinder, SIDI, VVT":
                        info["transmission"] = "A8"

            if "order_number" in all_json:
                info["ordernum"] = all_json["order_number"]
    
    # Reorder the fields
    info_ordered = {field: info.get(field, None) for field in field_order}
    
    return info_ordered

def writeCSV(pdf_info):
    if pdf_info is None:
        return
    # Define the field names based on the keys of pdf_info
    fieldnames = pdf_info.keys()
    
    # Open the CSV file in append mode with newline='' to avoid extra newline characters
    with open(f"{year}/{year}_camaro.csv", "a", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write the pdf_info to the CSV file
        writer.writerow(pdf_info)

def processVin(vin):
    lastSix = int(vin[-6:])
    urlFirst = "https://cws.gm.com/vs-cws/vehshop/v2/vehicle/windowsticker?vin="

    if lastSix in skip_camaro or lastSix in skip_cadillac:
        print("\033[30mExisting sequence, skipping\033[0m")
        return
    else:
        try:
            newUrl = urlFirst + vin

            max_retries = 3
            retries = 0

            while retries < max_retries:
                try:
                    # Get Request
                    contentsGet = requests.get(newUrl, headers = {'User-Agent': 'camaro count finder version', 'Accept-Language': 'en-US'}, timeout=120)
                    contents = contentsGet.text
                    time.sleep(1)

                    # Check if request returns errorMessage or actual content (meaning a window sticker was found)
                    try:
                        # If json content found = no window sticker
                        jsonCont = json.loads(contents)
                        print("\033[30m" + jsonCont["errorMessage"] + "\033[0m")
                    # If request returns not a json content = window sticker found
                    except json.decoder.JSONDecodeError:
                        # Inform console
                        print("\033[33mMatch Found For VIN: [" + vin + "].\033[0m")
                        pdf_text = extractPDF(contentsGet, vin)
                        pdf_info = extractInfo(pdf_text, vin)
                        writeCSV(pdf_info)
                    break

                except requests.exceptions.ReadTimeout:
                    # Retry request
                    print("Timed out, retrying...")
                    retries += 1
                    time.sleep(120)

        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            if isinstance(e, requests.exceptions.ConnectionError) and isinstance(e.__cause__, ConnectionResetError):
                print("ConnectionResetError occurred. Retrying...")
                return
            else:
                print("Unknown error occurred. Skipping this VIN.")
                # Write VIN to RETRY.txt file
                with open(f"{year}/RETRY.txt", "a") as f:
                    f.write(str(vin + "\n"))
                return

        except KeyboardInterrupt:
            sys.exit(0)

# Open the file RETRY.txt and read lines
with open(f"{year}/RETRY.txt", 'r') as file:
    lines = file.readlines()

foundVIN = 0

i = 0

startTime = time.time()

# Process each line
for vin in lines:
    vin = vin.strip()
    processVin(vin)
    i += 1
print("")

endTime = time.time()
elapsedTime = endTime - startTime

hours = int(elapsedTime // 3600)
remainder = elapsedTime % 3600
minutes = int(remainder // 60)
seconds = int(remainder  % 60)

t = time.localtime()
currentTime = time.strftime("%H:%M:%S", t)
print("Ended:", currentTime, " - Elapsed time: {} hour(s), {} minute(s), {} second(s)".format(hours, minutes, seconds))
print("Tested {} VIN(s) - Found {} match(es)".format(i, foundVIN))
