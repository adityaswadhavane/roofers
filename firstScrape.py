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
from multiprocessing import Pool, Lock, Manager,Value
import os
import uuid
from ctypes import c_int



OUTPUT_FOLDER = "Data/OutputData/FirstScrapeV2/temp_results"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

manager_driver_counter = Value(c_int, 0)

# Setup Chrome options for headless browsing
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--enable-unsafe-swiftshader")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)


# Scroll for search suggestions
def scroll_down_search(driver, by):
    element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[1]/div[1]')
        )
    )
    for _ in range(by):
        driver.execute_script("arguments[0].scrollTop += 5000", element)
        time.sleep(0.2)

lock = Lock()
import  json
# Main scraping logic
def main_scraper(main_row):
    driver = get_driver()
    blank_dict = {col: [] for col in main_row.keys()}
    my_dict = {
        "search_google": [],
        "all_text_first_page": [],
        "google_map_link": [],
    }
    my_dict.update(blank_dict)

    search_google = f"Roofing companies near {main_row['DELIVERY ZIPCODE']}, {main_row['PHYSICAL STATE']}, USA"

    try:
        driver.get("https://www.google.com/maps")
        time.sleep(5)

        search = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="searchboxinput"]'))
        )
        search.clear()
        search.send_keys(search_google)
        search.send_keys(Keys.ENTER)
        time.sleep(3)
        scroll_down_search(driver, 25)
        time.sleep(2)
        get_all_courts = driver.find_elements(By.CLASS_NAME, 'Nv2PK')
        for court in get_all_courts: 
            try:
                all_text_first_page = court.text
                googlemap_link = court.find_element(By.CLASS_NAME, 'hfpxzc').get_attribute('href')

                my_dict['search_google'].append(search_google)
                my_dict['all_text_first_page'].append(all_text_first_page)
                my_dict['google_map_link'].append(googlemap_link)

                for k, v in main_row.items():
                    my_dict[k].append(v)

            except Exception as e:
                continue

    except Exception as e:
        my_dict["error"] = str(e)

    finally:
        driver.quit()

    file_id = f"{main_row['DELIVERY ZIPCODE']}_{uuid.uuid4().hex[:6]}.json"
    with lock:
        with open(os.path.join(OUTPUT_FOLDER, file_id), "w", encoding="utf-8") as f:
            json.dump(my_dict, f, ensure_ascii=False, indent=2)
    
    return my_dict


# Entry point

if __name__ == '__main__':
    start = time.time()
    file_path = r"C:\Users\Dell\PycharmProjects\roofingComapnies\Data\OutputData\Roofers_commpleted.csv"

    df_input = pd.read_excel("Data/InputData/ZipCodes.xlsx",sheet_name='Sheet1').sort_values("Total_records")[['DELIVERY ZIPCODE', 'PHYSICAL CITY', 'PHYSICAL STATE']]
    df_input = df_input[df_input["PHYSICAL STATE"].isin(['WA'])].reset_index(drop=True)
    df_input = df_input.drop_duplicates().reset_index(drop=True)
    print("Total States ",df_input['PHYSICAL STATE'].nunique())

    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path)
        df_input = df_input[~df_input["PHYSICAL STATE"].isin(existing_df['PHYSICAL STATE'])].reset_index(drop=True)

    print("Remaining Total States ",df_input['PHYSICAL STATE'].nunique())

    for state in df_input['PHYSICAL STATE'].unique():
        df_input_state = df_input[df_input["PHYSICAL STATE"] == state].reset_index(drop=True)
        print(df_input_state.shape,"-------------- for the state   ",state)
        rows = df_input_state.to_dict("records")

        with Pool(5) as p:
            results = p.map(main_scraper, rows)

        # Optional: Flatten results to a DataFrame and save
        flat_rows = []
        for result in results:
            flat_rows.extend(pd.DataFrame(result).to_dict("records"))

        df_final = pd.DataFrame(flat_rows)
        df_final.to_pickle(f"Data/OutputData/FirstScrapeV2/Roofing_Companies_{state}.pickle")

        print(f"✅ Scraping completed and saved to Pickle for {state} with total rows {df_final.shape}")
        
        if not os.path.exists(file_path):
            updated_row = pd.DataFrame(rows) 
            updated_row['total_counts'] = df_final.shape[0] 
            updated_row.to_csv(file_path,index=False)
        else:
            updated_row = pd.DataFrame(rows) 
            updated_row['total_counts'] = df_final.shape[0]

            existing_df = pd.read_csv(file_path)     
            updated_df = pd.concat([existing_df, updated_row], ignore_index=True)
            updated_df.to_csv(file_path,index=False)
            print(f"✅ Sheet {state} updated in {file_path}")


    print(f"Total time is {time.time()-start}")