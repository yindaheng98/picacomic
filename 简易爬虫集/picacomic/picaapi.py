# -*- coding: utf-8 -*-
import urllib3
import re
import os
import sys

import hmac
import time
import json
import uuid
import sqlite3
import hashlib
import requests
from urllib import parse
import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(message)s',
                    datefmt='%m-%d %H:%M:%S')
urllib3.disable_warnings()


class PicaApi:
    def __init__(self, proxies=None,
                 global_url="https://picaapi.picacomic.com/",
                 api_key="C69BAF41DA5ABD1FFEDC6D2FEA56B",
                 secret_key="~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"):
        self.header = {
            "api-key": api_key,
            "accept": "application/vnd.picacomic.com.v1+json",
            "app-channel": "2",
            "app-version": "2.2.1.2.3.3",
            "app-uuid": "defaultUuid",
            "app-platform": "android",
            "app-build-version": "44",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/3.8.1",
            "image-quality": "original",
            "nonce": str(uuid.uuid4()).replace("-", ""),

            "time": None,
            "signature": None,
            "authorization": None,
        }
        self.uuid_s = self.header["nonce"]
        self.proxies = proxies
        self.global_url = global_url
        self.api_key = api_key
        self.secret_key = secret_key

    def __post(self, url, header, data=None):
        logging.info("POST %s %s" % (url, str(data)))
        while True:
            try:
                return requests.post(url=url, data=data, headers=header, verify=False, proxies=self.proxies)
            except:
                logging.info(sys.exc_info()[0])
                logging.info("出错重试 POST %s %s" % (url, str(data)))
                time.sleep(10)

    def __post_api(self, api, data=None):
        url = self.global_url + api
        header = self.__header(api, "POST")
        return self.__post(url=url, header=header, data=data)

    def __get(self, url, header):
        logging.info("GET %s" % url)
        while True:
            try:
                return requests.get(url=url, headers=header, verify=False, proxies=self.proxies)
            except:
                logging.info(sys.exc_info()[0])
                logging.info("出错重试 GET %s" % url)
                time.sleep(10)

    def __get_api(self, api):
        url = self.global_url + api
        header = self.__header(api, "GET")
        header.pop("Content-Type")
        return self.__get(url=url, header=header)

    def __header(self, url, method):
        header = self.header.copy()
        ts = str(int(time.time()))
        header["time"] = ts
        header["signature"] = self.__encrypt(url, ts, method)
        return header

    def __encrypt(self, url, ts, method):
        """
        :param url: 完整链接：https://picaapi.picacomic.com/auth/sign-in
        :param ts: 要和head里面的time一致, int(time.time())
        :param method: http请求方式: "GET" or "POST"
        :return: header["signature"]
        """
        raw = url.replace(self.global_url, "") + \
            str(ts) + self.uuid_s + method + self.api_key
        raw = raw.lower()
        hc = hmac.new(self.secret_key.encode(), digestmod=hashlib.sha256)
        hc.update(raw.encode())
        return hc.hexdigest()

    def set_authorization(self, authorization):
        self.header["authorization"] = authorization

    def login(self, account, password):
        logging.info("%s 登录中......" % account)
        api = "auth/sign-in"
        send = {"email": account, "password": password}
        recv = self.__post_api(api=api, data=json.dumps(send)).json()
        token = recv["data"]["token"]
        self.set_authorization(token)
        logging.info("%s 登录成功, token=%s" % (account, token))
        return token

    def profile(self):
        logging.info("获取当前用户的个人信息......")
        recv = self.__get_api("users/profile").json()
        logging.info("当前用户的个人信息已获取")
        return recv

    def favourite(self, page, order="dd"):
        logging.info("获取收藏第%d页......" % page)
        api = "users/favourite?s=%s&page=%d" % (order, page)
        response = self.__get_api(api).json()
        favourites = response["data"]['comics']
        logging.info("收藏第%d页已获取" % page)
        return favourites

    def comics(self, id):
        logging.info("获取漫画%s的详细信息......" % id)
        api = "comics/%s" % id
        response = self.__get_api(api).json()
        try:
            comics = response["data"]['comic']
            logging.info("漫画%s的详细信息已获取" % id)
            return comics
        except:
            logging.info("漫画%s的详细信息不存在" % id)
            return None

    def eps(self, id, page):
        logging.info("获取漫画%s分话列表的第%d页......" % (id, page))
        api = 'comics/%s/eps?page=%d' % (id, page)
        response = self.__get_api(api).json()
        try:
            eps = response["data"]['eps']
            logging.info("漫画%s分话列表的第%d页已获取" % (id, page))
            return eps
        except:
            logging.info("漫画%s的分话列表不存在" % id)
            return None

    def pages(self, id, eps, page):
        logging.info("获取漫画%s第%s分话的第%d页图片信息......" % (id, eps, page))
        api = 'comics/%s/order/%s/pages?page=%d' % (id, eps, page)
        response = self.__get_api(api).json()
        try:
            pages = response["data"]['pages']
            logging.info("漫画%s第%s分话的第%d页图片信息已获取" % (id, eps, page))
            return pages
        except:
            logging.info("漫画%s的图片信息不存在" % id)
            return None

    def download(self, url, write_to_path):
        try:
            if not os.path.exists(os.path.dirname(write_to_path)):
                os.makedirs(os.path.dirname(write_to_path))
        except:
            logging.info("线程上的小错误，莫慌")
        if os.path.exists(write_to_path) and os.path.getsize(write_to_path) != 0:
            logging.info("图片 %s 已存在" % write_to_path)
            return
        with open(write_to_path, "wb") as out:
            logging.info("正在下载图片 %s 到 %s" % (url, write_to_path))
            header = self.header.copy()
            header["time"] = str(int(time.time()))
            _pic = self.__get(url=url, header=header).content
            out.write(_pic)
        logging.info("图片 %s 已下载" % write_to_path)
