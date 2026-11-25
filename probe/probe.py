import time, MetaTrader5 as mt5
P = r"C:\Program Files\MetaTrader 5\terminal64.exe"
t = time.time()
ok = mt5.initialize(P, timeout=120000)
print("initialize(no login):", ok, mt5.last_error(), f"{time.time()-t:.1f}s")
if ok:
    print("version:", mt5.version())
    ti = mt5.terminal_info()
    print("terminal:", ti and {k: getattr(ti, k) for k in ("connected", "trade_allowed", "community_account", "path", "build")})
# wrong-password logins: the error tells whether the terminal found and reached each broker's server
for srv in ["MetaQuotes-Demo", "ICMarketsSC-Demo", "Exness-MT5Trial", "Pepperstone-Demo", "NoSuchBroker-Server"]:
    t = time.time()
    r = mt5.login(12345678, password="wrong-pass-1", server=srv, timeout=60000)
    print(f"login probe {srv}: {r} {mt5.last_error()} {time.time()-t:.1f}s")
mt5.shutdown()
