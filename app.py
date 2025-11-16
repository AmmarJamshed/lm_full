import streamlit as st
import requests
import json
import time
import io
from PIL import Image
from web3 import Web3
from datetime import datetime, timedelta
import base64

st.set_page_config(page_title="LivestockMon DApp", layout="wide")

##########################################
# LOAD SECRETS
##########################################

RPC_URL = st.secrets["blockchain"]["RPC_URL"]
PRIVATE_KEY = st.secrets["blockchain"]["PRIVATE_KEY"]
CONTRACT_ADDRESS = st.secrets["blockchain"]["CONTRACT_ADDRESS"]
CHAIN_ID = st.secrets["blockchain"]["CHAIN_ID"]

PINATA_JWT = st.secrets["pinata"]["JWT"]

ROBOFLOW_API_KEY = st.secrets["roboflow"]["API_KEY"]
ROBOFLOW_MODEL = st.secrets["roboflow"]["MODEL_ID"]

SUPABASE_URL = st.secrets["supabase"]["URL"]
SUPABASE_KEY = st.secrets["supabase"]["ANON_KEY"]

##########################################
# WEB3 INIT
##########################################

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

##########################################
# LOAD CONTRACT ABI
##########################################

ABI = [
  {
    "inputs": [
      {"internalType": "address","name": "to","type": "address"},
      {"internalType": "string","name": "uri","type": "string"}
    ],
    "name": "mintLivestockNFT",
    "outputs": [{"internalType": "uint256","name": "","type": "uint256"}],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {"internalType": "uint256","name": "tokenId","type": "uint256"},
      {"internalType": "uint256","name": "startPrice","type": "uint256"},
      {"internalType": "uint256","name": "endPrice","type": "uint256"},
      {"internalType": "uint256","name": "duration","type": "uint256"}
    ],
    "name": "createDutchAuction",
    "outputs": [{"internalType": "uint256","name": "","type": "uint256"}],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [{"internalType": "uint256","name": "auctionId","type": "uint256"}],
    "name": "getCurrentPrice",
    "outputs": [{"internalType": "uint256","name": "","type": "uint256"}],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{"internalType": "uint256","name": "auctionId","type": "uint256"}],
    "name": "buyDutchAuction",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  }
]

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

##########################################
# UTILITY FUNCTIONS
##########################################

def pin_to_pinata(image_bytes, filename="image.jpg"):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}
    files = {"file": (filename, image_bytes)}
    res = requests.post(url, headers=headers, files=files)
    ipfs_hash = res.json()["IpfsHash"]
    return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"

def pin_json_to_pinata(data):
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json"
    }
    res = requests.post(url, headers=headers, json=data)
    ipfs_hash = res.json()["IpfsHash"]
    return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"

def roboflow_detect(image_bytes):
    url = f"https://detect.roboflow.com/{ROBOFLOW_MODEL}?api_key={ROBOFLOW_API_KEY}"
    r = requests.post(url, files={"file": image_bytes})
    try:
        return r.json()
    except:
        return {"error": "Invalid response"}

def send_txn(tx):
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def mint_nft(owner_wallet, token_uri):
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.mintLivestockNFT(owner_wallet, token_uri).build_transaction({
        "from": account.address,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID
    })
    return send_txn(tx)

def create_dutch_auction(token_id, start_price, end_price):
    duration = 6 * 60 * 60  # 6 hours
    nonce = w3.eth.get_transaction_count(account.address)

    tx = contract.functions.createDutchAuction(
        token_id, start_price, end_price, duration
    ).build_transaction({
        "from": account.address,
        "gas": 700000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID
    })
    return send_txn(tx)

def buy_auction(auction_id, amount_wei):
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.buyDutchAuction(auction_id).build_transaction({
        "from": account.address,
        "value": amount_wei,
        "gas": 700000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID
    })
    return send_txn(tx)
##########################################
# STREAMLIT UI
##########################################

st.title("🐄 LivestockMon – AI + Blockchain Trading DApp")
st.caption("AI Disease Detection • NFT Proof of Ownership • Dutch Auctions • Supabase Chat")

tab1, tab2, tab3, tab4 = st.tabs(["Livestock ID", "Marketplace", "Chat", "Auctions"])

##########################################
# TAB 1: UPLOAD + NFT MINTING
##########################################

with tab1:
    st.header("📤 Upload Livestock Image")

    file = st.file_uploader("Upload animal image", type=["jpg", "jpeg", "png"])

    if file:
        image = Image.open(file)
        st.image(image, caption="Uploaded Image", use_column_width=True)

        # Convert to bytes
        img_bytes_io = io.BytesIO()
        image.save(img_bytes_io, format="JPEG")
        img_bytes = img_bytes_io.getvalue()

        st.info("🔍 Running Roboflow AI detection...")
        detection = roboflow_detect(img_bytes)

        st.subheader("AI Detection Result:")
        st.json(detection)

        # Save image to IPFS (Pinata)
        st.info("📡 Uploading image to IPFS…")
        ipfs_image_url = pin_to_pinata(img_bytes)

        st.success(f"Image pinned to IPFS:\n{ipfs_image_url}")

        # Metadata JSON
        metadata = {
            "name": "Livestock NFT",
            "description": "Cow/Goat/Bull with historical disease & ownership record.",
            "image": ipfs_image_url,
            "detection": detection,
        }

        st.info("📡 Uploading metadata JSON to IPFS…")
        token_uri = pin_json_to_pinata(metadata)
        st.success(f"Metadata pinned at:\n{token_uri}")

        st.subheader("🪙 Mint NFT")

        wallet = st.text_input("New Owner Wallet Address", value=account.address)

        if st.button("Mint NFT"):
            with st.spinner("Minting on blockchain…"):
                try:
                    tx_hash, receipt = mint_nft(wallet, token_uri)
                    st.success(f"NFT Minted! Tx: {tx_hash}")
                    st.json(receipt)
                except Exception as e:
                    st.error(f"Error: {e}")

##########################################
# TAB 2 — AUCTIONS
##########################################

with tab2:
    st.header("💰 Dutch Auctions")

    st.subheader("Create Auction")

    token_id = st.number_input("Token ID", min_value=0, step=1)
    start_price_eth = st.number_input("Start Price (ETH)", min_value=0.0)
    end_price_eth = st.number_input("End Price (ETH)", min_value=0.0)

    if st.button("Create Auction"):
        start_price_wei = int(start_price_eth * 1e18)
        end_price_wei = int(end_price_eth * 1e18)

        with st.spinner("Creating auction on-chain…"):
            try:
                tx_hash, rcpt = create_dutch_auction(token_id, start_price_wei, end_price_wei)
                st.success(f"Auction Created! Tx: {tx_hash}")
            except Exception as e:
                st.error(e)

    st.divider()
    st.subheader("Buy From Auction")

    auction_id = st.number_input("Auction ID", min_value=0, step=1)

    if st.button("Get Current Price"):
        with st.spinner("Fetching blockchain price…"):
            try:
                price = contract.functions.getCurrentPrice(auction_id).call()
                st.success(f"Current Price: {price/1e18} ETH")
            except:
                st.error("Invalid auction ID")

    buy_amount = st.number_input("Buy Amount (ETH)", min_value=0.0)

    if st.button("Buy Auction"):
        amount_wei = int(buy_amount * 1e18)

        with st.spinner("Submitting buy transaction…"):
            try:
                tx_hash, rcpt = buy_auction(auction_id, amount_wei)
                st.success(f"Purchased! Tx: {tx_hash}")
            except Exception as e:
                st.error(e)
##########################################
# TAB 3 — BUYER ↔ SELLER CHAT
##########################################

with tab3:
    st.header("💬 Buyer–Seller Chat")

    # ---- LOGIN SYSTEM (Wallet Based) ----
    st.subheader("🔐 Login with Wallet")

    if "wallet" not in st.session_state:
        st.session_state.wallet = None

    wallet_input = st.text_input("Enter your wallet address", placeholder="0x123...")

    if st.button("Login"):
        if wallet_input.startswith("0x") and len(wallet_input) == 42:
            st.session_state.wallet = wallet_input
            st.success("Logged in!")
        else:
            st.error("Invalid wallet address")

    if not st.session_state.wallet:
        st.stop()

    user_wallet = st.session_state.wallet
    st.info(f"Logged in as: **{user_wallet}**")

    # ---- SELECT USER TO CHAT WITH ----
    st.subheader("Select Chat Partner")

    # Fetch users from supabase
    users = supabase.table("users").select("*").execute().data

    # Convert to list of wallet strings
    user_list = [u["wallet"] for u in users if u["wallet"] != user_wallet]

    chat_partner = st.selectbox("Choose a user to chat with", user_list)

    # Create both users in DB if not exists
    supabase.table("users").upsert({"wallet": user_wallet}).execute()

    # ---- DISPLAY CHAT ----
    st.subheader(f"Chat with: {chat_partner}")

    def load_messages():
        return (
            supabase.table("messages")
            .select("*")
            .eq("sender", user_wallet)
            .eq("receiver", chat_partner)
            .order("timestamp", desc=False)
            .execute()
            .data
            +
            supabase.table("messages")
            .select("*")
            .eq("sender", chat_partner)
            .eq("receiver", user_wallet)
            .order("timestamp", desc=False)
            .execute()
            .data
        )

    messages = load_messages()

    # Display messages
    for msg in sorted(messages, key=lambda x: x["timestamp"]):
        if msg["sender"] == user_wallet:
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["content"])

    # ---- SEND MESSAGE ----
    st.text_input("Your message", key="chat_input")

    if st.button("Send"):
        text = st.session_state.chat_input
        if text.strip():
            supabase.table("messages").insert({
                "sender": user_wallet,
                "receiver": chat_partner,
                "content": text
            }).execute()

            st.session_state.chat_input = ""   # clear input
            st.experimental_rerun()
##########################################
# TAB 4 — BLOCKCHAIN AUCTIONS
##########################################

with tab4:
    st.header("🐮 Livestock Auctions (On-Chain)")

    # Load Auction Contract
    auction_contract = w3.eth.contract(
        address=AUCTION_CONTRACT_ADDRESS,
        abi=AUCTION_ABI
    )

    # --- SECTION: CREATE AUCTION ---
    st.subheader("📤 Create an Auction")

    token_id = st.number_input("Token ID", min_value=0, step=1)
    duration = st.number_input("Auction Duration (minutes)", min_value=1, step=1)

    if st.button("Create Auction"):
        try:
            tx = auction_contract.functions.createAuction(
                token_id,
                duration
            ).build_transaction({
                "from": owner_address,
                "nonce": w3.eth.get_transaction_count(owner_address),
                "gas": 300000,
                "gasPrice": w3.eth.gas_price,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            st.success(f"Auction Created! Tx: {tx_hash.hex()}")

        except Exception as e:
            st.error(f"Error: {str(e)}")

    # --- SECTION: BID ---
    st.subheader("💰 Place a Bid")

    auction_id = st.number_input("Auction ID", min_value=1, step=1)
    bid_amount = st.number_input("Bid Amount (ETH)", min_value=0.001, step=0.001)

    if st.button("Place Bid"):
        try:
            tx = auction_contract.functions.bid(auction_id).build_transaction({
                "from": owner_address,
                "value": w3.to_wei(bid_amount, "ether"),
                "nonce": w3.eth.get_transaction_count(owner_address),
                "gas": 300000,
                "gasPrice": w3.eth.gas_price,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            st.success(f"Bid Placed! Tx: {tx_hash.hex()}")

        except Exception as e:
            st.error(str(e))

    # --- WITHDRAW OUTBID FUNDS ---
    st.subheader("↩ Withdraw")

    if st.button("Withdraw Funds"):
        try:
            tx = auction_contract.functions.withdraw().build_transaction({
                "from": owner_address,
                "nonce": w3.eth.get_transaction_count(owner_address),
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            st.success(tx_hash.hex())

        except Exception as e:
            st.error(str(e))

    # --- END AUCTION ---
    st.subheader("🏁 End Auction")

    end_id = st.number_input("End Auction ID", min_value=1, step=1)

    if st.button("End Auction Now"):
        try:
            tx = auction_contract.functions.endAuction(end_id).build_transaction({
                "from": owner_address,
                "nonce": w3.eth.get_transaction_count(owner_address),
                "gas": 300000,
                "gasPrice": w3.eth.gas_price,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            st.success(f"Auction Ended! {tx_hash.hex()}")

        except Exception as e:
            st.error(str(e))
