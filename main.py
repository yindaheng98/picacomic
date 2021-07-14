from picaact import PicaAction
import optparse
import os

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-u', '--user', dest='user',
                      type='string', help='pica用户名')
    parser.add_option('-p', '--pass', dest='pasw',
                      type='string', help='pica密码')
    parser.add_option('-d', '--directory', dest='directory', default=os.path.join(os.path.split(__file__)[0], "data"),
                      type='string', help='数据存放位置')
    parser.add_option('-x', '--exec', dest='exec', default='download',
                      type='string', help='执行指令: init 初始化数据库, update 更新数据库, download 下载图片，reset_download 重置下载记录（不会删除文件）')
    parser.add_option('-n', '--numb', dest='numb', default=0,
                      type='int', help='执行指令=init或update时初始化前多少个')
    parser.add_option('-t', '--thread', dest='thread', default=5,
                      type='int', help='执行指令=download时使用多少线程')
    parser.add_option('-y', '--proxy', dest='proxy',
                      type='string', help='代理设置')
    options, _ = parser.parse_args()

    p = PicaAction(options.user,
                   options.pasw,
                   {
                       'http': options.proxy,
                       'https': options.proxy
                   },
                   data_path=options.directory,
                   threadn=options.thread)

    if options.exec == "init":
        if options.numb>0:
            p.init_favourites(options.numb)
        else:
            p.init_favourites()
        p.init_episodes()
        p.append_download_status()

    if options.exec == "update":
        if options.numb>0:
            p.append_favourites(options.numb)
        else:
            p.append_favourites()
        p.update_episodes()
        p.update_finish_status()
        p.append_download_status()

    if options.exec == "download":
        p.download_all()

    if options.exec == "reset_download":
        p.reset_download_status()
