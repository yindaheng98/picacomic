from picaact import PicaAction
import optparse

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-u', '--user', dest='user',
                      type='string', help='pica用户名')
    parser.add_option('-p', '--pass', dest='pasw',
                      type='string', help='pica密码')
    parser.add_option('-x', '--exec', dest='exec', default='download',
                      type='string', help='执行指令: init 初始化数据库, update 更新数据库, download 下载图片')
    parser.add_option('-y', '--proxy', dest='proxy',
                      type='string', help='代理设置')
    options, _ = parser.parse_args()

    p = PicaAction(options.user,
                   options.pasw,
                   {
                       'http': options.proxy,
                       'https': options.proxy
                   })

    if options.exec == "init":
        p.init_favourites()
        p.init_episodes()
        p.append_download_status()

    if options.exec == "update":
        p.append_favourites()
        p.update_finish_status()
        p.append_download_status()

    if options.exec == "download":
        p.download_all()
