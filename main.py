import logging
from logging.handlers import RotatingFileHandler
from seleniumbase import SB
from selenium.webdriver.common.by import By
import platform
import requests
import os
import json
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("dexscreener.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"),  # 1MB
    ],
)
logger = logging.getLogger(__name__)


class DexScreenerScraper:
    def __init__(self):
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.scraperapi_api_key = os.getenv("SCRAPERAPI_API_KEY")
        self.url = "https://dexscreener.com/?rankBy=trendingScoreH6&order=desc&chainIds=solana&minLiq=20000&minMarketCap=1000000&maxMarketCap=5000000&maxAge=2&min24HVol=20000"
        self.price_change_fields = ["price-change-m5", "price-change-h1", "price-change-h6", "price-change-h24"]
        self.coin_data_fields = {
            "ds_url": {"attr": "href"},
            **{field: {"class": f"ds-dex-table-row-col-{field}"} for field in self.price_change_fields},
            "token_symbol": {"class": "ds-dex-table-row-base-token-symbol"},
            "price": {"class": "ds-dex-table-row-col-price"},
            "pair_age": {"class": "ds-dex-table-row-col-pair-age"},
            "txns": {"class": "ds-dex-table-row-col-txns"},
            "volume": {"class": "ds-dex-table-row-col-volume"},
            "makers": {"class": "ds-dex-table-row-col-makers"},
            "liquidity": {"class": "ds-dex-table-row-col-liquidity"},
            "market_cap": {"class": "ds-dex-table-row-col-market-cap"},
        }
        self.cache_file = "sent_tokens.json"
        self.load_cache()

    def load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                logger.debug(f"Loading cache from {self.cache_file}")
                with open(self.cache_file, "r") as f:
                    self.sent_tokens = json.load(f)
                # Clean up old entries (older than 24 hours)
                current_time = datetime.now().timestamp()
                old_count = len(self.sent_tokens)
                self.sent_tokens = {
                    token: timestamp
                    for token, timestamp in self.sent_tokens.items()
                    if current_time - timestamp < 24 * 3600
                }
                logger.debug(f"Cleaned up cache: removed {old_count - len(self.sent_tokens)} old entries")
            else:
                logger.debug("Cache file not found, creating new cache")
                self.sent_tokens = {}
        except Exception as e:
            logger.error(f"Error loading cache from {self.cache_file}: {str(e)}", exc_info=True)
            self.sent_tokens = {}

    def save_cache(self):
        try:
            logger.debug(f"Saving {len(self.sent_tokens)} entries to cache")
            with open(self.cache_file, "w") as f:
                json.dump(self.sent_tokens, f)
            logger.debug("Cache saved successfully")
        except Exception as e:
            logger.error(f"Error saving cache to {self.cache_file}: {str(e)}", exc_info=True)

    def was_token_sent_recently(self, token_address):
        current_time = datetime.now().timestamp()
        if token_address in self.sent_tokens:
            # Check if token was sent in the last 24 hours
            return current_time - self.sent_tokens[token_address] < 24 * 3600
        return False

    def mark_token_as_sent(self, token_address):
        self.sent_tokens[token_address] = datetime.now().timestamp()
        self.save_cache()

    def send_to_telegram(self, coin_data):
        token_address = coin_data["ds_url"].split("/")[-1]
        logger.info(f"Preparing to send Telegram message for token {coin_data['token_symbol']} ({token_address})")
        message_format = """
🚨 <b>1 MILLION MARKETCAP MOVER</b> 🚨

📊 <b>Coin:</b> {}
💰 <b>Market Cap:</b> {}
⚡️ <b>Age:</b> {}
📈 <b>Volume:</b> {}

🔗 <a href="{}">View on DexScreener</a>
"""
        send_message_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        params = {
            "chat_id": self.telegram_chat_id,
            "text": message_format.format(
                coin_data["token_symbol"],
                coin_data["market_cap"],
                coin_data["pair_age"],
                coin_data["volume"],
                coin_data["ds_url"],
            ),
            "parse_mode": "HTML",
        }
        try:
            response = requests.get(send_message_url, params=params)
            response.raise_for_status()
            logger.info(f"Successfully sent Telegram message for {coin_data['token_symbol']}")
            self.mark_token_as_sent(token_address)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message for {coin_data['token_symbol']}: {str(e)}", exc_info=True)

    def get_coin_data(self, coin_selector):
        try:
            logger.debug("Extracting coin data from selector")
            coin_data = {}
            for field, config in self.coin_data_fields.items():
                try:
                    if "attr" in config:
                        coin_data[field] = coin_selector.get_attribute(config["attr"])
                    else:
                        coin_data[field] = coin_selector.find_element(By.CLASS_NAME, config["class"]).text
                    logger.debug(f"Extracted {field}: {coin_data[field]}")
                except Exception as field_error:
                    logger.error(f"Failed to extract field {field}: {str(field_error)}")
                    coin_data[field] = None
            return coin_data
        except Exception as e:
            logger.error(f"Error getting coin data: {str(e)}", exc_info=True)
            raise

    def scrape(self):
        logger.info("Starting scraping process")
        try:
            with SB(uc=True, incognito=True, xvfb=True, undetectable=True, page_load_strategy="eager") as sb:
                try:
                    logger.info(f"Opening URL: {self.url}")
                    sb.uc_open_with_reconnect(self.url, 5)

                    logger.info("Handling captcha based on platform")
                    if platform.system() == "Linux":
                        logger.debug("Linux platform detected, using uc_gui_click_captcha")
                        sb.uc_gui_click_captcha()
                    else:
                        logger.debug("Non-Linux platform detected, using uc_gui_handle_captcha")
                        sb.uc_gui_handle_captcha()

                    for i in range(1, 101):
                        try:
                            coin_selector = sb.find_element(f'//*[@id="root"]/div/main/div/div[4]/a[{i}]')
                        except NoSuchElementException:
                            logger.debug(f"No more coins found, stopping at index {i}")
                            break
                        coin_data = self.get_coin_data(coin_selector)
                        token_address = coin_data["ds_url"].split("/")[-1]

                        if not self.was_token_sent_recently(token_address):
                            self.send_to_telegram(coin_data)
                finally:
                    try:
                        sb.clear_session_storage()
                        sb.delete_all_cookies()
                        sb.driver.quit()
                    except Exception as e:
                        logger.error(f"Error during browser cleanup: {e}")

        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}", exc_info=True)
            raise
        finally:
            self.cleanup_temp_files()

    def cleanup_temp_files(self):
        try:
            if platform.system() == "Linux":
                try:
                    subprocess.run(["pkill", "-f", "chrome"], check=False)
                    subprocess.run(["pkill", "-f", "chromedriver"], check=False)
                    logger.debug("Cleaned up Chrome processes")
                except Exception as e:
                    logger.error(f"Error cleaning up Chrome processes: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)


if __name__ == "__main__":
    try:
        scraper = DexScreenerScraper()
        scraper.scrape()
    except Exception as e:
        logger.error(f"Application failed: {str(e)}", exc_info=True)
    finally:
        if "scraper" in locals():
            scraper.cleanup_temp_files()
