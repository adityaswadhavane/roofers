# from geopy.geocoders import Nominatim

# import pandas as pd

# data = pd.read_pickle("C:/Users/Dell/PycharmProjects/roofingComapnies/Data/OutputData/NyRoofFirstScrape.pickle")

# def get_address(lat,long):
#     l = str(lat)
#     lg = str(long)
#     try:
#         geolocator = Nominatim(user_agent="my_geopy_app")
#         location = geolocator.reverse(l+","+lg)
#         return [location.address,location.raw['address']]
#     except:
#         return {}


# import numpy as np
# data['geopyAddress'] = np.vectorize(get_address)(data['Lat'],data['Long'])
# data.to_pickle("NyAdd.pickle")


import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from multiprocessing import Pool
from multiprocessing import Pool, Lock, Manager,Value


# Setup Chrome options for headless browsing
def get_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

import uuid
import os
import json

# Scroll for search suggestions
def scroll_down_search(driver, by):
    element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[1]/div[1]')
        )
    )
    for _ in range(by):
        driver.execute_script("arguments[0].scrollTop += 5000", element)
        time.sleep(0.5)

import requests
headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
link = "https://www.google.com/maps/place/Eagle+Roofing+Contractor+Inc./data=!4m7!3m6!1s0x89e82b58c6c189b3:0x69f9dd484c408da7!8m2!3d40.8327239!4d-73.2616423!16s%2Fg%2F11h0vq_b0j!19sChIJs4nBxlgr6IkRp41ATEjd-Wk?authuser=0&hl=en&rclk=1"
response = requests.get(link, headers=headers, timeout=20)
if response.status_code != 200:
    raise Exception(f"Request failed with status code {response.status_code}")

time.sleep(5)

soup = BeautifulSoup(response.text, "html.parser")

try:
    overview = soup.find_all(class_="RcCsl")
    for e in overview:
        print(e.text)
    all_overview = [over.text for over in overview]
except:
    all_overview = []

try:
    time.sleep(0.5)
    # table_data = driver.find_element(By.CLASS_NAME, 'ExlQHd').get_attribute('outerHTML')
    # soup = BeautifulSoup(table_data, 'html.parser')
    table = soup.find('table')
    rows = table.find_all('tr')
    data = []
    for row in rows:
        aria_label = row.get('aria-label')
        if aria_label:
            data.append([aria_label])
    df = pd.DataFrame(data, columns=['aria-label'])
except:
    df = pd.DataFrame()




