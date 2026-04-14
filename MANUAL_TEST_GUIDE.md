# 手动测试傻瓜文档（MySQL 演示版）

这份文档分成三种启动方式：

- 推荐演示方式：MySQL + 本地内存缓存
- 正式方式：MySQL + Redis
- 临时演示方式：SQLite + 本地内存缓存

如果你现在只是想手动把功能点一遍，直接用下面的“方式 A：MySQL 演示方式”。当前我已经按这个方式启动过服务。

## 方式 A：MySQL 演示方式

这个方式使用 MySQL，但不依赖 Redis。缓存使用 Django 本地内存缓存，适合本机答辩演示。

### 1. 打开终端并进入项目目录

```powershell
cd E:\projects\book-recommender-cf
```

### 2. 设置当前终端的 MySQL 参数

这些变量只在当前 PowerShell 窗口里生效，不会写进项目文件。

```powershell
$env:MYSQL_DATABASE='book_recommender_cf'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='<填写你的 MySQL root 密码>'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_mysql_demo'
```

### 3. 初始化 MySQL 数据库

```powershell
mysql -u root -p<填写你的 MySQL root 密码> -h 127.0.0.1 -P 3306 -e "CREATE DATABASE IF NOT EXISTS book_recommender_cf CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_mysql_demo
```

### 4. 初始化演示账号、图书、评分、推荐和实验数据

```powershell
conda run -n bookrec311 python scripts/init_demo_data.py
conda run -n bookrec311 python manage.py evaluate_recommenders --settings=book_recommender.settings_mysql_demo
conda run -n bookrec311 python manage.py shell --settings=book_recommender.settings_mysql_demo -c "from apps.ratings.models import ImportedInteraction; print(ImportedInteraction.objects.count())"
```

执行完成后，会创建：

- 管理员：`thesis_admin` / `AdminPass123!`
- 演示用户：`demo_reader` / `DemoPass123!`

同时会自动写入：

- 一小批演示图书
- `demo_reader` 的 3 条评分
- 一轮离线推荐结果
- 一份实验页读取的评估结果

如果最后一条命令输出 `0`，说明当前 demo 数据库只使用本地 seed 评分，还没有实际导入 Goodbooks 公开交互数据。要展示公开数据路径，先把 `books.csv` 和 `ratings.csv` 放到 `data/raw/goodbooks/`，再执行：

```powershell
conda run -n bookrec311 python manage.py import_goodbooks --source data/raw/goodbooks --limit-ratings 5000 --settings=book_recommender.settings_mysql_demo
conda run -n bookrec311 python manage.py rebuild_recommendations --settings=book_recommender.settings_mysql_demo
conda run -n bookrec311 python manage.py evaluate_recommenders --settings=book_recommender.settings_mysql_demo
```

如果 `data/raw/goodbooks/books.csv` 或 `data/raw/goodbooks/ratings.csv` 不存在，当前 demo 只能证明导入命令、seed 数据、推荐重建和评估页面路径可用，不能证明已经接入真实公开交互数据。

### 5. 启动服务

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_mysql_demo
```

浏览器打开：

`http://127.0.0.1:8000/`

当前已启动的服务：

- 地址：`http://127.0.0.1:8000/`
- 监听 PID：`23864`
- 停止命令：

```powershell
Stop-Process -Id 19504,23528,34472,23864 -Force
```

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
10. 确认推荐页能看到推荐书目和推荐理由，例如 `Similar to your ratings` 或 `Popular fallback because ItemCF had sparse data`
11. 打开 `http://127.0.0.1:8000/experiments/`
12. 确认实验页能看到：`K-value checkpoints`、`Precision curves`、`Recall curves`、`Case studies`、`Similarity comparison`、`Random interaction split`

### 再测管理员路径

1. 先退出当前账号
2. 登录 `thesis_admin` / `AdminPass123!`
3. 打开 `http://127.0.0.1:8000/dashboard/`
4. 确认页面能看到：`Operations overview`
5. 确认页面能看到：最新离线任务、Processed users、`Trigger rebuild`
6. 点击 `Trigger rebuild`
7. 刷新 dashboard，确认页面仍能正常打开
8. 记住：dashboard 按钮是手动触发路径；每日自动 rebuild 路径由 `scripts/register_daily_rebuild_task.ps1` 注册
9. 点击 `Open Django Admin`
10. 确认 `http://127.0.0.1:8000/admin/` 可以访问

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

## 方式 C：SQLite 临时演示方式

这个方式不依赖 MySQL 密码和 Redis 服务。当前这台机器上 SQLite 文件写入曾经出现过 `disk I/O error`，所以优先使用方式 A。

```powershell
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_local_demo
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_local_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
conda run -n bookrec311 python manage.py evaluate_recommenders --settings=book_recommender.settings_local_demo
Remove-Item Env:DJANGO_SETTINGS_MODULE
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_local_demo
```

## 常见问题

### 1. 首页报 Redis 或缓存错误

说明你走的是正式方式，但 Redis 没启动。

解决：

- 要么启动 Redis
- 要么改用“方式 A：MySQL 演示方式”

### 2. 登录不上

重新初始化一次 demo 数据：

```powershell
$env:MYSQL_DATABASE='book_recommender_cf'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='<填写你的 MySQL root 密码>'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_mysql_demo'
conda run -n bookrec311 python scripts/init_demo_data.py
Remove-Item Env:DJANGO_SETTINGS_MODULE
```

### 3. 8000 端口被占用

改成 8001：

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8001 --settings=book_recommender.settings_mysql_demo
```

然后打开：

`http://127.0.0.1:8001/`
