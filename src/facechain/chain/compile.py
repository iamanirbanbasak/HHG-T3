"""Solidity compilation via py-solc-x.

No Foundry, no Hardhat, no Node toolchain -- the contract is 40 lines and py-solc-x compiles it
from a pinned solc. Keeping the project single-language is worth more than the extra tooling.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..errors import ChainError

SOLC_VERSION = "0.8.24"
CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "FaceMatchRegistry.sol"
CONTRACT_NAME = "FaceMatchRegistry"


def _ensure_solc() -> None:
    import solcx

    installed = {str(v) for v in solcx.get_installed_solc_versions()}
    if SOLC_VERSION not in installed:
        try:
            solcx.install_solc(SOLC_VERSION)
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error below
            raise ChainError(
                f"could not install solc {SOLC_VERSION}",
                {"hint": "network required on first run", "error": str(exc)},
            ) from exc


@lru_cache(maxsize=1)
def compile_registry() -> tuple[tuple, str]:
    """Compile the registry. Returns (abi, bytecode).

    ABI is returned as a tuple so the result stays hashable for the lru_cache.
    """
    import solcx

    if not CONTRACT_PATH.exists():
        raise ChainError("contract source missing", {"path": str(CONTRACT_PATH)})

    _ensure_solc()
    try:
        compiled = solcx.compile_source(
            CONTRACT_PATH.read_text(),
            output_values=["abi", "bin"],
            solc_version=SOLC_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        raise ChainError("solidity compilation failed", {"error": str(exc)}) from exc

    key = next((k for k in compiled if k.endswith(f":{CONTRACT_NAME}")), None)
    if key is None:
        raise ChainError("compiled output missing contract", {"expected": CONTRACT_NAME})

    artifact = compiled[key]
    return tuple(artifact["abi"]), artifact["bin"]


def registry_abi() -> list:
    abi, _ = compile_registry()
    return list(abi)
