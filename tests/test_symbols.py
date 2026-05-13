import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import json

from broker_ai.delta.symbols import Symbol


@pytest.fixture
def mock_download():
    raw = {
        "result": [
            {
                "id": 133633,
                "symbol": "C-BTC-95000-310726",
                "contract_type": "call_options",
                "strike_price": "95000",
                "underlying_asset": {"symbol": "BTC"},
                "settlement_time": "2026-07-31T12:00:00Z",
                "contract_value": "0.001",
            },
            {
                "id": 133634,
                "symbol": "P-BTC-95000-310726",
                "contract_type": "put_options",
                "strike_price": "95000",
                "underlying_asset": {"symbol": "BTC"},
                "settlement_time": "2026-07-31T12:00:00Z",
                "contract_value": "0.001",
            },
            {
                "id": 133635,
                "symbol": "C-BTC-96000-310726",
                "contract_type": "call_options",
                "strike_price": "96000",
                "underlying_asset": {"symbol": "BTC"},
                "settlement_time": "2026-07-31T12:00:00Z",
                "contract_value": "0.001",
            },
            {
                "id": 133636,
                "symbol": "P-BTC-96000-310726",
                "contract_type": "put_options",
                "strike_price": "96000",
                "underlying_asset": {"symbol": "BTC"},
                "settlement_time": "2026-07-31T12:00:00Z",
                "contract_value": "0.001",
            },
            {
                "id": 27,
                "symbol": "BTCUSD",
                "contract_type": "perpetual_futures",
                "strike_price": None,
                "underlying_asset": {"symbol": "BTC"},
                "settlement_time": None,
                "contract_value": "0.001",
            },
        ]
    }
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = raw
        mock_get.return_value = mock_response
        yield


class TestSymbolLoad:
    def test_download_and_normalize_btc_options(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        df = sym.df
        assert len(df) == 5
        assert all(df["underlying"] == "BTC")
        assert all(df["exchange"] == "DELTA")

    def test_normalize_contract_types(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        ce = sym.df[sym.df["option_type"] == "CE"]
        pe = sym.df[sym.df["option_type"] == "PE"]
        assert len(ce) == 2
        assert len(pe) == 2
        assert ce.iloc[0]["strike"] == 95000
        assert pe.iloc[0]["strike"] == 95000

    def test_normalize_expiry_date(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.df["expiry_date"].iloc[0] == "31Jul2026"

    def test_normalize_lot_size_from_contract_value(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.df["lot_size"].iloc[0] == 1000

    def test_normalize_token_from_id(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert str(sym.df["token"].iloc[0]) == "133633"

    def test_caches_to_csv(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        csv_path = os.path.join(str(temp_data_dir), "DELTA_BTC.csv")
        assert os.path.exists(csv_path)

    def test_option_type_column_exists(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert "option_type" in sym.df.columns
        assert set(sym.df["option_type"].unique()) <= {"CE", "PE", ""}


class TestSymbolDeriveDiff:
    def test_diff_between_adjacent_strikes(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.diff == 1000

    def test_diff_with_single_strike(self, temp_data_dir):
        raw = {
            "result": [
                {
                    "id": 133633,
                    "symbol": "C-BTC-95000-310726",
                    "contract_type": "call_options",
                    "strike_price": "95000",
                    "underlying_asset": {"symbol": "BTC"},
                    "settlement_time": "2026-07-31T12:00:00Z",
                    "contract_value": "0.001",
                },
            ]
        }
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = raw
            mock_get.return_value = mock_response
            sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
            assert sym.diff == 100


class TestSymbolFind:
    def test_find_nearest_expiry(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        expiry = sym.find("expiry_date")
        assert expiry == "31Jul2026"

    def test_find_exchange(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.find("exchange") == "DELTA"

    def test_find_token(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        token = sym.find("token")
        assert token is not None


class TestSymbolAtmStrike:
    def test_atm_strike_uses_diff_to_round(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        atm = sym.atm_strike(79300)
        assert atm == 78000

    def test_atm_strike_exact(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        atm = sym.atm_strike(80000)
        assert atm == 79000


class TestSymbolFilterByMoneyness:
    def test_filter_otm_call(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.filter_by_moneyness(ltp=95500, distance=1, c_or_p="CE")
        assert rows[0]["strike"] == 96000

    def test_filter_atm_call(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.filter_by_moneyness(ltp=95500, distance=0, c_or_p="CE")
        assert rows[0]["strike"] == 95000

    def test_filter_itm_put(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.filter_by_moneyness(ltp=96500, distance=1, c_or_p="PE")
        assert rows[0]["strike"] == 95000

    def test_filter_no_match_returns_empty(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.filter_by_moneyness(ltp=79300, distance=100, c_or_p="CE")
        assert rows == []


class TestSymbolGetAtmRows:
    def test_get_atm_rows_calls(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.get_atm_rows(ltp=95000, c_or_p="CE")
        assert len(rows) > 0
        for r in rows:
            assert r["option_type"] == "CE"

    def test_get_atm_rows_puts(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        sym.diff = 1000
        rows = sym.get_atm_rows(ltp=95000, c_or_p="PE")
        assert len(rows) > 0
        for r in rows:
            assert r["option_type"] == "PE"


class TestSymbolWsToken:
    def test_to_ws_tokens(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        rows = sym.get_atm_rows(ltp=95000, c_or_p="CE")
        tokens = sym.to_ws_tokens(rows)
        assert len(tokens) == len(rows)
        assert all(t.isdigit() for t in tokens)

    def test_from_ws_token(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        row = sym.from_ws_token("133633")
        assert row is not None
        assert row["tradingsymbol"] == "C-BTC-95000-310726"

    def test_from_ws_token_not_found(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.from_ws_token("999999") is None


class TestSymbolFindClosestPremium:
    def test_find_closest_premium_returns_exact_match(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        quotes = {"C-BTC-95000-310726": 3200, "C-BTC-96000-310726": 2800}
        rows = sym.find_closest_premium(quotes, premium=3200, c_or_p="CE")
        assert rows[0]["tradingsymbol"] == "C-BTC-95000-310726"

    def test_find_closest_premium_no_match(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        assert sym.find_closest_premium({}, premium=3000, c_or_p="CE") == []


class TestSymbolDataPersistence:
    def test_data_dumped_to_data_folder(self, mock_download, temp_data_dir):
        sym = Symbol(exchange="DELTA", symbol="BTC", data_path=str(temp_data_dir))
        csv_path = os.path.join(str(temp_data_dir), "DELTA_BTC.csv")
        assert os.path.exists(csv_path)
        df_read = pd.read_csv(csv_path)
        assert len(df_read) == 5
        assert "tradingsymbol" in df_read.columns
        assert "token" in df_read.columns
        assert "strike" in df_read.columns
