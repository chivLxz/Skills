"""Project-scoped configuration shared by the preview server, launcher and bootstrap.

设计要点：
  * 端口由 project_id 确定性推导到 20000-32767，避开 OS 临时端口段（49152+），
    那一段既会被系统派给出站连接，在 Windows 上还有 Hyper-V/WSL/Docker 的保留块。
  * 端口可自愈：bind 失败时换 salt 重新推导并回写配置，不会永久占坑。
  * ensure_config() 是 create-or-load，缺配置时创建而不是抛错——任何人 clone 一个
    项目仓（.pm-workflow/ 被 gitignore）都不该看到 traceback。
  * 本模块同时承载「PRD 编辑登录」的账号与会话逻辑（v3.4 起）：账号落在
    `.pm-workflow/users.json`（同样被 gitignore），会话是无状态签名串，签名密钥
    复用项目 token，所以不引入任何新的持久化文件或依赖。
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

VERSION = "3.5.0"
PORTS_SCHEME = "deterministic-v2"
PORT_FLOOR = 20000
PORT_SPAN = 12767  # 20000..32766，+1 后仍不超过 32767


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def config_path(root):
    return Path(root).resolve() / ".pm-workflow/runtime.json"


def derive_ports(project_id, salt=0):
    """由项目标识确定性推导服务端口与启动器端口；salt 用于 bind 冲突时换一个。

    **salt 只作用于服务端口，启动器端口固定不变。** 后者被写死在 macOS 的
    LaunchAgent plist 里，而换 plist 端口只能 bootout + bootstrap——bootout 会
    连带杀掉正在处理这次请求的启动器进程自己。让它永不漂移，这个竞态就不存在。
    真正会跟别的应用撞车的本来也只有服务端口。
    """
    launcher = PORT_FLOOR + int.from_bytes(
        hashlib.sha256(f"{project_id}:0".encode()).digest()[:4], "big") % PORT_SPAN + 1
    seed = hashlib.sha256(f"{project_id}:{salt}".encode()).digest()
    port = PORT_FLOOR + int.from_bytes(seed[:4], "big") % PORT_SPAN
    if port == launcher:  # 重抽时正好撞上固定的启动器端口，往后挪一格
        port = PORT_FLOOR + (port + 1 - PORT_FLOOR) % PORT_SPAN
    return port, launcher


def _browser_config(config):
    return {
        "projectId": config["project_id"],
        "token": config["token"],
        "server": "http://127.0.0.1:" + str(config["port"]),
        "launcher": "http://127.0.0.1:" + str(config["launcher_port"]),
    }


def write_browser_config(root, config):
    """浏览器侧配置，随端口变化重写，被 prototype-export-client.js 动态加载。"""
    atomic_write(Path(root).resolve() / "scripts/pm-runtime-config.js",
                 "window.PM_RUNTIME = " + json.dumps(_browser_config(config)) + ";\n")


def save_config(root, config):
    root = Path(root).resolve()
    path = config_path(root)
    config["version"] = VERSION
    atomic_write(path, json.dumps(config, ensure_ascii=False, indent=2))
    try:
        path.chmod(0o600)  # 内含项目 token；Windows 上该位无意义，失败不阻断
    except OSError:
        pass
    write_browser_config(root, config)
    return config


def ensure_config(root):
    """读不到就创建；结构过期就就地升级。永不因缺文件抛错。"""
    root = Path(root).resolve()
    path = config_path(root)
    config = {}
    if path.is_file():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            config = {}  # 配置损坏时重建，比让每个入口都 traceback 好
    if not isinstance(config, dict):
        config = {}

    moved = config.get("root") != str(root)
    if moved or not config.get("project_id"):
        # 目录被移动过：project_id 由绝对路径派生，必须重算，否则端口/身份都对不上
        config["root"] = str(root)
        config["project_id"] = hashlib.sha256(str(root).encode()).hexdigest()[:16]
        config.pop("ports_scheme", None)
    if not config.get("token"):
        config["token"] = secrets.token_urlsafe(32)
    if config.get("ports_scheme") != PORTS_SCHEME or not config.get("port"):
        # 老配置的端口抽自 OS 临时端口段，迁到确定性区间
        config["port"], config["launcher_port"] = derive_ports(config["project_id"])
        config["port_salt"] = 0
        config["ports_scheme"] = PORTS_SCHEME
    return save_config(root, config)


def load_config(root):
    """只读加载；供已初始化的场景使用，缺文件时给出可执行的指引而非裸 traceback。"""
    path = config_path(root)
    if not path.is_file():
        raise RuntimeError(
            "尚未初始化项目运行配置。请双击项目根目录的「启动原型导出服务」"
            "（Windows 为 .bat），它会自动创建配置并启动服务。")
    config = json.loads(path.read_text(encoding="utf-8"))
    if Path(config["root"]).resolve() != Path(root).resolve():
        raise RuntimeError(
            "项目目录已移动。请双击项目根目录的「启动原型导出服务」（Windows 为 .bat）重新初始化。")
    return config


def reroll_ports(root, config):
    """bind 冲突后换一对端口并回写，返回新配置。

    这里是全局唯一改动端口的地方，所以 LaunchAgent 的同步也放在这里：plist 里的
    端口是写死的，漏同步一次，launchd 就会守着一个没人访问的旧端口，
    「点导出自动起服务」静默失效。放在调用点上同步的话，每新增一条自愈路径
    都得记得补一次——迟早漏。
    """
    config["port_salt"] = int(config.get("port_salt", 0)) + 1
    config["port"], config["launcher_port"] = derive_ports(config["project_id"], config["port_salt"])
    config["ports_scheme"] = PORTS_SCHEME
    config = save_config(root, config)
    try:
        import pm_launchagent
        pm_launchagent.sync(root, config)  # 没注册过则什么都不做
    except Exception:  # noqa: BLE001 — 同步失败不该拖垮启动，doctor 会报错位
        pass
    return config


def local_opener():
    """127.0.0.1 的健康检查必须绕开代理——urllib 默认也会走 HTTP_PROXY，
    代理返回的 HTML 会让 json 解析失败，从而误判“服务没在跑”并重复启动。"""
    return build_opener(ProxyHandler({}))


def probe_health(port, timeout=1.5):
    """返回服务自报的状态；连不上或不是本服务时返回 None。"""
    try:
        with local_opener().open(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as response:
            state = json.load(response)
        return state if isinstance(state, dict) else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 本机地址集合 / 同源判定（v2.6 内网托管）
#
# v2.5 之前服务只监听 127.0.0.1，「来源必须是 loopback」这条既是 CORS 策略、
# 也是安全边界。v2.6 要允许内网托管，同事浏览器发的是 `http://192.168.x.x:PORT`
# ——再拿 loopback 白名单去比，同事一律 401/403。所以改成「同源判定」：
#   来源的 host:port 必须等于本次请求的 Host，且 Host 必须指向本机网卡。
# 后一句是防 DNS-rebinding 的那道门：evil.com 解析到 127.0.0.1 时，请求里的
# Host 会是 evil.com，不在本机地址集合里，直接拒。
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_ADDRESSES = None


def local_addresses():
    """本机所有能访问到自己的地址：回环 + 各网卡 IPv4。

    缓存一次——`gethostbyname` 在部分 Windows 上要几百毫秒，而它会被每个请求的
    鉴权路径调用。
    """
    global _LOCAL_ADDRESSES
    if _LOCAL_ADDRESSES is not None:
        return _LOCAL_ADDRESSES
    found = {"127.0.0.1", "localhost", "::1"}
    try:
        found.add(socket.gethostbyname(socket.gethostname()))
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    _LOCAL_ADDRESSES = found
    return found


def register_local_host(host):
    """把显式绑定的监听地址也纳入「本机」。

    VPN / 虚拟网卡的地址经常从 gethostbyname 拿不到，但用户就是绑着它启动的；
    不补这一句会出现「服务起来了、同事却一律 401」的假故障。
    """
    if host and host not in ("0.0.0.0", "::"):
        local_addresses().add(host.strip().lower())


def primary_lan_address():
    """挑一个最适合发给同事的地址。

    用 UDP connect 让内核选默认出口网卡（不发任何包），比 gethostbyname 可靠：
    后者在有 VPN / 虚拟网卡时经常返回一个同事根本连不上的地址。
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            address = probe.getsockname()[0]
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    for address in sorted(local_addresses()):
        if address not in ("127.0.0.1", "localhost", "::1"):
            return address
    return "127.0.0.1"


def _split_host_port(value):
    """拆 `host[:port]`，兼容 `[::1]:8080` 这种 IPv6 写法。"""
    value = (value or "").strip()
    if value.startswith("["):
        host, _, rest = value[1:].partition("]")
        return host, (rest[1:] if rest.startswith(":") else "")
    host, _, port = value.partition(":")
    return host, port


def host_points_at_self(value, port):
    """Host / Referer 里的 host[:port] 是否指向本机（防 DNS-rebinding）。"""
    host, found_port = _split_host_port(value)
    if not host:
        return False
    if found_port and found_port != str(port):
        return False
    return host.lower() in local_addresses()


def is_lan_host(host):
    return host not in ("127.0.0.1", "localhost", "::1")


def origin_allowed(origin, port, host=None):
    """同源判定。

    - 无来源 / `null`：PRD 以 `file://` 打开时 Chrome 就是这么报的，放行。
    - `http://127.0.0.1` / `http://localhost`（不带端口）：同样是本地文件页的
      序列化形态，历史行为，保留。
    - 其余：必须是 `http://<本次请求的 Host>`（严格同源），或 host 落在本机
      地址集合里且端口一致。
    """
    if origin in (None, "null", "http://127.0.0.1", "http://localhost"):
        return True
    if host and origin == "http://" + host:
        return True
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.port != port:
        return False
    return parsed.hostname.lower() in local_addresses()


def cors_response_origin(origin):
    # Chrome reports local file pages as an opaque null origin while sending
    # the loopback site origin in the HTTP request header.
    if origin in ("http://127.0.0.1", "http://localhost"):
        return "null"
    return origin


def config_host(config):
    """配置里记的监听地址。v2.6 起 `--lan` 会把它写进 runtime.json，
    这样双击入口脚本起的服务也是内网可访问的，不用每次带参数。"""
    return (config or {}).get("host") or "127.0.0.1"


def require_editor_account_for_lan(root, host, read_only):
    """局域网 + 可写，必须至少有一个编辑账号。

    没有账号时 `/api/login` 一律 428，等于**托上去谁都编辑不了**——那比直接
    报错更难查，所以在启动时就拦住，并把该跑的命令写进错误里。
    """
    if read_only or not is_lan_host(host):
        return
    if load_users(root).get("users"):
        return
    raise RuntimeError(
        "局域网可写监听需要先有一个编辑账号，否则同事打开后谁都编辑不了。\n"
        "  创建账号：python3 scripts/start_service.py --add-user 你的名字\n"
        "  只想给同事看、不需要编辑：改成 --read-only 启动")


def valid_token(headers, config):
    return (headers.get("X-PM-Project") == config["project_id"] and
            secrets.compare_digest(headers.get("X-PM-Token", ""), config["token"]))


# ─────────────────────────────────────────────────────────────────────────────
# 编辑账号与会话（PRD 的「登录后才可编辑」）
#
# 为什么是本地账号而不是公司 SSO：PRD 常常在内网 `file://` / 裸 http 下打开，
# 那里没有可信的身份源；而这份文档本来就躺在 PM 自己机器的项目目录里，导出服务
# 也只听 127.0.0.1（除非显式只读模式）。所以「谁改的」这件事，以本机项目为界最实在。
#
# 会话不做 cookie：PRD 可能是 `file://` 打开的，向 127.0.0.1:PORT 写 cookie 会命中
# 第三方 cookie 策略。改用与 X-PM-Token 同一套显式 header（X-PM-Session），
# 由页面自己存在 localStorage 里——语义清楚，也不依赖浏览器对本地文件的 cookie 宽容度。
#
# 账号存储用的是 pbkdf2-sha256 + 每用户独立 salt；users.json 本身在 .pm-workflow/
# （安装器已写进项目 .gitignore），不会跟着产物提交出去。
# ─────────────────────────────────────────────────────────────────────────────

SESSION_TTL = 12 * 3600            # 一次登录管一个工作日
SESSION_HEADER = "X-PM-Session"
_PBKDF2_ROUNDS = 120_000
USERS_FILE = "users.json"


def users_path(root):
    return Path(root).resolve() / ".pm-workflow" / USERS_FILE


def load_users(root):
    """读账号表；文件缺失/损坏一律回落成「未启用编辑」，不抛错。"""
    path = users_path(root)
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    users = data.get("users")
    data["users"] = [u for u in users if isinstance(u, dict) and u.get("username")] if isinstance(users, list) else []
    return data


def save_users(root, data):
    path = users_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))
    try:
        path.chmod(0o600)          # 里面有口令散列；Windows 上该位无意义，失败不阻断
    except OSError:
        pass
    return data


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ROUNDS)
    return "pbkdf2${}${}".format(salt, digest.hex())


def verify_password(password, stored):
    try:
        scheme, salt, _ = str(stored).split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def find_user(root, username):
    for user in load_users(root).get("users", []):
        if user.get("username") == username:
            return user
    return None


def add_user(root, username, display_name, password, role="editor"):
    """新增或覆盖一个账号。返回不含散列的用户信息（可直接回给前端）。"""
    username = (username or "").strip()
    if not username:
        raise ValueError("用户名不能为空")
    if not password or len(password) < 4:
        raise ValueError("口令至少 4 位")
    data = load_users(root)
    record = {
        "username": username,
        "name": (display_name or username).strip(),
        "role": role if role in ("editor", "viewer") else "editor",
        "password": hash_password(password),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data["users"] = [u for u in data["users"] if u.get("username") != username] + [record]
    save_users(root, data)
    return {k: record[k] for k in ("username", "name", "role")}


def remove_user(root, username):
    data = load_users(root)
    before = len(data["users"])
    data["users"] = [u for u in data["users"] if u.get("username") != username]
    save_users(root, data)
    return len(data["users"]) < before


def public_user(record):
    return {"username": record.get("username"), "name": record.get("name") or record.get("username"),
            "role": record.get("role") or "editor"}


def make_session(config, username, ttl=SESSION_TTL):
    """无状态会话串：base64url(username).expiry.hmac。密钥就是项目 token。"""
    expiry = int(time.time()) + int(ttl)
    payload = "{}.{}".format(username, expiry)
    signature = hmac.new(config["token"].encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return "{}.{}".format(base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("="), signature)


def read_session(config, token):
    """校验并解出会话内容；任何一处不对都返回 None（过期、被改、格式坏）。"""
    if not token or token.count(".") != 1:
        return None
    blob, signature = token.split(".", 1)
    try:
        payload = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    expected = hmac.new(config["token"].encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return None
    username, _, expiry = payload.rpartition(".")
    try:
        if int(expiry) < int(time.time()):
            return None
    except ValueError:
        return None
    return {"username": username, "expiry": int(expiry)}


def authenticate(root, config, headers):
    """把请求头里的会话换成用户记录；未登录 / 账号已被删 / 过期都返回 None。"""
    session = read_session(config, headers.get(SESSION_HEADER, ""))
    if not session:
        return None
    return find_user(root, session["username"])
