"""Module providing a CsvCreator."""

from __future__ import annotations

import csv
import json
import os
import shutil
import time
import traceback
import urllib.parse
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import playwright
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests_file import FileAdapter
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.service import Service as ChromiumService
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from typing_extensions import deprecated
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from webdriver_manager.firefox import GeckoDriverManager
from pyvirtualdisplay import Display
from playwright.sync_api import sync_playwright

class CsvCreator:
    """Class for outputting Csv."""

    TIMEZONE = timezone(timedelta(hours=+9), 'JST')
    CSV_HEADER = ['社名', '番号', '住所', 'URL', '検索キーワード', '検索地域', '日時']

    def __init__(self, **kwargs):
        self.areas = kwargs['areas']
        self.keyword = kwargs['keyword']
        self.filename = kwargs['filename']
        self.encoding = kwargs['encoding']
        self.uri = kwargs['uri']
        self.timeout = kwargs['timeout']
        self.interval = kwargs['interval']

    def create(self) -> CsvCreator:
        """Output CSV file."""
        try:
            self._setUp()
            self._write_csv()
            self._tearDown()
        except Exception:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            self._on_error()

    def _now(self) -> datetime:
        """Returns the current time."""
        return datetime.now(self.TIMEZONE)

    def _now_str(self) -> str:
        """Returns the current time as a string."""
        return self._now().strftime('%Y年%m月%d日 %H:%M:%S')

    def _search_url(self, from_param, area_param, keyword_param):
        if self.uri.startswith('http'):
            return f'{self.uri}/keyword?from={from_param}&areaword={area_param}&keyword={keyword_param}&sort=01'

        parsed_url = urlparse(self.uri)
        original_filename = os.path.basename(parsed_url.path)
        filename, file_extension = os.path.splitext(original_filename)
        filename = f"{filename.split('_')[0]}_{str(int(from_param / 20) + 1).zfill(2)}{file_extension}"
        return self.uri.replace(original_filename, filename)

    @abstractmethod
    def _setUp(self):
        """setUp."""

    @abstractmethod
    def _tearDown(self):
        """tearDown."""

    def _on_error(self):
        """Cleaning up after an error."""
        if os.path.isfile(self.filename):
            os.remove(self.filename)
        self._tearDown()

    @abstractmethod
    def _write_csv(self):
        """Write to CSV file"""


class CsvCreatorFactory:
    """Factory class for CsvCreator."""

    @staticmethod
    def create_csv_creator(**kwargs) -> CsvCreator:
        """Returns an instance of CsvCreator."""

        lib = kwargs['lib']
        if lib == 'requests':
            return RequestsCsvCreator(**kwargs)
        if lib == 'selenium':
            return SeleniumCsvCreator(**kwargs)
        if lib == 'playwright':
            return PlaywrightCsvCreator(**kwargs)
        raise ValueError(f'Unknown type: {lib}')


@deprecated('It does not work well.')
class RequestsCsvCreator(CsvCreator):
    """CsvCreator for requests."""

    # Override
    def _setUp(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)
        print('uri', self.uri, self.uri.startswith('file:///opt/python/scraping_tp_ubuntu_rye/src/scraping_tp_ubuntu_rye/static/html/'))
        if self.uri.startswith('file:///opt/python/scraping_tp_ubuntu_rye/src/scraping_tp_ubuntu_rye/static/html/'):
            shutil.unpack_archive('scraping_tp_ubuntu_rye/static/html.zip', 'scraping_tp_ubuntu_rye/static/html')

    # Override
    def _tearDown(self):
        if os.path.isdir('scraping_tp_ubuntu_rye/static/html'):
            shutil.rmtree('scraping_tp_ubuntu_rye/static/html')

    def __beautiful_soup_instance(self, url, from_param):
        session = requests.Session()
        user_agent = UserAgent().chrome

        if url.startswith('http'):
            target_url = f'{url}&from={from_param}'
            res = session.get(target_url, headers={'User-Agent': user_agent, 'Content-Type': 'text/html'}, timeout=self.timeout)
            return BeautifulSoup(res.content.decode('utf-8'), 'html.parser')

        parsed_url = urlparse(url)
        original_filename = os.path.basename(parsed_url.path)
        filename, file_extension = os.path.splitext(original_filename)
        if from_param:
            filename = f"{filename.split('_')[0]}_{str(int(from_param / 20) + 1).zfill(2)}{file_extension}"
            target_url = url.replace(original_filename, filename)
        else:
            target_url = url

        session.mount('file://', FileAdapter())
        res = session.get(target_url, headers={'User-Agent': user_agent})
        with open(target_url.replace('file://', ''), mode='r', encoding='utf-8') as file:
            return BeautifulSoup(file, 'html.parser')

    # Override
    def _write_csv(self):
        print('INFO ', self._now(), f'{self.keyword}のCSVを出力します')
        keyword_param = urllib.parse.quote(self.keyword)
        page = 1
        company_count = 0
        PER_PAGE = 20

        with open(self.filename, 'w', encoding=self.encoding, newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.CSV_HEADER)

        for area in self.areas:
            print('INFO ', self._now(), f'{area}のCSVを出力します')
            area_param = urllib.parse.quote(area)

            while True:
                from_param = (page - 1) * PER_PAGE
                search_url = self._search_url(from_param, area_param, keyword_param)
                soup = self.__beautiful_soup_instance(search_url, from_param=from_param)
                json_element = soup.find('script', type='application/ld+json')
                company_elements = []
                row_count = 0
                if json_element:
                    print('INFO ', self._now(), f'JSONデータを解析します({page})')
                    json_ld = json.loads(json_element.text)
                    row_count = self._write_csv_by_json(area=area, json=json_ld)

                else:
                    print('INFO ', self._now(), f'HTMLを解析します({page})')
                    company_elements = soup.select(
                        'div.dev-only-search-result-itemContainer[role="listitem"],div.dev-only-search-searchResultsBottom-itemContainer[role="listitem"]'
                    )
                    row_count = self._write_csv_by_html(area=area, elements=company_elements)

                company_count += row_count
                if row_count < PER_PAGE:
                    print('INFO ', self._now(), f'{area}を{company_count}件出力しました')
                    page = 1
                    company_count = 0
                    time.sleep(self.interval)
                    break

                page += 1
                time.sleep(self.interval)

        print('INFO ', self._now(), f'{self.keyword}のCSVを出力しました')

    def _write_csv_by_json(self, area='', json=None) -> int:
        company_count = 0
        if not json:
            return company_count

        for element in json:
            row = []
            item = element.get('item', {})
            company_name = item['name']
            if not company_name:
                raise ValueError('company name is none.')
            row.append(company_name)  # 社名
            row.append(item['telephone'])  # 番号
            address = item.get('address', {})
            row.append(f"{address['addressLocality']}{address.get('streetAddress', '')}")  # 住所
            row.append(item['url'])
            row.append(self.keyword)
            row.append(area)
            row.append(self._now_str())
            company_count += 1
            with open(self.filename, 'a', encoding=self.encoding, newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)

        return company_count

    def _write_csv_by_html(self, area='', elements=None) -> int:
        company_count = 0
        if not elements:
            return company_count

        for element in elements:
            row = []
            company_name_element = element.select_one('p.font_8 a')
            if not company_name_element:
                raise ValueError('company name is none.')
            row.append(company_name_element.text)  # 社名
            tel_element = element.select_one(
                'div.dev-only-searchResultsTop-phone > p > span,div.dev-only-searchResultsBottom-phone > p > span'
            )
            row.append(tel_element.text)  # 番号
            address_element = element.select_one(
                'div.dev-only-searchResultsTop-address > p > span,div.dev-only-searchResultsBottom-address > p > span'
            )
            row.append(address_element.text)  # 住所
            website_element = element.select_one(
                'div.dev-only-searchResultsTop-website > p > a,div.dev-only-searchResultsBottom-website > p > a'
            )
            website = website_element.get('href') if website_element else ''
            row.append(website)  # URL
            row.append(self.keyword)  # 検索キーワード
            row.append(area)  # 検索地域
            row.append(self._now_str())  # 日時
            company_count += 1
            with open(self.filename, 'a', encoding=self.encoding, newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)

        return company_count


class SeleniumCsvCreator(CsvCreator):
    """CsvCreator for selenium."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.browser = kwargs['browser']
        self.driver = None
        self.display = None
        self.wait = None

    def _build_driver(self):
        # if self.display is None:
        #     self.display = Display(visible=0, size=(800, 600))
        if self.browser == 'chrome':
            options = webdriver.ChromeOptions()
            options.set_capability('browserVersion', 'stable')
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("--single-process")
            options.add_argument('--enable-javascript')
            # options.add_argument('--remote-debugging-pipe')
            options.add_argument('----user-agent={UserAgent().chrome}')
            self.driver = webdriver.Chrome(options=options)
            # self.display = Display(visible=0, size=(800, 600))

        elif self.browser == 'firefox':
            options = webdriver.FirefoxOptions()
            options.set_capability('browserVersion', 'stable')
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('----user-agent={UserAgent().firefox}')
            firefox_profile = FirefoxProfile()
            firefox_profile.set_preference("javascript.enabled", True)
            options.profile = firefox_profile
            self.driver = webdriver.Firefox(options=options)
        else:
            raise ValueError(f'Unknown browser {self.browser}')

    # Override
    def _setUp(self):
        self._build_driver()
        self.wait = WebDriverWait(driver=self.driver, timeout=self.timeout)

        if os.path.isfile(self.filename):
            os.remove(self.filename)
        if self.uri.startswith('file:///opt/python/scraping_tp_ubuntu_rye/src/scraping_tp_ubuntu_rye/static/html/'):
            shutil.unpack_archive('static/html.zip', 'static/html')

    # Override
    def _write_csv(self):
        print('INFO ', self._now(), f'{self.keyword}のCSVを出力します')
        keyword_param = urllib.parse.quote(self.keyword)
        page = 1
        company_count = 0
        PER_PAGE = 20

        with open(self.filename, 'w', encoding=self.encoding, newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.CSV_HEADER)

        if self.display:
            self.display.start()

        for area in self.areas:
            area_param = urllib.parse.quote(area)
            while True:
                print('DEBUG', self._now(), f'{area}:{page}ページ目')
                if self.driver is None:
                    self._build_driver()

                from_param = (page - 1) * PER_PAGE
                search_url = self._search_url(from_param, area_param, keyword_param)
                print('DEBUG', self._now(), 'search_url', search_url)
                # try:
                #     self.driver.get(search_url)
                # except selenium.common.exceptions.WebDriverException:
                #     traceback.print_exc()
                self.driver.get(search_url)

                try:
                    self.wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.dev-only-search-result-itemContainer[role="listitem"]'))
                    )
                except TimeoutException as e:
                    print('DEBUG', self._now(), self.driver.page_source)
                    raise e

                time.sleep(self.interval)  # 描画が完了するのにタイムラグが有る
                # ==============================
                # ページ上部
                # ==============================
                elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.dev-only-search-result-itemContainer[role="listitem"]')
                print('DEBUG', self._now(), f'ページ上部で{len(elements)}件取得しました')
                row_count = 0
                for element in elements:
                    row = []
                    company_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsTop-title > p.font_8 > a')
                    row.append(company_element.text)  # 社名
                    phone_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsTop-phone > p.font_3 > span')
                    row.append(phone_element.text)  # 番号
                    address_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsTop-address > p.font_8 > span')
                    row.append(address_element.text)  # 住所
                    website_elements = element.find_elements(By.CSS_SELECTOR, 'div.dev-only-searchResultsTop-website > p.font_8 > a')
                    website = website_elements[0].get_attribute('href') if website_elements else ''
                    row.append(website)  # URL
                    row.append(self.keyword)  # 検索キーワード
                    row.append(area)  # 検索地域
                    row.append(self._now_str())  # 日時
                    with open(self.filename, 'a', encoding=self.encoding, newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(row)
                row_count += len(elements)

                # ==============================
                # ページ下部
                # ==============================
                elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 'div.dev-only-search-searchResultsBottom-itemContainer[role="listitem"]'
                )
                print('DEBUG', self._now(), f'ページ下部で{len(elements)}件取得しました')
                for element in elements:
                    row = []
                    company_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsBottom-title > p.font_8 > a')
                    row.append(company_element.text)  # 社名
                    phone_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsBottom-phone > p.font_3 > span')
                    row.append(phone_element.text)  # 番号
                    address_element = element.find_element(By.CSS_SELECTOR, 'div.dev-only-searchResultsBottom-address > p.font_8 > span')
                    address = address_element.text if address_element else ''
                    row.append(address)  # 住所
                    website_elements = element.find_elements(By.CSS_SELECTOR, 'div.dev-only-searchResultsBottom-website > p.font_8 > a')
                    website = website_elements[0].get_attribute('href') if website_elements else ''
                    row.append(website)  # URL
                    row.append(self.keyword)  # 検索キーワード
                    row.append(area)  # 検索地域
                    row.append(self._now_str())  # 日時
                    with open(self.filename, 'a', encoding=
                              self.encoding, newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(row)
                row_count += len(elements)
                company_count += row_count

                # page_buttons = self.driver.find_elements(
                #     By.CSS_SELECTOR, 'div.dev-only-search-paginationRpt > div[role="list"] > div[role="listitem"] button'
                # )
                # target_button = page_buttons[page]
                # if row_count < PER_PAGE or target_button is None:
                #     print('INFO ', self._now(), f'{area}を{company_count}件出力しました')
                #     page = 1
                #     company_count = 0
                #     time.sleep(self.interval)
                #     break

                # page += 1
                # target_button.click()
                # time.sleep(self.interval)
                # TODO: 一旦切断しないと継続できない
                if row_count < PER_PAGE:
                    print('INFO ', self._now(), f'{area}を{company_count}件出力しました')
                    page = 1
                    company_count = 0
                    # self.driver.close()
                    # self.driver.quit()
                    # self.driver = None
                    time.sleep(self.interval)
                    break

                page += 1
                time.sleep(self.interval)
                # self.driver.close()
                # self.driver.quit()
                # self.driver = None

        print('INFO ', self._now(), f'{self.keyword}のCSVを出力しました')

    # Override
    def _tearDown(self):
        if os.path.isdir('scraping_tp_ubuntu_rye/static/html'):
            shutil.rmtree('scraping_tp_ubuntu_rye/static/html')

        if self.driver:
          self.driver.close()
          self.driver.quit()

        if self.display:
            try:
                self.display.stop()
            except:
                pass

class PlaywrightCsvCreator(CsvCreator):
    """CsvCreator for playwright."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.browser = kwargs['browser']
        self.playwright = None
        self.launcher = None
        self.context = None
        self.display = None

    # Override
    def _setUp(self):
        self.display = Display(visible=0, size=(800, 600))
        self.display.start()
        self.playwright = sync_playwright().start()
        user_agent = None
        if self.browser == 'chrome':
            # self.launcher = self.playwright.chromium.launch()
            self.launcher = self.playwright.chromium.launch(headless=False)
            self.context = self.launcher.new_context(ignore_https_errors=True, user_agent = UserAgent().chrome)

        elif self.browser == 'firefox':
            # self.launcher = self.playwright.firefox.launch()
            self.launcher = self.playwright.firefox.launch(headless=False)
            self.context = self.launcher.new_context(ignore_https_errors=True)
            # self.context = self.launcher.new_context()
        else:
            raise ValueError(f'Unknown browser {self.browser}')

    # Override
    def _write_csv(self):
        print('INFO ', self._now(), f'{self.keyword}のCSVを出力します')

        # page = self.context.new_page()
        # page = self.context.new_page()
        # page.set_default_timeout(self.timeout * 1000)
        # page.set_default_timeout(0)
        # page.set_default_navigation_timeout(60000)
        keyword_param = urllib.parse.quote(self.keyword)
        page_no = 1
        company_count = 0
        PER_PAGE = 20

        with open(self.filename, 'w', encoding=self.encoding, newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.CSV_HEADER)

        for area in self.areas:
            area_param = urllib.parse.quote(area)
            while True:
                print('DEBUG', self._now(), f'{area}:{page_no}ページ目')
                from_param = (page_no - 1) * PER_PAGE
                search_url = self._search_url(from_param, area_param, keyword_param)
                print('DEBUG', self._now(), 'search_url', search_url)
                # page.goto(search_url, timeout = self.timeout * 1000)
                PAGING_AREA_SELECTOR = 'div.dev-only-search-paginationRpt'
                HEADER_ITEMS_SELECTOR = 'div.dev-only-search-result-itemContainer[role="listitem"]'

                # page.on("request", lambda request: print(">>", request.method, request.url))
                # page.on("response", lambda response: print("<<", response.status, response.url))
                # try:
                #     if page_no == 1:
                #         page.goto(search_url)
                #         locator = page.locator(PAGING_AREA_SELECTOR)
                #         locator.wait_for()
                #     else:
                #         page = self.context.new_page() # 後ろにもっていく
                #         page.goto(search_url)
                #         locator = page.locator(PAGING_AREA_SELECTOR)
                #         locator.scroll_into_view_if_needed() # たぶん不要
                #         locator.wait_for()
                # except Exception as e:
                #     print('DEBUG', self._now(), page.content())
                #     raise e
                page = self.context.new_page()
                page.set_default_timeout(self.timeout * 1000)
                page.goto(search_url)
                # response = page.goto(search_url)
                # print(response.status_text)
                # locator = page.locator(PAGING_AREA_SELECTOR)
                locator = page.locator(f'{HEADER_ITEMS_SELECTOR}:last-child')
                try:
                    locator.wait_for()
                except Exception as e:
                    print(page.content())
                    raise e

                # page.wait_for_selector(PAGING_AREA_SELECTOR)
                # locator = page.locator(PAGING_AREA_SELECTOR)
                # locator.scroll_into_view_if_needed()
                # locator.wait_for(state = 'attached')

                # ==============================
                # ページ上部
                # ==============================
                # header_selector = 'div.dev-only-search-result-itemContainer[role="listitem"]'
                # locator = page.locator(header_selector).nth(1)
                # locator.wait_for()
                # elements = page.locator(header_selector).all()
                # page.wait_for_selector(f'{header_selector}:last-child div.dev-only-searchResultsTop-title > p.font_8 > a')
                elements = page.query_selector_all(HEADER_ITEMS_SELECTOR)
                print('DEBUG', self._now(), f'ページ上部で{len(elements)}件取得しました')
                row_count = 0
                for element in elements:
                    row = []
                    company_element = element.query_selector('div.dev-only-searchResultsTop-title > p.font_8 > a')
                    row.append(company_element.text_content())  # 社名
                    phone_element = element.query_selector('div.dev-only-searchResultsTop-phone > p.font_3 > span')
                    row.append(phone_element.text_content())  # 番号
                    address_element = element.query_selector('div.dev-only-searchResultsTop-address > p.font_8 > span')
                    address = address_element.text_content() if address_element else ''
                    row.append(address)  # 住所
                    website_elements = element.query_selector_all('div.dev-only-searchResultsTop-website > p.font_8 > a')
                    website = website_elements[0].get_attribute('href') if website_elements else ''
                    row.append(website)  # URL
                    row.append(self.keyword)  # 検索キーワード
                    row.append(area)  # 検索地域
                    row.append(self._now_str())  # 日時
                    with open(self.filename, 'a', encoding=self.encoding, newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(row)
                row_count += len(elements)
                if row_count == 0:
                    # print('DEBUG', self._now(), page.content())
                    raise Exception('要素が取得できませんでした')

                # ==============================
                # ページ下部
                # ==============================
                elements = page.query_selector_all('div.dev-only-search-searchResultsBottom-itemContainer[role="listitem"]')
                print('DEBUG', self._now(), f'ページ下部で{len(elements)}件取得しました')
                for element in elements:
                    row = []
                    company_element = element.query_selector('div.dev-only-searchResultsBottom-title > p.font_8 > a')
                    row.append(company_element.text_content())  # 社名
                    phone_element = element.query_selector('div.dev-only-searchResultsBottom-phone > p.font_3 > span')
                    row.append(phone_element.text_content())  # 番号
                    address_element = element.query_selector('div.dev-only-searchResultsBottom-address > p.font_8 > span')
                    address = address_element.text_content() if address_element else ''
                    row.append(address)  # 住所
                    website_elements = element.query_selector_all('div.dev-only-searchResultsBottom-website > p.font_8 > a')
                    website = website_elements[0].get_attribute('href') if website_elements else ''
                    row.append(website)  # URL
                    row.append(self.keyword)  # 検索キーワード
                    row.append(area)  # 検索地域
                    row.append(self._now_str())  # 日時
                    with open(self.filename, 'a', encoding=
                              self.encoding, newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(row)
                row_count += len(elements)
                company_count += row_count

                next_page_button = page.query_selector(f'{PAGING_AREA_SELECTOR} button[aria-disabled="false"]')
                if row_count < PER_PAGE or next_page_button is None:
                    print('INFO ', self._now(), f'{area}を{company_count}件出力しました')
                    page_no = 1
                    company_count = 0
                    self.launcher.close()
                    self.playwright.stop()
                    self._setUp()
                    time.sleep(self.interval)
                    # time.sleep(60)
                    # page.close()
                    break

                page_no += 1
                self.launcher.close()
                self.playwright.stop()
                self._setUp()
                time.sleep(self.interval)
                # next_page_button.click()
                # time.sleep(60)

        # page.close()
        print('INFO ', self._now(), f'{self.keyword}のCSVを出力しました')

    def _tearDown(self):
        if os.path.isdir('scraping_tp_ubuntu_rye/static/html'):
            shutil.rmtree('scraping_tp_ubuntu_rye/static/html')

        if self.playwright:
            self.playwright.stop()

        if self.display:
            self.display.stop()
