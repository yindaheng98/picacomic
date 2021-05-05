import os
import re
import logging
import sqlite3
import json
import threading
from picaapi import PicaApi
from urllib import parse
from multiprocessing.pool import ThreadPool

class PicaAction:
    def __init__(self, account, password,
                 proxies=None, data_path=os.path.join(os.path.split(__file__)[0], "data"), threadn=5,
                 global_url="https://picaapi.picacomic.com/",
                 api_key="C69BAF41DA5ABD1FFEDC6D2FEA56B",
                 secret_key="~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"):
        logging.info("PicaAction启动中......")
        self.picaapi = PicaApi(proxies=proxies,
                               global_url=global_url,
                               api_key=api_key,
                               secret_key=secret_key)
        self.download_path = data_path
        if not os.path.exists(data_path):
            os.makedirs(data_path)
        self.db = sqlite3.connect(os.path.join(data_path, "data.db"))
        self.__login(account, password)
        self.account = account
        self.threadn = threadn

    def __ExecuteSQL(self, sql, args=None):
        cur = self.db.cursor()
        if args == None:
            logging.info("Executing in DB: %s" % sql)
            __res = cur.execute(sql).fetchall()
        else:
            logging.info("Executing in DB: %s,%s" % (sql, str(args)))
            __res = cur.execute(sql, args).fetchall()
        self.db.commit()
        return __res

    def __login(self, account, password):
        logging.info("%s 登录......" % account)
        _ = self.__ExecuteSQL(
            "create table if not exists account (email text PRIMARY KEY NOT NULL, password text, token text);")
        logging.info("从数据库中查找 %s 的token......" % account)
        token = self.__ExecuteSQL("select token from account where email=?;",
                                  (account,))

        def gettoken():
            logging.info("为 %s 获取新的token......" % account)
            token = self.picaapi.login(account, password)
            logging.info("%s 的新token已获取: %s" % (account, token))
            return token

        if len(token) > 0:
            token = token[0][0]
            logging.info("数据库中有 %s 的token: %s" % (account, token))
            self.picaapi.set_authorization(token)
            logging.info("测试数据库中 %s 的token是否有效......" % account)
            profile = self.picaapi.profile()
            if profile["code"] == 200:
                logging.info("数据库中 %s 的token有效" % account)
            else:
                logging.info("数据库中 %s 的token失效" % account)
                token = gettoken()
                self.__ExecuteSQL("update account set token=? where email=?;",
                                  (token, account))
        else:
            logging.info("数据库中没有 %s 的token" % account)
            token = gettoken()
            self.__ExecuteSQL("insert into account (email, password, token)values (?, ?, ?);",
                              (account, password, token))
        self.picaapi.set_authorization(token)

    def __travel_favourites_ol(self, limit=None, order="dd"):
        def islimited():
            nonlocal limit
            if limit != None:
                limit -= 1
                if limit <= 0:
                    return True
            return False
        pages = self.picaapi.favourite(1, order=order)['pages']
        if pages < 2:
            return
        for i in range(1, pages+1):
            docs = self.picaapi.favourite(i, order=order)['docs']
            for favourite in docs:
                yield favourite
                if islimited():
                    return

    def __travel_favourites_db(self, limit=None):
        favourites = []
        if limit != None:
            favourites = self.__ExecuteSQL(
                "select * from comics limit %d;" % limit)
        else:
            favourites = self.__ExecuteSQL("select * from comics;")
        for favourite in favourites:
            data = json.loads(favourite[1])
            detail = json.loads(favourite[2])
            yield data, detail

    def gather_favourites_ol(self, n=None, order="dd"):
        favourites = []
        for favourite in self.__travel_favourites_ol(limit=n, order=order):
            favourites.append(favourite)
        return favourites

    def gather_favourites_db(self, n=None):
        favourites = []
        details = []
        for favourite, detail in self.__travel_favourites_db(limit=n):
            favourites.append(favourite)
            details.append(detail)
        return favourites, details

    def __insert_favourite(self, favourite):
        detail = self.picaapi.comics(favourite["_id"])
        if detail == None:
            return
        _ = self.__ExecuteSQL("insert or REPLACE into comics (id, data, detail)values(?, ?, ?);",
                              (favourite["_id"], json.dumps(favourite), json.dumps(detail)))
        _ = self.__ExecuteSQL("insert or REPLACE into favourites (id, user)values(?, ?);",
                              (favourite["_id"], self.account))

    def init_favourites(self, n=None):
        logging.info("初始化 %s 的收藏列表......" % self.account)
        _ = self.__ExecuteSQL(
            "create table if not exists comics (id text PRIMARY KEY NOT NULL, data json, detail json);")
        _ = self.__ExecuteSQL(
            "create table if not exists favourites (id text, user text, PRIMARY KEY(id, user)," +
            "FOREIGN KEY(id) REFERENCES comics(id)," +
            "FOREIGN KEY(user) REFERENCES account(email));")
        for favourite in self.__travel_favourites_ol(limit=n, order="da"):
            self.__insert_favourite(favourite)
        logging.info("%s 的收藏列表初始化完成" % self.account)

    def append_favourites(self, n=None):
        logging.info("将 %s 的收藏列表中的新增收藏写入数据库......" % self.account)
        for favourite in self.__travel_favourites_ol(limit=n):
            fs = self.__ExecuteSQL("select * from favourites where id=? and user=?;",
                                   (favourite["_id"], self.account))
            if len(fs) > 0:
                logging.info("%s 的收藏 %s 已入数据库......" %
                             (self.account, favourite["_id"]))
                break
            logging.info("%s 的收藏 %s 未入数据库......" %
                         (self.account, favourite["_id"]))
            self.__insert_favourite(favourite)
        logging.info("%s 的收藏列表中的新增收藏已写入数据库" % self.account)

    def update_finish_status(self):
        logging.info("更新数据库中已有收藏的finish状态......")
        for favourite, _ in self.__travel_favourites_db():
            if not favourite["finished"]:
                self.__insert_favourite(favourite)
        logging.info("数据库中已有收藏的finish状态已更新......")

    def __travel_episodes_ol(self, id):
        data = self.picaapi.eps(id, 1)
        if data is None:
            return
        pages, epss = data["pages"], data["docs"]
        for eps in epss:
            yield eps
        if pages < 2:
            return
        for i in (2, pages+1):
            epss = self.picaapi.eps(id, i)['docs']
            for eps in epss:
                yield eps

    def init_episode(self, id):
        logging.info("初始化漫画%s的分话列表......" % id)
        for eps in self.__travel_episodes_ol(id):
            _ = self.__ExecuteSQL("insert or REPLACE into episodes (id, data, comic)values(?, ?, ?);",
                                  (eps["_id"], json.dumps(eps), id))
        logging.info("漫画%s的分话列表初始化完成" % id)

    def init_episodes(self):
        logging.info("初始化系统内所有漫画的分话列表......")
        _ = self.__ExecuteSQL(
            "create table if not exists episodes (id text PRIMARY KEY NOT NULL, data json, comic text," +
            "FOREIGN KEY(id) REFERENCES comics(id));")
        for favourite, _ in self.__travel_favourites_db():
            self.init_episode(favourite["_id"])
        logging.info("系统内所有漫画的分话列表初始化完成")

    def update_episodes(self):
        logging.info("更新系统内所有未完成漫画的分话列表......")
        for favourite, _ in self.__travel_favourites_db():
            if not favourite["finished"]:
                self.init_episode(favourite["_id"])
        logging.info("系统内所有未完成漫画的分话列表初始化完成")

    def append_download_status(self):
        logging.info("为系统内新增的分话添加下载状态记录......")
        _ = self.__ExecuteSQL(
            "create table if not exists status (id text PRIMARY KEY NOT NULL, finished bool," +
            "FOREIGN KEY(id) REFERENCES episodes(id));")
        _ = self.__ExecuteSQL(
            "insert into status(id, finished) select id,FALSE from" +
            "(select * from episodes left outer join status on status.id=episodes.id)" +
            "where finished IS NULL;")
        logging.info("已为系统内新增的分话添加下载状态记录")

    def reset_download_status(self):
        logging.info("重置系统内的分话下载状态记录......")
        _ = self.__ExecuteSQL(
            "insert or REPLACE into status(id, finished) select id,FALSE from episodes;")
        logging.info("系统内的分话下载状态记录已重置")

    def __travel_img(self, comic, order):
        data = self.picaapi.pages(comic, order, 1)
        pages, docs = data['pages'], data["docs"]
        for img in docs:
            yield img
        if pages < 2:
            return
        for i in range(2, pages+1):
            docs = self.picaapi.pages(comic, order, i)['docs']
            for img in docs:
                yield img
    
    def __download(self, comic, eps):
        order = eps["order"]
        logging.info("开始下载漫画%s的分话%s" % (comic["_id"], eps["_id"]))
        threadpool = ThreadPool(processes=self.threadn)
        for data in self.__travel_img(comic["_id"], order):
            media = data["media"]
            url = parse.urljoin(media["fileServer"],
                                "static/"+media["path"])
            path = None

            def cor_dirname(dn):
                dn = re.sub('[\/:*?"<>|]', '', dn)
                dn = dn.strip()
                return dn
            author = 'null'
            if 'author' in comic:
                author = cor_dirname(comic['author'])
            ctitle = cor_dirname(comic['title'])
            etitle = cor_dirname(eps['title'])
            if comic['finished'] and comic['epsCount'] <= 1:
                path = os.path.join(self.download_path,
                                    author, ctitle,
                                    media['originalName'])
            else:
                path = os.path.join(self.download_path,
                                    author, ctitle, etitle,
                                    media['originalName'])
            threadpool.apply_async(self.picaapi.download, (url, path,))
        threadpool.close()
        threadpool.join()
        _ = self.__ExecuteSQL("update status set finished=true where id=?;",
                              (eps["_id"],))
        logging.info("漫画%s的分话%s下载完成" % (comic["_id"], eps["_id"]))

    def download_all(self):
        episodes = self.__ExecuteSQL(
            "select episodes.data, comics.data from episodes inner join status on status.id=episodes.id and status.finished=false inner join comics on episodes.comic=comics.id;")
        n = len(episodes)
        logging.info("开始下载系统内所有未完成分话(共%d个)" % n)
        for eps_data, comic_data in episodes:
            eps_data, comic_data = json.loads(eps_data), json.loads(comic_data)
            self.__download(comic_data, eps_data)
            n -= 1
            logging.info("系统内未完成分话还有%d个" % n)
        logging.info("系统内所有分话下载完成")
