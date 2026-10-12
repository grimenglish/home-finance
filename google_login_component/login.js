(() => {
  const parentOrigin = location.origin;
  const status = document.getElementById('status');
  let args = null, activeNonce = '', loading = false, callbackVersion = 0;
  function send(type, values = {}) {
    window.parent.postMessage({isStreamlitMessage: true, type, ...values}, parentOrigin);
  }
  function height() { send('streamlit:setFrameHeight', {height: 145}); }
  function render() {
    if (!args || !window.google?.accounts?.id || activeNonce === args.nonce) return;
    activeNonce = args.nonce;
    const nonce = args.nonce, version = ++callbackVersion;
    google.accounts.id.initialize({
      client_id: args.client_id,
      nonce,
      ux_mode: 'popup',
      auto_select: false,
      use_fedcm_for_button: false,
      callback(response) {
        if (version !== callbackVersion || !response?.credential) return;
        status.textContent = '로그인 확인 중…';
        // Pass only to the owning Streamlit page, never via URL or browser storage.
        send('streamlit:setComponentValue', {dataType: 'json', value: {credential: response.credential}});
      }
    });
    google.accounts.id.renderButton(document.getElementById('button'), {type:'standard', theme:'outline', size:'large', text:'signin_with', shape:'pill', width:280, locale:'ko'});
    status.textContent = '구글 버튼을 눌러 계정을 선택하세요. 팝업이 막히면 이 사이트의 팝업을 허용해 주세요.';
    height();
  }
  function load() {
    if (window.google?.accounts?.id) { render(); return; }
    if (loading) return;
    loading = true;
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = render;
    script.onerror = () => {status.textContent = '구글 로그인 버튼을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침하세요.'; height();};
    document.head.appendChild(script);
  }
  window.addEventListener('message', (e) => {
    if (e.source !== window.parent || e.origin !== parentOrigin || e.data?.type !== 'streamlit:render') return;
    const next = e.data.args;
    if (typeof next?.client_id !== 'string' || typeof next?.nonce !== 'string') return;
    args = next; load(); height();
  });
  send('streamlit:componentReady', {apiVersion: 1});
  height();
})();
