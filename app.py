import streamlit as st
import requests
import json
import time
import io
from PIL import Image
from web3 import Web3
from datetime import datetime
from supabase import create_client, Client

# ============================================
# LOAD SECRETS
# ============================================
RPC_URL = st.secrets["blockchain"]["RPC_URL"]
PRIVATE_KEY = st.secrets["blockchain"]["PRIVATE_KEY"]
NFT_CONTRACT_ADDRESS = st.secrets["blockchain"]["NFT_CONTRACT_ADDRESS"]
AUCTION_CONTRACT_ADDRESS = st.secrets["blockchain"]["AUCTION_CONTRACT_ADDRESS"]
NFT_ABI = json.loads(st.secrets["blockchain"]["NFT_ABI"])
AUCTION_ABI = json.loads(st.secrets["blockchain"]["AUCTION_ABI"])

PINATA_JWT = st.secrets["pinata"]["PINATA_JWT"]
ROBOFLOW_API_KEY = st.secrets["roboflow"]["API_KEY"]
ROBOFLOW_MODEL = st.secrets["roboflow"]["MODEL_ID"]

SUPABASE_URL = st.secrets["supabase"]["URL"]
SUPABASE_KEY = st.secrets["supabase"]["ANON_KEY"]

# ============================================
# INITIALIZE WEB3 + SUPABASE
# ============================================
web3 = Web3(Web3.HTTPProvider(RPC_URL))
account = web3.eth.account.from_key(PRIVATE_KEY)
sender = account.address

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

nft_contract = web3.eth.contract(address=NFT_CONTRACT_ADDRESS, abi=NFT_ABI)
auction_contract = web3.eth.contract(address=AUCTION_CONTRACT_ADDRESS, abi=AUCTION_ABI)

# ============================================
# STREAMLIT SETUP
# ============================================
st.set_page_config(page_title="LivestockMon DApp", layout="wide")


# =========================================================
# UTILITY — UPLOAD IMAGE TO PINATA (IPFS)
# =========================================================
def upload_to_ipfs(image_bytes, filename="livestock.jpg"):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}
    files = {"file": (filename, image_bytes, "image/jpeg")}

    res = requests.post(url, headers=headers, files=files)
    if res.status_code == 200:
        ipfs_hash = res.json()["IpfsHash"]
        return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
    else:
        return None


# =========================================================
# UTILITY — RUN ROBOFLOW AI DETECTION
# =========================================================
def detect_livestock(image_bytes):
    url = f"https://detect.roboflow.com/{ROBOFLOW_MODEL}?api_key={ROBOFLOW_API_KEY}"
    res = requests.post(url, files={"file": image_bytes})

    if res.status_code != 200:
        return None

    data = res.json()
    return data


# =========================================================
# UTILITY — SEND MESSAGE TO SUPABASE CHAT
# =========================================================
def send_chat_message(listing_id, sender, receiver, message):
    supabase.table("messages").insert({
        "listing_id": listing_id,
        "sender": sender,
        "receiver": receiver,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()


# =========================================================
# UTILITY — FETCH CHAT MESSAGES
# =========================================================
def fetch_chat(listing_id):
    result = supabase.table("messages").select("*").eq("listing_id", listing_id).order("timestamp").execute()
    return result.data


# =========================================================
# MINT NFT (PINATA + CONTRACT CALL)
# =========================================================
def mint_livestock_nft(token_uri):
    nonce = web3.eth.get_transaction_count(sender)

    tx = nft_contract.functions.mintLivestockNFT(sender, token_uri).build_transaction({
        "from": sender,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": web3.to_wei("2", "gwei")
    })

    signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

    return web3.to_hex(tx_hash)


# =========================================================
# CREATE AUCTION
# =========================================================
def create_auction(token_id, duration_minutes):
    nonce = web3.eth.get_transaction_count(sender)

    tx = auction_contract.functions.createAuction(
        token_id,
        duration_minutes
    ).build_transaction({
        "from": sender,
        "nonce": nonce,
        "gas": 600000,
        "gasPrice": web3.to_wei("2", "gwei")
    })

    signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    return web3.to_hex(tx_hash)


# =========================================================
# PLACE BID
# =========================================================
def place_bid(auction_id, amount_eth):
    nonce = web3.eth.get_transaction_count(sender)

    tx = auction_contract.functions.bid(auction_id).build_transaction({
        "from": sender,
        "value": web3.to_wei(amount_eth, "ether"),
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": web3.to_wei("2", "gwei")
    })

    signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    return web3.to_hex(tx_hash)


# =========================================================
# UI — PAGE SELECTION
# =========================================================
st.sidebar.header("Navigation")
page = st.sidebar.selectbox("Select Page", [
    "Mint Livestock NFT",
    "Create Auction",
    "Browse Auctions",
    "Chat (Buyer ↔ Seller)"
])

# =========================================================
# PAGE 1 — MINT NFT
# =========================================================
if page == "Mint Livestock NFT":
    st.title("🐄 Mint Livestock NFT")

    file = st.file_uploader("Upload livestock image", type=["jpg", "jpeg", "png"])

    if file:
        image = Image.open(file)
        st.image(image, use_column_width=True)

        # Fix image format
        buf = io.BytesIO()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        st.write("🔍 Running Roboflow AI...")
        detection = detect_livestock(img_bytes)

        if detection is None or detection.get("predictions") == []:
            st.error("No livestock detected!")
        else:
            st.success("Livestock detected ✔")

        if st.button("Upload to IPFS & Mint NFT"):
            ipfs_url = upload_to_ipfs(img_bytes)

            if ipfs_url:
                st.success(f"Uploaded to IPFS: {ipfs_url}")
                tx = mint_livestock_nft(ipfs_url)
                st.success(f"NFT Minted! Tx: {tx}")
            else:
                st.error("Failed to upload to IPFS")


# =========================================================
# PAGE 2 — CREATE AUCTION
# =========================================================
elif page == "Create Auction":
    st.title("📦 Create Livestock Auction")

    token_id = st.number_input("Token ID", min_value=0, step=1)
    duration = st.number_input("Auction Duration (minutes)", min_value=1, step=1)

    if st.button("Create Auction"):
        tx = create_auction(token_id, duration)
        st.success(f"Auction created! Tx: {tx}")


# =========================================================
# PAGE 3 — BROWSE AUCTIONS
# =========================================================
elif page == "Browse Auctions":
    st.title("🛒 Browse Auctions")

    auction_count = auction_contract.functions.auctionCount().call()

    for auction_id in range(auction_count):
        a = auction_contract.functions.auctions(auction_id).call()

        seller, token_id, highest_bid, highest_bidder, end_time, active = a

        if not active:
            continue

        st.subheader(f"Livestock Auction #{auction_id}")
        st.write(f"Seller: {seller}")
        st.write(f"Token ID: {token_id}")
        st.write(f"Highest Bid: {web3.from_wei(highest_bid, 'ether')} ETH")
        st.write(f"Highest Bidder: {highest_bidder}")

        bid_amount = st.number_input(f"Your Bid for Auction #{auction_id} (ETH)", min_value=0.0)

        if st.button(f"Place Bid #{auction_id}"):
            tx = place_bid(auction_id, bid_amount)
            st.success(f"Bid Submitted! Tx: {tx}")


# =========================================================
# PAGE 4 — CHAT
# =========================================================
elif page == "Chat (Buyer ↔ Seller)":
    st.title("💬 Buyer–Seller Chat")

    listing = st.number_input("Enter Listing / Auction ID", min_value=0, step=1)
    user = st.text_input("Your Address")
    receiver = st.text_input("Receiver Address")
    message = st.text_input("Message")

    if st.button("Send Message"):
        send_chat_message(listing, user, receiver, message)
        st.success("Message sent!")

    st.subheader("Chat History")
    chat = fetch_chat(listing)

    for m in chat:
        st.write(f"**{m['sender']}** → {m['receiver']}: {m['message']}")
