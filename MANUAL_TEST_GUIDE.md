# 手动测试傻瓜文档

这份文档分成两种启动方式：

- 正式方式：MySQL + Redis
- 临时演示方式：SQLite + 本地内存缓存

如果你现在只是想手动把功能点一遍，直接用下面的“方式 A：临时演示方式”。

## 方式 A：临时演示方式

这个方式不依赖 `.env`、MySQL 密码、Redis 服务，适合本机快速点功能。

### 1. 打开终端并进入项目目录

```powershell
cd E:\projects\book-recommender-cf
```

### 2. 初始化本地演示数据库

```powershell
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_local_demo
```

### 3. 初始化演示账号和演示数据

```powershell
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_local_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
Remove-Item Env:DJANGO_SETTINGS_MODULE
```

执行完成后，会创建：

- 管理员：`thesis_admin` / `AdminPass123!`
- 演示用户：`demo_reader` / `DemoPass123!`

同时会自动写入：

- 一小批演示图书
- `demo_reader` 的 3 条评分
- 一轮离线推荐结果

### 4. 启动服务

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_local_demo
```

浏览器打开：

`http://127.0.0.1:8000/`

## 现在你应该怎么点

### 先测普通用户路径

1. 打开首页，确认顶部导航能看到：`Browse books`、`Experiments`、`Log in`、`Register`
2. 点击右上角 `Log in`
3. 登录 `demo_reader` / `DemoPass123!`
4. 登录后回到首页，确认顶部导航出现：`Recommendations`、`Profile`
5. 点击 `Browse books`，检查图书列表页是否正常
6. 点开任意一本书，检查详情页是否有：图书信息、分类、评分入口、相似图书
7. 打开个人中心：`/accounts/profile/`
8. 确认能看到：用户名、`Recommendation state: personalized`、至少 3 条评分记录
9. 在个人中心点击 `Recommendation center`
10. 确认推荐页能看到推荐书目和推荐理由，例如 `Popular fallback because ItemCF had sparse data`

### 再测管理员路径

1. 先退出当前账号
2. 登录 `thesis_admin` / `AdminPass123!`
3. 打开 `http://127.0.0.1:8000/dashboard/`
4. 确认页面能看到：`Operations overview`
5. 确认页面能看到：最新离线任务、Processed users、`Trigger rebuild`
6. 点击 `Trigger rebuild`
7. 刷新 dashboard，确认页面仍能正常打开
8. 点击 `Open Django Admin`
9. 确认 `http://127.0.0.1:8000/admin/` 可以访问

## 方式 B：正式方式

这个方式走项目原始栈，需要：

- MySQL
- Redis
- 项目根目录下存在 `.env`

### 1. 创建 `.env`

```powershell
Copy-Item .env.example .env
```

然后把 `.env` 里的 MySQL 和 Redis 参数改成你机器上的真实值。

### 2. 跑迁移

```powershell
conda run -n bookrec311 python manage.py migrate
```

### 3. 初始化 demo 数据

```powershell
conda run -n bookrec311 python scripts/init_demo_data.py
```

### 4. 启动服务

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000
```

## 常见问题

### 1. 首页报 Redis 或缓存错误

说明你走的是正式方式，但 Redis 没启动。

解决：

- 要么启动 Redis
- 要么改用“方式 A：临时演示方式”

### 2. 登录不上

重新初始化一次 demo 数据：

```powershell
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_local_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
Remove-Item Env:DJANGO_SETTINGS_MODULE
```

### 3. 8000 端口被占用

改成 8001：

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8001 --settings=book_recommender.settings_local_demo
```

然后打开：

`http://127.0.0.1:8001/`
