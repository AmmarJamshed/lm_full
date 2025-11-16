from supabase import create_client
import streamlit as st

SUPABASE_URL = st.secrets["supabase"]["URL"]
SUPABASE_KEY = st.secrets["supabase"]["ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_message(listing_id, wallet, text):
    supabase.table("messages").insert({
        "listing_id": listing_id,
        "sender_wallet": wallet,
        "message": text
    }).execute()

def get_messages(listing_id):
    return supabase.table("messages").select("*").eq("listing_id", listing_id).execute().data
