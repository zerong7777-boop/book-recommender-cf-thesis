# 项目实现说明

本文档面向答辩、客户演示和后续维护，按代码真实实现回答项目的关键技术问题。所有结论均以当前仓库代码和当前 MySQL demo 数据库状态为准，而不是按论文理想方案反推。

## 1. 项目实际技术栈

### 1.1 Web 与运行时

- Python：`3.11.15`
- Django：`5.2.1`
- WSGI 服务：`gunicorn 23.0.0`
- 静态资源：`whitenoise 6.8.2`
- 数据处理与算法依赖：
  - `pandas 2.2.3`
  - `numpy 2.2.4`
  - `scikit-learn 1.6.1`

### 1.2 数据库类型

- 生产/标准配置：MySQL
  - Django 驱动层使用 `PyMySQL 1.1.1`
  - Django 数据库引擎为 `django.db.backends.mysql`
- 本地轻量演示配置：SQLite
  - 仅在 `book_recommender/settings_local_demo.py` 中使用
  - 不作为 Railway 线上演示的数据库

### 1.3 Redis 部署方式

- Django 缓存后端：`django-redis 5.4.0`
- Redis 客户端库：`redis 5.2.1`
- 标准配置下通过 `REDIS_URL` 连接 Redis
- Railway 线上演示使用 Railway 提供的独立 Redis 服务，通过内部地址注入 `REDIS_URL`
- 本地 `settings_mysql_demo.py` 和 `settings_local_demo.py` 为了减少环境依赖，改用 `LocMemCache`

### 1.4 Railway 部署配置

当前仓库不是 `railway.json` 路线，而是 `Procfile + 环境变量` 路线。

- 启动命令：

```procfile
web: python manage.py collectstatic --noinput && python manage.py evaluate_recommenders --skip-record && gunicorn book_recommender.wsgi:application --bind 0.0.0.0:$PORT
```

- 关键环境变量：
  - `DJANGO_SECRET_KEY`
  - `DJANGO_DEBUG`
  - `DJANGO_ALLOWED_HOSTS`
  - `CSRF_TRUSTED_ORIGINS`
  - `RAILWAY_PUBLIC_DOMAIN`
  - `MYSQLDATABASE` / `MYSQL_DATABASE`
  - `MYSQLUSER` / `MYSQL_USER`
  - `MYSQLPASSWORD` / `MYSQL_PASSWORD`
  - `MYSQLHOST` / `MYSQL_HOST`
  - `MYSQLPORT` / `MYSQL_PORT`
  - `REDIS_URL`

部署特征：

- `book_recommender/settings.py` 会兼容 Railway 风格的 MySQL 变量名和本地 `.env` 变量名
- `RAILWAY_PUBLIC_DOMAIN` 会自动加入 `ALLOWED_HOSTS` 和 `CSRF_TRUSTED_ORIGINS`
- 每次 Railway 容器启动时会先执行 `evaluate_recommenders --skip-record`，确保实验页依赖的 `artifacts/evaluations/summary.json` 存在
- 线上实验页展示依赖文件产物，不是每次请求现算

## 2. 数据集信息

### 2.1 Goodbooks 数据来源

项目中的公开数据下载脚本 `scripts/download_goodbooks_data.py` 指向：

- `https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/books.csv`
- `https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master/ratings.csv`

因此本项目使用的是 `zygmuntz/goodbooks-10k` 的公开 CSV 数据，而不是自定义整理版。

### 2.2 Goodbooks 原始源数据规模

基于当前仓库内 `data/raw/goodbooks/` 的原始 CSV 文件统计：

- 图书总数：`10000`
- 用户总数：`53424`
- 评分总数：`5976479`
- 评分范围：`1 ~ 5`

### 2.3 当前项目实际导入规模

当前 MySQL demo 数据库不是导入完整 `ratings.csv`，而是通过：

```powershell
python manage.py import_goodbooks --source data/raw/goodbooks --limit-ratings 5000
```

导入了一个受限子集。当前库中的真实计数为：

- Goodbooks 导入图书数：`10000`
- Goodbooks 导入用户数：`137`
- Goodbooks 导入评分数：`5000`
- Goodbooks 导入评分范围：`1 ~ 5`

同时，当前演示数据库还额外包含站内演示数据：

- 当前数据库总图书数：`10009`
- 当前 Django 用户总数：`7`
- 当前站内评分总数：`15`
- 当前有站内评分记录的用户数：`5`

所以需要区分：

- “公开源数据规模”是 `10000 / 53424 / 5976479`
- “当前实际导入规模”是 `10000 / 137 / 5000`
- “当前整库规模”还叠加了 demo 用户和站内评分

### 2.4 字段映射

`import_goodbooks` 的字段映射如下。

#### `books.csv` -> `catalog_book`

必需字段：

- `book_id`
- `title`
- `authors`

实际映射：

- `title` -> `Book.title`
- `authors` -> `Book.author`
- 固定分类 `goodbooks-import` -> `Book.category`
- `original_publication_year` -> `Book.publication_year`
- `average_rating` -> `Book.average_rating`
- `ratings_count` -> `Book.rating_count`
- `image_url` -> `Book.cover_url`
- 描述字段未从源文件抽取，统一写入 `"Imported from Goodbooks baseline data."`
- `publisher` 未从源文件映射，写空字符串

说明：

- 项目没有保存 Goodbooks 的原始 `book_id` 到 `Book` 独立字段中，而是仅在导入过程中用它做内存映射，将评分记录关联到创建后的 Django `Book.id`

#### `ratings.csv` -> `ratings_importedinteraction`

必需字段：

- `user_id`
- `book_id`
- `rating`

实际映射：

- 固定 `dataset_name="goodbooks-10k"` -> `ImportedInteraction.dataset_name`
- `user_id` -> `ImportedInteraction.dataset_user_id`
- 通过导入期的 `book_id -> Book` 映射 -> `ImportedInteraction.book_id`
- `rating` -> `ImportedInteraction.score`
- `imported_at` 为 Django 入库时间，不是源文件时间

## 3. 数据库结构

### 3.1 用户模型

项目没有自定义用户模型，使用 Django 默认用户表：

- 模型类：`django.contrib.auth.models.User`
- 表名：`auth_user`

项目内所有用户外键都指向 `settings.AUTH_USER_MODEL`，在当前实现下就是 `auth_user`。

### 3.2 业务模型总览

#### `Category`

- 类名：`apps.catalog.models.Category`
- 表名：`catalog_category`
- 字段：
  - `id`
  - `name`
  - `slug`
- 约束：
  - `name` 唯一
  - `slug` 唯一

#### `Book`

- 类名：`apps.catalog.models.Book`
- 表名：`catalog_book`
- 字段：
  - `id`
  - `title`
  - `author`
  - `category_id`
  - `cover_url`
  - `description`
  - `publisher`
  - `publication_year`
  - `average_rating`
  - `rating_count`
  - `created_at`
- 外键：
  - `category_id -> catalog_category.id`
- 约束：
  - `book_average_rating_0_5`

#### `UserRating`

- 类名：`apps.ratings.models.UserRating`
- 表名：`ratings_userrating`
- 字段：
  - `id`
  - `user_id`
  - `book_id`
  - `score`
  - `rated_at`
- 外键：
  - `user_id -> auth_user.id`
  - `book_id -> catalog_book.id`
- 唯一约束：
  - `unique_user_book_rating`：`(user_id, book_id)`
- 检查约束：
  - `user_rating_score_1_5`

#### `UserRatingHistory`

- 类名：`apps.ratings.models.UserRatingHistory`
- 表名：`ratings_userratinghistory`
- 字段：
  - `id`
  - `user_id`
  - `book_id`
  - `score`
  - `action`
  - `created_at`
- 外键：
  - `user_id -> auth_user.id`
  - `book_id -> catalog_book.id`
- 检查约束：
  - `user_rating_history_score_1_5`

#### `ImportedInteraction`

- 类名：`apps.ratings.models.ImportedInteraction`
- 表名：`ratings_importedinteraction`
- 字段：
  - `id`
  - `dataset_name`
  - `dataset_user_id`
  - `book_id`
  - `score`
  - `imported_at`
- 外键：
  - `book_id -> catalog_book.id`
- 唯一约束：
  - `unique_imported_interaction_dataset_user_book`：`(dataset_name, dataset_user_id, book_id)`
- 检查约束：
  - `imported_interaction_score_1_5`

#### `OfflineJobRun`

- 类名：`apps.recommendations.models.OfflineJobRun`
- 表名：`recommendations_offlinejobrun`
- 字段：
  - `id`
  - `job_name`
  - `status`
  - `started_at`
  - `finished_at`
  - `processed_user_count`
  - `summary`

#### `RecommendationResult`

- 类名：`apps.recommendations.models.RecommendationResult`
- 表名：`recommendations_recommendationresult`
- 字段：
  - `id`
  - `user_id`
  - `strategy`
  - `generated_at`
  - `top_k`
- 外键：
  - `user_id -> auth_user.id`
- 说明：
  - `user_id` 允许为空，空值代表全局热门结果

#### `RecommendationItem`

- 类名：`apps.recommendations.models.RecommendationItem`
- 表名：`recommendations_recommendationitem`
- 字段：
  - `id`
  - `result_id`
  - `book_id`
  - `rank`
  - `score`
  - `reason`
- 外键：
  - `result_id -> recommendations_recommendationresult.id`
  - `book_id -> catalog_book.id`
- 唯一约束：
  - `unique_recommendation_result_rank`：`(result_id, rank)`
  - `unique_recommendation_result_book`：`(result_id, book_id)`

#### `SimilarBookResult`

- 类名：`apps.recommendations.models.SimilarBookResult`
- 表名：`recommendations_similarbookresult`
- 字段：
  - `id`
  - `source_book_id`
  - `target_book_id`
  - `score`
  - `rank`
- 外键：
  - `source_book_id -> catalog_book.id`
  - `target_book_id -> catalog_book.id`
- 唯一约束：
  - `unique_similar_book_source_rank`：`(source_book_id, rank)`
  - `unique_similar_book_source_target`：`(source_book_id, target_book_id)`

#### `EvaluationRun`

- 类名：`apps.evaluations.models.EvaluationRun`
- 表名：`evaluations_evaluationrun`
- 字段：
  - `id`
  - `experiment_name`
  - `strategy`
  - `dataset_name`
  - `started_at`
  - `finished_at`
  - `metric_summary`

### 3.3 外键关系图

- `Book.category_id -> Category.id`
- `UserRating.user_id -> auth_user.id`
- `UserRating.book_id -> Book.id`
- `UserRatingHistory.user_id -> auth_user.id`
- `UserRatingHistory.book_id -> Book.id`
- `ImportedInteraction.book_id -> Book.id`
- `RecommendationResult.user_id -> auth_user.id`
- `RecommendationItem.result_id -> RecommendationResult.id`
- `RecommendationItem.book_id -> Book.id`
- `SimilarBookResult.source_book_id -> Book.id`
- `SimilarBookResult.target_book_id -> Book.id`

### 3.4 索引设计

当前项目没有额外手写 `Meta.indexes`，索引设计主要来自三类来源：

1. 主键索引  
所有表的 `id` 自动带主键索引。

2. 唯一约束生成的唯一索引  
包括：

- `Category.name`
- `Category.slug`
- `UserRating(user_id, book_id)`
- `ImportedInteraction(dataset_name, dataset_user_id, book_id)`
- `RecommendationItem(result_id, rank)`
- `RecommendationItem(result_id, book_id)`
- `SimilarBookResult(source_book_id, rank)`
- `SimilarBookResult(source_book_id, target_book_id)`

3. 外键字段自动索引  
Django/MySQL 会为大多数外键字段生成普通索引，例如：

- `Book.category_id`
- `UserRating.user_id`
- `UserRating.book_id`
- `ImportedInteraction.book_id`
- `RecommendationResult.user_id`
- `RecommendationItem.result_id`
- `RecommendationItem.book_id`
- `SimilarBookResult.source_book_id`
- `SimilarBookResult.target_book_id`

结论：

- 当前索引设计偏“关系正确 + 演示可用”
- 没有为复杂分析查询额外设计联合普通索引
- 也没有为 `generated_at`、`strategy`、`dataset_user_id` 等查询热点再做专门优化

## 4. 推荐算法细节

### 4.1 是否都已实现

四种策略都已经实现并会在离线重建中持久化：

- `hot`
- `itemcf`
- `usercf`
- `hybrid`

对应枚举定义在 `RecommendationResult.STRATEGY_CHOICES` 中。

### 4.2 交互矩阵来源

推荐训练数据不是只看站内评分，而是合并两类数据：

- `UserRating`：站内真实用户评分
- `ImportedInteraction`：Goodbooks 导入评分

二者通过 `apps.ratings.services.build_interaction_frame()` 合并成统一 DataFrame：

- 行键：`subject_key`
  - 站内用户：`site:{user_id}`
  - 导入用户：`goodbooks-10k:{dataset_user_id}`
- 列键：`book_id`
- 值：`score`

### 4.3 Hot 推荐

实现方式最简单：

- 直接按 `Book.rating_count DESC, Book.average_rating DESC` 排序
- 默认返回 `Top 20`

它既是匿名用户的展示策略，也是个性化失败时的回退策略。

### 4.4 ItemCF

实现位置：`apps.recommendations.services._itemcf_recommendations_from_similarity`

流程：

1. 将交互表透视为 `subject_key x book_id` 矩阵
2. 以图书列向量做余弦相似度
3. 对目标用户已评分图书集合做加权求和
4. 去掉用户已看过图书
5. 取分数最高的 `Top N`

相似度公式：

```text
sim(i, j) = cosine(v_i, v_j)
          = (v_i · v_j) / (||v_i|| ||v_j||)
```

候选图书得分形式：

```text
score(candidate) = Σ sim(candidate, rated_book_k) * rating_k
```

实现特征：

- 使用 `sklearn.metrics.pairwise.cosine_similarity`
- 未做评分中心化
- 未做用户均值扣除
- 未做相似度截断、显著性缩放或偏置校正
- 缺数据时直接回退热门推荐

### 4.5 UserCF

实现位置：`apps.recommendations.services._usercf_recommendations_from_similarity`

流程：

1. 基于同一评分矩阵按行做用户余弦相似度
2. 找到与目标用户相似度大于 0 的邻居
3. 对邻居喜欢、目标用户没看过的书累加：

```text
score(book) = Σ sim(user, neighbor) * neighbor_rating(book)
```

实现特征：

- 同样使用余弦相似度
- 同样未做均值中心化
- 未显式限制邻居数
- 最终仅取排序后的前 `Top N`

### 4.6 Hybrid

这里要区分两个实现口径。

#### 线上/离线重建用的 Hybrid

实现位置：`apps.recommendations.services._hybrid_recommendations`

步骤：

1. 分别生成 ItemCF 候选、UserCF 候选、热门候选
2. 对三路分数各自做 Min-Max 归一化
3. 线性融合：

```text
hybrid_score =
  0.5 * normalized_itemcf
  + 0.3 * normalized_usercf
  + 0.2 * normalized_hot
```

#### 实验评估页用的 Hybrid

实现位置：`apps.evaluations.services._hybrid_predictions`

这里不是同一个公式，而是：

```text
hybrid_score =
  0.7 * normalized_itemcf
  + 0.3 * normalized_popularity
```

它没有把 `UserCF` 纳入实验页的 Hybrid 计算。

因此必须明确：

- “推荐系统离线重建结果里的 Hybrid”
- “实验页评估时的 Hybrid”

当前并不是同一个实现。

### 4.7 评分中心化

当前代码中：

- ItemCF：未中心化
- UserCF：未中心化
- Hybrid：仅对最终候选分数做 Min-Max 归一化
- Pearson 相似度只用于实验页的相似度对比，不用于线上推荐主链路

所以如果问题是“是否使用了评分中心化”，答案是：**没有**。

### 4.8 Top-N 默认值

- `RecommendationResult.top_k` 默认值：`20`
- `rebuild_recommendations` 管理命令默认 `--top-k=20`
- 热门推荐默认 `20`
- 个性化推荐默认 `20`
- 相似图书重建只保留每本书前 `10` 个邻居
- 图书详情页实际展示前 `6` 条相似图书
- 个人中心推荐预览默认只截取前 `3` 条

### 4.9 切换规则

当前用户侧页面并不会在 `itemcf/usercf/hybrid` 间动态切换。

实际规则是：

- 未登录：展示 `hot`
- 已登录但评分数 `< 3`：状态记为 `cold-start`，展示 `hot`
- 已登录且评分数 `>= 3`：页面读取 `itemcf`

也就是说：

- `usercf` 和 `hybrid` 已经实现并落库
- 但当前 UI 主链路读取的是 `itemcf`
- `usercf`/`hybrid` 更像对比策略或后续扩展位，而不是当前线上默认推荐入口

## 5. 离线任务机制

### 5.1 是否使用 Celery / APScheduler / django-cron / Railway Cron

当前项目都没有使用：

- 没有 Celery
- 没有 APScheduler
- 没有 django-cron
- 仓库里也没有 Railway Cron 配置文件

### 5.2 实际任务入口

当前离线任务实际有三条路径。

#### 1. 管理命令

- 推荐重建：`python manage.py rebuild_recommendations`
- 实验评估：`python manage.py evaluate_recommenders`

这是最核心的离线入口。

#### 2. 管理后台手动触发

`/dashboard/trigger-rebuild/` 会在 Django Web 进程内启动一个后台线程执行：

```python
call_command("rebuild_recommendations")
```

并通过 `.runtime/dashboard_rebuild.lock` 文件锁避免并发重复触发。

这是一种“演示友好”的轻量方案，不是标准任务队列。

#### 3. 本地 Windows 计划任务

脚本：`scripts/register_daily_rebuild_task.ps1`

默认注册方式：

- 频率：每天一次
- 默认时间：`02:00`
- 执行命令：`conda run -n bookrec311 python manage.py rebuild_recommendations --settings=...`

因此当前“定时重建”主要依赖 Windows Scheduled Task，而不是 Django 内建 scheduler。

### 5.3 Railway 上的评估文件刷新

Railway 目前做的是“启动时刷新实验产物”，不是周期 Cron。

执行频率：

- 每次部署
- 每次容器启动

执行命令：

```bash
python manage.py evaluate_recommenders --skip-record
```

作用：

- 重写 `artifacts/evaluations/summary.json`
- 不新增 `EvaluationRun` 行

## 6. Redis 缓存设计

### 6.1 缓存键格式

定义在 `apps.recommendations.cache`：

- 个性化推荐：`user:{user_id}:recs`
- 全局热门推荐：`hot:recs`

### 6.2 缓存内容

缓存值是一个序列化后的 Python dict，主要结构如下：

```json
{
  "strategy": "itemcf",
  "user_id": 12,
  "generated_at": "2026-04-26T10:00:00+08:00",
  "top_k": 20,
  "items": [
    {
      "rank": 1,
      "score": 0.91,
      "reason": "与你的评分相似",
      "book_id": 123,
      "title": "Book title",
      "author": "Author",
      "category": "History",
      "category_slug": "history",
      "cover_url": "...",
      "average_rating": 4.5,
      "book": {
        "id": 123,
        "title": "Book title",
        "author": "Author",
        "cover_url": "...",
        "description": "...",
        "publisher": "...",
        "publication_year": 2024,
        "average_rating": 4.5,
        "rating_count": 20,
        "category": {
          "id": 3,
          "name": "History",
          "slug": "history"
        }
      }
    }
  ]
}
```

### 6.3 过期时间

当前缓存不过期：

```python
DEFAULT_CACHE_TIMEOUT = None
```

也就是：

- Redis 中不会按 TTL 自动失效
- 需要依靠离线重建覆盖写入

### 6.4 缓存刷新逻辑

推荐重建结束后会执行：

- `cache_hot_recommendations(hot_result)`
- `cache_user_recommendations(user_id, result)`

因此刷新时机是：

- `rebuild_recommendations_for_all_users()` 成功跑完之后

### 6.5 缓存未命中处理

页面读取逻辑在 `apps.recommendations.selectors.recommendation_block_for_user()`：

1. 先读缓存
2. 如果缓存未命中：
   - 个性化用户：查最近一条 `RecommendationResult(strategy="itemcf")`
   - 匿名/冷启动用户：查最近一条全局 `RecommendationResult(strategy="hot")`
3. 若数据库也没有结果，则返回空 payload

注意：

- 当前代码在缓存 miss 回退数据库后，不会自动把结果重新写回缓存
- 所以它是“读缓存，miss 时查库”，不是“读穿 + 自动回填”

### 6.6 Redis 故障容忍

推荐重建写缓存时，如果 Redis 异常：

- 不会让整次重建失败
- 会把错误记入 `OfflineJobRun.summary`
- `OfflineJobRun.status` 仍可能是 `success`

这说明缓存属于性能层，不是推荐结果持久化的单一真源。

## 7. 推荐理由生成逻辑

### 7.1 当前理由是否可追溯

当前推荐理由是**策略级说明**，不是“证据级追溯”。

已经实现的理由文本：

- 热门：`受读者欢迎`
- ItemCF：`与你的评分相似`
- ItemCF 回退热门：`ItemCF 数据过稀时采用热门回退`
- UserCF：`相似读者也喜欢这本书`
- Hybrid：`融合 ItemCF、UserCF 和热门信号`

### 7.2 能否追溯到相似图书

部分能，部分不能。

- 系统会离线写入 `SimilarBookResult`
- 图书详情页会展示相似图书列表和相似度分数
- 但“为什么推荐你这本书”的那段文案，并不会写出“因为你喜欢了哪一本具体图书”

所以：

- 相似图书结果是有的
- 推荐理由文本本身没有绑定到具体相似图书 ID 或标题

### 7.3 能否追溯到相似用户

不能。

虽然 `UserCF` 逻辑存在，但：

- 没有把邻居用户 ID 持久化到推荐结果
- 没有把某个邻居用户的贡献拆解出来
- 页面上只展示模板文案“相似读者也喜欢这本书”

### 7.4 热门兜底是否可识别

可以。

当 ItemCF 没有足够有效候选时，会显式写入：

- `ItemCF 数据过稀时采用热门回退`

因此热门兜底在推荐结果中是可区分的。

### 7.5 当前结论

如果问题是“推荐理由是否达到论文级可解释推荐”，答案是否定的。

当前状态更准确地说是：

- 页面已能展示人类可读理由
- 理由可区分推荐来源策略
- 但尚未追溯到具体相似图书、具体相似用户或逐项贡献值

## 8. 实验评估方法

### 8.1 默认评估口径：留一法

默认主评估在 `apps.evaluations.services._split_train_holdout()` 中完成。

规则：

1. 按 `subject_key` 分组
2. 只保留交互数 `>= 2` 的用户
3. 按 `event_at, event_id` 升序排序
4. 取每个用户最后一条交互作为 holdout 测试样本
5. 其余交互作为训练集

这就是典型的 leave-one-out 评估。

### 8.2 随机划分口径

辅助评估在 `apps.evaluations.services._split_random_interactions()` 中完成。

参数：

- `test_fraction=0.2`
- `random_state=42`

规则：

1. 只从交互数 `>= 2` 的用户中抽样
2. 从所有 eligible 交互中按约 `20%` 采样
3. 再按 `subject_key` 去重，每个用户最多留一条测试样本
4. 剩余交互进入训练集

因此它不是“严格按用户独立 8:2 划分”，而是：

- 先全局抽样
- 再限制每个用户最多一条测试记录

### 8.3 训练/测试比例

需要分两种说法：

1. 留一法  
不是固定比例，而是每个有至少 2 条交互的用户都拿出最后 1 条做测试。

2. 随机划分  
目标比例是 `80% train / 20% test`，但因为最终按用户去重，每次真正的测试条数是“抽样后唯一用户数”，不是精确总交互的 20%。

### 8.4 Precision / Recall 公式

项目评估默认每个用户只有 1 个 holdout 正例，因此代码里的指标等价为：

```text
hit(u, K) = 1,  if holdout_item ∈ topK(u)
            0,  otherwise

Precision@K = (1 / |U|) * Σ_u [ hit(u, K) / K ]
Recall@K    = (1 / |U|) * Σ_u [ hit(u, K) ]
```

解释：

- 因为每个用户只有 1 个相关项
- 所以单用户 Recall 要么是 `1`，要么是 `0`
- 宏平均后就变成“命中率”

### 8.5 参与评估的算法

实验页会评估：

- `hot`
- `itemcf`
- `usercf`
- `hybrid`

另外还会额外做：

- `cosine` vs `pearson` 的 ItemCF 相似度比较

注意：

- `pearson` 只在实验比较里出现
- 它不参与线上默认推荐主链路

### 8.6 K 值选择依据

当前 K 值是硬编码：

```python
[5, 10, 20, 30]
```

代码中没有自动调参逻辑，也没有根据数据规模自适应选择。

因此更准确的表述是：

- 当前项目固定用 `K=5/10/20/30` 作为演示与对比检查点
- 这是工程上预设的观测窗口
- 不是通过验证集搜索得到的最优 K

### 8.7 实验结果产物

实验页最终依赖：

- 数据库中的 `EvaluationRun`
- 文件产物 `artifacts/evaluations/summary.json`

其中页面读取的是 `summary.json`，不是请求时直接重算。

`summary.json` 内包含：

- `metadata`
- `overview`
- `algorithms`
- `curves`
- `case_studies`
- `similarity_comparison`
- `random_split`

## 9. 当前实现结论

如果要对外用一句话概括当前项目实现，可以这样说：

> 这是一个基于 Django + MySQL + Redis + Railway 的图书推荐演示系统，已经实现 Hot、ItemCF、UserCF 和 Hybrid 四类离线推荐策略，使用 Goodbooks-10k 原始公开数据做图书和评分导入，线上页面展示的是预计算推荐结果和离线评估产物；但当前主推荐链路仍以 ItemCF 为默认个性化策略，推荐理由还停留在策略级说明，尚未做到细粒度可解释推荐。
