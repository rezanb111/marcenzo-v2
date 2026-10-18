"""
Polygon USDT payment service for MARCENZO Loan Bot.
Deterministic unique deposit addresses + treasury disbursement + sweep.
Compatible with web3.py v6 and v7.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Optional, Tuple

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from loguru import logger

from config import settings


def _inject_poa(w3: Web3) -> None:
    """Polygon needs POA middleware; API changed between web3 v6 and v7."""
    try:
        from web3.middleware import ExtraDataToPOAMiddleware
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return
    except Exception:
        pass
    try:
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return
    except Exception:
        pass
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware as POA
        w3.middleware_onion.inject(POA, layer=0)
    except Exception as e:
        logger.warning(f"POA middleware not injected: {e}")


def _raw_tx_bytes(signed) -> bytes:
    """web3/eth-account: rawTransaction vs raw_transaction."""
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
    if raw is None:
        raise RuntimeError("Signed transaction has no raw bytes")
    return raw


ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


class PolygonPayService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL, request_kwargs={"timeout": 30}))
        _inject_poa(self.w3)
        self.usdt = self.w3.eth.contract(
            address=Web3.to_checksum_address(settings.USDT_CONTRACT),
            abi=ERC20_ABI,
        )
        self.treasury: LocalAccount = Account.from_key(settings.POLYGON_PRIVATE_KEY)
        self.decimals = settings.USDT_DECIMALS
        self.chain_id = settings.CHAIN_ID
        logger.info(f"PolygonPayService initialized | treasury={self.treasury.address}")

    def generate_deposit_account(
        self, purpose: str, entity_id: int, telegram_user_id: int
    ) -> Tuple[str, str]:
        key_bytes = bytes.fromhex(settings.POLYGON_PRIVATE_KEY.replace("0x", ""))
        material = (
            key_bytes
            + f"|{purpose}|".encode()
            + str(entity_id).encode()
            + b"|"
            + str(telegram_user_id).encode()
        )
        derived = self.w3.keccak(material)
        account = Account.from_key(derived)
        return account.address, account.key.hex()

    def generate_installment_deposit(
        self, installment_id: int, telegram_user_id: int
    ) -> Tuple[str, str]:
        return self.generate_deposit_account("dep", installment_id, telegram_user_id)

    def generate_investment_deposit(
        self, investment_id: int, telegram_user_id: int
    ) -> Tuple[str, str]:
        return self.generate_deposit_account("inv", investment_id, telegram_user_id)

    async def get_usdt_balance(self, address: str) -> float:
        def _get():
            raw = self.usdt.functions.balanceOf(Web3.to_checksum_address(address)).call()
            return float(Decimal(raw) / Decimal(10 ** self.decimals))
        return await asyncio.to_thread(_get)

    async def get_matic_balance(self, address: str) -> float:
        def _get():
            wei = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(self.w3.from_wei(wei, "ether"))
        return await asyncio.to_thread(_get)

    async def _get_gas_price(self) -> int:
        def _gp():
            return int(self.w3.eth.gas_price * 1.25)
        return await asyncio.to_thread(_gp)

    async def send_gas_for_sweep(self, to_address: str, amount_matic: float = 0.002) -> Optional[str]:
        def _send():
            try:
                nonce = self.w3.eth.get_transaction_count(self.treasury.address)
                gas_price = int(self.w3.eth.gas_price * 1.25)
                tx = {
                    "to": Web3.to_checksum_address(to_address),
                    "value": self.w3.to_wei(amount_matic, "ether"),
                    "gas": 21000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                    "chainId": self.chain_id,
                }
                signed = self.treasury.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(_raw_tx_bytes(signed))
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt.status == 1:
                    h = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
                    logger.info(f"Gas sent {amount_matic} MATIC → {to_address} | tx={h}")
                    return h
                return None
            except Exception as e:
                logger.exception(f"send_gas_for_sweep error: {e}")
                return None
        return await asyncio.to_thread(_send)

    async def sweep_usdt(
        self, deposit_private_key: str, deposit_address: str
    ) -> Tuple[bool, Optional[str], float]:
        def _sweep():
            try:
                deposit_acc = Account.from_key(deposit_private_key)
                if deposit_acc.address.lower() != deposit_address.lower():
                    logger.error("Deposit key/address mismatch")
                    return False, None, 0.0
                balance_raw = self.usdt.functions.balanceOf(
                    Web3.to_checksum_address(deposit_address)
                ).call()
                if balance_raw == 0:
                    return False, None, 0.0
                amount_usdt = float(Decimal(balance_raw) / Decimal(10 ** self.decimals))
                matic_bal = self.w3.eth.get_balance(Web3.to_checksum_address(deposit_address))
                if matic_bal < self.w3.to_wei(0.001, "ether"):
                    logger.warning(f"Deposit {deposit_address} has low MATIC")
                    return False, None, amount_usdt
                nonce = self.w3.eth.get_transaction_count(deposit_acc.address)
                gas_price = int(self.w3.eth.gas_price * 1.25)
                tx = self.usdt.functions.transfer(
                    Web3.to_checksum_address(settings.TREASURY_ADDRESS),
                    balance_raw,
                ).build_transaction({
                    "from": deposit_acc.address,
                    "gas": 100000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                    "chainId": self.chain_id,
                })
                signed = deposit_acc.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(_raw_tx_bytes(signed))
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                if receipt.status == 1:
                    h = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
                    logger.info(f"Swept {amount_usdt} USDT from {deposit_address} | tx={h}")
                    return True, h, amount_usdt
                return False, None, amount_usdt
            except Exception as e:
                logger.exception(f"sweep_usdt error: {e}")
                return False, None, 0.0
        return await asyncio.to_thread(_sweep)

    async def disburse_usdt(
        self, to_address: str, amount: float
    ) -> Tuple[bool, Optional[str], str]:
        def _disburse():
            try:
                to_cs = Web3.to_checksum_address(to_address)
                amount_raw = int(Decimal(str(amount)) * Decimal(10 ** self.decimals))
                treasury_bal = self.usdt.functions.balanceOf(self.treasury.address).call()
                if treasury_bal < amount_raw:
                    return False, None, f"Insufficient treasury USDT. Need {amount}, have {treasury_bal / 10**self.decimals}"
                nonce = self.w3.eth.get_transaction_count(self.treasury.address)
                gas_price = int(self.w3.eth.gas_price * 1.25)
                tx = self.usdt.functions.transfer(to_cs, amount_raw).build_transaction({
                    "from": self.treasury.address,
                    "gas": 100000,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                    "chainId": self.chain_id,
                })
                signed = self.treasury.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(_raw_tx_bytes(signed))
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                if receipt.status == 1:
                    h = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
                    logger.info(f"Disbursed {amount} USDT → {to_address} | tx={h}")
                    return True, h, "OK"
                return False, None, f"TX failed status={receipt.status}"
            except Exception as e:
                logger.exception(f"disburse_usdt error: {e}")
                return False, None, str(e)
        return await asyncio.to_thread(_disburse)

    async def verify_and_sweep_installment(
        self,
        deposit_address: str,
        deposit_private_key: str,
        required_amount: float,
        tolerance: float = 0.01,
    ) -> Tuple[bool, str, float, Optional[str]]:
        received = await self.get_usdt_balance(deposit_address)
        if received + 1e-9 < required_amount - tolerance:
            return (
                False,
                f"Insufficient payment.\nReceived: {received:.6f} USDT\nRequired: {required_amount:.6f} USDT",
                received,
                None,
            )
        matic = await self.get_matic_balance(deposit_address)
        if matic < 0.0015:
            gas_tx = await self.send_gas_for_sweep(deposit_address, 0.002)
            if not gas_tx:
                return False, "Failed to send gas for sweep. Try again later.", received, None
            await asyncio.sleep(3)
        success, tx_hash, swept = await self.sweep_usdt(deposit_private_key, deposit_address)
        if success:
            return True, f"✅ Payment verified & swept {swept:.6f} USDT", swept, tx_hash
        return False, "Sweep transaction failed. Funds may still be on deposit address.", received, None

    async def verify_and_sweep_investment(
        self,
        deposit_address: str,
        deposit_private_key: str,
        required_amount: float,
        tolerance: float = 0.01,
    ) -> Tuple[bool, str, float, Optional[str]]:
        return await self.verify_and_sweep_installment(
            deposit_address, deposit_private_key, required_amount, tolerance
        )

    def is_valid_address(self, address: str) -> bool:
        try:
            Web3.to_checksum_address(address)
            return address.startswith("0x") and len(address) == 42
        except Exception:
            return False

    def to_checksum(self, address: str) -> str:
        return Web3.to_checksum_address(address)


polygon_pay = PolygonPayService()
