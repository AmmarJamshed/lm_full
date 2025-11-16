import streamlit as st
import requests
import json
import io
from PIL import Image
from web3 import Web3

# -------------------------------------------------------
# 1. Load Secrets
# -------------------------------------------------------
RPC_URL = st.secrets["blockchain"]["RPC_URL"]
PRIVATE_KEY = st.secrets["blockchain"]["PRIVATE_KEY"]
NFT_CONTRACT_ADDRESS = st.secrets["blockchain"]["NFT_CONTRACT_ADDRESS"]
AUCTION_CONTRACT_ADDRESS = st.secrets["blockchain"]["AUCTION_CONTRACT_ADDRESS"]
NFT_ABI = json.loads(st.secrets["blockchain"]["NFT_ABI"])
AUCTION_ABI = json.loads(st.secrets["blockchain"]["AUCTION_ABI"])

SUPABASE_URL = st.secrets["supabase"]["URL"]
SUPABASE_KEY = st.secrets["supabase"]["ANON_KEY"]

ROBOFLOW_MODEL = st.secrets["ai"]["ROBOFLOW_MODEL"]
ROBOFLOW_API_KEY = st.secrets["ai"]["ROBOFLOW_API_KEY"]

# -------------------------------------------------------
# 2. Initialize Web3
# -------------------------------------------------------
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = w3.eth.account.from_key(PRIVATE_KEY)

nft_contract = w3.eth.contract(
    address=Web3.to_checksum_address(NFT_CONTRACT_ADDRESS),
    abi=NFT_ABI
)

auction_contract = w3.eth.contract(
    address=Web3.to_checksum_address(AUCTION_CONTRACT_ADDRESS),
    abi=AUCTION_ABI
)

# -------------------------------------------------------
# 3. Supabase REST helpers
# -------------------------------------------------------
def supabase_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    return requests.post(url, json=data, headers=headers)

def supabase_select(table, query="*"):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={query}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    return requests.get(url, headers=headers)

# -------------------------------------------------------
# 4. Roboflow AI Livestock Detection
# -------------------------------------------------------
def detect_livestock(image_bytes):
    url = f"https://detect.roboflow.com/{ROBOFLOW_MODEL}?api_key={ROBOFLOW_API_KEY}"
    resp = requests.post(url, files={"file": image_bytes})
    try:
        return resp.json()
    except:
        return {"error": True}

# -------------------------------------------------------
# 5. Mint Livestock NFT
# -------------------------------------------------------
def mint_nft(metadata_uri):
    tx = nft_contract.functions.mintLivestockNFT(
        account.address,
        metadata_uri
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()

# -------------------------------------------------------
# 6. Create Auction
# -------------------------------------------------------
def create_auction(token_id, starting_bid):
    tx = auction_contract.functions.createAuction(
        token_id,
        Web3.to_wei(starting_bid, "ether")
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()

# -------------------------------------------------------
# 7. Place Bid
# -------------------------------------------------------
def place_bid(auction_id, bid_amount):
    tx = auction_contract.functions.bid(
        auction_id
    ).build_transaction({
        "from": account.address,
        "value": Web3.to_wei(bid_amount, "ether"),
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()

# -------------------------------------------------------
# 8. Supabase Chat
# -------------------------------------------------------
def send_chat(sender, receiver, msg):
    supabase_insert("chat_messages", {
        "sender": sender,
        "receiver": receiver,
        "message": msg
    })

def get_chat(sender, receiver):
    return supabase_select(
        "chat_messages",
        f"*"
    ).json()

# -------------------------------------------------------
# 9. UI
# -------------------------------------------------------
st.title("🐄 LivestockMon DApp – NFT + Auctions + AI Detection + Chat")

page = st.sidebar.selectbox("Menu", [
    "Mint Livestock NFT",
    "Create Auction",
    "Place Bid",
    "Chat"
])

# ---------------------------
# PAGE 1: MINT NFT
# ---------------------------
if page == "Mint Livestock NFT":
    st.header("Mint a Livestock NFT")

    file = st.file_uploader("Upload Livestock Image")

    if file:
        image = Image.open(file)
        st.image(image, caption="Uploaded Image")

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        st.info("🔍 Running AI detection...")
        result = detect_livestock(img_bytes)

        st.write(result)

        metadata_uri = st.text_input("Metadata URI")

        if st.button("Mint NFT"):
            tx_hash = mint_nft(metadata_uri)
            st.success(f"NFT Minted! Tx Hash: {tx_hash}")

# ---------------------------
# PAGE 2: CREATE AUCTION
# ---------------------------
elif page == "Create Auction":
    st.header("Create Auction")

    token_id = st.number_input("Token ID", step=1)
    starting_bid = st.number_input("Starting Bid (ETH)", step=0.01)

    if st.button("Create Auction"):
        tx = create_auction(token_id, starting_bid)
        st.success(f"Auction Created! Tx: {tx}")

# ---------------------------
# PAGE 3: PLACE BID
# ---------------------------
elif page == "Place Bid":
    st.header("Place Bid")

    auction_id = st.number_input("Auction ID", step=1)
    bid_amount = st.number_input("Bid Amount (ETH)", step=0.01)

    if st.button("Place Bid"):
        tx = place_bid(auction_id, bid_amount)
        st.success(f"Bid Submitted! Tx: {tx}")

# ---------------------------
# PAGE 4: CHAT
# ---------------------------
elif page == "Chat":
    st.header("Buyer–Seller Chat")

    sender = st.text_input("Your Name")
    receiver = st.text_input("Chat With")

    message = st.text_area("Type your message")

    if st.button("Send"):
        send_chat(sender, receiver, message)
        st.success("Message Sent!")

    st.subheader("Conversation")
    chat = get_chat(sender, receiver)

    for msg in chat:
        st.write(f"**{msg['sender']}**: {msg['message']}")
