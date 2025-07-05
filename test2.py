import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import os
import json

# Setup Chrome driver
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

# Scroll function
def scroll_down_search(driver, by):
    element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[1]/div[1]')
        )
    )
    for _ in range(by):
        driver.execute_script("arguments[0].scrollTop += 5000", element)
        time.sleep(0.5)

# Setup folders
OUTPUT_FOLDER = "Data/OutputData/FinalScrape/temp_results4"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Scraper function (1 item)
def main_scraper(main_row):
    driver = get_driver()
    blank_dict = {col: [] for col in main_row.keys()}
    my_dict = {
        "all_overview": [],
        "start_dist": [],
    }
    my_dict.update(blank_dict)

    link = main_row['google_map_link']

    try:
        driver.get(link)
        time.sleep(7)

        try:
            overview = driver.find_elements(By.CLASS_NAME, 'CsEnBe')
            all_overview = [over.get_attribute("aria-label") for over in overview]
        except:
            all_overview = []

        try:
            driver.find_elements(By.CLASS_NAME, 'LRkQ2')[1].click()
        except:
            pass

        try:
            time.sleep(1)
            table_data = driver.find_element(By.CLASS_NAME, 'ExlQHd').get_attribute('outerHTML')
            soup = BeautifulSoup(table_data, 'html.parser')
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

        my_dict['all_overview'].append(all_overview)
        my_dict['start_dist'].append(df.to_dict())

        for k, v in main_row.items():
            my_dict[k].append(v)

    except Exception as e:
        my_dict["error"] = str(e)

    finally:
        driver.quit()

    file_id = f"{uuid.uuid5(uuid.NAMESPACE_DNS, link)}.json"
    with open(os.path.join(OUTPUT_FOLDER, file_id), "w", encoding="utf-8") as f:
        json.dump(my_dict, f, ensure_ascii=False, indent=2)

    return my_dict

def run_scraper():
    df_input = pd.read_pickle("OR_Data_First_scrape.pickle").head(2)
    rows = df_input.to_dict("records")
    results = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(main_scraper, r): r for r in rows}
        for future in as_completed(futures):
            result = future.result()
            results.append(pd.DataFrame(result))

    pd.concat(results).to_pickle("NewDataDump.pickle")
    print("✅ Scraping completed and saved to Pickle.")

    