import os
import re
import sqlite3

import requests

from clever_battle import TOKEN, DEVID, DEVIC


class Answer:
    def __init__(self, text="", score=0):
        self.text = text
        self.score = score
        self.parts = re.findall(r"[\w']+", text)
        self.parts_score = [0]*len(self.parts)
        self.probability = 0
        self.predicted = False

    def recount(self):
        self.score = sum(self.parts_score)

    def __getitem__(self, item):
        return self.parts[item]

    def __setitem__(self, key, value):
        self.parts_score[key] = value

    def __repr__(self):
        return "<Answer %s - %d>" % (self.text, self.score)

class CaptchaNeededError(Exception):
    def __init__(self, sid, img, retry, args: dict):
        self.img = img
        args["captcha_sid"] = sid

        def on_retry(key: str):
            args["captcha_key"] = key
            retry(**args)
        self.retry = on_retry


class SubMethod:
    __slots__ = ['_node', '_token']

    def __init__(self, node, token):
        self._node = node
        self._token = token

    def __getattr__(self, item):
        def handler(**kwargs):
            kwargs["v"] = '5.96'
            kwargs["lang"] = 'ru'
            kwargs["https"] = '1'
            kwargs["access_token"] = self._token
            try:
                r = requests.post("https://api.vk.com/method/{}.{}".format(self._node, item),
                              data=kwargs, headers={"user-agent": "android-3.0.2#{}#{}".format(DEVID, DEVIC)}).json()
            except requests.RequestException:
                return {"error": {"error_code": -100}}
            if r.get("error", None) is not None:
                if r["error"]["error_code"] == 5:
                    raise ValueError("Invalid Auth Token")
                elif r["error"]["error_code"] == 14:
                    raise CaptchaNeededError(r["error"]["captcha_sid"], r["error"]["captcha_img"], self.item, kwargs)
            return r

        return handler


class ApiHelper:
    __slots__ = ['_subs', '_token']

    def __init__(self, token=TOKEN):
        self._subs = {}
        self._token = token

    def __getattr__(self, item):
        if item not in self._subs:
            a = SubMethod(item, self._token)
            self._subs[item] = a
            return a
        else:
            return self._subs[item]


class Database:
    filename = "clever.bd"
    init = None

    def __init__(self):
        r = False
        if not os.path.exists(self.filename):
            r = True
        self.conn = sqlite3.connect(self.filename)
        self.conn.row_factory = self.dict_factory
        self.cur = self.conn.cursor()
        if r and self.init:
            for q in self.init:
                self.query(q)

    def query(self, q, *params):
        self.cur.execute(q, params)
        self.conn.commit()
        return self.cur.fetchall()

    @staticmethod
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d