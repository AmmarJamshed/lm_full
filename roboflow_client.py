import requests
import streamlit as st

API_KEY = st.secrets["roboflow"]["API_KEY"]
MODEL_ID = st.secrets["roboflow"]["MODEL_ID"]

def detect(image_bytes):
    url = f"https://detect.roboflow.com/{MODEL_ID}?api_key={API_KEY}"
    resp = requests.post(url, files={"file": image_bytes})
    return resp.json()
