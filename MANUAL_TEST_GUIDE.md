# 手动测试傻瓜文档（MySQL 演示版）

这份文档先写启动命令，再写页面怎么点、看到什么。页面名称统一按当前中文 UI 写，必要时保留英文对照。

## 一、本地启动命令

这份文档分成三种启动方式：

- 推荐演示方式：MySQL + 本地内存缓存
- 正式方式：MySQL + Redis
- 临时演示方式：SQLite + 本地内存缓存

如果你现在只是想手动把功能点一遍，直接用下面的“方式 A：MySQL 演示方式”。

## 方式 A：MySQL 演示方式

这个方式使用 MySQL，但不依赖 Redis。缓存使用 Django 本地内存缓存，适合本机答辩演示。

### 启动命令

1. 打开终端并进入项目目录

```powershell
cd E:\projects\book-recommender-cf
```

2. 设置当前终端的 MySQL 参数

这些变量只在当前 PowerShell 窗口里生效，不会写进项目文件。

```powershell
$env:MYSQL_DATABASE='book_recommender_cf'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='<填写你的 MySQL root 密码>'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
$env:DJANGO_SETTINGS_MODULE='book_recommender.settings_mysql_demo'
```

3. 初始化 MySQL 数据库

```powershell
mysql -u root -p<填写你的 MySQL root 密码> -h 127.0.0.1 -P 3306 -e "CREATE DATABASE IF NOT EXISTS book_recommender_cf CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
conda run -n bookrec311 python manage.py migrate --settings=book_recommender.settings_mysql_demo
```

4. 初始化演示账号、图书、评分、推荐和实验数据

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

当前 MySQL demo 已导入 Goodbooks 公开交互数据。最近一次验证结果：

```text
imported_interactions 5000
goodbooks_books 10000
strategies ['hot', 'hybrid', 'itemcf', 'usercf']
```

如果你清空数据库或删除 `data/raw/goodbooks/` 后重建环境，重新执行下载、导入、rebuild 和 evaluate 命令：

```powershell
conda run -n bookrec311 python scripts/download_goodbooks_data.py --destination data/raw/goodbooks
conda run -n bookrec311 python manage.py import_goodbooks --source data/raw/goodbooks --limit-ratings 5000 --settings=book_recommender.settings_mysql_demo
conda run -n bookrec311 python manage.py rebuild_recommendations --settings=book_recommender.settings_mysql_demo
conda run -n bookrec311 python manage.py evaluate_recommenders --settings=book_recommender.settings_mysql_demo
```

5. 启动服务

```powershell
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_mysql_demo
```

浏览器打开：

`http://127.0.0.1:8000/`

服务启动后：

- 浏览器打开地址：`http://127.0.0.1:8000/`
- 查询当前监听 PID：

```powershell
netstat -ano | Select-String ':8000'
```

- 停止时，先用上面的命令查到 PID，再执行：

```powershell
Stop-Process -Id <PID> -Force
```

## 二、页面怎么点 / 看到什么

### 普通用户路径

1. 打开首页，确认顶部导航能看到：`浏览图书`、`实验结果`、`登录`、`注册`
2. 点击 `登录`
3. 登录 `demo_reader` / `DemoPass123!`
4. 登录后回到首页，确认顶部导航出现：`推荐中心`、`个人中心`
5. 点击 `浏览图书`，检查图书列表页是否正常
6. 点开任意一本书，检查详情页是否有：图书信息、分类、评分入口、相似图书
7. 打开个人中心：`/accounts/profile/`
8. 确认能看到：用户名、`推荐状态：个性化推荐`、至少 3 条评分记录
9. 在个人中心点击 `推荐中心`
10. 确认推荐页能看到推荐书目和推荐理由，例如 `与你的评分相似` 或 `由于 ItemCF 数据稀疏，当前显示热门兜底结果`
11. 打开 `http://127.0.0.1:8000/experiments/`
12. 确认实验页能看到：`K 值检查点`、`精确率曲线`、`召回率曲线`、`案例分析`、`相似度对比`、`随机交互划分`

### 管理员路径

1. 先退出当前账号
2. 登录 `thesis_admin` / `AdminPass123!`
3. 打开 `http://127.0.0.1:8000/dashboard/`
4. 确认页面能看到：`运维总览`
5. 确认页面能看到：最新离线任务、`已处理用户`、`手动触发刷新`
6. 点击 `手动触发刷新`
7. 刷新管理页，确认页面仍能正常打开
8. 记住：管理页里的手动触发按钮是临时操作路径；每日自动重建路径由 `scripts/register_daily_rebuild_task.ps1` 注册
9. 每日自动重建已注册为 Windows 计划任务。查询命令：

```powershell
Get-ScheduledTask -TaskName BookRecommenderDailyRebuild | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName BookRecommenderDailyRebuild | Select-Object LastRunTime,LastTaskResult,NextRunTime
```

最近一次手动触发验证结果：`LastTaskResult = 0`，表示手动触发路径执行成功。这个计划任务使用当前 Windows 交互账号注册，适合本机答辩演示；要让它按 02:00 自动运行，需要该 Windows 用户保持登录。任务读取当前项目根目录下被 Git 忽略的 `.env` 中的 MySQL/Redis 配置。

10. 点击 `打开 Django 管理后台`
11. 确认 `http://127.0.0.1:8000/admin/` 可以访问

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
