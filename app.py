import streamlit as st
import requests
import json
import io
from PIL import Image
from web3 import Web3
from supabase import create_client
import time

# ----------------------------
# Load secrets
# ----------------------------

RPC_URL = st.secrets["blockchain"]["RPC_URL"]
PRIVATE_KEY = st.secrets["blockchain"]["PRIVATE_KEY"]
CONTRACT_ADDRESS = st.secrets["blockchain"]["CONTRACT_ADDRESS"]

PINATA_JWT = st.secrets["pinata"]["JWT"]

ROBOFLOW_API_KEY = st.secrets["roboflow"]["API_KEY"]
ROBOFLOW_MODEL_ID = st.secrets["roboflow"]["MODEL_ID"]

SUPA_URL = st.secrets["supabase"]["URL"]
SUPA_KEY = st.secrets["supabase"]["ANON_KEY"]

# ----------------------------
# Setup Blockchain + Supabase
# ----------------------------

web3 = Web3(Web3.HTTPProvider(RPC_URL))
account = web3.eth.account.from_key(PRIVATE_KEY)

supabase = create_client(SUPA_URL, SUPA_KEY)

ABI = [
  {
    "inputs": [
      {"internalType": "address", "name": "to", "type": "address"},
      {"internalType": "string", "name": "tokenURI", "type": "string"}
    ],
    "name": "mintLivestockNFT",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]

contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

# ----------------------------
# Helper Functions
# ----------------------------

def roboflow_detect(image_bytes):
    url = f"https://detect.roboflow.com/{ROBOFLOW_MODEL_ID}?api_key={ROBOFLOW_API_KEY}"
    response = requests.post(url, files={"file": image_bytes})
    if response.status_code == 200:
        return response.json()
    return None


def upload_to_pinata(image_bytes, filename="livestock.jpg"):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}

    files = {"file": (filename, image_bytes, "image/jpeg")}

    res = requests.post(url, headers=headers, files=files)
    if res.status_code == 200:
        ipfs_hash = res.json()["IpfsHash"]
        return f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
    return None


def upload_metadata_to_pinata(metadata: dict):
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json"
    }
    res = requests.post(url, headers=headers, json=metadata)
    if res.status_code == 200:
        return f"https://gateway.pinata.cloud/ipfs/{res.json()['IpfsHash']}"
    return None


def mint_nft(uri):
    nonce = web3.eth.get_transaction_count(account.address)
    tx = contract.functions.mintLivestockNFT(account.address, uri).build_transaction({
        "chainId": web3.eth.chain_id,
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": web3.eth.gas_price
    })

    signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return tx_hash.hex()


def create_listing(owner, name, species, age, price, image, metadata, token_id):
    supabase.table("livestock_listings").insert({
        "owner_wallet": owner,
        "name": name,
        "species": species,
        "age": age,
        "price": price,
        "image_ipfs": image,
        "metadata_ipfs": metadata,
        "nft_token_id": token_id
    }).execute()


def send_message(listing_id, sender, msg):
    supabase.table("messages").insert({
        "listing_id": listing_id,
        "sender_wallet": sender,
        "message": msg
    }).execute()


def get_messages(listing_id):
    return supabase.table("messages").select("*").eq("listing_id", listing_id).order("timestamp").execute().data


# ----------------------------
# UI
# ----------------------------

st.title("🐄 LivestockMon – Blockchain Marketplace + AI Verification")

menu = st.sidebar.selectbox("Navigation", ["Create Listing", "Marketplace", "Verify Livestock"])

# ----------------------------
# CREATE LISTING
# ----------------------------

if menu == "Create Listing":
    st.header("📌 Create Livestock Listing")

    wallet = st.text_input("Your Wallet Address")
    name = st.text_input("Animal Name")
    species = st.selectbox("Species", ["Cow", "Goat", "Buffalo", "Camel"])
    age = st.number_input("Age (years)", min_value=0.5, max_value=30.0)
    price = st.number_input("Price (PKR)", min_value=1000)

    file = st.file_uploader("Upload Livestock Image", type=["jpg", "jpeg", "png"])

    if file:
        image = Image.open(file)
        st.image(image, caption="Uploaded Image")

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        st.info("Running AI Detection...")
        detect = roboflow_detect(img_bytes)

        st.write(detect)

        st.success("AI data extracted!")

        if st.button("Mint NFT & Create Listing"):
            st.warning("Uploading to IPFS...")
            img_ipfs = upload_to_pinata(img_bytes)

            metadata = {
                "name": name,
                "species": species,
                "age": age,
                "price": price,
                "detection": detect,
                "image": img_ipfs
            }

            metadata_uri = upload_metadata_to_pinata(metadata)

            st.warning("Minting NFT...")
            tx_hash = mint_nft(metadata_uri)

            st.success(f"NFT Minted! Tx: {tx_hash}")

            token_id = int(time.time()) % 10000000

            create_listing(wallet, name, species, age, price, img_ipfs, metadata_uri, token_id)

            st.success("Listing Created!")

# ----------------------------
# MARKETPLACE
# ----------------------------

elif menu == "Marketplace":
    st.header("🛒 Livestock for Sale")

    listings = supabase.table("livestock_listings").select("*").execute().data

    for item in listings:
        st.subheader(f"{item['name']} – {item['price']} PKR")
        st.image(item["image_ipfs"])

        st.write(f"Species: {item['species']}")
        st.write(f"Age: {item['age']} years")
        st.write(f"Owner: {item['owner_wallet']}")

        with st.expander("Chat with Seller"):
            msg = st.text_input(f"Message to {item['owner_wallet']}", key=item["id"])
            if st.button("Send", key=f"send_{item['id']}"):
                send_message(item["id"], "buyer", msg)

            st.write("💬 Messages:")
            chat = get_messages(item["id"])
            for m in chat:
                st.write(f"**{m['sender_wallet']}**: {m['message']}")

# ----------------------------
# VERIFY LIVESTOCK
# ----------------------------

elif menu == "Verify Livestock":
    st.header("🔍 Livestock Verification (Buyer)")

    listing_id = st.text_input("Enter Listing ID")
    file = st.file_uploader("Upload Delivery Image")

    if file:
        image = Image.open(file)
        st.image(image)

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        st.warning("Running AI verification...")
        detect2 = roboflow_detect(img_bytes)

        st.write(detect2)

        if st.button("Compare With Blockchain"):
            listing = supabase.table("livestock_listings").select("*").eq("id", listing_id).execute().data
            if not listing:
                st.error("Invalid Listing ID")
            else:
                original = listing[0]["metadata_ipfs"]

                metadata_json = requests.get(original).json()

                st.write("Blockchain Metadata:", metadata_json)

                if str(metadata_json["species"]) in str(detect2):
                    st.success("✔ Livestock Verified – Matches Blockchain")
                else:
                    st.error("❌ Does Not Match Blockchain. Possible Fraud.")
