from web3 import Web3
from solcx import compile_standard, install_solc
import json

RPC_URL = st.secrets["blockchain"]["RPC_URL"]
PRIVATE_KEY = st.secrets["blockchain"]["PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

with open("smart_contract.sol", "r") as f:
    source = f.read()

install_solc("0.8.20")

compiled = compile_standard({
    "language": "Solidity",
    "sources": {"LivestockAuctionNFT.sol": {"content": source}},
    "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}}}
}, solc_version="0.8.20")

abi = compiled["contracts"]["LivestockAuctionNFT.sol"]["LivestockAuctionNFT"]["abi"]
bytecode = compiled["contracts"]["LivestockAuctionNFT.sol"]["LivestockAuctionNFT"]["evm"]["bytecode"]["object"]

contract = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce = w3.eth.get_transaction_count(account.address)

tx = contract.constructor().build_transaction({
    "from": account.address,
    "nonce": nonce,
    "gas": 5000000,
    "gasPrice": w3.eth.gas_price
})

signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print("Deployed:", receipt.contractAddress)
with open("contract_abi.json", "w") as f:
    json.dump(abi, f)

