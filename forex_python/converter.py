import os
from decimal import Decimal
import simplejson as json
import requests


class RatesNotAvailableError(Exception):
    """
    Custom Exception when https://ratesapi.io is Down and not available for currency rates
    """
    pass

class OpenexchangeAppIdNotAvailableError(Exception):
    """
    Custom Exception when openexchangerates is used an no FOREX_PYTHON_OPENXCHNG_APP_ID is provided
    """
    pass


class DecimalFloatMismatchError(Exception):
    """
    A float has been supplied when force_decimal was set to True
    """
    pass


class ResponseProvider:
    def __init__(self):
        pass

    def __call__(self, base_cur, provider, date_obj, params=None):
        method = 'provide_' + provider
        if hasattr(self, method):
            return getattr(ResponseProvider, method)(base_cur, date_obj, params)

    @staticmethod
    def _get_date_string(date_obj=None):
        """
        :type date_obj: DateTime | None
        :rtype: str
        """
        if date_obj is None:
            return 'latest'
        date_str = date_obj.strftime('%Y-%m-%d')

        return date_str

    @staticmethod
    def provide_openexchangerates(base_cur, date_obj=None, params=None):
        """
        :type base_cur: str
        :type date_obj: datetime | None
        :type params: dict | None
        :rtype: requests
        """

        source_url = os.getenv('FOREX_PYTHON_OPENXCHNG_SOURCE_URL', 'https://openexchangerates.org/api/')
        app_id = os.getenv('FOREX_PYTHON_OPENXCHNG_APP_ID', None)
        if not app_id:
            raise OpenexchangeAppIdNotAvailableError

        date_str = ResponseProvider._get_date_string(date_obj)
        if date_obj:
            source_url += 'historical/'

        payload = {
            'app_id': app_id,
            'base': base_cur
        }
        if params:
            payload.update(params)

        return requests.get(source_url + date_str + '.json', params=payload)

    @staticmethod
    def provide_ratesapi(base_cur, date_obj=None, params=None):
        date_str = ResponseProvider._get_date_string(date_obj)
        payload = {'base': base_cur, 'rtype': 'fpy'}
        if params:
            payload.update(payload)

        source_url = os.getenv('FOREX_PYTHON_OPENXCHNG_SOURCE_URL', 'https://ratesapi.io/api/') + date_str

        requests.get(source_url, params=payload)


class Common:

    def __init__(self, force_decimal=False):
        self._force_decimal = force_decimal
        self.response_provider = ResponseProvider()

    def _decode_rates(self, response, use_decimal=False):
        if self._force_decimal or use_decimal:
            decoded_data = json.loads(response.text, use_decimal=True).get('rates', {})
        else:
            decoded_data = response.json().get('rates', {})
        return decoded_data

    def _get_decoded_rate(self, response, dest_cur, use_decimal=False):
        return self._decode_rates(response, use_decimal=use_decimal).get(dest_cur, None)


class CurrencyRates(Common):

    def get_rates(self, base_cur, date_obj=None):
        response = self.response_provider(
            base_cur, os.getenv('FOREX_PYTHON_RATES_PROVIDER', 'openexchangerates'), date_obj
        )
        if response.status_code == 200:
            rates = self._decode_rates(response)
            return rates
        raise RatesNotAvailableError("Currency Rates Source Not Ready")

    def get_rate(self, base_cur, dest_cur, date_obj=None):
        if base_cur == dest_cur:
            if self._force_decimal:
                return Decimal(1)
            return 1.

        response = self.response_provider(
            base_cur, os.getenv('FOREX_PYTHON_RATES_PROVIDER', 'openexchangerates'), date_obj, {'symbols': dest_cur}
        )

        if response.status_code == 200:
            rate = self._get_decoded_rate(response, dest_cur)
            if not rate:
                raise RatesNotAvailableError("Currency Rate {0} => {1} not available for Date {2}".format(
                    base_cur, dest_cur, date_obj.strftime('%Y-%m-%d') if date_obj else "latest"))
            return rate
        raise RatesNotAvailableError("Currency Rates Source Not Ready")

    def convert(self, base_cur, dest_cur, amount, date_obj=None):
        if isinstance(amount, Decimal):
            use_decimal = True
        else:
            use_decimal = self._force_decimal

        if base_cur == dest_cur:  # Return same amount if both base_cur, dest_cur are same
            if use_decimal:
                return Decimal(amount)
            return float(amount)

        response = self.response_provider(
            base_cur, os.getenv('FOREX_PYTHON_RATES_PROVIDER', 'openexchangerates'), date_obj, {'symbols': dest_cur}
        )

        if response.status_code == 200:
            rate = self._get_decoded_rate(response, dest_cur, use_decimal=use_decimal)
            if not rate:
                raise RatesNotAvailableError("Currency {0} => {1} rate not available for Date {2}.".format(
                    base_cur, dest_cur, date_obj.strftime('%Y-%m-%d') if date_obj else "latest"))
            try:
                converted_amount = rate * amount
                return converted_amount
            except TypeError:
                raise DecimalFloatMismatchError("convert requires amount parameter is of type Decimal when force_decimal=True")
        raise RatesNotAvailableError("Currency Rates Source Not Ready")


_CURRENCY_FORMATTER = CurrencyRates()

get_rates = _CURRENCY_FORMATTER.get_rates
get_rate = _CURRENCY_FORMATTER.get_rate
convert = _CURRENCY_FORMATTER.convert


class CurrencyCodes:

    def __init__(self):
        pass

    def _get_data(self, currency_code):
        file_path = os.path.dirname(os.path.abspath(__file__))
        with open(file_path+'/raw_data/currencies.json') as f:
            currency_data = json.loads(f.read())
        currency_dict = next((item for item in currency_data if item["cc"] == currency_code), None)
        return currency_dict

    def _get_data_from_symbol(self, symbol):
        file_path = os.path.dirname(os.path.abspath(__file__))
        with open(file_path + '/raw_data/currencies.json') as f:
            currency_data = json.loads(f.read())
        currency_dict = next((item for item in currency_data if item["symbol"] == symbol), None)
        return currency_dict

    def get_symbol(self, currency_code):
        currency_dict = self._get_data(currency_code)
        if currency_dict:
            return currency_dict.get('symbol')
        return None

    def get_currency_name(self, currency_code):
        currency_dict = self._get_data(currency_code)
        if currency_dict:
            return currency_dict.get('name')
        return None

    def get_currency_code_from_symbol(self, symbol):
        currency_dict = self._get_data_from_symbol(symbol)
        if currency_dict:
            return currency_dict.get('cc')
        return None


_CURRENCY_CODES = CurrencyCodes()


get_symbol = _CURRENCY_CODES.get_symbol
get_currency_name = _CURRENCY_CODES.get_currency_name
get_currency_code_from_symbol = _CURRENCY_CODES.get_currency_code_from_symbol
