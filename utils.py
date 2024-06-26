import traceback

import time
import pyotp
import sys
from config import (
    WALLETS,
    links,
    token,
    chain,
    EMAIL_LOGIN,
    EMAIL_2FA,
    OKX_2FA,
    IMAP_URL,
)
from loguru import logger

from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

from imap_tools import MailBox


from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium import webdriver

from selenium.webdriver.remote.webelement import WebElement


from services.authenticator import OTP
from services import random_string
from services.user_data import create_json, read_json

from config import Config as cfg


class OKX:
    def __init__(self):
        self.okx_url_login = "https://www.okx.cab/ru/account/login"
        service = Service()
        self.browser = webdriver.Chrome(service=service)
        self.actions = ActionChains(self.browser)
        self.keys = Keys()
        self.AMOUNT_WALLETS = 20  # There's a maximum of 20 wallets in one pack
        self._zero = 0
        self._len_wallets = len(WALLETS)
        self.wallets_batches = [
            WALLETS[i : i + self.AMOUNT_WALLETS]
            for i in range(0, len(WALLETS), self.AMOUNT_WALLETS)
        ]

    @staticmethod
    def manual_login():
        logger.info("Log in to your account and press ENTER")
        input()

    def scroll_window(self, x: int = 0, y: int = 50, up: bool = False):
        """
        Scrolls the window by the specified amount.

        Args:
            x (int): The horizontal scroll amount (default is 0).
            y (int): The vertical scroll amount (default is 50).
            up (bool): If True, scrolls the window upwards; if False, scrolls the window downwards (default is False).

        Returns:
            None
        """
        if up:
            y = -y
        self.browser.execute_script(f"window.scrollBy({x}, {y})")

    def filling_addresses(self, wallets: list):
        """Select the network and fill in the addresses in the fields"""

        # choose a chain
        element = self.wait_an_element(
            By.XPATH, "//input[@placeholder='Выберите сеть']"
        )
        if element:
            try:
                element.click()
            except (
                ElementClickInterceptedException,
                StaleElementReferenceException,
            ):
                time.sleep(3)
                element = self.wait_an_element(
                    By.XPATH, "//input[@placeholder='Выберите сеть']"
                )
                element.click()
        time.sleep(0.3)
        chains = self.browser.find_elements(
            By.CLASS_NAME, "balance_okui-select-item"
        )
        try:
            for i in chains:
                if chain in i.text:
                    i.click()
                    continue
        except Exception as error:
            logger.error(f"Error in filling_addresses function: {error}")
        time.sleep(0.3)

        # click add wallet
        for i in range(0, len(wallets) - 1):
            btn = self.browser.find_element(
                By.XPATH,
                "/html/body/div[1]/div/div/div/div[2]/div/form/button/span",
            )
            if btn:
                btn.click()
            else:
                self.browser.find_element(
                    By.XPATH,
                    "/html/body/div[1]/div/div/div/div[2]/div/form/button",
                ).click()
                self.scroll_window()
            time.sleep(0.5)
        delete_acc = []

        input_forms = self.browser.find_elements(
            By.CLASS_NAME, "balance_okui-input-input"
        )

        input_forms = [
            i
            for i in self.browser.find_elements(
                By.CLASS_NAME, "balance_okui-input-input"
            )
            if "Адрес" in i.accessible_name
        ]
        for wallet, form, _ in zip(
            wallets, input_forms, range(0, self.AMOUNT_WALLETS)
        ):
            try:  # TODO: try/except block for debugging. To be removed later.
                self._zero += 1
                logger.info(
                    f"add : {wallet} [{self._zero}/{self._len_wallets}]"
                )
                self.actions.scroll_to_element(form).perform()
                time.sleep(0.1)
                form.send_keys(wallet)
                delete_acc.append(wallet)
                time.sleep(0.01)
            except Exception:
                traceback.print_exc()

        # filling a checkbox
        self.browser.find_element(
            By.XPATH,
            "/html/body/div[1]/div/div/div/div[2]"
            "/div/form/div[3]/div/div/div/label/span[1]/input",
        ).click()

        # clicking a submit button
        self.browser.find_element(
            By.XPATH,
            "/html/body/div[1]/div/div/div"
            "/div[2]/div/form/div[4]/div/div/div/button",
        ).click()
        time.sleep(1)

    def wait_an_element(self, by, element_selector: str, wait_time: int = 5):
        try:
            WebDriverWait(self.browser, wait_time).until(
                ec.presence_of_element_located((by, element_selector))
            )
            return self.browser.find_element(by, element_selector)
        except TimeoutException:
            logger.error(
                f"Error while waiting for an element: {element_selector}"
            )
            sys.exit(-1)

    def confirmations(self):
        """Get the code from the mail and insert 2FA, close the window"""
        while True:
            for i in range(5):
                try:
                    time.sleep(1)
                    element = self.wait_an_element(
                        By.XPATH, "//span[text()='Отправить код']"
                    )
                    if element:
                        element.click()
                    logger.success("Send code to email")
                    time.sleep(15)
                    break
                except Exception as error:
                    logger.error(f"Error in confirmations function: {error}")
            with MailBox(IMAP_URL).login(EMAIL_LOGIN, EMAIL_2FA) as mailbox:
                for msg in mailbox.fetch(limit=1, reverse=True):
                    if "код" in msg.html or "code" in msg.html:
                        code_email = (
                            msg.html.split('class="code" style')[1]
                            .split(">")[1]
                            .split("</div")[0]
                            .strip()
                        )
                        logger.success(f"mail_code : {code_email}")
                        check = True
                    else:
                        logger.info("Couldnt find the code, trying again")
                        check = False
                        time.sleep(5)
            if check:
                break
        code_forms = self.browser.find_elements(
            By.XPATH, "//input[@placeholder='Ввести код']"
        )
        code_forms[0].send_keys(code_email)
        time.sleep(0.2)
        totp = pyotp.TOTP(OKX_2FA)
        code_forms[1].send_keys(totp.now())
        time.sleep(0.3)
        self.browser.find_elements(By.CLASS_NAME, "btn-content")[-1].click()
        time.sleep(2)
        self.browser.get(
            "https://www.okx.cab/ru/balance/withdrawal-address/eth/2"
        )

    def add_addresses(self):
        """
        A method to perform a series of actions, including accessing a URL, performing a manual login, accessing specific links,
         filling addresses, and handling confirmations.
        """
        self.browser.get(self.okx_url_login)
        time.sleep(5)
        self.manual_login()
        time.sleep(5)
        self.browser.get(links[token]["link"])
        time.sleep(5)
        for wallets in self.wallets_batches:
            while True:
                self.filling_addresses(wallets)
                self.confirmations()
                break

            self.browser.get(links[token]["link"])
            logger.info("Sleep for 60   sec.")
            time.sleep(60)
        print()

    def confirm_modal(self) -> None:
        dialog_container = self.wait_an_element(
            by=By.CSS_SELECTOR,
            element_selector="div[class="
            "'okui-dialog-window okui-dialog-window-float']",
        )
        button = dialog_container.find_element(By.TAG_NAME, "button")
        self.actions.click(button).perform()

    def sa_deletion(self, settings_button: WebElement) -> None:
        self.actions.move_to_element(settings_button).perform()

        setup_item_box = self.wait_an_element(
            by=By.CLASS_NAME, element_selector="subaccount-setup-item-box"
        )
        delete_button = setup_item_box.find_element(
            By.CSS_SELECTOR, "div[class='setup-item text-red delete']"
        )
        self.actions.click(delete_button).perform()

        modal = self.wait_an_element(
            by=By.CLASS_NAME,
            element_selector="okui-form-item-control-input-content",
        )
        input_box = modal.find_element(By.CLASS_NAME, "okui-input-box")

        self.actions.click(input_box).perform()

        input_area = input_box.find_element(By.CLASS_NAME, "okui-input-input")
        otp = OTP().otp

        input_area.send_keys(otp)
        confirm_button = self.wait_an_element(
            by=By.CSS_SELECTOR,
            element_selector="button[class='okui-btn btn-sm "
            "btn-fill-highlight dialog-btn double-btn']",
        )
        self.actions.click(confirm_button).perform()
        time.sleep(5)
        try:
            # Error message indicates that okx does not accept the code.
            # If the message is shown we use recursion.
            self.browser.find_element(
                By.CSS_SELECTOR,
                "div[class='okui-form-item-control-explain-error']",
            )

            # Waiting for an otp to be renewed.
            while otp == OTP().otp:
                time.sleep(1)

            self.sa_deletion(settings_button=settings_button)
        except NoSuchElementException:
            time.sleep(5)

    def delete_subaccounts(self) -> None:
        """Removing all subaccounts"""
        self.browser.get(cfg.SUB_ACCOUNTS_BASE_URL)
        self.manual_login()

        self.confirm_modal()

        sub_account_container = self.wait_an_element(
            by=By.CLASS_NAME, element_selector="sub-account-container"
        )

        settings_buttons = sub_account_container.find_elements(
            By.CLASS_NAME, "subaccount-setup-popup-title"
        )
        for settings_button in settings_buttons:
            self.sa_deletion(settings_button=settings_button)

    def insert_sa_code(self) -> None:
        dialogue_window = self.wait_an_element(
            By.CSS_SELECTOR,
            "div[class='okui-dialog-window "
            "okui-dialog-window-float bottom-align no-margin']",
        )
        input_area = dialogue_window.find_element(
            By.CSS_SELECTOR, "input[placeholder='Ввести код']"
        )
        otp = OTP().otp
        input_area.send_keys(otp)

        submit_button = dialogue_window.find_element(
            By.CSS_SELECTOR,
            "button[class='okui-btn "
            "btn-sm btn-fill-highlight dialog-btn double-btn']",
        )
        submit_button.click()

        try:
            dialogue_window.find_element(
                By.CSS_SELECTOR,
                "div[class='okui-form-item-control-explain-error']",
            )

            while otp == OTP().otp:
                time.sleep(1)
            self.insert_sa_code()
        except NoSuchElementException:
            pass

    def add_subaccounts(self) -> None:
        username = random_string(19)
        self.browser.get(cfg.SUB_ACCOUNTS_BASE_URL)
        self.manual_login()

        self.confirm_modal()

        sub_account_add_container = self.wait_an_element(
            by=By.CLASS_NAME, element_selector="sub-account-add-container"
        )

        WebDriverWait(self.browser, 5).until(
            ec.element_to_be_clickable(sub_account_add_container)
        )

        self.actions.move_to_element(sub_account_add_container).perform()
        self.actions.click(sub_account_add_container).perform()

        subaccount_data = []

        for i in range(3):
            if i == 0:
                area_index = i
            elif i == 1:
                area_index = i * 2
            else:
                area_index = 4

            sa_name = f"{username}{i+1}"

            add_container_area = self.wait_an_element(
                by=By.CLASS_NAME, element_selector="batch-add-container"
            )

            input_areas = add_container_area.find_elements(
                By.CLASS_NAME, "okui-input-input"
            )

            input_area = input_areas[area_index]

            input_area.send_keys(f"{username}{i+1}")

            select_boxes = self.browser.find_elements(
                By.CLASS_NAME, "okui-select"
            )

            select_box = select_boxes[i]

            self.actions.click(select_box).perform()
            select_container = self.browser.find_element(
                By.CSS_SELECTOR,
                "div[class='okui-select-item-container "
                "okui-select-item-container-real']",
            )
            standard_variant = select_container.find_element(
                By.CLASS_NAME, "okui-select-item"
            )
            self.actions.click(standard_variant).perform()

            switch_button = add_container_area.find_elements(
                By.CLASS_NAME, "okui-switch"
            )[i]
            self.actions.click(switch_button).perform()

            add_draft_button = self.browser.find_element(
                By.CSS_SELECTOR,
                "button[class='okui-btn btn-md btn-outline-secondary "
                "index_action-btn__p8O5+ "
                "index_create__N1l4i index_is-inline__s8XOi']",
            )

            if i != 2:
                self.actions.click(add_draft_button).perform()
            else:

                save_button = self.wait_an_element(
                    by=By.CSS_SELECTOR,
                    element_selector="button[class='okui-btn btn-md "
                    "btn-fill-highlight block index_action-btn__p8O5+']",
                )

                self.actions.move_to_element(save_button).perform()
                self.actions.click(save_button).perform()
                self.insert_sa_code()

            subaccount_data.append(dict(name=sa_name, addr=[]))
        create_json(subaccount_data, cfg.SUBACCOUNTS_JSON_PATH)

    def add_deposit_wallets(self) -> None:
        self.browser.get(self.okx_url_login)
        self.manual_login()

        accounts = read_json(path=cfg.SUBACCOUNTS_JSON_PATH)
        for account in accounts:
            account_name = account["name"]

            user_info_button = self.wait_an_element(
                by=By.CLASS_NAME, element_selector="user-info"
            )

            self.actions.move_to_element(user_info_button).perform()

            change_account_button = self.browser.find_element(
                By.ID, "tog-acc-btn"
            )
            change_account_button.click()
            account_buttons = WebDriverWait(self.browser, 5).until(
                ec.presence_of_all_elements_located(
                    (By.CLASS_NAME, "toggle-info")
                )
            )
            for button in account_buttons:
                button_text = button.text
                if account_name in button_text:
                    self.actions.click(button).perform()
                    continue

            self.browser.refresh()
