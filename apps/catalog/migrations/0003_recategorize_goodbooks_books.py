from django.db import migrations


DEFAULT_CATEGORY_NAME = "Goodbooks Import"
DEFAULT_CATEGORY_SLUG = "goodbooks-import"
GOODBOOKS_CATEGORY_RULES = [
    ("Computer Science", "computer-science", ("python", "data", "algorithm", "computer", "programming", "machine learning")),
    ("History", "history", ("history", "kingdom", "war", "empire", "histor", "archive")),
    ("Poetry", "poetry", ("poem", "poems", "poetry", "keats", "shakespeare")),
    ("Romance", "romance", ("romance", "romantic", "love")),
    ("Fantasy", "fantasy", ("fantasy", "dragon", "magic", "king", "queen")),
    ("Mystery", "mystery", ("mystery", "detective", "crime", "murder", "secret")),
    ("Science Fiction", "science-fiction", ("science fiction", "sci-fi", "space", "alien", "dune")),
    ("Young Adult", "young-adult", ("young adult", "hunger games", "harry potter", "twilight")),
    ("Nonfiction", "nonfiction", ("memoir", "biography", "handbook", "guide", "science")),
]


def _matching_category_slug(book):
    text = f"{book.title} {book.author}".lower()
    for _name, slug, keywords in GOODBOOKS_CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return slug
    return DEFAULT_CATEGORY_SLUG


def recategorize_goodbooks_books(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Book = apps.get_model("catalog", "Book")

    default_category = Category.objects.filter(slug=DEFAULT_CATEGORY_SLUG).first()
    if default_category is None:
        return

    books = Book.objects.filter(category_id=default_category.id).only("id", "title", "author", "category_id")
    if not books.exists():
        return

    category_lookup = {DEFAULT_CATEGORY_SLUG: default_category}
    for name, slug, _keywords in GOODBOOKS_CATEGORY_RULES:
        category = Category.objects.filter(slug=slug).first()
        if category is None:
            category = Category.objects.filter(name=name).first()
        if category is None:
            category = Category.objects.create(slug=slug, name=name)
        category_lookup[slug] = category

    books_to_update = []
    for book in books:
        category = category_lookup[_matching_category_slug(book)]
        if category.id != book.category_id:
            book.category_id = category.id
            books_to_update.append(book)

    if books_to_update:
        Book.objects.bulk_update(books_to_update, ["category"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_alter_book_average_rating_and_more"),
    ]

    operations = [
        migrations.RunPython(recategorize_goodbooks_books, migrations.RunPython.noop),
    ]
