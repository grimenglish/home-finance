from pathlib import Path
import streamlit.components.v1 as components

_component = components.declare_component('home_google_signin', path=str(Path(__file__).resolve().parent / 'google_login_component'))

def google_button(client_id, nonce):
    return _component(client_id=client_id, nonce=nonce, key='google_signin:' + nonce, default=None)
