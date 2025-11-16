import requests
import streamlit as st

PINATA_JWT = st.secrets["pinata"]["JWT"]

def pin_image(image_bytes, filename="livestock.jpg"):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {PINATA_JWT}"}
    files = {"file": (filename, image_bytes)}
    res = requests.post(url, headers=headers, files=files)
    return "https://gateway.pinata.cloud/ipfs/" + res.json()["IpfsHash"]

def pin_json(data):
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json"
    }
    res = requests.post(url, headers=headers, json=data)
    return "https://gateway.pinata.cloud/ipfs/" + res.json()["IpfsHash"]
