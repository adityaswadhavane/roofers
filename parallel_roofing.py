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


# Setup Chrome options for headless browsing
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
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
        time.sleep(0.5)


# Main scraping logic
def main_scraper(main_row):
    driver = get_driver()
    blank_dict = {col: [] for col in main_row.keys()}
    my_dict = {
        "search_google": [],
        "all_text_first_page": [],
        "google_map_link": [],
        "current_link": [],
        "all_overview": [],
        "start_dist": []
    }
    my_dict.update(blank_dict)

    search_google = f"Roofing companies {main_row['DELIVERY ZIPCODE']} USA"

    try:
        driver.get("https://www.google.com/maps")
        time.sleep(5)

        search = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="searchboxinput"]'))
        )
        search.clear()
        search.send_keys(search_google)
        search.send_keys(Keys.ENTER)
        time.sleep(7)
        scroll_down_search(driver, 50)

        get_all_courts = driver.find_elements(By.CLASS_NAME, 'Nv2PK')
        for court in get_all_courts: 
            try:
                all_text_first_page = court.text
                googlemap_link = court.find_element(By.CLASS_NAME, 'hfpxzc').get_attribute('href')

                ActionChains(driver).move_to_element(court).click(court).perform()
                time.sleep(3)
                current_url = driver.current_url

                # Overview tab
                try:
                    overview = driver.find_elements(By.CLASS_NAME, 'RcCsl')
                    all_overview = [over.text for over in overview]
                except:
                    all_overview = []

                # Attempt to click the Distance tab
                try:
                    driver.find_elements(By.CLASS_NAME, 'LRkQ2')[1].click()
                except:
                    pass

                try:
                    time.sleep(5)
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

                # Store results
                my_dict['search_google'].append(search_google)
                my_dict['all_text_first_page'].append(all_text_first_page)
                my_dict['google_map_link'].append(googlemap_link)
                my_dict['current_link'].append(current_url)
                my_dict['all_overview'].append(all_overview)
                my_dict['start_dist'].append(df.to_dict())

                for k, v in main_row.items():
                    my_dict[k].append(v)

            except Exception as e:
                continue

    except Exception as e:
        my_dict["error"] = str(e)

    finally:
        driver.quit()

    return my_dict


# Entry point
if __name__ == '__main__':
    df_input = pd.read_excel("ZipCodes.xlsx")[['DELIVERY ZIPCODE', 'PHYSICAL CITY', 'PHYSICAL STATE']]
    df_input = df_input.drop_duplicates().reset_index(drop=True)
    df_input = df_input[df_input["PHYSICAL STATE"] == "CA"].reset_index(drop=True)
    print(df_input)
    rows = df_input.to_dict("records")

    with Pool(5) as p:
        results = p.map(main_scraper, rows)

    # Optional: Flatten results to a DataFrame and save
    flat_rows = []
    for result in results:
        flat_rows.extend(pd.DataFrame(result).to_dict("records"))

    df_final = pd.DataFrame(flat_rows)
    df_final.to_pickle("Google_Maps_Roofing_Companies_CA_parallel.pickle")

    print("✅ Scraping completed and saved to Pickle.")
