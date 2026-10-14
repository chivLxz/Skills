#!/usr/bin/env python3
"""导出服务的命令行入口——所有实际策略都在 pm_bootstrap 里，这里只做参数解析。

常用：
  --serve      启动服务并占用当前窗口（双击启动脚本走的就是这条）
  --doctor     打印环境体检结果，排查问题时先跑这个
  --check      只检查依赖是否就绪，不启动
  --install    显式重装共享运行环境（平时不需要，--serve 会自动准备）
  --add-user   创建/重置 PRD 编辑账号（不启动服务）
  --list-users 列出已配置的编辑账号
  --remove-user 删除账号
  --lan        按内网托管启动（同事可访问，编辑仍需登录）
  --host IP    指定监听地址；--host 127.0.0.1 可改回只有本机可访问
"""
import argparse
import getpass
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pm_bootstrap import doctor, ensure_runtime, ensure_serving, reachable_url  # noqa: E402
from pm_runtime import (add_user, config_host, ensure_config, is_lan_host,  # noqa: E402
                        load_users, remove_user, require_editor_account_for_lan,
                        save_config, users_path)

ROOT = Path(os.environ.get("PROTOTYPE_PROJECT_DIR")
            or Path(__file__).resolve().parent.parent).resolve()
HINT = "排查办法：在项目目录执行  python3 scripts/start_service.py --doctor" \
    if os.name != "nt" else \
    "排查办法：在项目目录执行  py -3 scripts\\start_service.py --doctor"


def _ask_password(prompt="口令（输入时不回显）: "):
    """交互输入优先；stdin 不是终端时（脚本/CI）退化成一次明文读取，避免卡住。"""
    if sys.stdin.isatty():
        first = getpass.getpass(prompt)
        again = getpass.getpass("再输一次确认: ")
        if first != again:
            raise SystemExit("两次输入不一致，已取消")
        return first
    return sys.stdin.readline().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查依赖")
    parser.add_argument("--install", action="store_true", help="强制重装共享运行环境")
    parser.add_argument("--serve", action="store_true", help="启动服务并占用当前窗口")
    parser.add_argument("--doctor", action="store_true", help="打印环境体检结果")
    parser.add_argument("--background", action="store_true", help="脱离终端在后台启动")
    parser.add_argument("--open-browser", action="store_true", help="启动后打开首个原型页")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--host", help="监听地址；默认读 runtime.json（初始 127.0.0.1）")
    parser.add_argument("--lan", action="store_true",
                        help="按内网托管启动（等价 --host 0.0.0.0，同事可访问）")
    parser.add_argument("--no-download", action="store_true",
                        help="不允许下载 Chromium（没有可复用的系统浏览器时直接报错）")
    parser.add_argument("--add-user", metavar="用户名", help="创建/重置编辑账号后退出")
    parser.add_argument("--name", help="配合 --add-user：显示名（默认与用户名相同）")
    parser.add_argument("--password", help="配合 --add-user：口令（省略则交互输入）")
    parser.add_argument("--role", default="editor", choices=["editor", "viewer"])
    parser.add_argument("--list-users", action="store_true", help="列出已配置账号")
    parser.add_argument("--remove-user", metavar="用户名", help="删除账号后退出")
    args = parser.parse_args()

    if sys.version_info < (3, 9):
        raise SystemExit(f"需要 Python 3.9 或更高版本，当前是 {sys.version.split()[0]}")

    if args.list_users:
        users = load_users(ROOT).get("users", [])
        if not users:
            print("尚未创建编辑账号（PRD 默认只读）。")
            print("创建：python3 scripts/start_service.py --add-user 张三")
        else:
            print(f"账号表：{users_path(ROOT)}")
            for user in users:
                print(f"  · {user.get('name')}（{user.get('username')}，{user.get('role')}）")
        return 0

    if args.remove_user:
        removed = remove_user(ROOT, args.remove_user)
        print("✅ 已删除" if removed else "⚠️  未找到该账号")
        return 0

    if args.add_user:
        password = args.password or _ask_password()
        record = add_user(ROOT, args.add_user, args.name or args.add_user, password, args.role)
        print(f"✅ 已创建编辑账号：{record['name']}（{record['username']}，{record['role']}）")
        print(f"   账号表：{users_path(ROOT)}")
        print("   重新打开 PRD 页面后，点右上角「编辑」即可登录。")
        return 0

    if args.doctor:
        return doctor(ROOT)

    if args.install:
        ensure_config(ROOT)
        ensure_runtime(allow_download=not args.no_download, force_install=True)
        print("✅ 共享运行环境已就绪")
        if not args.serve:
            return 0

    if args.check:
        ensure_config(ROOT)
        ensure_runtime(allow_download=not args.no_download)
        print("✅ 环境检查通过：Python、playwright、浏览器引擎均可运行")
        return 0

    if not args.serve:
        parser.print_help()
        return 0

    # 监听地址：--lan 是 --host 0.0.0.0 的友好写法。写进 runtime.json，双击入口
    # 脚本起的服务也就跟着是内网可访问的，不用每次带参数。
    host = "0.0.0.0" if args.lan else args.host
    if host:
        # 先校验再落配置：否则会先打印「已设为内网」紧接着报错，读起来像自相矛盾。
        require_editor_account_for_lan(ROOT, host, args.read_only)
        config = ensure_config(ROOT)
        if config.get("host") != host:
            config["host"] = host
            save_config(ROOT, config)
        scope = "内网可访问（编辑仍需登录）" if is_lan_host(host) else "只有本机能访问"
        print(f"✅ 监听地址已设为 {host} —— {scope}")

    result, config = ensure_serving(
        ROOT, background=args.background, read_only=args.read_only, host=host,
        open_browser=args.open_browser, allow_download=not args.no_download)
    if args.background and result == "launched":
        print(f"✅ 服务已在后台启动：{reachable_url(host or config_host(config), config['port'])}")
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error:
        # 双击启动的场景里用户看不到 traceback 之外的东西，所以先说人话，再给排查入口。
        print(f"\n❌ {error}\n", file=sys.stderr)
        if os.environ.get("PM_DEBUG"):
            traceback.print_exc()
        print(HINT, file=sys.stderr)
        sys.exit(1)
