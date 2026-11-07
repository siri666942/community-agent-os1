# 私域合伙人 · React 前端

前端为 React + Vite，源文件位于 src/。主菜单沿用私域运营参考界面的页面分组，包含运营总览、客户会话、客户画像、SOP 管理、跟进线索、日结报告和客户端模拟；GENERAL 区保留风控与审批、经营分析和品牌首页。业务数据继续通过本地 API 读取，客户端模拟只在浏览器内生成示例回复。

## 本地开发（两个终端）

在第一个终端，从仓库根目录进入 junction：

```bash
cd junction
pip install -r requirements.txt
python -m web_api.main
```

在第二个终端，从仓库根目录进入前端：

```bash
cd junction/web
npm install
npm run dev
```

浏览器访问 http://127.0.0.1:5173/，Vite 将 /api 请求代理到本机 8765 端口；不用配置 CORS。业务 API / 角色逻辑 / 本地人工审批流程均保持在 Python 后端。

## 由 Python 直接提供构建后的页面

```bash
cd junction/web
npm install
npm run build
cd ..
python -m web_api.main
```

访问 http://127.0.0.1:8765/，后端从 web/dist/ 提供构建好的静态文件。若 dist/ 尚不存在，后端会返回明确的构建提示。

本项目仍为**仅监听 127.0.0.1 的本地演示系统**，缺少公网登录与访问控制，请勿直接开放到互联网。示例客户为模拟数据，草稿和回执不会真实发送。

## Windows 一键启动

仓库根目录直接运行 `.\\start-dev.cmd`（也可双击），自动拉取设计分支、安装依赖、启动 Python 8765 + Vite 5173，并打开 `#dashboard`。它不会强行重置本地更改；如果端口已被占用，会检查是否是本应用服务。详见根目录 `start-dev.ps1`。
