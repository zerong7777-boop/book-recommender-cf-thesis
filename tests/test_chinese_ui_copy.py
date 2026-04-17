import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.urls import reverse

from apps.catalog.models import Book, Category
from apps.evaluations.services import evaluation_artifact_dir
from book_recommender import settings


TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp_testdata"


@pytest.mark.django_db
def test_homepage_surfaces_chinese_navigation_and_entry_copy(client):
    response = client.get(reverse("catalog:home"))

    content = response.content.decode()

    assert f'href="{reverse("catalog:home")}">首页</a>' in content
    assert f'href="{reverse("catalog:book_list")}">浏览图书</a>' in content
    assert f'href="{reverse("evaluations:results")}">实验结果</a>' in content
    assert f'href="{reverse("accounts:login")}">登录</a>' in content
    assert f'href="{reverse("accounts:register")}">注册</a>' in content
    assert "发现下一本想读的书" in content
    assert "推荐精选" in content


@pytest.mark.django_db
def test_homepage_surfaces_chinese_sections(client):
    response = client.get(reverse("catalog:home"))

    content = response.content.decode()

    assert "浏览分类" in content
    assert "两个演示路径" in content
    assert "实验依据" in content


@pytest.mark.django_db
def test_experiment_results_page_surfaces_chinese_sections(client, settings):
    tmp_path = TMP_ROOT / f"cn-eval-{uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    settings.BASE_DIR = tmp_path
    artifact_dir = evaluation_artifact_dir(tmp_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(
        json.dumps(
            {
                "overview": [{"k": 5, "precision": 0.1, "recall": 0.2}],
                "metadata": {"dataset_user_count": 4, "site_user_count": 1, "run_count": 4},
                "curves": {
                    "precision": [{"name": "itemcf", "points": [{"k": 5, "value": 0.1}], "svg_points": "12,12"}],
                    "recall": [{"name": "itemcf", "points": [{"k": 5, "value": 0.2}], "svg_points": "12,12"}],
                },
                "case_studies": [],
                "algorithms": [],
                "similarity_comparison": {},
                "random_split": {
                    "train_interaction_count": 8,
                    "test_interaction_count": 2,
                    "algorithms": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    response = client.get(reverse("evaluations:results"))
    content = response.content.decode()

    assert "K 值检查点" in content
    assert "精确率曲线" in content
    assert "召回率曲线" in content


@pytest.mark.django_db
def test_login_page_uses_chinese_title_or_form_guidance(client):
    response = client.get(reverse("accounts:login"))

    content = response.content.decode()

    assert "<title>登录 | 图书推荐系统</title>" in content
    assert '<h1 class="page-title">登录</h1>' in content
    assert "使用演示账号" in content
    assert "评分" in content
    assert "推荐" in content
    assert "后台验证" in content


@pytest.mark.django_db
def test_rating_page_uses_chinese_button_and_guidance(client, django_user_model):
    user = django_user_model.objects.create_user(username="rate_cn", password="Pass12345!")
    category = Category.objects.create(name="Drama", slug="drama-test")
    Book.objects.create(
        title="Stage Light",
        author="Writer",
        category=category,
        description="d",
        publisher="p",
        publication_year=2022,
        rating_count=12,
        average_rating=4.6,
    )
    client.force_login(user)

    response = client.get(reverse("ratings:first-rate"))
    content = response.content.decode()

    assert "快速评分" in content
    assert "适合先评分的热门图书" in content
    assert "保存" in content


@pytest.mark.django_db
def test_authenticated_nav_shows_chinese_entries(client, django_user_model):
    user = django_user_model.objects.create_user(username="reader_cn", password="Pass12345!")
    staff_user = django_user_model.objects.create_user(
        username="staff_cn",
        password="Pass12345!",
        is_staff=True,
    )

    client.force_login(user)
    response = client.get(reverse("catalog:home"))
    content = response.content.decode()
    assert f'href="{reverse("recommendations:list")}">推荐中心</a>' in content
    assert f'href="{reverse("accounts:profile")}">个人中心</a>' in content
    assert "管理面板" not in content

    client.force_login(staff_user)
    staff_response = client.get(reverse("catalog:home"))
    staff_content = staff_response.content.decode()
    assert f'href="{reverse("dashboard:home")}">管理面板</a>' in staff_content


@pytest.mark.django_db
def test_dashboard_page_shows_chinese_admin_copy(client, django_user_model):
    admin_user = django_user_model.objects.create_user(
        username="dashboard_admin",
        password="Pass12345!",
        is_staff=True,
    )
    client.force_login(admin_user)

    response = client.get(reverse("dashboard:home"))
    content = response.content.decode()

    assert "运维总览" in content
    assert "手动触发刷新" in content
    assert "打开 Django 管理后台" in content


@pytest.mark.django_db
def test_profile_page_shows_chinese_profile_labels(client, django_user_model):
    user = django_user_model.objects.create_user(username="reader_profile", password="Pass12345!")
    client.force_login(user)

    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()

    assert "个人中心" in content
    assert "推荐状态" in content
    assert "冷启动推荐" in content


def test_default_language_is_simplified_chinese():
    assert settings.LANGUAGE_CODE == "zh-hans"
