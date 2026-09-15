"""
blockchain_manager.py — Nyaya Vault on-chain evidence anchoring.

Written against web3.py v6+ (snake_case API: build_transaction,
to_checksum_address, raw_transaction) and py-solc-x.

ONE-TIME SETUP (do this before running app.py with blockchain.enabled=true):
    1. pip install web3 py-solc-x
    2. Start Ganache (GUI default: http://127.0.0.1:7545, CLI default: :8545 —
       update "rpc_url" in config.json if yours differs).
    3. Copy one of Ganache's test-account private keys into
       config.json -> blockchain.deployer_private_key.
       These are throwaway test-network keys with fake ETH — never put a
       real-network private key in a plaintext config file.
    4. Run:  python blockchain_manager.py
       This compiles NyayaVault.sol, deploys it to your local chain, and
       writes the resulting contract address back into config.json.

After that, app.py's evidence-sealing flow calls anchor_evidence_hash()
automatically for every new exhibit.
"""

import os
import json

from web3 import Web3

try:
    import solcx
except ImportError:
    solcx = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CONTRACT_SOURCE_PATH = os.path.join(BASE_DIR, "NyayaVault.sol")
BUILD_CACHE_PATH = os.path.join(BASE_DIR, "nyayavault_build.json")

SOLC_VERSION = "0.8.19"


def _load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def _save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_web3(cfg=None):
    cfg = cfg or _load_config()
    bc_cfg = cfg.get("blockchain", {})
    rpc_url = bc_cfg.get("rpc_url", "http://127.0.0.1:7545")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(
            f"Could not reach local blockchain node at {rpc_url}. "
            "Make sure Ganache is running and rpc_url in config.json is correct."
        )
    return w3


def compile_contract():
    """Compiles NyayaVault.sol with py-solc-x and caches the ABI/bytecode to disk."""
    if solcx is None:
        raise RuntimeError("py-solc-x is not installed. Run: pip install py-solc-x")

    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        solcx.install_solc(SOLC_VERSION)
    solcx.set_solc_version(SOLC_VERSION)

    with open(CONTRACT_SOURCE_PATH, "r") as f:
        source = f.read()

    compiled = solcx.compile_source(source, output_values=["abi", "bin"])
    _, contract_interface = list(compiled.items())[0]
    build = {"abi": contract_interface["abi"], "bytecode": contract_interface["bin"]}

    with open(BUILD_CACHE_PATH, "w") as f:
        json.dump(build, f)

    return build


def _load_build():
    if os.path.exists(BUILD_CACHE_PATH):
        with open(BUILD_CACHE_PATH, "r") as f:
            return json.load(f)
    return compile_contract()


def _raw_tx_bytes(signed_tx):
    # web3.py v6+ uses raw_transaction; some builds still expose rawTransaction.
    return getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction")


def deploy_contract():
    """One-time deployment to the local chain. Saves the address into config.json."""
    cfg = _load_config()
    bc_cfg = cfg.setdefault("blockchain", {})

    w3 = get_web3(cfg)
    build = compile_contract()

    private_key = bc_cfg.get("deployer_private_key", "")
    if not private_key:
        raise ValueError(
            "Set blockchain.deployer_private_key in config.json to a Ganache "
            "test-account private key first."
        )

    account = w3.eth.account.from_key(private_key)
    contract_factory = w3.eth.contract(abi=build["abi"], bytecode=build["bytecode"])

    tx = contract_factory.constructor().build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": bc_cfg.get("gas_limit", 3000000),
        "gasPrice": w3.eth.gas_price,
        "chainId": bc_cfg.get("chain_id", 1337),
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(_raw_tx_bytes(signed))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    bc_cfg["contract_address"] = receipt.contractAddress
    _save_config(cfg)

    print(f"NyayaVault deployed at {receipt.contractAddress}")
    print("config.json updated with the contract address.")
    return receipt.contractAddress


def _get_contract(cfg=None):
    cfg = cfg or _load_config()
    bc_cfg = cfg.get("blockchain", {})
    address = bc_cfg.get("contract_address", "")
    if not address:
        raise ValueError(
            "No contract_address in config.json yet. Run 'python blockchain_manager.py' "
            "to deploy the contract first."
        )

    w3 = get_web3(cfg)
    build = _load_build()
    contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=build["abi"])
    return w3, contract, bc_cfg


def anchor_evidence_hash(case_no, evidence_id, sha256_hex):
    """
    Anchors a sealed evidence file's SHA-256 hash on-chain.

    Returns (tx_hash_hex, block_number) on success. Raises on failure —
    callers should catch this and treat it as "anchoring still pending",
    never as a reason to roll back the already-committed off-chain DB record.
    The Oracle DB row is always the immediate source of truth; the chain is
    the tamper-evident backstop.
    """
    w3, contract, bc_cfg = _get_contract()
    private_key = bc_cfg.get("deployer_private_key", "")
    if not private_key:
        raise ValueError("blockchain.deployer_private_key is not set in config.json.")

    account = w3.eth.account.from_key(private_key)
    file_hash_bytes = bytes.fromhex(sha256_hex)

    tx = contract.functions.anchorEvidence(case_no, evidence_id, file_hash_bytes).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": bc_cfg.get("gas_limit", 3000000),
        "gasPrice": w3.eth.gas_price,
        "chainId": bc_cfg.get("chain_id", 1337),
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(_raw_tx_bytes(signed))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.transactionHash.hex(), receipt.blockNumber


def verify_evidence_onchain(case_no, evidence_id):
    """Reads back the on-chain hash for a given exhibit, for tamper verification."""
    _, contract, _ = _get_contract()
    file_hash, anchored_by, block_ts, exists = contract.functions.getEvidenceHash(case_no, evidence_id).call()
    if not exists:
        return None
    return {
        "sha256_hash": file_hash.hex(),
        "anchored_by": anchored_by,
        "block_timestamp": block_ts,
    }


if __name__ == "__main__":
    deploy_contract()