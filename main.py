import logging
from seleniumbase import SB
from selenium.webdriver.common.by import By
import platform
import requests
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("dexscreener.log")],
)
logger = logging.getLogger(__name__)


class DexScreenerScraper:
    def __init__(self):
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_admin_id = os.getenv("TELEGRAM_ADMIN_ID")
        self.scraperapi_api_key = os.getenv("SCRAPERAPI_API_KEY")
        self.url = "https://dexscreener.com/?rankBy=trendingScoreM5&order=desc&chainIds=solana&minMarketCap=40000&maxMarketCap=800000"
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

    def send_to_telegram(self, coin_data):
        message_format = """
        🚀 <b>New Fast Mover</b>
        
💎 <b>Coin:</b> {}
💰 <b>Market Cap:</b> {}
⏰ <b>Age:</b> {}
📈 <b>Volume:</b> {}
🔗 <b>Contract Address: </b> <a href="{}">{}</a>
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
                coin_data["ds_url"].split("/")[-1],
            ),
            "parse_mode": "HTML",
        }
        try:
            requests.get(send_message_url, params=params)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")

    def get_coin_data(self, coin_selector):
        try:
            coin_data = {}
            for field, config in self.coin_data_fields.items():
                if "attr" in config:
                    coin_data[field] = coin_selector.get_attribute(config["attr"])
                else:
                    coin_data[field] = coin_selector.find_element(By.CLASS_NAME, config["class"]).text
            return coin_data
        except Exception as e:
            logger.error(f"Error getting coin data: {str(e)}")
            raise

    def check_price_changes(self, coin_data):
        try:
            price_changes = [
                float(coin_data[field].replace("%", "").replace(",", "")) for field in self.price_change_fields
            ]
            return all(change > 0 for change in price_changes)
        except ValueError as e:
            logger.error(f"Error parsing price changes: {str(e)}")
            return False

    def scrape(self):
        logger.info("Starting scraping process")
        try:
            with SB(uc=True, incognito=True, xvfb=True, headless=False) as sb:
                sb.uc_open_with_reconnect(self.url, 5)

                if platform.system() == "Linux":
                    sb.uc_gui_click_captcha()
                else:
                    sb.uc_gui_handle_captcha()

                for i in range(1, 101):
                    coin_selector = sb.find_element(f'//*[@id="root"]/div/main/div/div[4]/a[{i}]')
                    coin_data = self.get_coin_data(coin_selector)

                    if self.check_price_changes(coin_data):
                        self.send_to_telegram(coin_data)
        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        scraper = DexScreenerScraper()
        scraper.scrape()
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
