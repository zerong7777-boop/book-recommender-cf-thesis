# Site Chinese Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前书籍推荐系统的主要用户可见界面、交互文案、动态推荐解释、实验页说明和线上演示文档统一改成中文版本，同时保持现有功能、路由和数据链路不变。

**Architecture:** 采用“显式中文文案替换 + 最小范围本地化设置”的低风险方案，不引入完整 i18n 翻译目录体系，也不改公开数据本身。优先覆盖 Django 模板、表单标签、用户提示消息、推荐理由和管理入口标题；业务逻辑、数据库结构和 URL 路径保持不变。

**Tech Stack:** Django 5.2、Django templates、Django forms、Python services、pytest、Railway 部署配置

---

## File Map

### 需要修改

- `E:/projects/book-recommender-cf/book_recommender/settings.py`
  - 设置站点默认语言、时区展示策略、必要的 locale 配置
- `E:/projects/book-recommender-cf/book_recommender/templates/base.html`
  - 全站导航、站点标题、底部入口中文化
- `E:/projects/book-recommender-cf/apps/accounts/forms.py`
  - 注册、登录、改密表单标签和帮助文本中文化
- `E:/projects/book-recommender-cf/apps/accounts/views.py`
  - 成功/失败提示消息中文化
- `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/login.html`
- `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/register.html`
- `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/profile.html`
- `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/password_change.html`
  - 账户相关页面中文化
- `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/home.html`
- `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/book_list.html`
- `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/book_detail.html`
- `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/category_list.html`
- `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/_book_card.html`
  - 首页、列表页、详情页、分类页中文化
- `E:/projects/book-recommender-cf/apps/ratings/forms.py`
- `E:/projects/book-recommender-cf/apps/ratings/views.py`
- `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/first_rate.html`
- `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/rate_book.html`
- `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/delete_rating.html`
  - 评分入口、删除确认、表单标签中文化
- `E:/projects/book-recommender-cf/apps/recommendations/services.py`
  - 动态推荐理由中文化
- `E:/projects/book-recommender-cf/apps/recommendations/templates/recommendations/recommendation_list.html`
  - 推荐页标题、空状态、说明中文化
- `E:/projects/book-recommender-cf/apps/evaluations/templates/evaluations/experiment_results.html`
  - 实验页模块标题、空状态、描述中文化
- `E:/projects/book-recommender-cf/apps/dashboard/templates/dashboard/home.html`
  - 管理员 dashboard 中文化
- `E:/projects/book-recommender-cf/apps/evaluations/services.py`
  - 评估摘要中的算法说明、case study 标签等动态文本中文化
- `E:/projects/book-recommender-cf/apps/catalog/views.py`
- `E:/projects/book-recommender-cf/apps/recommendations/views.py`
- `E:/projects/book-recommender-cf/apps/dashboard/views.py`
  - 若存在 `messages.success/error`，需要统一改成中文
- `E:/projects/book-recommender-cf/ONLINE_DEMO_GUIDE.md`
  - 保持线上演示文档与中文 UI 一致
- `E:/projects/book-recommender-cf/MANUAL_TEST_GUIDE.md`
  - 增加中文版本说明和入口指引

### 需要新增

- `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`
  - 针对关键页面断言中文标题、导航和动态理由

### 明确保持不变

- URL 路径本身：`/accounts/login/`、`/experiments/`、`/dashboard/`
- 公开图书原始元数据：书名、作者、封面 URL
- 推荐算法和实验计算逻辑
- Railway 部署域名和环境变量结构

---

### Task 1: 建立中文化基线与覆盖测试

**Files:**
- Create: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`
- Modify: `E:/projects/book-recommender-cf/tests/test_end_to_end_smoke.py`
- Modify: `E:/projects/book-recommender-cf/book_recommender/settings_test.py`

- [ ] **Step 1: 写关键页面中文文案测试**

```python
from django.urls import reverse


def test_home_page_shows_chinese_navigation(client):
    response = client.get(reverse("catalog:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "浏览图书" in content
    assert "实验结果" in content
    assert "登录" in content
    assert "注册" in content


def test_login_page_shows_chinese_heading(client):
    response = client.get(reverse("accounts:login"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "登录" in content
    assert "使用演示账号可直接体验评分、推荐和后台验证" in content
```

- [ ] **Step 2: 运行测试，确认先失败**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py -q`

Expected: FAIL，因为当前页面仍然包含英文导航和英文标题

- [ ] **Step 3: 给端到端 smoke 补一个中文断言点**

```python
def test_thesis_demo_smoke_flow(client, django_user_model):
    ...
    home_response = client.get(reverse("catalog:home"))
    assert "浏览图书" in home_response.content.decode("utf-8")
```

- [ ] **Step 4: 运行新增 smoke 断言，确认也失败**

Run: `conda run -n bookrec311 pytest tests/test_end_to_end_smoke.py::test_thesis_demo_smoke_flow -q`

Expected: FAIL，原因是首页仍是英文

- [ ] **Step 5: 提交**

```bash
git add tests/test_chinese_ui_copy.py tests/test_end_to_end_smoke.py
git commit -m "test: lock chinese ui copy expectations"
```

---

### Task 2: 设置站点默认中文展示

**Files:**
- Modify: `E:/projects/book-recommender-cf/book_recommender/settings.py`
- Modify: `E:/projects/book-recommender-cf/book_recommender/settings_test.py`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写 settings 层 failing test**

```python
from book_recommender import settings


def test_default_language_is_simplified_chinese():
    assert settings.LANGUAGE_CODE == "zh-hans"
```

- [ ] **Step 2: 运行单测确认失败**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py::test_default_language_is_simplified_chinese -q`

Expected: FAIL，当前 settings 未明确设置中文

- [ ] **Step 3: 最小实现中文默认配置**

```python
LANGUAGE_CODE = "zh-hans"
USE_I18N = True
```

如需 locale 中间件且当前项目未启用，插入：

```python
"django.middleware.locale.LocaleMiddleware",
```

位置：`SessionMiddleware` 之后、`CommonMiddleware` 之前。

- [ ] **Step 4: 运行语言测试与 Django check**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py::test_default_language_is_simplified_chinese -q`

Expected: PASS

Run: `conda run -n bookrec311 python manage.py check --settings=book_recommender.settings_local_demo`

Expected: `System check identified no issues`

- [ ] **Step 5: 提交**

```bash
git add book_recommender/settings.py book_recommender/settings_test.py tests/test_chinese_ui_copy.py
git commit -m "feat: set default site language to simplified chinese"
```

---

### Task 3: 全站导航与基础布局中文化

**Files:**
- Modify: `E:/projects/book-recommender-cf/book_recommender/templates/base.html`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写 failing test 覆盖导航中文**

```python
def test_authenticated_nav_shows_chinese_entries(client, django_user_model):
    user = django_user_model.objects.create_user(username="reader_cn", password="Pass12345!")
    client.force_login(user)

    response = client.get(reverse("catalog:home"))
    content = response.content.decode("utf-8")

    assert "推荐中心" in content
    assert "个人中心" in content
```

- [ ] **Step 2: 运行确认失败**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py::test_authenticated_nav_shows_chinese_entries -q`

Expected: FAIL

- [ ] **Step 3: 把 base.html 中用户可见英文入口改成中文**

替换示例：

```html
<title>{% block title %}图书推荐系统{% endblock %}</title>
<span class="site-brand-subtitle">推荐实验平台</span>
<a ...>浏览图书</a>
<a ...>实验结果</a>
<a ...>推荐中心</a>
<a ...>个人中心</a>
<a ...>管理面板</a>
<a ...>登录</a>
<a ...>注册</a>
```

- [ ] **Step 4: 运行导航测试**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py -q`

Expected: 与导航相关测试 PASS

- [ ] **Step 5: 提交**

```bash
git add book_recommender/templates/base.html tests/test_chinese_ui_copy.py
git commit -m "feat: translate base navigation to chinese"
```

---

### Task 4: 账户页面与表单中文化

**Files:**
- Modify: `E:/projects/book-recommender-cf/apps/accounts/forms.py`
- Modify: `E:/projects/book-recommender-cf/apps/accounts/views.py`
- Modify: `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/login.html`
- Modify: `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/register.html`
- Modify: `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/profile.html`
- Modify: `E:/projects/book-recommender-cf/apps/accounts/templates/accounts/password_change.html`
- Test: `E:/projects/book-recommender-cf/tests/test_accounts.py`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写 failing tests 覆盖登录/注册/个人中心中文标题**

```python
def test_profile_page_shows_chinese_profile_labels(client, django_user_model):
    user = django_user_model.objects.create_user(username="reader_profile", password="Pass12345!")
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    content = response.content.decode("utf-8")

    assert "个人中心" in content
    assert "推荐状态" in content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py::test_profile_page_shows_chinese_profile_labels -q`

Expected: FAIL

- [ ] **Step 3: 最小实现页面与表单标签中文**

示例改动：

```python
self.fields["username"].label = "用户名"
self.fields["password"].label = "密码"
self.fields["email"].label = "邮箱"
```

```html
<h1 class="page-title">登录</h1>
<p class="auth-hint">使用演示账号可直接体验评分、推荐和后台验证。</p>
```

```html
<h1 class="page-title">个人中心</h1>
<li class="status-pill">推荐状态：{{ recommendation_state }}</li>
```

- [ ] **Step 4: 把成功/错误消息改成中文**

示例：

```python
messages.success(request, "注册成功，已为你创建账户。")
messages.success(request, "评分已更新。")
```

- [ ] **Step 5: 跑账户相关测试**

Run: `conda run -n bookrec311 pytest tests/test_accounts.py tests/test_chinese_ui_copy.py -q`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add apps/accounts/forms.py apps/accounts/views.py apps/accounts/templates/accounts/login.html apps/accounts/templates/accounts/register.html apps/accounts/templates/accounts/profile.html apps/accounts/templates/accounts/password_change.html tests/test_accounts.py tests/test_chinese_ui_copy.py
git commit -m "feat: translate account flows to chinese"
```

---

### Task 5: 目录、详情页与评分流程中文化

**Files:**
- Modify: `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/home.html`
- Modify: `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/book_list.html`
- Modify: `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/book_detail.html`
- Modify: `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/category_list.html`
- Modify: `E:/projects/book-recommender-cf/apps/catalog/templates/catalog/_book_card.html`
- Modify: `E:/projects/book-recommender-cf/apps/ratings/forms.py`
- Modify: `E:/projects/book-recommender-cf/apps/ratings/views.py`
- Modify: `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/first_rate.html`
- Modify: `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/rate_book.html`
- Modify: `E:/projects/book-recommender-cf/apps/ratings/templates/ratings/delete_rating.html`
- Test: `E:/projects/book-recommender-cf/tests/test_catalog.py`
- Test: `E:/projects/book-recommender-cf/tests/test_ratings.py`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写首页与评分页 failing tests**

```python
def test_home_page_shows_chinese_sections(client):
    response = client.get(reverse("catalog:home"))
    content = response.content.decode("utf-8")

    assert "推荐精选" in content
    assert "浏览图书" in content
```

```python
def test_rate_page_shows_chinese_button(client, django_user_model, book):
    user = django_user_model.objects.create_user(username="rate_cn", password="Pass12345!")
    client.force_login(user)
    response = client.get(reverse("ratings:rate-book", args=[book.pk]))
    assert "提交评分" in response.content.decode("utf-8")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n bookrec311 pytest tests/test_catalog.py tests/test_ratings.py tests/test_chinese_ui_copy.py -q`

Expected: FAIL

- [ ] **Step 3: 替换目录和评分流程文案**

示例：

```html
<h2 class="section-title h1 mb-0">推荐精选</h2>
<a class="btn btn-dark">浏览图书</a>
<a class="btn btn-dark">登录后评分</a>
```

```html
<button type="submit" class="btn btn-dark">提交评分</button>
```

- [ ] **Step 4: 统一评分成功/删除确认消息为中文**

```python
messages.success(request, "评分已保存。")
messages.success(request, "评分已删除。")
```

- [ ] **Step 5: 跑目录与评分测试**

Run: `conda run -n bookrec311 pytest tests/test_catalog.py tests/test_ratings.py tests/test_chinese_ui_copy.py -q`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add apps/catalog/templates/catalog/home.html apps/catalog/templates/catalog/book_list.html apps/catalog/templates/catalog/book_detail.html apps/catalog/templates/catalog/category_list.html apps/catalog/templates/catalog/_book_card.html apps/ratings/forms.py apps/ratings/views.py apps/ratings/templates/ratings/first_rate.html apps/ratings/templates/ratings/rate_book.html apps/ratings/templates/ratings/delete_rating.html tests/test_catalog.py tests/test_ratings.py tests/test_chinese_ui_copy.py
git commit -m "feat: translate catalog and rating flows to chinese"
```

---

### Task 6: 推荐页、动态推荐理由与实验页中文化

**Files:**
- Modify: `E:/projects/book-recommender-cf/apps/recommendations/services.py`
- Modify: `E:/projects/book-recommender-cf/apps/recommendations/templates/recommendations/recommendation_list.html`
- Modify: `E:/projects/book-recommender-cf/apps/evaluations/services.py`
- Modify: `E:/projects/book-recommender-cf/apps/evaluations/templates/evaluations/experiment_results.html`
- Test: `E:/projects/book-recommender-cf/tests/test_recommendation_pipeline.py`
- Test: `E:/projects/book-recommender-cf/tests/test_evaluations.py`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写 failing tests 断言推荐理由与实验页中文**

```python
def test_recommendation_reason_is_chinese(...):
    ...
    assert item.reason in {"与你的评分偏好相似", "由于 ItemCF 数据较稀疏，当前展示热门兜底结果"}
```

```python
def test_experiment_page_shows_chinese_sections(client):
    response = client.get(reverse("evaluations:results"))
    content = response.content.decode("utf-8")

    assert "K 值检查点" in content
    assert "精确率曲线" in content
    assert "召回率曲线" in content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n bookrec311 pytest tests/test_recommendation_pipeline.py tests/test_evaluations.py tests/test_chinese_ui_copy.py -q`

Expected: FAIL

- [ ] **Step 3: 翻译推荐理由与推荐页静态文案**

```python
reason = "与你的评分偏好相似"
reason = "由于 ItemCF 数据较稀疏，当前展示热门兜底结果"
```

```html
<p class="section-kicker">推荐中心</p>
<h1 class="page-title">推荐中心</h1>
<p class="empty-state mb-0">推荐结果暂未生成，请先评分或等待下一轮离线刷新。</p>
```

- [ ] **Step 4: 翻译实验页模块标题与空状态**

示例：

```html
<h2 class="section-title h1 mb-0">K 值检查点</h2>
<h2 class="section-title h1 mb-0">精确率曲线</h2>
<h2 class="section-title h1 mb-0">召回率曲线</h2>
<h2 class="section-title h1 mb-0">案例分析</h2>
<h2 class="section-title h1 mb-0">随机交互划分</h2>
```

- [ ] **Step 5: 跑推荐与实验测试**

Run: `conda run -n bookrec311 pytest tests/test_recommendation_pipeline.py tests/test_evaluations.py tests/test_chinese_ui_copy.py -q`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add apps/recommendations/services.py apps/recommendations/templates/recommendations/recommendation_list.html apps/evaluations/services.py apps/evaluations/templates/evaluations/experiment_results.html tests/test_recommendation_pipeline.py tests/test_evaluations.py tests/test_chinese_ui_copy.py
git commit -m "feat: translate recommendation and evaluation views to chinese"
```

---

### Task 7: 管理员 dashboard 与后台入口中文化

**Files:**
- Modify: `E:/projects/book-recommender-cf/apps/dashboard/templates/dashboard/home.html`
- Modify: `E:/projects/book-recommender-cf/apps/dashboard/views.py`
- Test: `E:/projects/book-recommender-cf/tests/test_dashboard.py`
- Test: `E:/projects/book-recommender-cf/tests/test_chinese_ui_copy.py`

- [ ] **Step 1: 写 dashboard 中文 failing test**

```python
def test_dashboard_page_shows_chinese_admin_copy(client, admin_user):
    client.force_login(admin_user)
    response = client.get(reverse("dashboard:home"))
    content = response.content.decode("utf-8")

    assert "运维总览" in content
    assert "手动触发刷新" in content
    assert "打开 Django 管理后台" in content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n bookrec311 pytest tests/test_dashboard.py tests/test_chinese_ui_copy.py -q`

Expected: FAIL

- [ ] **Step 3: 翻译 dashboard 页面和消息**

```html
<h1 class="page-title mb-2">运维总览</h1>
<a class="btn btn-outline-dark">打开 Django 管理后台</a>
<button class="btn btn-dark" type="submit">手动触发刷新</button>
```

如 views 中存在消息提示，改为：

```python
messages.success(request, "离线推荐刷新任务已启动。")
messages.warning(request, "当前已有刷新任务正在运行。")
```

- [ ] **Step 4: 跑 dashboard 测试**

Run: `conda run -n bookrec311 pytest tests/test_dashboard.py tests/test_chinese_ui_copy.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add apps/dashboard/templates/dashboard/home.html apps/dashboard/views.py tests/test_dashboard.py tests/test_chinese_ui_copy.py
git commit -m "feat: translate dashboard management copy to chinese"
```

---

### Task 8: 文档与线上演示说明中文对齐

**Files:**
- Modify: `E:/projects/book-recommender-cf/ONLINE_DEMO_GUIDE.md`
- Modify: `E:/projects/book-recommender-cf/MANUAL_TEST_GUIDE.md`
- Optionally Modify: `E:/projects/book-recommender-cf/README.md`

- [ ] **Step 1: 更新线上演示文档，保证中文按钮名称与实际页面一致**

示例：

```md
- `Browse books` → `浏览图书`
- `Experiments` → `实验结果`
- `Recommendation center` → `推荐中心`
- `Dashboard` → `管理面板`
```

- [ ] **Step 2: 更新本地手册，把“本地命令”和“中文界面入口”分开写**

示例：

```md
登录后顶部导航会出现：`推荐中心`、`个人中心`
```

- [ ] **Step 3: 手动核对 README 是否仍在对外描述英文界面**

如存在明显英文界面说明，替换为中文或中英兼容描述。

- [ ] **Step 4: 自查文档链接和地址**

Run: `rg -n "Browse books|Log in|Recommendation center|Dashboard" README.md MANUAL_TEST_GUIDE.md ONLINE_DEMO_GUIDE.md`

Expected: 只保留必要的中英对照，不再把英文当默认主文案

- [ ] **Step 5: 提交**

```bash
git add ONLINE_DEMO_GUIDE.md MANUAL_TEST_GUIDE.md README.md
git commit -m "docs: align demo guides with chinese ui"
```

---

### Task 9: 全量验收与 Railway 回归

**Files:**
- Verify only

- [ ] **Step 1: 跑核心测试集**

Run: `conda run -n bookrec311 pytest tests/test_chinese_ui_copy.py tests/test_accounts.py tests/test_catalog.py tests/test_ratings.py tests/test_recommendation_pipeline.py tests/test_evaluations.py tests/test_dashboard.py tests/test_end_to_end_smoke.py -q --basetemp E:/projects/book-recommender-cf/.pytest_tmp/chinese-ui-acceptance -p no:cacheprovider`

Expected: 全绿

- [ ] **Step 2: 跑 Django 配置检查**

Run: `conda run -n bookrec311 python manage.py check --settings=book_recommender.settings_local_demo`

Expected: `System check identified no issues`

- [ ] **Step 3: 本地 smoke 打开三个关键页**

Run:

```bash
conda run -n bookrec311 python manage.py runserver 127.0.0.1:8000 --settings=book_recommender.settings_local_demo
```

手动确认：

- `/` 页面标题和导航为中文
- `/accounts/login/` 为中文
- `/experiments/` 模块标题为中文

- [ ] **Step 4: Railway 回归检查**

重新部署后，人工访问：

- `https://web-production-7e7f.up.railway.app/`
- `https://web-production-7e7f.up.railway.app/accounts/login/`
- `https://web-production-7e7f.up.railway.app/experiments/`
- `https://web-production-7e7f.up.railway.app/dashboard/`

确认页面仍然 200 且按钮文字已变成中文。

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "feat: localize site ui to chinese"
```

---

## Scope Notes

- 本计划默认“整体改成中文版本”指的是**用户可见界面和说明文案**改成中文，不包括把书名、作者名、公开数据集元信息人工翻译成中文。
- Django Admin 内部模型名如果还保留英文，不阻塞第一阶段上线；如用户要求“连管理后台表名也全中文”，应另开一个小计划，涉及 `verbose_name`、`verbose_name_plural` 和 admin 标题覆盖。
- 推荐算法、实验算法、数据库结构、云端部署架构不在本次语言改造范围内。

## Self-Review

- **Spec coverage:** 覆盖了基础布局、账户页、目录页、评分页、推荐页、实验页、dashboard、动态推荐理由、文档与线上回归。未覆盖公开图书元数据翻译，这是有意排除。
- **Placeholder scan:** 计划里没有 `TODO/TBD`。每个任务都给了目标文件、测试入口和运行命令。
- **Type consistency:** 所有页面断言均基于现有 Django 路由名：`catalog:home`、`accounts:login`、`accounts:profile`、`recommendations:list`、`evaluations:results`、`dashboard:home`，与当前项目一致。

## Execution Handoff

Plan complete and saved to `E:/projects/book-recommender-cf/docs/superpowers/plans/2026-04-17-site-chinese-localization.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
