"""Network selection and contract deployment.

Network selection happens here and in the CLI, never inside business logic (FR-036).
"""

from __future__ import annotations

from ..config import Config
from ..errors import ChainError
from .compile import compile_registry
from .registry import Registry


def make_web3(cfg: Config):
    """Construct a Web3 for the configured network.

    `local` is an in-process eth-tester chain: no RPC, no binary, no network.
    """
    from web3 import EthereumTesterProvider, Web3

    if cfg.network == "local":
        return Web3(EthereumTesterProvider())

    cfg.require("rpc_url")
    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise ChainError("RPC endpoint unreachable", {"rpc_url": cfg.rpc_url})
    return w3


def _sender(w3, cfg: Config):
    if cfg.network == "local":
        return w3.eth.accounts[0]
    cfg.require("private_key")
    acct = w3.eth.account.from_key(cfg.private_key)
    w3.eth.default_account = acct.address
    return acct.address


def deploy(w3, cfg: Config) -> str:
    """Deploy the registry and return its address."""
    abi, bytecode = compile_registry()
    sender = _sender(w3, cfg)

    try:
        contract = w3.eth.contract(abi=list(abi), bytecode=bytecode)
        if cfg.network == "local":
            tx_hash = contract.constructor().transact({"from": sender})
        else:
            acct = w3.eth.account.from_key(cfg.private_key)
            tx = contract.constructor().build_transaction(
                {
                    "from": acct.address,
                    "nonce": w3.eth.get_transaction_count(acct.address),
                    "gas": 1_200_000,
                    "gasPrice": w3.eth.gas_price,
                }
            )
            signed = acct.sign_transaction(tx)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            tx_hash = w3.eth.send_raw_transaction(raw)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    except ChainError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ChainError("deployment failed", {"network": cfg.network, "error": str(exc)}) from exc

    if receipt["status"] != 1:
        raise ChainError("deployment reverted", {"network": cfg.network})
    return receipt["contractAddress"]


def signing_account(w3, cfg: Config):
    """The local account used to sign, or None when the node signs for us (eth-tester)."""
    if cfg.network == "local":
        return None
    cfg.require("private_key")
    return w3.eth.account.from_key(cfg.private_key)


def connect(w3, cfg: Config) -> Registry:
    """Attach to an already-deployed registry."""
    cfg.require("contract_address")
    abi, _ = compile_registry()
    return Registry(w3, cfg.contract_address, list(abi), account=signing_account(w3, cfg))
